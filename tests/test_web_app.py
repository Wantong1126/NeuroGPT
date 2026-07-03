# SPDX-License-Identifier: MIT
from __future__ import annotations

from core import product_store
from core.session import delete_session, load_session
from core.types import CaseState
from ui.web import create_app


def _select_demo_resident(client) -> None:
    resident = product_store.get_demo_resident()
    response = client.post("/elder/select", data={"resident_choice": resident.resident_id})
    assert response.status_code == 302



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
    _select_demo_resident(client)
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


def test_report_waits_for_resident_identity_before_pipeline(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(product_store, "PRODUCT_DATA_DIR", tmp_path / ".product_data")
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()
    client.get("/elder")
    with client.session_transaction() as flask_session:
        session_id = flask_session["neurogpt_session_id"]

    response = client.post("/elder/report", data={"user_input": "我今天头晕。"})
    state = load_session(session_id)

    assert "请先告诉我您是哪位，这样护理员才能知道要去看谁。" in response.get_data(as_text=True)
    assert "我今天头晕。" in response.get_data(as_text=True)
    assert '<div class="new-resident-fields">' in response.get_data(as_text=True)
    assert state is not None
    assert state.conversation_history == []
    assert product_store.list_events_for_resident(product_store.get_demo_resident().resident_id) == []


def test_new_or_exact_match_resident_receives_report(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(product_store, "PRODUCT_DATA_DIR", tmp_path / ".product_data")
    existing = product_store.create_resident("李桂芳", room="205床")
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    missing_name = client.post(
        "/elder/select",
        data={"resident_choice": "new", "resident_name": "", "resident_room": "206床"},
    )
    assert "请告诉我您的姓名。" in missing_name.get_data(as_text=True)

    response = client.post(
        "/elder/select",
        data={"resident_choice": "new", "resident_name": "李桂芳", "resident_room": "999床"},
    )
    assert response.status_code == 302
    with client.session_transaction() as flask_session:
        assert flask_session["neurogpt_resident_id"] == existing.resident_id

    client.post("/elder/report", data={"user_input": "我昨晚没有睡好。"})
    events = product_store.list_events_for_resident(existing.resident_id)
    assert len(events) == 1
    assert events[0].raw_report == "我昨晚没有睡好。"
    assert product_store.find_resident_by_exact_name("李桂芳").room == "205床"

    assert "李桂芳" in client.get("/staff").get_data(as_text=True)
    assert "李桂芳" in client.get("/family").get_data(as_text=True)
    admin_page = client.get("/admin").get_data(as_text=True)
    assert "李桂芳" in admin_page
    assert "我昨晚没有睡好。" in admin_page


def test_switching_resident_starts_a_separate_case_session(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(product_store, "PRODUCT_DATA_DIR", tmp_path / ".product_data")
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    client.get("/elder")
    _select_demo_resident(client)
    client.get("/elder")
    with client.session_transaction() as flask_session:
        first_session_id = flask_session["neurogpt_session_id"]
    client.post("/elder/report", data={"user_input": "我今天左手没力。"})

    client.post(
        "/elder/select",
        data={"resident_choice": "new", "resident_name": "赵玉兰", "resident_room": "208床"},
    )
    assert load_session(first_session_id) is None

    client.get("/elder")
    with client.session_transaction() as flask_session:
        second_session_id = flask_session["neurogpt_session_id"]
        selected_resident_id = flask_session["neurogpt_resident_id"]
    second_state = load_session(second_session_id)

    assert second_session_id != first_session_id
    assert second_state is not None
    assert second_state.conversation_history == []
    assert product_store.get_resident(selected_resident_id).name == "赵玉兰"


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
