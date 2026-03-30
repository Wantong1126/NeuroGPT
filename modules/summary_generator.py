# SPDX-License-Identifier: MIT
"""NeuroGPT v2 - Summary Generator."""
from __future__ import annotations

from core.types import CaseState, CaregiverSummary



def generate_summary(state: CaseState) -> CaregiverSummary:
    """Return a caregiver-facing placeholder summary until LLM mode is enabled."""
    rf = state.symptoms_detected.red_flags
    red_flags = [
        label
        for present, label in [
            (rf.weakness_one_side, "单侧无力"),
            (rf.facial_droop, "面部歪斜"),
            (rf.slurred_speech, "言语不清"),
            (rf.acute_confusion, "急性意识/认知改变"),
            (rf.seizure, "抽搐/疑似癫痫发作"),
            (rf.loss_of_consciousness, "意识丧失"),
            (rf.severe_headache, "剧烈头痛"),
        ]
        if present
    ]

    urgency = "请立即就医或呼叫急救。" if state.concern_level.value == "high" else "请尽快安排门诊或急诊评估。"

    return CaregiverSummary(
        summary_paragraph=(
            f"当前对话提取到的主要症状为：{state.symptoms_detected.primary_symptom or state.raw_user_input}。"
            f"系统评估关注等级为 {state.concern_level.value}，建议行动为 {state.action_level.value}。"
        ),
        red_flags_summary=red_flags,
        urgency=urgency,
        recommended_action="陪同老人尽快就医，并向医生按时间线描述症状变化。",
        what_to_say_to_elder="这些症状值得认真评估，我陪你一起去看医生。",
        what_to_say_to_emergency_services="患者出现新的神经系统症状，请评估是否需要急诊处理。",
        what_to_expect_at_er="医生可能会问起病时间、症状变化，并安排神经系统检查或影像检查。",
        questions_for_doctor=[
            "症状最早从什么时候开始？",
            "是否像脑卒中、癫痫或其他神经系统问题？",
            "下一步需要做哪些检查？",
        ],
    )
