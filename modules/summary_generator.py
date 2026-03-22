# SPDX-License-Identifier: MIT
"""NeuroGPT v2 — Summary Generator (Step 6 output).

Generates caregiver-facing summary.
STUB: requires OpenAI API key to call LLM.
"""
from __future__ import annotations
from core.types import CaseState, CaregiverSummary

def generate_summary(state: CaseState) -> CaregiverSummary:
    """
    Generates a structured summary for the caregiver / adult child.

    Input: populated CaseState (symptoms + concern + action)
    Output: CaregiverSummary structured object

    This is a STUB — the LLM call requires API key.
    Until API key is available, returns a basic placeholder.
    """
    # TODO: Replace with LLM call via core/llm.py
    # Prompt: summarize symptoms, red flags, urgency, and next step for a caregiver.
    return CaregiverSummary(
        summary_paragraph=(
            f"患者报告了以下症状：{state.symptoms_detected.primary_symptom or '见上方对话'}。"
            f"评估担忧等级：{state.concern_level.value}，建议：{state.action_level.value}。"
        ),
        red_flags_summary=[
            flag for flag in [
                "单侧肢体无力" if state.symptoms_detected.red_flags.weakness_one_side else None,
                "面部歪斜" if state.symptoms_detected.red_flags.facial_droop else None,
                "言语不清" if state.symptoms_detected.red_flags.slurred_speech else None,
                "意识混乱" if state.symptoms_detected.red_flags.acute_confusion else None,
                "跌倒史" if state.falls_or_injury else None,
            ] if flag
        ],
        urgency=(
            "紧急——请立即联系120或前往急诊。"
            if state.concern_level.value == "high"
            else "请尽快安排门诊评估。"
        ),
        recommended_action="请陪同老人尽快就医，并向医生如实描述症状变化过程。",
        what_to_say_to_elder="医生想了解您最近的情况，我来帮您整理一下要说的话。",
        what_to_say_to_emergency_services="患者出现突发症状，包括[根据对话填入]，请准备神经科评估。",
        what_to_expect_at_er="急诊医生会进行神经系统检查，可能安排CT或MRI，以及血液检查。",
        questions_for_doctor=[
            "症状是什么时候开始的？",
            "之前有没有出现过类似情况？",
            "老人平时吃什么药？",
        ],
    )
