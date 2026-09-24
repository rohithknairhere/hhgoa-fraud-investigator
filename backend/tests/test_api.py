import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.config import Settings


def make_client(**overrides) -> TestClient:
    settings = Settings(graph_backend="mock", benchmark_dir=__import__("pathlib").Path("does-not-exist"),
                        **overrides)
    return TestClient(create_app(settings), base_url="https://testserver")


@pytest.fixture
def client():
    with make_client() as c:
        yield c


def test_health_and_security_headers(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["graph_backend"] == "mock"
    assert "max-age" in r.headers["strict-transport-security"]
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["x-ratelimit-limit"]


def test_plain_http_rejected_when_not_loopback():
    with make_client(allow_local_http=False) as c:
        http = TestClient(c.app, base_url="http://testserver")
        assert http.get("/api/health").status_code == 403


def test_forwarded_proto_from_trusted_proxy_is_honoured():
    with make_client(allow_local_http=False) as c:
        http = TestClient(c.app, base_url="http://testserver", client=("127.0.0.1", 5000))
        assert http.get("/api/health", headers={"X-Forwarded-Proto": "https"}).status_code == 200
        assert http.get("/api/health", headers={"X-Forwarded-Proto": "http"}).status_code == 403


def test_rate_limit_returns_429():
    with make_client(rate_limit_per_minute=3) as c:
        codes = [c.get("/api/health").status_code for _ in range(5)]
        assert codes[:3] == [200, 200, 200] and codes[3] == 429


def test_case_listing_and_detail(client):
    cases = client.get("/api/cases").json()["cases"]
    assert len(cases) == 20
    detail = client.get("/api/cases/HHGOA-004").json()
    assert detail["nba_before_additional_evidence"]["action"] == "MONITOR_ACCOUNT_AND_REQUEST_STEP_UP_AUTH"
    assert detail["nba_after_additional_evidence"]["action"] == "ALLOW_TRANSACTION"
    assert client.get("/api/cases/HHGOA-999").status_code == 404
    assert client.get("/api/cases/../etc").status_code in (404, 422)


def test_execute_requires_recommended_action_and_is_idempotent(client):
    assert client.post("/api/cases/HHGOA-002/execute", json={"action": "ALLOW_TRANSACTION"}).status_code == 409
    first = client.post("/api/cases/HHGOA-002/execute", json={"action": "BLOCK_TRANSACTION"})
    assert first.status_code == 200
    again = client.post("/api/cases/HHGOA-002/execute", json={"action": "BLOCK_TRANSACTION"}).json()
    assert again["execution_id"] == first.json()["execution_id"] and again["idempotent_replay"]


def test_analyst_note_validation(client):
    bad = client.post("/api/cases/HHGOA-001/notes", json={"author": "A", "disposition": "maybe", "note": "short"})
    assert bad.status_code == 422
    xss = client.post("/api/cases/HHGOA-001/notes",
                      json={"author": "Ana", "disposition": "agree", "note": "<script>alert(1)</script>"})
    assert xss.status_code == 422
    ok = client.post("/api/cases/HHGOA-001/notes",
                     json={"author": "Ana Analyst", "disposition": "agree", "note": "Ring confirmed via device."})
    assert ok.status_code == 201


def test_pattern_endpoints_and_mcp_tools(client):
    assert client.get("/api/patterns/device-sharing").json()["devices"]
    assert client.get("/api/patterns/velocity").json()["bursts"]
    tools = client.get("/api/mcp/tools").json()
    assert "update_case_memory" not in {t["name"] for t in tools["tools"]}
