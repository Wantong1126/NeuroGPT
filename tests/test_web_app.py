# SPDX-License-Identifier: MIT
from __future__ import annotations

import threading
import time

from core import product_store
from core.session import delete_session, load_session
from core.types import CaseState
from ui import web
from ui.web import SAFE_ELDER_FALLBACK, create_app


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
    for label, description in (
        ("我是老人", "记录今天身体和生活上的变化"),
        ("我是护理员", "查看并确认老人提交的状态记录"),
        ("我是家属", "查看护理员确认后的老人近况"),
        ("我是机构管理者", "查看老人状态总览和处理进度"),
    ):
        assert label in home_response.get_data(as_text=True)
        assert description in home_response.get_data(as_text=True)


def test_chinese_is_the_default_product_language(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(product_store, "PRODUCT_DATA_DIR", tmp_path / ".product_data")
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    elder_page = client.get("/elder").get_data(as_text=True)

    assert '<html lang="zh-CN">' in elder_page
    assert "请先告诉我您是哪位" in elder_page
    assert "王秀兰" in elder_page
    assert "李国强" in elder_page
    assert "张明德" in elder_page
    assert "我不在列表中" in elder_page
    assert "房间/床位" not in elder_page
    assert "请填写您的姓名" not in elder_page
    assert "resident_name" not in elder_page
    assert "user_input" not in elder_page
    assert "/elder?lang=en" in elder_page

    _select_demo_resident(client)
    selected_page = client.get("/elder").get_data(as_text=True)
    assert "已选择：王秀兰" in selected_page
    assert "今天哪里不舒服，或者有什么想告诉护理员/家人？" in selected_page
    assert "请在这里说" in selected_page
    assert "告诉护理员" in selected_page
    assert "例如：今天头有点痛，昨晚没睡好。" in selected_page
    assert "user_input" in selected_page
    assert "继续告诉我" not in selected_page
    assert ">提交<" not in selected_page
    assert "请填写您的姓名" not in selected_page
    assert "resident_name" not in selected_page
    assert ">确认身份</button>" not in selected_page


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
        "状态记录", "老人", "床位", "老人原话", "今天走路比平时慢一些。", "具体情况", "处理状态", "已确认",
        "家属报告状态", "可生成",
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


def test_real_elder_route_renders_active_observation_responses(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(product_store, "PRODUCT_DATA_DIR", tmp_path / ".product_data")
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()
    client.get("/elder")
    _select_demo_resident(client)

    shoulder_html = client.post(
        "/elder/report",
        data={"user_input": "我肩膀和背很酸"},
    ).get_data(as_text=True)
    assert any(reason in shoulder_html for reason in ("睡姿", "久坐", "肌肉酸痛", "受凉"))
    for legacy_text in ("麻木、没力、动作不灵活", "感觉迟钝"):
        assert legacy_text not in shoulder_html

    client.post("/reset")
    client.get("/elder")
    first_html = client.post(
        "/elder/report",
        data={"user_input": "我早上起来突然肚子非常痛"},
    ).get_data(as_text=True)
    assert "肚子具体哪个位置最痛" in first_html
    assert "肚子突然明显疼痛" in first_html

    second_html = client.post("/elder/report", data={"user_input": "上腹"}).get_data(as_text=True)
    assert "上腹不舒服" in second_html
    assert "更像是痛、胀、绞着痛" in second_html

    third_html = client.post("/elder/report", data={"user_input": "痛和胀"}).get_data(as_text=True)
    assert "上腹痛和胀" in third_html
    assert "持续多久" in third_html
    assert "哪里痛和胀" not in third_html

    with client.session_transaction() as flask_session:
        saved = load_session(flask_session["neurogpt_session_id"])
    assert saved is not None
    assert saved.elder_display_response in third_html
    assert saved.observation_extraction["elder_display_response"] == saved.elder_display_response


def test_elder_report_api_returns_active_workflow_json(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(product_store, "PRODUCT_DATA_DIR", tmp_path / ".product_data")
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()
    client.get("/elder")
    _select_demo_resident(client)
    resident = product_store.get_demo_resident()

    response = client.post(
        "/api/elder/report",
        json={"resident_id": resident.resident_id, "message": "我早上起来突然肚子非常痛"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert "肚子具体哪个位置最痛" in payload["elder_response"]
    assert payload["pending_field"] == "body_location"
    assert payload["active_observation"]["domain"] == "abdominal_digestive"
    assert payload["event_id"]


def test_elder_report_api_times_out_to_local_pipeline(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(product_store, "PRODUCT_DATA_DIR", tmp_path / ".product_data")
    monkeypatch.setattr(web, "ELDER_PIPELINE_TIMEOUT_SECONDS", 0.01)
    real_run_pipeline = web.run_pipeline

    def slow_worker_only(*args, **kwargs):
        if threading.current_thread().name.startswith("elder-pipeline"):
            time.sleep(0.3)
        return real_run_pipeline(*args, **kwargs)

    monkeypatch.setattr(web, "run_pipeline", slow_worker_only)
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()
    client.get("/elder")
    _select_demo_resident(client)
    resident = product_store.get_demo_resident()

    started = time.monotonic()
    response = client.post(
        "/api/elder/report",
        json={"resident_id": resident.resident_id, "message": "昨晚没睡好"},
    )
    elapsed = time.monotonic() - started
    payload = response.get_json()

    assert elapsed < 0.25
    assert response.status_code == 200
    assert payload["ok"] is True
    assert "睡不好可能和" in payload["elder_response"]


def test_elder_page_contains_async_feedback_and_html_fallback(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(product_store, "PRODUCT_DATA_DIR", tmp_path / ".product_data")
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()
    client.get("/elder")
    _select_demo_resident(client)

    html = client.get("/elder").get_data(as_text=True)
    script = client.get("/static/elder.js").get_data(as_text=True)

    assert 'action="/elder/report"' in html
    assert 'data-api-url="/api/elder/report"' in html
    assert "正在帮您记录，请稍等……" in script
    assert "还在整理，请稍等。如果现在很不舒服，请先叫护理员。" in script
    assert "网络有点慢，如果现在很不舒服，请马上叫护理员。" in script
    assert "8000" in script
    assert "15000" in script


def test_elder_route_uses_safe_fallback_not_legacy_question(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(product_store, "PRODUCT_DATA_DIR", tmp_path / ".product_data")
    monkeypatch.setattr(web, "run_pipeline", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("failed")))
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()
    client.get("/elder")
    _select_demo_resident(client)

    html = client.post("/elder/report", data={"user_input": "我肩膀疼"}).get_data(as_text=True)

    assert SAFE_ELDER_FALLBACK in html
    assert "麻木、没力、动作不灵活" not in html

    resident = product_store.get_demo_resident()
    api_response = client.post(
        "/api/elder/report",
        json={"resident_id": resident.resident_id, "message": "我肩膀还是疼"},
    )
    payload = api_response.get_json()
    assert api_response.status_code == 200
    assert payload["ok"] is True
    assert payload["elder_response"] == SAFE_ELDER_FALLBACK


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
    assert "王秀兰" in response.get_data(as_text=True)
    assert "李国强" in response.get_data(as_text=True)
    assert "张明德" in response.get_data(as_text=True)
    assert "我不在列表中" in response.get_data(as_text=True)
    assert "请填写您的姓名" not in response.get_data(as_text=True)
    assert "user_input" not in response.get_data(as_text=True)
    assert state is not None
    assert state.conversation_history == []
    assert product_store.list_events_for_resident(product_store.get_demo_resident().resident_id) == []


def test_new_or_exact_match_resident_receives_report(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(product_store, "PRODUCT_DATA_DIR", tmp_path / ".product_data")
    existing = product_store.create_resident("李桂芳", room="205床")
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    name_step = client.post(
        "/elder/select",
        data={"resident_choice": "new"},
    )
    name_step_page = name_step.get_data(as_text=True)
    assert "请填写您的姓名" in name_step_page
    assert "例如：刘阿姨" in name_step_page
    assert "确认身份" in name_step_page
    assert "已选择：" not in name_step_page
    assert "user_input" not in name_step_page

    missing_name = client.post(
        "/elder/select",
        data={"resident_choice": "new", "identity_step": "name", "resident_name": ""},
    )
    assert "请填写您的姓名。" in missing_name.get_data(as_text=True)
    assert "请填写您的姓名" in missing_name.get_data(as_text=True)
    assert "例如：刘阿姨" in missing_name.get_data(as_text=True)
    assert "房间/床位" not in missing_name.get_data(as_text=True)

    response = client.post(
        "/elder/select",
        data={"resident_choice": "new", "resident_name": "李桂芳"},
    )
    assert response.status_code == 302
    with client.session_transaction() as flask_session:
        assert flask_session["neurogpt_resident_id"] == existing.resident_id

    identity_page = client.get("/elder").get_data(as_text=True)
    assert "好的，已记录您的姓名。接下来请告诉我哪里不舒服，或者有什么想告诉护理员/家人。" in identity_page

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


def test_detailed_observation_flows_to_staff_and_confirmed_family(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(product_store, "PRODUCT_DATA_DIR", tmp_path / ".product_data")
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()
    client.get("/elder")
    _select_demo_resident(client)
    client.post("/elder/report", data={"user_input": "昨晚没睡好"})

    resident = product_store.get_demo_resident()
    event = product_store.get_latest_event_for_resident(resident.resident_id)
    assert event is not None
    assert event.observation_extraction["observations"][0]["specific_problem"] == "昨晚睡眠质量不好"

    staff_page = client.get("/staff").get_data(as_text=True)
    for expected in ("老人原话", "昨晚没睡好", "系统理解到的具体情况", "昨晚睡眠质量不好", "还需要护理员确认", "护理员检查建议", "重点排查", "交接建议", "护理员备注", "确认完成", "继续关注"):
        assert expected in staff_page

    response = client.post(
        f"/staff/events/{event.event_id}/update",
        data={"staff_status": "confirmed", "staff_note": "已询问，老人是半夜醒了两次，白天精神尚可。"},
    )
    assert response.status_code == 302
    updated = product_store.get_latest_event_for_resident(resident.resident_id)
    assert updated is not None
    assert updated.staff_status.value == "confirmed"
    assert updated.staff_note == "已询问，老人是半夜醒了两次，白天精神尚可。"

    family_page = client.get("/family").get_data(as_text=True)
    for expected in (
        "老人原话", "昨晚没睡好", "护理员确认情况", "已询问，老人是半夜醒了两次，白天精神尚可。",
        "本次状态摘要", "老人反映昨晚睡眠不好，护理员将进一步了解原因和白天精神状态。",
        "后续安排", "已处理，将继续关注",
    ):
        assert expected in family_page
    assert "staff_checklist" not in family_page
    assert "是入睡困难、半夜醒来、早醒，还是睡得浅" not in family_page


def test_staff_page_shows_optional_concrete_observation_fields(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(product_store, "PRODUCT_DATA_DIR", tmp_path / ".product_data")
    resident = product_store.get_demo_resident()
    state = CaseState(
        session_id="staff-concrete",
        observation_extraction={
            "observations": [{
                "raw_quote": "我肩膀和背很酸",
                "specific_problem": "肩膀和背部酸痛",
                "body_location": "肩膀和背部",
                "sensation_quality": "酸",
                "time_reference": "今天早上",
                "triggers_or_context": ["活动后", "久坐"],
                "functional_impact": "抬手时不舒服",
                "emotional_context": "担心影响活动",
                "missing_information": ["持续多久"],
                "staff_checklist": ["查看活动范围"],
                "red_flag_checks_needed": ["胸闷", "气短"],
            }],
            "recommended_staff_handoff": "请查看肩背活动和伴随不适。",
            "recommended_family_summary_after_confirmation": "老人肩背酸痛，护理员已查看。",
        },
    )
    product_store.create_care_event_from_state(state, resident.resident_id, "我肩膀和背很酸")
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()
    client.get("/elder")
    _select_demo_resident(client)

    page = client.get("/staff").get_data(as_text=True)

    for expected in ("肩膀和背部", "感觉：酸", "时间：今天早上", "相关情境：活动后、久坐", "日常影响：抬手时不舒服", "情绪情况：担心影响活动"):
        assert expected in page


def test_institution_page_lists_events_across_residents(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(product_store, "PRODUCT_DATA_DIR", tmp_path / ".product_data")
    wang = product_store.get_demo_resident()
    zhou = product_store.create_resident("周阿姨", room="206床")
    for resident, report, problem in (
        (wang, "昨晚没睡好", "昨晚睡眠质量不好"),
        (zhou, "膝盖有点疼", "膝盖疼痛"),
    ):
        state = CaseState(
            session_id=f"admin-{resident.resident_id}",
            observation_extraction={"observations": [{"raw_quote": report, "specific_problem": problem}]},
        )
        product_store.create_care_event_from_state(state, resident.resident_id, report)

    app = create_app()
    app.config["TESTING"] = True
    page = app.test_client().get("/admin").get_data(as_text=True)

    for expected in ("王秀兰", "203床", "昨晚没睡好", "昨晚睡眠质量不好", "周阿姨", "206床", "膝盖有点疼", "膝盖疼痛", "护理员备注", "家属报告状态"):
        assert expected in page


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
        data={"resident_choice": "new", "resident_name": "赵玉兰"},
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
    assert product_store.get_resident(selected_resident_id).room == ""


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
