import uuid

from fastapi.testclient import TestClient


def test_request_id_echoed_when_provided(client: TestClient):
    rid = "test-request-id-123"
    resp = client.get("/healthz", headers={"X-Request-ID": rid})
    assert resp.headers.get("x-request-id") == rid


def test_request_id_generated_when_absent(client: TestClient):
    resp = client.get("/healthz")
    got = resp.headers.get("x-request-id")
    assert got is not None
    uuid.UUID(got, version=4)
