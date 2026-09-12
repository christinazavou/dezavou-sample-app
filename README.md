# Sample DevOps API

A simple FastAPI application designed for DevOps assessment, featuring health checks, request information, and CPU stress testing capabilities for monitoring demonstrations.

## Features

- **Health Check Endpoint** (`/health`): Kubernetes-ready health probe
- **Request Info Endpoint** (`/get`): HTTPBin-style request information
- **CPU Stress Test** (`/stress`): Configurable CPU load for monitoring demos
- **Metrics Endpoint** (`/metrics`): Prometheus-compatible metrics
- **OpenAPI Documentation** (`/docs`): Auto-generated API documentation

## Technology Stack

- **Python 3.9+**
- **FastAPI**: Modern web framework
- **UV**: Fast Python package manager
- **Uvicorn**: ASGI server
- **Docker**: Containerization

## Quick Start

### Local Development with UV

```bash
# Install UV (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"

# Run the application
python main.py

# Or with hot reload
DEV_MODE=true python main.py
```

### Run with Docker

```bash
# Build the image
docker build -t sample-devops-api:latest .

# Run the container
docker run -p 8000:8000 sample-devops-api:latest

# Run with custom port
docker run -p 8080:8000 -e PORT=8000 sample-devops-api:latest
```

## API Endpoints

### 1. Root Endpoint
```bash
curl http://localhost:8000/
```

### 2. Health Check
```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00",
  "uptime_seconds": 123.45,
  "version": "1.0.0"
}
```

### 3. Get Request Info
```bash
curl "http://localhost:8000/get?param1=value1&param2=value2" \
  -H "X-Custom-Header: test"
```

Response includes:
- Request arguments
- Headers
- Client information
- Server information

### 4. CPU Stress Test
```bash
# Start 3-minute stress test (default)
curl -X POST http://localhost:8000/stress

# Start 1-minute stress test
curl -X POST "http://localhost:8000/stress?duration_seconds=60"

# Check stress test status
curl http://localhost:8000/stress/status
```

### 5. Metrics (Prometheus Format)
```bash
curl http://localhost:8000/metrics
```

## Running Tests

```bash
# Install test dependencies
uv pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage
pytest --cov=main --cov-report=term-missing

# Run specific test file
pytest test_main.py::TestGetEndpoint

# Run tests with verbose output
pytest -v
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Application port | `8000` |
| `HOST` | Bind host | `0.0.0.0` |
| `DEV_MODE` | Enable hot reload | `false` |

## Project Structure

```
sample-app/
├── main.py              # FastAPI application
├── test_main.py         # Unit tests
├── pyproject.toml       # Project dependencies (UV)
├── Dockerfile           # Multi-stage Docker build
├── README.md            # This file
└── .gitignore
```

## Docker Build Details

The Dockerfile uses a multi-stage build:
1. **Builder stage**: Installs UV and Python dependencies
2. **Runtime stage**: Minimal image with only runtime requirements
3. **Security**: Runs as non-root user
4. **Health check**: Built-in health check for container orchestration



## Load Testing

Use the stress endpoint to simulate load:
```bash
# Start stress test
curl -X POST http://localhost:8000/stress

# Monitor CPU usage
docker stats

# Check metrics
curl http://localhost:8000/metrics | grep stress
```

## Development Workflow

1. **Make changes** to `main.py`
2. **Run tests**: `pytest`
3. **Format code**: `black main.py test_main.py`
4. **Lint**: `ruff check main.py`
5. **Type check**: `mypy main.py`
6. **Build Docker image**: `docker build -t sample-api:dev .`
7. **Test container**: `docker run -p 8000:8000 sample-api:dev`


### Tests Failing
```bash
# Run tests with detailed output
pytest -vv --tb=long
```
