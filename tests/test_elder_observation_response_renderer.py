# SPDX-License-Identifier: MIT
from __future__ import annotations

from modules.elder_observation_response_renderer import render_elder_observation_response
from pipeline.orchestrator import run_pipeline


def test_renderer_uses_accumulated_abdominal_fields_not_latest_answer() -> None:
    observation = {
        "raw_quote": "我早上起来突然肚子非常痛",
        "domain": "abdominal_digestive",
        "specific_problem": "腹部不适/腹痛",
        "body_location": "上腹",
        "sensation_quality": "痛、胀",
        "answer_history": [
            {"field": "body_location", "answer": "上腹"},
            {"field": "sensation_quality", "answer": "痛和胀"},
        ],
    }

    response = render_elder_observation_response(
        observation,
        "痛和胀",
        "从早上开始到现在持续多久了？是一阵一阵，还是一直痛？",
        "monitor",
        "merge",
    )

    assert "已记录：上腹痛和胀" in response
    assert any(reason in response for reason in ("胃部不适", "消化不良", "胀气"))
    assert "持续多久" in response
    assert "哪里痛和胀" not in response
    assert len(response) <= 420


def test_renderer_rejects_model_diagnosis_wording() -> None:
    response = render_elder_observation_response(
        {
            "raw_quote": "我上腹痛",
            "domain": "abdominal_digestive",
            "specific_problem": "腹痛",
            "body_location": "上腹",
            "possible_reasons_plain": "你可能是胃炎。",
        },
        "我上腹痛",
        "持续多久了？",
    )

    assert "你可能是胃炎" not in response
    assert "胃部不适" in response


def test_urgent_renderer_uses_deterministic_staff_sentence() -> None:
    response = render_elder_observation_response(
        {"raw_quote": "我突然右手没力", "domain": "sensory", "specific_problem": "右手没力"},
        "我突然右手没力",
        None,
        "emergency_now",
        "urgent",
    )

    assert "这个情况需要护理员尽快过来看一下。请马上叫护理员" in response


def test_pipeline_sleep_and_shoulder_responses_keep_specific_reasons() -> None:
    _state, sleep = run_pipeline("renderer-sleep", "昨晚没睡好")
    assert any(reason in sleep.user_message for reason in ("起夜", "疼痛", "心里惦记事", "环境"))
    assert "半夜醒了很多次" in (sleep.follow_up_question or "")

    _state, soreness = run_pipeline("renderer-soreness", "我肩膀和背很酸")
    assert any(reason in soreness.user_message for reason in ("低头久坐", "肩背受凉", "活动后肌肉酸痛"))
    assert any(action in soreness.user_message for action in ("避免继续弯腰", "提重物"))
    for forbidden in ("也要留意", "需要排查", "红旗", "风险因素", "建议结合实际情况"):
        assert forbidden not in soreness.user_message
    assert "今天刚出现" in (soreness.follow_up_question or "")


def test_back_pain_response_has_concrete_causes_mitigation_and_direct_question() -> None:
    _state, output = run_pipeline("renderer-back-pain", "我今天早上起来背很痛")

    concrete_causes = ("睡姿", "床垫", "枕头", "久坐", "弯腰", "提东西", "肌肉酸痛")
    assert sum(cause in output.user_message for cause in concrete_causes) >= 2
    assert "别硬撑" in output.user_message
    assert any(action in output.user_message for action in ("坐下休息", "保持舒服姿势"))
    assert any(item in (output.follow_up_question or "") for item in ("摔倒", "扭到", "突然一下子很重"))


def test_back_pain_duration_answer_merges_before_direct_safety_question() -> None:
    state, _first = run_pipeline("renderer-back-multiturn", "我背很痛")
    assert state.pending_field == "duration"

    state, second = run_pipeline("renderer-back-multiturn", "今天刚出现", state)

    assert "已记录：背痛今天刚出现" in second.user_message
    assert "别硬撑" in second.user_message
    assert any(item in (second.follow_up_question or "") for item in ("摔倒", "扭到", "越来越重"))


def test_abdominal_response_has_concrete_reasons_and_safe_mitigation() -> None:
    _state, output = run_pipeline("renderer-abdominal-action", "我早上起来突然肚子非常痛")

    assert any(reason in output.user_message for reason in ("胃肠不适", "饮食刺激", "受凉", "胀气"))
    assert "不要硬撑" in output.user_message
    assert "别自行吃药" in output.user_message
    assert "具体哪个位置最痛" in (output.follow_up_question or "")
