"""Regression tests for the CI frontend-container smoke job.

Covers the path trigger (scripts/classify-scope.sh + the job's scope gate), the per-run compose
project isolation and cleanup of the job, and the exit status / teardown semantics of
`make test-frontend-container` (exercised against a fake `docker` on PATH, no daemon needed).
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CLASSIFIER = REPO_ROOT / "scripts" / "classify-scope.sh"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

SCOPE = "needs.detect-changes.outputs.scope"

# Every path whose change can alter the images or the smoke run.
CONTAINER_RELEVANT_PATHS = [
    "frontend/Dockerfile",
    "frontend/.dockerignore",
    "frontend/nginx.conf.template",
    "frontend/package-lock.json",
    "frontend/src/main.tsx",
    "frontend/vite.config.ts",
    "Dockerfile",
    "Dockerfile.test",
    ".dockerignore",
    "docker-compose.test.yml",
    "src/dnd_simulator/adapters/api.py",
    "content/worlds/default/manifest.yaml",
    "tests/frontend_proxy/test_frontend_proxy.py",
    "tests/integration/content/manifest.yaml",
    "pyproject.toml",
    "uv.lock",
    ".python-version",
    "Makefile",
    "scripts/classify-scope.sh",
    ".github/workflows/ci.yml",
]


def _classify(paths: list[str]) -> str:
    result = subprocess.run(
        [str(CLASSIFIER)], input="\n".join(paths) + "\n", capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _job() -> dict[str, Any]:
    workflow = yaml.safe_load(WORKFLOW.read_text())
    job = workflow["jobs"]["frontend-container"]
    assert isinstance(job, dict)
    return job


def _step(job: dict[str, Any], name: str) -> dict[str, Any]:
    steps = [s for s in job["steps"] if s.get("name") == name]
    assert len(steps) == 1, name
    step = steps[0]
    assert isinstance(step, dict)
    return step


class TestPathTrigger:
    @pytest.mark.parametrize("path", CONTAINER_RELEVANT_PATHS)
    def test_container_relevant_path_is_never_docs(self, path: str) -> None:
        assert _classify([path]) != "docs"
        assert _classify([path, "docs/ROADMAP.md"]) != "docs"

    def test_docs_only_change_is_docs(self) -> None:
        assert _classify(["docs/ROADMAP.md", "README.md"]) == "docs"

    def test_smoke_runs_for_every_scope_but_docs(self) -> None:
        job = _job()
        assert job["needs"] == "detect-changes"
        smoke = _step(job, "Run frontend container smoke")
        assert smoke["if"] == f"{SCOPE} != 'docs'"
        assert smoke["run"] == "make test-frontend-container"
        assert _step(job, "Skipped (out of scope)")["if"] == f"{SCOPE} == 'docs'"


class TestIsolationAndCleanup:
    def test_compose_project_is_unique_per_run_attempt_and_job(self) -> None:
        project = _job()["env"]["COMPOSE_PROJECT_NAME"]
        for part in ("${{ github.run_id }}", "${{ github.run_attempt }}", "${{ github.job }}"):
            assert part in project

    def test_frontend_port_is_ephemeral(self) -> None:
        assert _job()["env"]["FRONTEND_PORT"] == "0"

    def test_cleanup_runs_always_and_only_on_the_job_project(self) -> None:
        job = _job()
        cleanup = _step(job, "Clean up compose project")
        assert cleanup["if"].startswith("always() && ")
        command = cleanup["run"]
        assert command.startswith("docker compose -f docker-compose.test.yml --profile frontend down")
        # The project comes from the job env; nothing may override it or reach beyond it.
        assert " -p " not in command and "--project-name" not in command
        for step in job["steps"]:
            assert "prune" not in step.get("run", "")


def _fake_docker(tmp_path: Path, up_status: int) -> tuple[dict[str, str], Path]:
    calls = tmp_path / "docker-calls.log"
    fake = tmp_path / "bin" / "docker"
    fake.parent.mkdir()
    fake.write_text(
        "#!/bin/sh\n"
        f'echo "project=$COMPOSE_PROJECT_NAME $*" >> "{calls}"\n'
        'for arg in "$@"; do\n'
        f'  [ "$arg" = up ] && exit {up_status}\n'
        "done\n"
        "exit 0\n"
    )
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    env = {
        **os.environ,
        "PATH": f"{fake.parent}{os.pathsep}{os.environ['PATH']}",
        "COMPOSE_PROJECT_NAME": "dnd-fe-smoke-test",
    }
    return env, calls


class TestMakeTargetSemantics:
    @pytest.mark.parametrize("up_status", [0, 1, 7])
    def test_exit_status_follows_smoke_and_project_is_torn_down(self, tmp_path: Path, up_status: int) -> None:
        env, calls = _fake_docker(tmp_path, up_status)
        result = subprocess.run(
            ["make", "-s", "-C", str(REPO_ROOT), "test-frontend-container"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert (result.returncode == 0) == (up_status == 0), result.stderr
        lines = calls.read_text().splitlines()
        assert len(lines) == 2
        up, down = lines
        assert up.startswith("project=dnd-fe-smoke-test compose -f docker-compose.test.yml --profile frontend up ")
        assert "--exit-code-from frontend-smoke" in up
        assert down.startswith("project=dnd-fe-smoke-test compose -f docker-compose.test.yml --profile frontend down")
