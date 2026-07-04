# SPDX-License-Identifier: MIT
from __future__ import annotations

import pytest

from modules.symptom_family_router import route_symptom_family
from pipeline.orchestrator import run_pipeline


@pytest.mark.parametrize(
    ("text", "expected_family"),
    [
        ("我肩膀和背很酸", "musculoskeletal_pain"),
        ("我头突然很痛", "headache"),
        ("我手麻", "numbness_or_weakness"),
        ("我有点头晕", "dizziness"),
        ("我睡不好", "sleep"),
        ("我不想麻烦孩子", "mood_loneliness"),
        ("最近总忘事", "memory_language"),
        ("这两天走路不稳", "gait_fall"),
        ("最近没胃口", "appetite_digestion"),
        ("现在有点胸闷气短", "chest_breathing"),
        ("感觉不太舒服", "general_unclear"),
    ],
)
def test_symptom_family_router(text: str, expected_family: str) -> None:
    assert route_symptom_family(text) == expected_family


def test_musculoskeletal_soreness_gets_relevant_follow_up() -> None:
    _state, output = run_pipeline("context-musculoskeletal", "我肩膀和背很酸")

    assert output.needs_follow_up_question is True
    assert "今天刚出现" in (output.follow_up_question or "")
    assert "已经有几天了" in (output.follow_up_question or "")
    assert "避免继续弯腰或提重物" in output.user_message
    assert "也要留意" not in output.user_message
    assert "酸痛" in output.user_message
    for irrelevant in ("麻木", "没力、动作不灵活", "感觉变迟钝"):
        assert irrelevant not in output.user_message


def test_hand_numbness_gets_focal_safety_follow_up() -> None:
    _state, output = run_pipeline("context-numbness", "我手麻")

    assert output.needs_follow_up_question is True
    question = output.follow_up_question or ""
    assert "哪只手" in question
    assert "突然出现" in question
    assert "说话不清" in question
    assert "脸歪" in question
    assert "同时没力" in question


def test_sleep_complaint_gets_sleep_follow_up() -> None:
    _state, output = run_pipeline("context-sleep", "我睡不好")

    assert "昨晚是睡不着" in (output.follow_up_question or "")
    assert "夜里起夜" in output.user_message
    assert "房间太亮、太吵" in output.user_message
    assert "睡不着" in output.user_message
    assert "半夜醒了很多次" in output.user_message


def test_sudden_head_pain_gets_headache_red_flag_follow_up() -> None:
    _state, output = run_pipeline("context-headache", "我头突然很痛")

    assert "突然一下子很严重" in (output.follow_up_question or "")
    assert "呕吐" in output.user_message
    assert "看不清" in output.user_message
    assert "说话不清" in output.user_message
    assert "手脚没力" in output.user_message


def test_context_follow_up_keeps_staff_summary_out_of_elder_message() -> None:
    _state, output = run_pipeline("context-summary-boundary", "我肩膀酸")

    assert output.caregiver_summary
    assert "给家属/医生" not in output.user_message
    assert "我听到您说肩膀酸。" in output.user_message
    assert "请您再告诉我：" in output.user_message
