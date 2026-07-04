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
    assert len(response) <= 320


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

    assert "请马上叫护理员过来看一下。" in response


def test_pipeline_sleep_and_shoulder_responses_keep_specific_reasons() -> None:
    _state, sleep = run_pipeline("renderer-sleep", "昨晚没睡好")
    assert any(reason in sleep.user_message for reason in ("起夜", "疼痛", "心里惦记事", "环境"))
    assert "半夜醒了很多次" in (sleep.follow_up_question or "")

    _state, soreness = run_pipeline("renderer-soreness", "我肩膀和背很酸")
    assert any(reason in soreness.user_message for reason in ("睡姿", "久坐", "肌肉酸痛", "受凉"))
    assert "今天刚出现" in (soreness.follow_up_question or "")
