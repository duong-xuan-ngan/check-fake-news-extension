# 1. Start with the official standard Python slim image (glibc compatible)
FROM python:3.13-slim

# 2. Grab the pre-compiled uv binary from the official Astral image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Enable bytecode compilation for faster startups
ENV UV_COMPILE_BYTECODE=1

# Copy lockfiles first to leverage Docker caching
COPY pyproject.toml uv.lock ./

# Install dependencies without installing the project itself
RUN /bin/uv sync --frozen --no-install-project

# Copy the rest of your backend source code
COPY . .

EXPOSE 8000

# Run your FastAPI/Uvicorn app
CMD ["/bin/uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]