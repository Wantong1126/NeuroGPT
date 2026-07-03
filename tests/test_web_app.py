# SPDX-License-Identifier: MIT
from __future__ import annotations

from core import product_store
from core.session import delete_session, load_session
from core.types import CaseState
from ui.web import create_app



def test_product_routes_load(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(product_store, "PRODUCT_DATA_DIR", tmp_path / ".product_data")
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    routes = ["/", "/elder", "/staff", "/family", "/admin"]

    for route in routes:
        response = client.get(route)
        assert response.status_code == 200

    home_response = client.get("/")
    assert "请选择您的使用入口" in home_response.get_data(as_text=True)
    assert "中文" in home_response.get_data(as_text=True)
    assert "?lang=en" in home_response.get_data(as_text=True)


def test_chinese_is_the_default_product_language(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(product_store, "PRODUCT_DATA_DIR", tmp_path / ".product_data")
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    elder_page = client.get("/elder").get_data(as_text=True)

    assert '<html lang="zh-CN">' in elder_page
    assert "今天哪里不舒服，或者有什么想告诉护理员/家人？" in elder_page
    assert "可以直接说身体、睡眠、心情、行动、说话、记忆上的变化。" in elder_page
    assert "继续告诉我" in elder_page
    assert "提交" in elder_page
    assert "/elder?lang=en" in elder_page


def test_admin_page_shows_resident_event_and_workflow_summary(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(product_store, "PRODUCT_DATA_DIR", tmp_path / ".product_data")
    resident = product_store.get_demo_resident()
    pending_event = product_store.create_care_event_from_state(
        CaseState(session_id="admin-pending"),
        resident.resident_id,
        "昨晚没有睡好。",
    )
    confirmed_event = product_store.create_care_event_from_state(
        CaseState(session_id="admin-confirmed", caregiver_summary="今天需要继续关注睡眠。"),
        resident.resident_id,
        "今天走路比平时慢一些。",
    )
    product_store.update_event_staff_status(
        confirmed_event.event_id,
        "confirmed",
        staff_note="上午已到房间查看，老人精神平稳。",
    )

    app = create_app()
    app.config["TESTING"] = True
    page = app.test_client().get("/admin").get_data(as_text=True)

    assert pending_event.event_id not in page
    for expected in (
        "姓名", "王秀兰", "82岁", "性别", "女", "房间/床位", "203床",
        "示例养老院", "王女士", "关系", "女儿", "睡眠、记忆、行动变化",
        "老人原话", "今天走路比平时慢一些。", "创建时间", "当前处理状态", "已确认",
        "是否需要护理员确认", "否", "家属报告状态", "可生成",
        "护理员备注", "上午已到房间查看，老人精神平稳。",
        "今日记录", "待确认", "已处理", "家属报告可生成",
    ):
        assert expected in page

    assert '<strong>2</strong>' in page
    assert page.count('<strong>1</strong>') == 3
    for internal_field in ("pending_confirmation", "case_session_id", "action_level", "concern_level", "provider"):
        assert internal_field not in page



def test_flask_route_persists_case_state_across_requests(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(product_store, "PRODUCT_DATA_DIR", tmp_path / ".product_data")
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    client.get("/elder")
    with client.session_transaction() as flask_session:
        session_id = flask_session["neurogpt_session_id"]

    client.post("/elder/report", data={"user_input": "left arm weakness"})
    state_after_turn_one = load_session(session_id)
    assert state_after_turn_one is not None
    assert len(state_after_turn_one.conversation_history) >= 2

    response = client.post(
        "/elder/report",
        data={"user_input": "started suddenly this morning with slurred speech"},
    )
    state_after_turn_two = load_session(session_id)

    assert response.status_code == 200
    assert state_after_turn_two is not None
    assert state_after_turn_two.concern_level.value == "high"
    assert state_after_turn_two.action_level.value == "emergency_now"
    assert state_after_turn_two.symptoms_detected.red_flags.slurred_speech is True
    assert state_after_turn_two.symptoms_detected.red_flags.weakness_one_side is True

    resident = product_store.get_demo_resident()
    events = product_store.list_events_for_resident(resident.resident_id)
    assert len(events) == 2
    assert all(event.case_session_id == session_id for event in events)
    assert events[0].raw_report == "started suddenly this morning with slurred speech"

    delete_session(session_id)


def test_reset_replaces_current_elder_session(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(product_store, "PRODUCT_DATA_DIR", tmp_path / ".product_data")
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    client.get("/elder")
    with client.session_transaction() as flask_session:
        original_session_id = flask_session["neurogpt_session_id"]

    response = client.post("/reset")

    assert response.status_code == 302
    assert load_session(original_session_id) is None
