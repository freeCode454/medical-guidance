"""端到端冒烟测试：完整问诊链路。

覆盖：健康检查 → 匿名会话 → 创建预问诊（带性别年龄）→ 追问 → 回答 → 分诊结论 → 患者视图病历。

前置：后端 + PostgreSQL + Milvus 已启动（LLM 需可用，否则分诊断言会跳过）。

运行：
    python -m pytest tests/test_e2e_smoke.py -v -s
"""
from __future__ import annotations

import time

import httpx
import pytest

BASE = "http://127.0.0.1:8000"
# 唯一 device_id：避免命中「同设备未完成会话复用」逻辑，导致拿到旧会话
DEVICE = f"e2e_{int(time.time())}"


@pytest.fixture(scope="module")
def client():
    c = httpx.Client(base_url=BASE, timeout=180)
    try:
        assert c.get("/healthz").status_code == 200
    except Exception:  # 后端未启动时整体跳过，而不是失败
        pytest.skip("后端未运行，跳过端到端测试")
    yield c
    c.close()


def _patient_token(c: httpx.Client) -> str:
    r = c.post("/api/v1/auth/patient/session", json={"device_id": DEVICE})
    data = r.json()
    assert data["code"] == 200, data
    return data["data"]["access_token"]


def _wait_messages(c: httpx.Client, h: dict, sid: str, expect: int, timeout: int = 120) -> list:
    deadline = time.time() + timeout
    msgs: list = []
    while time.time() < deadline:
        msgs = c.get(f"/api/v1/patient/sessions/{sid}/messages", headers=h).json()["data"]["items"]
        if len(msgs) >= expect:
            return msgs
        time.sleep(3)
    return msgs


def test_health(client):
    body = client.get("/healthz").json()
    assert body["status"] == "ok"


def test_anonymous_session(client):
    token = _patient_token(client)
    assert token


def test_full_consultation(client):
    """主诉 → 追问 → 回答 → 分诊 → 病历。"""
    token = _patient_token(client)
    h = {"Authorization": f"Bearer {token}"}

    r = client.post(
        "/api/v1/patient/sessions",
        headers=h,
        json={
            "chief_complaint": "肚子疼三天了，还拉肚子，没有发烧",
            "device_id": DEVICE,
            "input_type": "TEXT",
            "gender": "男",
            "age": 30,
        },
    )
    d = r.json()
    assert d["code"] == 200, d
    sid = d["data"]["session_id"]

    msgs = _wait_messages(client, h, sid, 2)
    assert len(msgs) >= 2, f"未产生 AI 回复：{msgs}"
    ai_msgs = [m for m in msgs if m["role"] == "AI"]
    assert ai_msgs, "应至少有一条 AI 回复"
    print(f"\n  首轮 AI 回复：{ai_msgs[0]['content'][:50]}")

    # 若仍在追问，补答一条（给出部位 + 性质）
    if any("？" in m["content"] for m in ai_msgs):
        client.post(
            f"/api/v1/patient/sessions/{sid}/messages",
            headers=h,
            json={"content": "肚脐周围，一阵一阵的绞痛", "msg_type": "TEXT"},
        )
        _wait_messages(client, h, sid, len(msgs) + 1)

    # 等分诊结论（LLM 较慢，最多 2 分钟）
    deadline = time.time() + 120
    triage = None
    while time.time() < deadline:
        body = client.get(f"/api/v1/patient/sessions/{sid}/triage", headers=h).json()
        if body["code"] == 200:
            triage = body["data"]
            break
        time.sleep(3)

    if triage is None:
        pytest.skip("分诊未在限期内完成（LLM 较慢），跳过结论断言")

    assert triage["recommended_depts"], "分诊应至少返回一个推荐科室"
    top = triage["recommended_depts"][0]
    print(f"  分诊结果：{top['dept_name']}（置信度 {top['confidence']}）")
    # 「肚子疼 + 拉肚子」应分到消化内科
    assert top["dept_code"] == "DIG", f"期望消化内科，实际 {top['dept_code']}"

    # 患者视图病历：A 段必须为 null（R01）
    body = client.get(f"/api/v1/patient/sessions/{sid}/emr", headers=h).json()
    if body["code"] == 200:
        emr = body["data"]
        assert emr["assessment"] is None, "患者视图 A 段必须为 null（R01）"
        assert emr["subjective"]["chief_complaint"], "S 段主诉不应为空"


def test_red_flag_emergency(client):
    """红旗主诉应直接判 EMERGENCY，不走常规分诊。"""
    token = _patient_token(client)
    h = {"Authorization": f"Bearer {token}"}
    r = client.post(
        "/api/v1/patient/sessions",
        headers=h,
        json={
            "chief_complaint": "胸口疼冒冷汗",
            "device_id": DEVICE + "_em",
            "input_type": "TEXT",
            "gender": "男",
            "age": 55,
        },
    )
    d = r.json()
    assert d["code"] == 200, d
    sid = d["data"]["session_id"]

    deadline = time.time() + 90
    triage = None
    while time.time() < deadline:
        body = client.get(f"/api/v1/patient/sessions/{sid}/triage", headers=h).json()
        if body["code"] == 200:
            triage = body["data"]
            break
        time.sleep(3)
    if triage is None:
        pytest.skip("急救分诊未在限期内完成")
    print(f"\n  红旗主诉 route：{triage['route']}")
    assert triage["route"] == "EMERGENCY", f"红旗主诉应为 EMERGENCY，实际 {triage['route']}"
