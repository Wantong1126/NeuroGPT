# SPDX-License-Identifier: MIT
"""Deterministic multi-turn merging for an active elder observation."""
from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

ABDOMINAL_TERMS = (
    "肚子痛", "腹痛", "胃痛", "上腹痛", "下腹痛", "肚子胀", "胃胀", "恶心", "拉肚子",
)
NEW_TOPIC_TERMS = (
    "头晕", "头痛", "头疼", "手麻", "脚麻", "没力", "胸闷", "气短", "睡不着", "睡不好",
    "摔倒", "走路不稳", "心情不好", "孤单",
)
ASSOCIATED_SYMPTOMS = {
    "恶心": ("恶心", "想吐"),
    "呕吐": ("呕吐", "吐了", "一直吐"),
    "腹泻": ("腹泻", "拉肚子"),
    "发热": ("发热", "发烧"),
    "胸闷": ("胸闷",),
    "胸痛": ("胸痛", "胸口痛"),
    "气短": ("气短", "喘不上气"),
    "出汗": ("出汗", "冒汗", "冷汗"),
    "头晕": ("头晕",),
    "晕厥": ("晕倒", "昏倒", "晕厥"),
    "黑便/血便": ("黑便", "血便", "大便带血"),
    "血尿": ("血尿", "尿里有血"),
    "跌倒或外伤": ("跌倒", "摔倒", "外伤", "撞到"),
    "腹部变硬": ("肚子硬", "腹部变硬"),
    "无法进食或喝水": ("吃不下", "喝不下", "不能吃", "不能喝"),
}


def merge_observation_turn(
    previous_observation_state: dict,
    latest_user_input: str,
    previous_question: str | None,
    previous_pending_field: str | None,
) -> dict:
    """Merge a likely answer into the active observation without losing known fields."""
    merged = deepcopy(previous_observation_state or {})
    answer = (latest_user_input or "").strip()
    merged["is_answer_to_pending"] = False
    merged["topic_changed"] = False

    if not answer or not previous_pending_field or not previous_question:
        return merged
    if _changes_topic(answer, merged, previous_pending_field):
        merged["topic_changed"] = True
        return merged
    if not _looks_like_answer(answer, previous_pending_field):
        return merged

    value = _field_value(previous_pending_field, answer, merged)
    if value is None:
        return merged

    if previous_pending_field in {"associated_symptoms", "musculoskeletal_red_flags"}:
        merged.update(value)
        stored_value: Any = (
            value.get("associated_symptoms_reported")
            or value.get("associated_symptoms_denied")
            or answer
        )
    elif previous_pending_field == "severity_progression":
        merged.update(value)
        stored_value = answer
    else:
        merged[previous_pending_field] = value
        stored_value = value

    merged.setdefault("answer_history", []).append(
        {"field": previous_pending_field, "answer": answer}
    )
    merged.setdefault("answered_fields", {})[previous_pending_field] = stored_value
    merged["is_answer_to_pending"] = True
    return merged


def plan_next_observation_question(observation: dict) -> tuple[str | None, str | None, list[str]]:
    """Return the next missing structured field, never re-asking a known field."""
    if is_musculoskeletal_observation(observation):
        if not observation.get("body_location"):
            return (
                "是上背、下背、腰部，还是靠近肩膀的位置最痛？",
                "body_location",
                ["上背", "下背", "腰部", "靠近肩膀"],
            )
        if not observation.get("sensation_quality"):
            return (
                "更像是酸、胀、刺痛、抽着痛，还是僵硬？",
                "sensation_quality",
                ["酸", "胀", "刺痛", "抽着痛", "僵硬"],
            )
        if not observation.get("duration") and not observation.get("time_reference") and not observation.get("onset"):
            feeling = "这种酸痛" if "酸" in str(observation.get("sensation_quality") or "") else "这种不舒服"
            return (
                f"{feeling}是今天刚出现，还是已经有几天了？",
                "duration",
                ["今天刚出现", "几天了", "一周了"],
            )
        if not observation.get("musculoskeletal_red_flags_checked"):
            return (
                "今天有没有摔倒、扭到，或者疼痛是突然一下子很重、越来越重？",
                "musculoskeletal_red_flags",
                ["没有", "摔倒", "扭到", "突然很重", "越来越重"],
            )
        return None, None, []

    if observation.get("domain") != "abdominal_digestive":
        return None, None, []
    if not observation.get("body_location"):
        return (
            "肚子具体哪个位置最痛？是上腹、肚脐周围、下腹，还是左右某一边？",
            "body_location",
            ["上腹", "肚脐周围", "下腹", "左侧腹部", "右侧腹部"],
        )
    if not observation.get("sensation_quality"):
        return (
            "这种不舒服更像是痛、胀、绞着痛、烧心，还是恶心想吐？",
            "sensation_quality",
            ["痛", "胀", "绞着痛", "烧心", "恶心想吐"],
        )
    if not observation.get("duration"):
        return (
            "从早上开始到现在持续多久了？是一阵一阵，还是一直痛？",
            "duration",
            ["刚刚开始", "半小时", "一早上", "两天", "一阵一阵", "一直痛"],
        )
    if not observation.get("severity") and not observation.get("progression"):
        return (
            "现在比刚开始更痛，还是差不多？痛到影响走路、吃饭或说话了吗？",
            "severity_progression",
            ["更痛", "差不多", "减轻", "影响走路", "影响吃饭"],
        )
    if not observation.get("progression"):
        return "现在比刚开始更痛，还是差不多？", "severity_progression", ["更痛", "差不多", "减轻"]
    if not observation.get("severity"):
        return (
            "现在痛得还好、能忍，还是已经影响走路、吃饭或说话？",
            "severity_progression",
            ["还好", "能忍", "很痛", "影响走路", "影响吃饭"],
        )
    if not observation.get("associated_symptoms_checked"):
        return (
            "有没有发热、呕吐、腹泻、胸闷气短、出汗、头晕，或者大便发黑/带血？",
            "associated_symptoms",
            [],
        )
    return None, None, []


