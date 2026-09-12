# main.py
import asyncio
import time
import multiprocessing
from datetime import datetime
from typing import Dict, Any, Optional
import platform
import os

from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from prometheus_client import Counter, Gauge, Histogram, Info, generate_latest, CONTENT_TYPE_LATEST
import prometheus_client

app = FastAPI(
    title="Sample DevOps API",
    description="A simple API for DevOps assessment with monitoring capabilities",
    version="1.0.0"
)

# Clear default prometheus collectors to avoid duplicate metrics
prometheus_client.REGISTRY._collector_to_names.clear()
prometheus_client.REGISTRY._names_to_collectors.clear()

# Prometheus metrics
app_info = Info('app', 'Application information')
app_info.info({'version': '1.0.0', 'name': 'sample-devops-api'})

uptime_seconds = Gauge('app_uptime_seconds', 'Application uptime in seconds')
stress_test_active = Gauge('app_stress_test_active', 'Whether a stress test is currently running')
cpu_cores = Gauge('app_cpu_cores', 'Number of CPU cores available')
cpu_cores.set(multiprocessing.cpu_count())

# Request metrics with labels
http_requests_total = Counter(
    'http_requests_total',
    'Total number of HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency in seconds',
    ['method', 'endpoint']
)

# Stress test metrics
stress_test_runs_total = Counter('stress_test_runs_total', 'Total number of stress tests initiated')
stress_test_duration_seconds = Gauge('stress_test_duration_seconds', 'Duration of the current/last stress test')

# Global variables for stress test
stress_test_end_time: Optional[float] = None
app_start_time = time.time()


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    uptime_seconds: float
    version: str


class StressResponse(BaseModel):
    message: str
    duration_seconds: int
    started_at: str
    ends_at: str
    cpu_cores: int


@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    """Middleware to track request metrics"""
    # Skip metrics endpoint to avoid recursion
    if request.url.path == "/metrics":
        return await call_next(request)
    
    # Start timer
    start_time = time.time()
    
    # Process request
    response = await call_next(request)
    
    # Record metrics
    duration = time.time() - start_time
    
    # Update metrics
    http_requests_total.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    
    http_request_duration_seconds.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)
    
    return response


@app.on_event("startup")
async def startup_event():
    """Update uptime metric periodically"""
    async def update_uptime():
        while True:
            uptime_seconds.set(time.time() - app_start_time)
            await asyncio.sleep(10)  # Update every 10 seconds
    
    asyncio.create_task(update_uptime())


@app.get("/")
async def root():
    """Root endpoint - returns a simple welcome message"""
    return {
        "message": "Welcome to Sample DevOps API",
        "endpoints": [
            "/health",
            "/get",
            "/stress",
            "/metrics",
            "/docs"
        ]
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for Kubernetes probes"""
    uptime = time.time() - app_start_time
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        uptime_seconds=round(uptime, 2),
        version="1.0.0"
    )


@app.get("/get")
async def get_request_info(request: Request) -> Dict[str, Any]:
    """
    Similar to httpbin.org/get - returns information about the request
    """
    headers = dict(request.headers)
    
    # Get client host information
    client_host = request.client.host if request.client else "unknown"
    client_port = request.client.port if request.client else "unknown"
    
    # Get query parameters
    query_params = dict(request.query_params)
    
    response = {
        "args": query_params,
        "headers": headers,
        "origin": client_host,
        "url": str(request.url),
        "method": request.method,
        "path": request.url.path,
        "host": headers.get("host", "unknown"),
        "user-agent": headers.get("user-agent", "unknown"),
        "timestamp": datetime.utcnow().isoformat(),
        "server_info": {
            "hostname": platform.node(),
            "platform": platform.platform(),
            "python_version": platform.python_version()
        }
    }
    
    return response


def cpu_stress_worker(duration: int):
    """
    Worker function that creates CPU stress
    Performs intensive calculations for the specified duration
    """
    end_time = time.time() + duration
    counter = 0
    
    while time.time() < end_time:
        # Perform CPU-intensive calculations
        _ = sum(i * i for i in range(10000))
        counter += 1
        
        # Brief sleep every 1000 iterations to prevent complete system freeze
        if counter % 1000 == 0:
            time.sleep(0.001)


async def run_stress_test(duration_seconds: int):
    """
    Run CPU stress test using multiple processes
    """
    global stress_test_end_time
    
    stress_test_active.set(1)
    stress_test_end_time = time.time() + duration_seconds
    stress_test_duration_seconds.set(duration_seconds)
    
    # Get number of CPU cores
    num_cores = multiprocessing.cpu_count()
    
    # Create a process pool to stress multiple cores
    processes = []
    
    try:
        # Start stress on each core
        for _ in range(num_cores):
            process = multiprocessing.Process(
                target=cpu_stress_worker,
                args=(duration_seconds,)
            )
            process.start()
            processes.append(process)
        
        # Wait for all processes to complete
        for process in processes:
            process.join()
    
    finally:
        # Ensure all processes are terminated
        for process in processes:
            if process.is_alive():
                process.terminate()
        
        stress_test_active.set(0)
        stress_test_end_time = None


@app.post("/stress", response_model=StressResponse)
async def stress_endpoint(
    background_tasks: BackgroundTasks,
    duration_seconds: int = 180  # Default 3 minutes
):
    """
    Endpoint to create CPU stress for monitoring demonstration
    Default duration: 3 minutes (180 seconds)
    """
    global stress_test_end_time
    
    # Check if a stress test is already running
    if stress_test_active._value.get() == 1:
        remaining_time = int(stress_test_end_time - time.time()) if stress_test_end_time else 0
        raise HTTPException(
            status_code=409,
            detail=f"Stress test already running. {remaining_time} seconds remaining."
        )
    
    # Limit duration to prevent abuse (max 5 minutes)
    if duration_seconds > 300:
        duration_seconds = 300
    elif duration_seconds < 1:
        duration_seconds = 1
    
    # Increment stress test counter
    stress_test_runs_total.inc()
    
    # Start stress test in background
    background_tasks.add_task(run_stress_test, duration_seconds)
    
    started_at = datetime.utcnow()
    ends_at = datetime.fromtimestamp(time.time() + duration_seconds)
    
    return StressResponse(
        message=f"CPU stress test started for {duration_seconds} seconds",
        duration_seconds=duration_seconds,
        started_at=started_at.isoformat(),
        ends_at=ends_at.isoformat(),
        cpu_cores=multiprocessing.cpu_count()
    )


@app.get("/stress/status")
async def stress_status():
    """Check the status of the stress test"""
    global stress_test_end_time
    
    if stress_test_active._value.get() == 1 and stress_test_end_time:
        remaining_time = max(0, int(stress_test_end_time - time.time()))
        return {
            "active": True,
            "remaining_seconds": remaining_time,
            "end_time": datetime.fromtimestamp(stress_test_end_time).isoformat()
        }
    
    return {
        "active": False,
        "message": "No stress test running"
    }


@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint
    Returns metrics in Prometheus exposition format
    """
    # Generate metrics in Prometheus format
    metrics_output = generate_latest(prometheus_client.REGISTRY)
    
    return Response(
        content=metrics_output,
        media_type=CONTENT_TYPE_LATEST
    )


if __name__ == "__main__":
    import uvicorn
    
    # Get port from environment variable or use default
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=bool(os.getenv("DEV_MODE", False)),
        log_level="info"
    )