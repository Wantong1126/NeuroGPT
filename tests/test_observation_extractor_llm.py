# SPDX-License-Identifier: MIT
from __future__ import annotations

import pytest

from modules import observation_extractor_llm as extractor
from pipeline.orchestrator import run_pipeline


@pytest.mark.parametrize(
    ("text", "domain", "specific_text", "question_text"),
    [
        ("昨晚没睡好", "sleep", "昨晚睡眠质量不好", "半夜醒了很多次"),
        ("我肩膀和背很酸", "pain", "肩膀和背部酸痛", "已经有几天了"),
        ("我手麻", "sensory", "手部发麻", "是哪只手麻"),
        ("我不想麻烦孩子", "mood", "不想麻烦家人", "您是哪里不舒服"),
    ],
)
def test_heuristic_fallback_extracts_concrete_observation(
    monkeypatch,
    text: str,
    domain: str,
    specific_text: str,
    question_text: str,
) -> None:
    monkeypatch.setattr(extractor, "get_provider", lambda _module: "heuristic")

    result = extractor.extract_observation_details(text)
    observation = result.observations[0]

    assert observation.raw_quote == text
    assert observation.domain == domain
    assert specific_text in observation.specific_problem
    assert question_text in observation.next_best_question
    assert observation.missing_information
    assert observation.staff_checklist
    assert observation.family_safe_summary
    assert observation.confidence == "fallback"


def test_ds_extraction_uses_openai_compatible_config_and_schema(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(extractor, "get_provider", lambda _module: "openai_compatible")
    monkeypatch.setattr(extractor, "get_provider_model", lambda _module: "deepseek-v4-pro")
    monkeypatch.setattr(extractor, "get_provider_base_url", lambda _module: "https://api.deepseek.com/v1")

    def fake_call(prompt, system_prompt, schema, model=None, base_url=None):
        calls.append((prompt, system_prompt, schema, model, base_url))
        return {
            "observations": [{
                "raw_quote": "昨晚没睡好",
                "domain": "sleep",
                "specific_problem": "昨晚睡眠质量不好",
                "time_reference": "昨晚",
                "missing_information": ["具体是哪种睡不好"],
                "next_best_question": "昨晚是睡不着，还是半夜醒了很多次？",
                "staff_checklist": ["了解睡眠中断原因"],
                "family_safe_summary": "老人昨晚睡眠不好。",
                "red_flag_checks_needed": [],
                "confidence": "high",
            }],
            "overall_plain_summary": "昨晚睡眠质量不好",
            "recommended_elder_response": "这种情况可能有多种常见原因，也可能只是短暂不适。",
            "recommended_staff_handoff": "老人昨晚睡眠不好，请了解具体原因。",
            "recommended_family_summary_after_confirmation": "老人昨晚睡眠欠佳，护理员已关注。",
        }

    monkeypatch.setattr(extractor, "call_structured", fake_call)
    result = extractor.extract_observation_details("昨晚没睡好")

    assert result.observations[0].confidence == "high"
    assert calls[0][3] == "deepseek-v4-pro"
    assert calls[0][4] == "https://api.deepseek.com/v1"
    assert "Do not collapse" in calls[0][1]
    assert "next_best_question" in calls[0][2]
    assert "昨晚没睡好" in result.recommended_elder_response
    assert "起夜、身体不舒服、心里惦记事" in result.recommended_elder_response
    assert "多种常见原因" not in result.recommended_elder_response


def test_ds_failure_returns_fallback_confidence(monkeypatch) -> None:
    monkeypatch.setattr(extractor, "get_provider", lambda _module: "openai_compatible")
    monkeypatch.setattr(extractor, "call_structured", lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError()))

    result = extractor.extract_observation_details("昨晚没睡好")

    assert result.observations[0].confidence == "fallback"


def test_sleep_pipeline_uses_specific_observation_question() -> None:
    state, output = run_pipeline("detail-sleep", "昨晚没睡好")

    assert state.observation_extraction["observations"][0]["domain"] == "sleep"
    assert "半夜醒了很多次" in (output.follow_up_question or "")
    assert "起夜、身体不舒服、心里惦记事" in output.user_message
    assert "今天刚出现" not in output.user_message


def test_pain_pipeline_does_not_use_generic_neuro_question() -> None:
    _state, output = run_pipeline("detail-pain", "我肩膀和背很酸")

    assert "已经有几天了" in (output.follow_up_question or "")
    assert "睡姿、久坐、活动后肌肉酸痛或受凉" in output.user_message
    for phrase in ("麻木", "动作不灵活", "感觉变迟钝"):
        assert phrase not in output.user_message


def test_hand_numbness_pipeline_asks_specific_safety_question() -> None:
    _state, output = run_pipeline("detail-hand", "我手麻")

    question = output.follow_up_question or ""
    for phrase in ("哪只手", "突然出现", "没力", "说话不清", "脸歪"):
        assert phrase in question


def test_mood_report_preserves_intent_and_emotional_context() -> None:
    state, output = run_pipeline("detail-mood", "我不想麻烦孩子")
    observation = state.observation_extraction["observations"][0]

    assert observation["elder_intent"] == "不想麻烦孩子"
    assert observation["emotional_context"] == "我不想麻烦孩子"
    assert "您是哪里不舒服" in (output.follow_up_question or "")
    assert "护理员知道后才能更好照顾您" in output.user_message


@pytest.mark.parametrize(
    ("report", "expected"),
    [
        ("昨晚没睡好", "睡不好可能和起夜、身体不舒服"),
        ("我肩膀和背很酸", "睡姿、久坐、活动后肌肉酸痛"),
        ("我不想麻烦孩子", "护理员知道后才能更好照顾您"),
        ("我手麻", "手麻有时和姿势压迫"),
    ],
)
def test_elder_response_mentions_issue_and_specific_explanation(report: str, expected: str) -> None:
    _state, output = run_pipeline(f"detail-render-{report}", report)

    assert report.removeprefix("我") in output.user_message
    assert expected in output.user_message
    assert "多种常见原因" not in output.user_message
    assert len(output.user_message) <= 220


def test_deterministic_emergency_action_overrides_observation_question() -> None:
    _state, output = run_pipeline("detail-emergency", "我今天突然右手没力，嘴歪")

    assert output.action_level == "emergency_now"
    assert output.needs_follow_up_question is False
    assert "请马上叫护理员过来看一下。" in output.user_message


def test_same_day_action_also_tells_elder_to_call_staff() -> None:
    _state, output = run_pipeline("detail-same-day", "老人这几年说话越来越慢")

    assert output.action_level == "same_day_review"
    assert "请马上叫护理员过来看一下。" in output.user_message
