# multi_turn merger
from core.types import CaseState, Onset, Laterality, Progression
def merge_turn(existing, new_input):
    existing.add_user_message(new_input)
    from modules.symptom_extractor import extract_symptoms
    ns = extract_symptoms(new_input)
    _m(existing.symptoms_detected, ns)
    return existing
def _m(dest, src):
    rf=dest.red_flags
    srf=src.red_flags
    for symptom_type in src.symptom_type:
        if symptom_type not in dest.symptom_type:
            dest.symptom_type.append(symptom_type)
    if srf.weakness_one_side: rf.weakness_one_side=True
    if srf.facial_droop: rf.facial_droop=True
    if srf.slurred_speech: rf.slurred_speech=True
    if srf.sudden_onset: rf.sudden_onset=True
    if srf.acute_confusion: rf.acute_confusion=True
    if srf.stroke_beFAST: rf.stroke_beFAST=True
    if srf.seizure: rf.seizure=True
    if srf.loss_of_consciousness: rf.loss_of_consciousness=True
    if srf.severe_headache: rf.severe_headache=True
    if srf.vision_loss: rf.vision_loss=True
    if srf.gait_imbalance: rf.gait_imbalance=True
    if srf.focal_numbness: rf.focal_numbness=True
    if srf.new_falls: rf.new_falls=True
    if srf.head_injury: rf.head_injury=True
    if srf.incontinence: rf.incontinence=True
    if dest.onset==Onset.UNKNOWN and src.onset!=Onset.UNKNOWN: dest.onset=src.onset
    if dest.laterality==Laterality.UNKNOWN and src.laterality!=Laterality.UNKNOWN: dest.laterality=src.laterality
    if dest.progression==Progression.UNKNOWN and src.progression!=Progression.UNKNOWN: dest.progression=src.progression
    if not dest.primary_symptom and src.primary_symptom: dest.primary_symptom=src.primary_symptom
    if not dest.memory_concern and src.memory_concern: dest.memory_concern=src.memory_concern
    if not dest.word_finding_difficulty and src.word_finding_difficulty: dest.word_finding_difficulty=src.word_finding_difficulty
    if not dest.disorientation and src.disorientation: dest.disorientation=src.disorientation
    if not dest.tremor_present and src.tremor_present: dest.tremor_present=src.tremor_present
    if not dest.falls_present and src.falls_present: dest.falls_present=src.falls_present
    if not dest.gait_difficulty and src.gait_difficulty: dest.gait_difficulty=src.gait_difficulty
    if not dest.duration_text and src.duration_text: dest.duration_text=src.duration_text
