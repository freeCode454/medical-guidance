"""请求上下文中间件：trace id、安全头、统一 500 响应。"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.common.error_codes import INTERNAL_ERROR
from app.middleware.request_context import RequestContextMiddleware

app = FastAPI()
app.add_middleware(RequestContextMiddleware)


@app.get("/ok")
async def ok() -> dict[str, bool]:
    return {"ok": True}


@app.get("/boom")
async def boom() -> dict[str, bool]:
    raise RuntimeError("boom")


client = TestClient(app, raise_server_exceptions=False)


def test_trace_id_is_generated_and_echoed() -> None:
    response = client.get("/ok")
    assert response.status_code == 200
    trace_id = response.headers["X-Trace-ID"]
    assert trace_id
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_client_supplied_request_id_is_reused() -> None:
    response = client.get("/ok", headers={"X-Request-ID": "client-trace-123"})
    assert response.headers["X-Trace-ID"] == "client-trace-123"


def test_unhandled_error_uses_unified_envelope() -> None:
    response = client.get("/boom")
    assert response.status_code == INTERNAL_ERROR.http_status
    body = response.json()
    assert body["code"] == INTERNAL_ERROR.code
    assert body["data"] is None
    assert response.headers["X-Trace-ID"]
