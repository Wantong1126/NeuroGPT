# NeuroGPT v2 — 参考文献与知识源

> 所有医学内容必须来自权威、公开、有据可查的来源。
> 添加新知识前，先在这里登记来源，审核通过后再加入知识库。

---

## Layer 1 — 急性危险症状与就医时机

| # | 主题 | 来源 | 用途 |
|---|------|------|------|
| L1-01 | 脑卒中 BE-FAST 识别标准 | NHS — Stroke: act fast (https://www.nhs.uk/conditions/stroke/symptoms/) | STROKE_BEFAST 规则 |
| L1-02 | 老年人癫痫发作红旗 | NHS — Epilepsy: symptoms (https://www.nhs.uk/conditions/epilepsy/symptoms/) | SEIZURE 规则 |
| L1-03 | 短暂性脑缺血发作 (TIA) 警告信号 | NHS — TIA (https://www.nhs.uk/conditions/transient-ischaemic-attack-tia/) | TIA_WARNING 规则 |
| L1-04 | 急性意识混乱/谵妄评估 | Cleveland Clinic — Altered Mental Status / Delirium (https://my.clevelandclinic.org/health/symptoms/6160-altered-mental-status) | DELIRIUM 规则 |
| L1-05 | 老年人跌倒风险与评估 | NHS — Falls in older people (https://www.nhs.uk/conditions/falls-in-older-people/) | FALLS_HIGH 规则 |
| L1-06 | 紧急头痛红旗（Subarachnoid hemorrhage 等） | NICE CG150 — Headaches in over 12s (https://www.nice.org.uk/guidance/cg150) + NHS | SUDDEN_SEVERE_HEADACHE 规则 |
| L1-07 | 神经系统转诊时机 | NICE NG127 — Suspected neurological conditions (https://www.nice.org.uk/guidance/ng127) | 规则优先级参考 |

---

## Layer 2 — 常见神经疾病基础说明（待实现）

| # | 主题 | 推荐来源 | 状态 |
|---|------|----------|------|
| L2-01 | 帕金森病 — 早期症状与就医指征 | Parkinson's Foundation — 10 Early Warning Signs (https://www.parkinson.org/understanding-parkinsons/symptoms/) | 待整理 |
| L2-02 | 阿尔茨海默病/痴呆 — 识别与照护 | NHS — Dementia Guide (https://www.nhs.uk/conditions/dementia/) | 待整理 |
| L2-03 | 脑卒中 — 类型、恢复与二级预防 | NHS — Stroke (https://www.nhs.uk/conditions/stroke/) + Stroke Association | 待整理 |
| L2-04 | 癫痫 — 发作类型与急救 | NHS — Epilepsy (https://www.nhs.uk/conditions/epilepsy/) | 待整理 |
| L2-05 | 周围神经病变 — 症状与原因 | NHS — Peripheral neuropathy (https://www.nhs.uk/conditions/peripheral-neuropathy/) | 待整理 |
| L2-06 | 脑肿瘤警告信号 | NHS — Brain tumour symptoms (https://www.nhs.uk/conditions/brain-tumours/) + Cancer Research UK | 待整理 |
| L2-07 | 不典型帕金森红旗（MSA, PSP, CBD） | PMC5961706 — Atypical parkinsonian syndromes (https://pmc.ncbi.nlm.nih.gov/articles/PMC5961706/) | 待整理 |

---

## Layer 3 — Care-seeking 与沟通指引（待实现）

| # | 主题 | 推荐来源 | 状态 |
|---|------|----------|------|
| L3-01 | 何时叫急救 / 何时看门诊 | NHS 111 / 999 guidelines + American Geriatrics Society | 待整理 |
| L3-02 | 如何向医生描述症状 | NHS — Getting the most from your GP appointment | 待整理 |
| L3-03 | 照护者行动清单（分层级） | NICE CG48 — Falls assessment + CG32 Support for carers | 待整理 |
| L3-04 | 老年人用药与神经系统关系 | NHS — Medicines information | 待整理 |

---

## 添加新来源的标准

1. **权威性**：来自国家卫健委、NICE、WHO、NHS、Mayo Clinic、Cleveland Clinic、Peer-reviewed journal
2. **公开可查**：无需付费订阅即可访问
3. **中文版本**：如来源是英文，需在代码注释中注明"中文译本需核实"
4. **登记在此文件**：先登记再使用，不允许黑户引用

---

## 引用格式（在代码中注明）

```python
# 参考来源:
# - NHS Stroke Symptoms: https://www.nhs.uk/conditions/stroke/symptoms/
# - NICE NG127 (Neurological referral): https://www.nice.org.uk/guidance/ng127
# - PMC5961706 — Atypical parkinsonian syndromes
```

---
*最后更新: 2026-03-22*