def is_abdominal_report(text: str) -> bool:
    value = text or ""
    return any(term in value for term in ABDOMINAL_TERMS) or (
        any(location in value for location in ("肚子", "腹", "胃"))
        and any(feeling in value for feeling in ("痛", "疼", "胀"))
    )


def is_musculoskeletal_observation(observation: dict) -> bool:
    location = str(observation.get("body_location") or "")
    problem = str(observation.get("specific_problem") or "")
    return observation.get("domain") == "musculoskeletal_pain" or (
        observation.get("domain") == "pain"
        and any(term in f"{location}{problem}" for term in ("肩", "背", "腰", "颈", "脖子", "腿", "关节", "肌肉"))
    )


def _changes_topic(answer: str, observation: dict, pending_field: str) -> bool:
    if pending_field in {"associated_symptoms", "musculoskeletal_red_flags"}:
        return False
    if observation.get("domain") == "abdominal_digestive":
        return any(term in answer for term in NEW_TOPIC_TERMS) or ("头" in answer and "晕" in answer)
    return False


def _looks_like_answer(answer: str, pending_field: str) -> bool:
    if len(answer) > 40 and pending_field != "associated_symptoms":
        return False
    patterns = {
        "body_location": ("上腹", "肚脐", "下腹", "左边", "右边", "左侧", "右侧", "胃", "肚子", "上背", "下背", "腰", "肩", "脖子", "颈"),
        "sensation_quality": ("痛", "疼", "胀", "酸", "刺", "抽", "僵", "烧心", "恶心", "想吐"),
        "duration": ("刚刚", "刚才", "刚出现", "今天", "小时", "分钟", "天", "早上", "一阵", "一直", "周"),
        "severity_progression": ("痛", "严重", "还好", "能忍", "加重", "更", "差不多", "减轻", "影响"),
        "associated_symptoms": tuple(term for terms in ASSOCIATED_SYMPTOMS.values() for term in terms) + ("没有", "都没有", "没什么"),
        "musculoskeletal_red_flags": ("没有", "没", "摔", "跌", "扭", "突然", "很重", "加重", "越来越"),
    }
    return any(term in answer for term in patterns.get(pending_field, ()))


def _field_value(field: str, answer: str, observation: dict) -> Any:
    if field == "body_location":
        for terms, normalized in (
            (("上背",), "上背"), (("下背",), "下背"), (("腰",), "腰部"),
            (("肩膀", "肩"), "肩膀"), (("脖子", "颈"), "肩颈"),
        ):
            if any(term in answer for term in terms):
                return normalized
        for term in ("上腹", "肚脐周围", "肚脐", "下腹"):
            if term in answer:
                return "肚脐周围" if term == "肚脐" else term
        if "左" in answer:
            return "左侧腹部" if observation.get("domain") == "abdominal_digestive" else "左侧"
        if "右" in answer:
            return "右侧腹部" if observation.get("domain") == "abdominal_digestive" else "右侧"
        return answer
    if field == "sensation_quality":
        qualities = []
        for normalized, terms in (
            ("绞着痛", ("绞着痛", "绞痛")),
            ("烧心", ("烧心",)),
            ("恶心想吐", ("恶心想吐", "恶心", "想吐")),
            ("痛", ("痛", "疼")),
            ("胀", ("胀",)),
        ):
            if any(term in answer for term in terms) and normalized not in qualities:
                qualities.append(normalized)
        if "绞着痛" in qualities and "痛" in qualities:
            qualities.remove("痛")
        return "、".join(qualities) or answer
    if field == "duration":
        return answer
    if field == "severity_progression":
        values = {}
        progression = ""
        if any(term in answer for term in ("更痛", "加重", "越来越")):
            progression = "加重"
        elif any(term in answer for term in ("差不多", "一样")):
            progression = "无明显变化"
        elif any(term in answer for term in ("减轻", "好一点")):
            progression = "减轻"
        if progression:
            values["progression"] = progression
        if any(term in answer for term in ("很痛", "特别痛", "非常痛", "剧烈", "严重", "还好", "能忍", "影响")):
            values["severity"] = answer
        return values or {"severity": answer}
    if field == "associated_symptoms":
        reported: list[str] = []
        denied: list[str] = []
        for clause in re.split(r"[，,。；;]|但是|不过|但", answer):
            names = [name for name, terms in ASSOCIATED_SYMPTOMS.items() if any(term in clause for term in terms)]
            target = denied if re.search(r"没有|没|无", clause) else reported
            for name in names:
                if name not in target:
                    target.append(name)
        if re.search(r"都没有|没什么", answer) and not reported:
            denied = list(ASSOCIATED_SYMPTOMS)
        denied = [name for name in denied if name not in reported]
        return {
            "associated_symptoms_reported": reported,
            "associated_symptoms_denied": denied,
            "associated_symptoms_checked": True,
        }
    if field == "musculoskeletal_red_flags":
        reported = []
        for normalized, terms in (
            ("摔倒", ("摔", "跌倒")),
            ("扭伤", ("扭",)),
            ("突然剧烈疼痛", ("突然很重", "突然一下子很重")),
            ("疼痛持续加重", ("加重", "越来越重")),
        ):
            if any(term in answer for term in terms):
                reported.append(normalized)
        result = {
            "musculoskeletal_red_flags_checked": True,
            "musculoskeletal_red_flags_reported": reported,
        }
        if "疼痛持续加重" in reported:
            result["progression"] = "加重"
        return result
    return None
