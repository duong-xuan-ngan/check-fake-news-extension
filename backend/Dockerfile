# 1. Start with the official standard Python slim image (glibc compatible)
FROM python:3.13-slim

# 2. Grab the pre-compiled uv binary from the official Astral image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Bytecode compilation disabled: pre-compile step times out on t3.small
# (large PyTorch files exceed uv's 60s per-file compile limit under CPU pressure)
# .pyc files are generated lazily on first import instead — small one-time runtime cost.
ENV UV_COMPILE_BYTECODE=0

# Copy lockfiles first to leverage Docker caching
COPY pyproject.toml uv.lock ./

# Install dependencies without installing the project itself
RUN /bin/uv sync --frozen --no-install-project

# Copy the rest of your backend source code
COPY . .

EXPOSE 8000

# Run your FastAPI/Uvicorn app
CMD ["/bin/uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]