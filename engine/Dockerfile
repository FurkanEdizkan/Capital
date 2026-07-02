# Capital engine — container image.
# uv provides the Python toolchain and a reproducible, locked environment.

FROM python:3.12-slim

# uv binary (pinned image) — fast, lockfile-driven dependency install.
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/

WORKDIR /app

# Install dependencies first (cached layer) from the lockfile.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# llmfit (optional) — scores which local LLMs fit the host hardware, shown on
# Settings → Local models. Best-effort: the image builds fine without it.
RUN uv tool install llmfit && ln -s /root/.local/bin/llmfit /usr/local/bin/llmfit \
    || echo "llmfit install skipped"

# App source.
COPY . .

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

CMD ["uv", "run", "--no-dev", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
