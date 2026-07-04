# SPDX-License-Identifier: MIT
from __future__ import annotations

from core.types import ActionLevel, CaseState
from modules import elder_explanation_generator as generator
from modules.question_planner import plan_follow_up_question
from modules.symptom_family_router import route_symptom_family
from pipeline.orchestrator import run_pipeline


def _enable_fake_ds(monkeypatch, response_or_error):
    monkeypatch.setattr(generator, "get_provider", lambda _module: "openai_compatible")
    monkeypatch.setattr(generator, "get_provider_model", lambda _module: "deepseek-v4-pro")
    monkeypatch.setattr(generator, "get_provider_base_url", lambda _module: "https://api.deepseek.com/v1")

    calls = []

    def fake_call(prompt, system_prompt, schema, model=None, base_url=None):
        calls.append(
            {
                "prompt": prompt,
                "system_prompt": system_prompt,
                "schema": schema,
                "model": model,
                "base_url": base_url,
            }
        )
        if isinstance(response_or_error, Exception):
            raise response_or_error
        return response_or_error

    monkeypatch.setattr(generator, "call_structured", fake_call)
    return calls


def test_ds_structured_explanation_uses_config_and_preserves_planned_question(monkeypatch) -> None:
    planned_question = plan_follow_up_question("musculoskeletal_pain")
    calls = _enable_fake_ds(
        monkeypatch,
        {
            "acknowledgement": "我听到您说肩膀和背很酸。",
            "possible_reasons_plain": "这可能和姿势、活动后肌肉酸痛或休息不好有关。",
            "next_question": "模型试图换一个问题？",
            "when_to_call_staff": "如果疼痛加重，请马上叫护理员。",
        },
    )
    state = CaseState(raw_user_input="我肩膀和背很酸")

    explanation = generator.generate_elder_explanation(
        state,
        "musculoskeletal_pain",
        "monitor",
        planned_question,
    )

    assert explanation.possible_reasons_plain == "这可能和姿势、活动后肌肉酸痛或休息不好有关。"
    assert explanation.next_question == planned_question
    assert calls[0]["model"] == "deepseek-v4-pro"
    assert calls[0]["base_url"] == "https://api.deepseek.com/v1"
    assert '"deterministic_action_level": "monitor"' in calls[0]["prompt"]
    assert '"known_red_flags": []' in calls[0]["prompt"]


def test_urgent_ds_wording_cannot_remove_staff_instruction(monkeypatch) -> None:
    _enable_fake_ds(
        monkeypatch,
        {
            "acknowledgement": "我听到您说突然一边手脚没力。",
            "possible_reasons_plain": "需要马上请人查看，先不要判断原因。",
            "next_question": "",
            "when_to_call_staff": "请稍后留意。",
        },
    )
    state = CaseState(raw_user_input="突然一边手脚没力", action_level=ActionLevel.EMERGENCY_NOW)

    explanation = generator.generate_elder_explanation(
        state,
        "numbness_or_weakness",
        "emergency_now",
        None,
    )

    assert explanation.when_to_call_staff == "请马上叫护理员过来看一下。"


def test_ds_failure_falls_back_to_short_context_template(monkeypatch) -> None:
    _enable_fake_ds(monkeypatch, TimeoutError("provider unavailable"))
    state = CaseState(raw_user_input="我肩膀和背很酸")
    question = plan_follow_up_question("musculoskeletal_pain")

    explanation = generator.generate_elder_explanation(
        state,
        "musculoskeletal_pain",
        "monitor",
        question,
    )
    rendered = generator.format_elder_explanation(explanation)

    assert "姿势、活动后肌肉酸痛、受凉或休息不好" in rendered
    assert question in rendered
    assert "provider unavailable" not in rendered
    assert len(rendered) <= 180


def test_diagnostic_ds_reason_is_rejected(monkeypatch) -> None:
    _enable_fake_ds(
        monkeypatch,
        {
            "acknowledgement": "我听到您说手有点麻。",
            "possible_reasons_plain": "这可能就是脑梗。",
            "next_question": "",
            "when_to_call_staff": "可以继续等。",
        },
    )
    state = CaseState(raw_user_input="我手麻")

    explanation = generator.generate_elder_explanation(
        state,
        "numbness_or_weakness",
        "monitor",
        plan_follow_up_question("numbness_or_weakness"),
    )

    assert "脑梗" not in generator.format_elder_explanation(explanation)
    assert "姿势压迫" in explanation.possible_reasons_plain


def test_pipeline_uses_detailed_observation_without_changing_action() -> None:
    _state, output = run_pipeline("elder-explanation-integration", "我睡不好")

    assert output.action_level == "monitor"
    assert "睡不着，还是半夜醒了很多次" in output.user_message
    assert "起夜、身体不舒服、心里惦记事" in output.user_message
    assert "给家属/医生" not in output.user_message


def test_sample_fallbacks_cover_requested_elder_scenarios(monkeypatch) -> None:
    monkeypatch.setattr(generator, "get_provider", lambda _module: "heuristic")
    cases = (
        "我肩膀和背很酸",
        "我头突然很痛",
        "我手麻",
        "我睡不好",
    )
    for text in cases:
        family = route_symptom_family(text)
        question = plan_follow_up_question(family)
        explanation = generator.generate_elder_explanation(
            CaseState(raw_user_input=text),
            family,
            "monitor",
            question,
        )
        rendered = generator.format_elder_explanation(explanation)
        assert text in rendered
        assert question in rendered
        assert "给家属/医生" not in rendered
