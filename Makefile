.PHONY: install lint format typecheck test check messages compile-messages serve stop

install:
	uv sync

lint:
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

format:
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

typecheck:
	uv run mypy src/

test:
	uv run pytest

check: lint typecheck test

stop:
	@fuser -k 8001/tcp 2>/dev/null && echo "Stopped server on :8001" || echo "Nothing running on :8001"

serve: stop
	uv run uvicorn dnd_simulator.adapters.api.app:app --host 0.0.0.0 --port 8001 --reload

messages:
	find src/dnd_simulator -name '*.py' | xargs pygettext3 --keyword=_ --output=src/dnd_simulator/locale/messages.pot

compile-messages:
	python3 -c "import subprocess; subprocess.run(['msgfmt', '-o', 'src/dnd_simulator/locale/ru/LC_MESSAGES/dnd_simulator.mo', 'src/dnd_simulator/locale/ru/LC_MESSAGES/dnd_simulator.po'])" 2>/dev/null || echo "msgfmt not available, use scripts/compile_po.py"
