#!/usr/bin/env python3
"""
Tests for the REST API Control Plane
=====================================
Uses FastAPI's TestClient for synchronous endpoint testing.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from src.api_server import app  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


# ===================================================================
# Health Endpoint
# ===================================================================
class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_has_components(self, client):
        data = client.get("/health").json()
        assert "status" in data
        assert data["status"] == "healthy"
        assert "components" in data
        assert "circuit_breaker" in data["components"]
        assert "edge_buffer" in data["components"]
        assert "audit_log" in data["components"]

    def test_health_has_uptime(self, client):
        data = client.get("/health").json()
        assert "uptime_seconds" in data
        assert data["uptime_seconds"] >= 0

    def test_health_has_timestamp(self, client):
        data = client.get("/health").json()
        assert "timestamp" in data


# ===================================================================
# Metrics Endpoint
# ===================================================================
class TestMetricsEndpoint:
    def test_metrics_returns_200(self, client):
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_metrics_has_circuit_breaker(self, client):
        data = client.get("/metrics").json()
        cb = data["circuit_breaker"]
        assert "state" in cb
        assert "total_passed" in cb
        assert "total_rejected" in cb
        assert "consecutive_failures" in cb

    def test_metrics_has_dlq(self, client):
        data = client.get("/metrics").json()
        assert "dlq" in data
        assert "depth" in data["dlq"]

    def test_metrics_has_edge_buffer(self, client):
        data = client.get("/metrics").json()
        buf = data["edge_buffer"]
        assert "total_buffered" in buf
        assert "pending_sync" in buf
        assert "buffer_utilisation" in buf

    def test_metrics_has_audit(self, client):
        data = client.get("/metrics").json()
        assert "audit" in data
        assert "total_entries" in data["audit"]


# ===================================================================
# SLO Endpoint
# ===================================================================
class TestSLOEndpoint:
    def test_slo_returns_200(self, client):
        response = client.get("/slo")
        assert response.status_code == 200

    def test_slo_has_overall(self, client):
        data = client.get("/slo").json()
        assert "overall" in data
        assert "passed" in data
        assert "failed" in data

    def test_slo_has_results(self, client):
        data = client.get("/slo").json()
        assert "results" in data
        assert len(data["results"]) > 0
        for r in data["results"]:
            assert "name" in r
            assert "passed" in r
            assert "threshold" in r
            assert "actual" in r


# ===================================================================
# Reports Endpoint
# ===================================================================
class TestReportsEndpoint:
    def test_list_reports_returns_200(self, client):
        response = client.get("/reports")
        assert response.status_code == 200
        data = response.json()
        assert "reports" in data
        assert "total" in data

    def test_get_nonexistent_report(self, client):
        response = client.get("/reports/nonexistent_run_id_xyz")
        assert response.status_code == 404


# ===================================================================
# Controls Endpoints
# ===================================================================
class TestControlsEndpoints:
    def test_circuit_breaker_reset(self, client):
        response = client.post("/circuit-breaker/reset")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["new_state"] == "CLOSED"

    def test_smoke_run(self, client):
        response = client.post("/run")
        assert response.status_code == 200
        data = response.json()
        assert data["accepted"] + data["rejected"] == 20
        assert len(data["packets"]) == 20
        assert all("packet_id" in p for p in data["packets"])


# ===================================================================
# Dashboard Endpoint
# ===================================================================
class TestDashboardEndpoint:
    def test_dashboard_returns_html(self, client):
        response = client.get("/dashboard")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Resilient RAP Framework" in response.text
