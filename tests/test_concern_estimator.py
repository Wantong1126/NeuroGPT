# concern estimator tests
from core.types import CaseState, ExtractedSymptoms, Onset, Laterality, RedFlags
from modules.concern_estimator import estimate_concern
def test_stroke_high():
    s=ExtractedSymptoms(raw_input="嘴歪说话含糊一只手没力气",onset=Onset.SUDDEN,laterality=Laterality.ONE_SIDE,
        red_flags=RedFlags(weakness_one_side=True,facial_droop=True,slurred_speech=True,stroke_beFAST=True))
    r=estimate_concern(CaseState(symptoms_detected=s))
    assert r.concern_level.value=="high", f"got {r.concern_level.value}"
def test_unknown_unclear():
    s=ExtractedSymptoms(raw_input="老人最近有点不舒服。",onset=Onset.UNKNOWN)
    r=estimate_concern(CaseState(symptoms_detected=s))
    assert r.concern_level.value in ("unclear","low"), f"got {r.concern_level.value}"
def test_has_explanation():
    s=ExtractedSymptoms(raw_input="右边身子动不了",onset=Onset.SUDDEN,laterality=Laterality.ONE_SIDE,
        red_flags=RedFlags(weakness_one_side=True))
    r=estimate_concern(CaseState(symptoms_detected=s))
    assert r.explanation and r.why_not_normal_ageing
