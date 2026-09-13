# test_main.py
from datetime import datetime
from unittest.mock import patch

import pytest

# import asyncio
# import time
from fastapi.testclient import TestClient

from main import app

# from main stress_test_active

client = TestClient(app)


class TestBasicEndpoints:
    """Test basic API endpoints"""

    def test_root_endpoint(self):
        """Test the root endpoint returns expected structure"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "endpoints" in data
        assert isinstance(data["endpoints"], list)
        assert "/health" in data["endpoints"]
        assert "/get" in data["endpoints"]
        assert "/stress" in data["endpoints"]

    def test_health_endpoint(self):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "uptime_seconds" in data
        assert data["version"] == "1.0.0"
        assert isinstance(data["uptime_seconds"], float)

    def test_health_endpoint_structure(self):
        """Test health endpoint returns correct data types"""
        response = client.get("/health")
        data = response.json()

        # Validate timestamp is valid ISO format
        try:
            datetime.fromisoformat(data["timestamp"])
        except ValueError:
            pytest.fail("Invalid timestamp format")

        # Check uptime is positive
        assert data["uptime_seconds"] >= 0


class TestGetEndpoint:
    """Test the /get endpoint that mimics httpbin"""

    def test_get_endpoint_basic(self):
        """Test basic /get endpoint functionality"""
        response = client.get("/get")
        assert response.status_code == 200
        data = response.json()

        # Check required fields
        assert "args" in data
        assert "headers" in data
        assert "origin" in data
        assert "url" in data
        assert "method" in data
        assert data["method"] == "GET"
        assert "timestamp" in data
        assert "server_info" in data

    def test_get_endpoint_with_query_params(self):
        """Test /get endpoint with query parameters"""
        response = client.get("/get?foo=bar&test=123")
        assert response.status_code == 200
        data = response.json()

        assert data["args"] == {"foo": "bar", "test": "123"}
        assert "/get?foo=bar&test=123" in data["url"]

    def test_get_endpoint_with_headers(self):
        """Test /get endpoint captures custom headers"""
        custom_headers = {
            "X-Custom-Header": "test-value",
            "User-Agent": "pytest-client"
        }
        response = client.get("/get", headers=custom_headers)
        assert response.status_code == 200
        data = response.json()

        assert "x-custom-header" in data["headers"]
        assert data["headers"]["x-custom-header"] == "test-value"
        assert data["user-agent"] == "pytest-client"

    def test_get_endpoint_server_info(self):
        """Test /get endpoint includes server information"""
        response = client.get("/get")
        data = response.json()

        assert "hostname" in data["server_info"]
        assert "platform" in data["server_info"]
        assert "python_version" in data["server_info"]

        # Validate Python version format (e.g., "3.9.0")
        python_version = data["server_info"]["python_version"]
        assert len(python_version.split(".")) >= 2


# class TestStressEndpoint:
#     """Test the /stress endpoint for CPU stress testing"""

#     def test_stress_endpoint_default(self):
#         """Test stress endpoint with default duration"""
#         response = client.post("/stress")
#         assert response.status_code == 200
#         data = response.json()

#         assert "message" in data
#         assert "duration_seconds" in data
#         assert data["duration_seconds"] == 180  # Default 3 minutes
#         assert "started_at" in data
#         assert "ends_at" in data
#         assert "cpu_cores" in data
#         assert data["cpu_cores"] > 0

#     def test_stress_endpoint_custom_duration(self):
#         """Test stress endpoint with custom duration"""
#         response = client.post("/stress?duration_seconds=60")
#         assert response.status_code == 200
#         data = response.json()

#         assert data["duration_seconds"] == 60
#         assert "60 seconds" in data["message"]

#     def test_stress_endpoint_max_duration_limit(self):
#         """Test that stress endpoint limits maximum duration"""
#         response = client.post("/stress?duration_seconds=600")  # Try 10 minutes
#         assert response.status_code == 200
#         data = response.json()

#         # Should be capped at 300 seconds (5 minutes)
#         assert data["duration_seconds"] == 300

#     def test_stress_endpoint_min_duration_limit(self):
#         """Test that stress endpoint enforces minimum duration"""
#         response = client.post("/stress?duration_seconds=0")
#         assert response.status_code == 200
#         data = response.json()

#         # Should be at least 1 second
#         assert data["duration_seconds"] == 1

#     @patch('main.stress_test_active', True)
#     @patch('main.stress_test_end_time', time.time() + 100)
#     def test_stress_endpoint_already_running(self):
#         """Test stress endpoint when a test is already running"""
#         response = client.post("/stress")
#         assert response.status_code == 409
#         assert "already running" in response.json()["detail"]

#     def test_stress_status_not_running(self):
#         """Test stress status endpoint when no test is running"""
#         response = client.get("/stress/status")
#         assert response.status_code == 200
#         data = response.json()

#         assert data["active"] == False
#         assert "message" in data

#     @patch('main.stress_test_active', True)
#     @patch('main.stress_test_end_time', time.time() + 60)
#     def test_stress_status_running(self):
#         """Test stress status endpoint when test is running"""
#         response = client.get("/stress/status")
#         assert response.status_code == 200
#         data = response.json()

#         assert data["active"] == True
#         assert "remaining_seconds" in data
#         assert "end_time" in data
#         assert data["remaining_seconds"] > 0


class TestMetricsEndpoint:
    """Test the /metrics endpoint for Prometheus"""

    def test_metrics_endpoint(self):
        """Test metrics endpoint returns Prometheus format"""
        response = client.get("/metrics")
        assert response.status_code == 200

        # Check content type - prometheus_client uses text/plain
        assert "text/plain" in response.headers["content-type"]

        # Get the raw text content
        content = response.text

        # Check for expected metric lines from prometheus_client
        assert "app_info" in content
        assert "app_uptime_seconds" in content
        assert "app_stress_test_active" in content
        assert "http_requests_total" in content
        assert "http_request_duration_seconds" in content
        assert "app_cpu_cores" in content
        assert "# HELP" in content
        assert "# TYPE" in content

    def test_metrics_format(self):
        """Test that metrics are in valid Prometheus format"""
        response = client.get("/metrics")
        content = response.text

        # Check for proper Prometheus format
        lines = content.split('\n')

        # Check that we have HELP and TYPE declarations
        help_lines = [line for line in lines if line.startswith('# HELP')]
        type_lines = [line for line in lines if line.startswith('# TYPE')]
        metric_lines = [line for line in lines if line and not line.startswith('#')]

        assert len(help_lines) > 0
        assert len(type_lines) > 0
        assert len(metric_lines) > 0

        # Check for histogram buckets (prometheus_client feature)
        assert any('_bucket{' in line for line in lines)
        assert any('_count' in line for line in lines)
        assert any('_sum' in line for line in lines)

    def test_metrics_values(self):
        """Test that metrics contain valid values"""
        response = client.get("/metrics")
        content = response.text

        # Check that app_info metric is present
        assert 'app_info{name="sample-devops-api",version="1.0.0"} 1' in content

        # Check stress test metric shows 0 when not active
        import re
        stress_match = re.search(r'app_stress_test_active (\d+\.?\d*)', content)
        assert stress_match is not None
        assert float(stress_match.group(1)) in [0.0, 1.0]

        # Check that uptime is a positive number
        uptime_match = re.search(r'app_uptime_seconds (\d+\.?\d*)', content)
        assert uptime_match is not None
        assert float(uptime_match.group(1)) >= 0

    def test_request_counter_increments(self):
        """Test that request counter increments with requests"""
        # Make some requests first
        client.get("/")
        client.get("/health")
        client.get("/get")

        # Get metrics
        response = client.get("/metrics")
        content = response.text

        # Check that http_requests_total has recorded requests
        assert 'http_requests_total{' in content

        # Check for specific endpoints
        assert 'endpoint="/"' in content or 'endpoint="/health"' in content

        # Verify the counter is greater than 0
        import re
        matches = re.findall(r'http_requests_total\{[^}]+\} (\d+)', content)
        assert len(matches) > 0
        assert any(int(m) > 0 for m in matches)


class TestConcurrency:
    """Test concurrent requests handling"""

    def test_concurrent_get_requests(self):
        """Test that multiple concurrent GET requests work"""
        import concurrent.futures

        def make_request():
            return client.get("/get")

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All requests should succeed
        assert all(r.status_code == 200 for r in results)

    def test_health_during_stress(self):
        """Test that health endpoint remains responsive during stress"""
        # This is a simplified test - in real scenario, you'd start actual stress
        response = client.get("/health")
        assert response.status_code == 200

        # Even if stress test were running, health should respond
        with patch('main.stress_test_active', True):
            response = client.get("/health")
            assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
