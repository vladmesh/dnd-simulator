FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src/ src/
RUN uv sync --no-dev --frozen
COPY content/ content/
RUN mkdir saves

EXPOSE 8001
CMD ["uv", "run", "uvicorn", "dnd_simulator.adapters.api.app:app", "--host", "0.0.0.0", "--port", "8001"]
