"""Coverage for missing world metadata manifests."""

import re
from pathlib import Path

import pytest

from dnd_simulator.content_loader.manifest import load_world_meta_from_manifest


def test_load_world_meta_missing_manifest_raises(tmp_path: Path) -> None:
    world_dir = tmp_path / "no_manifest"
    world_dir.mkdir()

    with pytest.raises(RuntimeError, match=re.escape(f"No manifest.yaml found in {world_dir}")):
        load_world_meta_from_manifest(world_dir)
