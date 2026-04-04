# FN Extension Backend

A FastAPI backend service for the FN Extension project.

## Prerequisites

- **Python 3.13+** installed
- **[uv](https://docs.astral.sh/uv/)** package manager installed

  ```bash
  # Install uv (macOS)
  brew install uv

  # Or via pip
  pip install uv
  ```

## Quick Setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd fn-extension-backend
```

### 2. Install dependencies

```bash
uv sync
```

This creates a virtual environment and installs all dependencies from `pyproject.toml`.

### 3. Run the development server

```bash
uv run uvicorn main:app --reload
```

The server will start at `http://localhost:8000` with auto-reload enabled.

## API Endpoints

| Method | Endpoint     | Description        |
|--------|--------------|--------------------|
| GET    | `/`          | Hello world        |
| GET    | `/health`    | Health check       |
| GET    | `/analyze`   | Mock analyze endpoint |

## Interactive API Documentation

FastAPI provides auto-generated API docs:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## CORS Configuration

The backend is configured to accept requests from:
- `http://localhost:3000` (React frontend)

Update the `origins` list in `main.py` if you need to allow additional frontend URLs.

## Common Commands

```bash
# Install a new dependency
uv add <package-name>

# Remove a dependency
uv remove <package-name>

# Run any Python script
uv run python <script.py>

# Run with custom host/port
uv run uvicorn main:app --reload --host 0.0.0.0 --port 3001
```

## Project Structure

```
fn-extension-backend/
├── main.py              # FastAPI application entry point
├── pyproject.toml       # Project dependencies and metadata
├── uv.lock              # Locked dependency versions
└── README.md            # This file
```
