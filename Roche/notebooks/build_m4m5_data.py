#!/usr/bin/env python3
"""生成 M4/M5 检验科数据：中英文档 + eval_lab3.json + eval_lab4.json。
程序化生成，避免手写多个文件。重跑覆盖。
"""
from __future__ import annotations
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
CN = DATA / "m4" / "cn_docs"
EN = DATA / "m4" / "en_docs"
CN.mkdir(parents=True, exist_ok=True)
EN.mkdir(parents=True, exist_ok=True)

# ---- 中文检验科项目/SOP 文档（含仪器/试剂批号，供 M5 Hybrid 精确匹配 & Metadata 过滤）----
CN_DOCS = {
"kalium_k": """# 血钾（K）检测说明
- 方法学：间接离子选择电极法（ISE）
- 参考区间：3.5–5.3 mmol/L
- 专业组：生化组；检测系统：cobas c702；试剂批号示例：LOT-K-20240612
- 干扰：标本溶血会导致钾假性升高；EDTA 污染亦致钾假性升高
- 危急值：详见《危急值管理》SOP
""",
"crea": """# 血肌酐（CREA）检测说明
- 方法学：酶法（部分实验室用苦味酸 Jaffe 法）
- 参考区间：男 59–104、女 45–84 μmol/L
- 专业组：生化组；检测系统：cobas c702；试剂批号示例：LOT-CREA-20240518
- 临床意义：评估肾小球滤过功能；危急值 CREA 少见、误测概率相对高，需先查质控与历史
""",
"hba1c": """# 糖化血红蛋白（HbA1c）检测说明
- 方法学：离子交换高效液相色谱（HPLC）
- 临床意义：反映近 8–12 周平均血糖水平；糖尿病控制目标一般 <7%
- 专业组：糖代谢；检测系统：Bio-Rad D-100；试剂批号示例：LOT-A1C-20240701
- 标准化：遵循 NGSP 标准化溯源
""",
"crp": """# C 反应蛋白（CRP）检测说明
- 方法学：乳胶增强免疫比浊法
- 临床意义：急性时相炎症标志；hsCRP 用于心血管风险评估
- 专业组：生化组；检测系统：cobas c702；试剂批号示例：LOT-CRP-20240603
""",
"glucose": """# 血糖（GLU）检测说明
- 方法学：己糖激酶法
- 采集：使用氟化钠-草酸钾抗凝管抑制糖酵解；住院清晨采血超 3 小时未离心，GLU 会假性降低
- 参考区间：空腹 3.9–6.1 mmol/L
- 专业组：生化组；检测系统：cobas c702；试剂批号示例：LOT-GLU-20240620
""",
"troponin": """# 肌钙蛋白（cTnI/cTnT）检测说明
- 方法学：化学发光免疫分析（CLIA）
- 临床意义：急性心肌梗死重要标志物，需结合临床症状与动态变化判读
- 专业组：免疫组；检测系统：cobas e601；试剂批号示例：LOT-TNI-20240509
""",
"tsh": """# 促甲状腺激素（TSH）检测说明
- 方法学：化学发光免疫分析（CLIA）
- 临床意义：甲状腺功能筛查首选指标
- 专业组：免疫组；检测系统：cobas e601；试剂批号示例：LOT-TSH-20240515
""",
"coag_pt": """# 凝血酶原时间（PT）/ INR 检测说明
- 方法学：凝固法（浊度/光学）
- 临床意义：监测华法林抗凝；采血量与抗凝剂比例要求严格，量不足显著影响结果
- 专业组：凝血组；检测系统：Sysmex CS-5100；试剂批号示例：LOT-PT-20240530
""",
}

# ---- 英文标准/方法/试剂文档 ----
EN_DOCS = {
"iso15189_competence": """# ISO 15189 — Personnel Competence
The laboratory shall ensure that all personnel are competent to perform their assigned
activities. The laboratory shall have a documented procedure for determining competence
requirements, authorizing personnel, and periodically assessing competence of staff who
perform examinations and issue results.
""",
"iso15189_qc": """# ISO 15189 — Internal Quality Control
The laboratory shall have internal quality control (IQC) procedures that verify the
attainment of the intended quality of results. QC materials shall be run at defined
frequency; out-of-control situations shall be detected, recorded and corrected before
releasing patient results.
""",
"loinc_intro": """# LOINC — Logical Observation Identifiers Names and Codes
LOINC is a universal code system for identifying laboratory and clinical observations.
Each LOINC code names a distinct test (analyte, property, timing, system, scale, method),
enabling interoperable exchange of laboratory results across systems.
""",
"reagent_k_ise": """# Potassium (K) Reagent — Indirect ISE
Potassium is measured by an indirect ion-selective electrode (ISE) method. Measuring
range approximately 1.5–10 mmol/L. Known interference: hemolysis causes falsely elevated
potassium because intracellular potassium is released from red blood cells.
""",
"method_clia": """# Chemiluminescence Immunoassay (CLIA) — Principle
CLIA uses an antigen-antibody reaction coupled with a chemiluminescent label. Light
emission is proportional (or inversely proportional) to analyte concentration. It offers
high sensitivity and wide dynamic range, and is widely used for cardiac markers such as
troponin and for hormones such as TSH.
""",
"reagent_hba1c_hplc": """# HbA1c Reagent — Ion-Exchange HPLC
Hemoglobin A1c is separated by cation-exchange high-performance liquid chromatography
(HPLC). Results are standardized and traceable to the NGSP/IFCC reference systems.
""",
"metrological_traceability": """# Metrological Traceability of Calibrators (ISO 17511)
Calibrators shall be traceable, where possible, to higher-order reference measurement
procedures or reference materials, establishing an unbroken chain of comparisons to SI or
to an international conventional reference, as described in ISO 17511.
""",
"reagent_crp_turb": """# CRP Reagent — Latex-Enhanced Immunoturbidimetry
C-reactive protein is measured by latex particle-enhanced immunoturbidimetric assay.
Anti-CRP antibodies coated on latex particles agglutinate in the presence of CRP; the
resulting turbidity is proportional to CRP concentration.
""",
}

for did, body in CN_DOCS.items():
    (CN / f"{did}.md").write_text(body, encoding="utf-8")
for did, body in EN_DOCS.items():
    (EN / f"{did}.md").write_text(body, encoding="utf-8")

# ---- eval_lab3.json：跨语言 / 同语言检索题（≥15）----
EVAL3 = [
    # 同语言 zh→zh
    ("L3-01", "血钾的参考区间是多少？", "zh", "zh", ["kalium_k"], "same_lingual"),
    ("L3-02", "糖化血红蛋白反映多长时间的平均血糖？", "zh", "zh", ["hba1c"], "same_lingual"),
    ("L3-03", "CRP 是什么标志物？", "zh", "zh", ["crp"], "same_lingual"),
    ("L3-04", "血糖检测为什么要用氟化钠抗凝管？", "zh", "zh", ["glucose"], "same_lingual"),
    # 同语言 en→en
    ("L3-05", "What does ISO 15189 require for internal quality control?", "en", "en", ["iso15189_qc"], "same_lingual"),
    ("L3-06", "What is the principle of chemiluminescence immunoassay?", "en", "en", ["method_clia"], "same_lingual"),
    ("L3-07", "Which standard governs metrological traceability of calibrators?", "en", "en", ["metrological_traceability"], "same_lingual"),
    ("L3-08", "What assay is used to measure CRP?", "en", "en", ["reagent_crp_turb"], "same_lingual"),
    # 跨语言 zh→en
    ("L3-09", "ISO 15189 对检验人员的能力有什么要求？", "zh", "en", ["iso15189_competence"], "cross_lingual"),
    ("L3-10", "肌钙蛋白检测用的化学发光免疫法原理是什么？", "zh", "en", ["method_clia"], "cross_lingual"),
    ("L3-11", "钾的间接 ISE 法主要干扰因素是什么？", "zh", "en", ["reagent_k_ise"], "cross_lingual"),
    ("L3-12", "LOINC 是什么，用来做什么？", "zh", "en", ["loinc_intro"], "cross_lingual"),
    ("L3-13", "校准品的计量溯源应追溯到什么？", "zh", "en", ["metrological_traceability"], "cross_lingual"),
    ("L3-14", "糖化血红蛋白 HPLC 方法遵循什么标准化体系？", "zh", "en", ["reagent_hba1c_hplc"], "cross_lingual"),
    # 跨语言 en→zh
    ("L3-15", "What is the reference range for serum potassium?", "en", "zh", ["kalium_k"], "cross_lingual"),
    ("L3-16", "Which anticoagulant tube is used for glucose to inhibit glycolysis?", "en", "zh", ["glucose"], "cross_lingual"),
    ("L3-17", "What method is used to measure creatinine?", "en", "zh", ["crea"], "cross_lingual"),
    ("L3-18", "PT/INR is used to monitor which anticoagulant drug?", "en", "zh", ["coag_pt"], "cross_lingual"),
]
eval3 = [{"qid": q, "question": t, "lang_q": lq, "lang_doc": ld,
          "ground_truth_doc_ids": gt, "category": cat}
         for (q, t, lq, ld, gt, cat) in EVAL3]
(DATA / "eval_lab3.json").write_text(
    json.dumps(eval3, ensure_ascii=False, indent=2), encoding="utf-8")

# ---- eval_lab4.json：检索三板斧评估（含精确匹配 / Metadata 过滤子集）----
# filter 字段用于阶段3（Metadata 过滤）；type 标注该题考察哪一板斧。
EVAL4 = [
    # 精确匹配（Hybrid 受益：项目代码/试剂批号/仪器型号，纯向量会稀释）
    ("L4-01", "试剂批号 LOT-K-20240612 对应哪个检测项目？", ["kalium_k"], "exact", None),
    ("L4-02", "cobas e601 上化学发光测的心肌标志物是什么？", ["troponin"], "exact", None),
    ("L4-03", "LOT-A1C-20240701 是哪个项目的试剂批号？", ["hba1c"], "exact", None),
    ("L4-04", "Sysmex CS-5100 检测什么项目？", ["coag_pt"], "exact", None),
    # Metadata 过滤（按专业组）
    ("L4-05", "免疫组用化学发光测哪些项目？", ["troponin", "tsh"], "metadata", {"专业组": "免疫组"}),
    ("L4-06", "生化组测血糖用什么方法？", ["glucose"], "metadata", {"专业组": "生化组"}),
    ("L4-07", "凝血组的 PT 项目采血有什么要求？", ["coag_pt"], "metadata", {"专业组": "凝血组"}),
    # 语义检索（一般题）
    ("L4-08", "肌酐用什么方法学检测？", ["crea"], "semantic", None),
    ("L4-09", "糖化血红蛋白反映多久的血糖？", ["hba1c"], "semantic", None),
    ("L4-10", "TSH 是筛查什么功能的指标？", ["tsh"], "semantic", None),
    ("L4-11", "血钾溶血为什么会假性升高？", ["kalium_k", "reagent_k_ise"], "semantic", None),
    ("L4-12", "CRP 采用什么原理的免疫比浊？", ["crp", "reagent_crp_turb"], "semantic", None),
    # 似相关而非相关（Rerank 受益）
    ("L4-13", "急性心肌梗死看哪个标志物，怎么判读？", ["troponin"], "rerank", None),
    ("L4-14", "空腹血糖的参考区间是多少？", ["glucose"], "rerank", None),
    ("L4-15", "华法林抗凝监测看哪个凝血指标？", ["coag_pt"], "rerank", None),
    ("L4-16", "计量溯源要追溯到什么参考体系？", ["metrological_traceability"], "rerank", None),
]
eval4 = [{"qid": q, "question": t, "ground_truth_doc_ids": gt,
          "type": ty, "filter": flt}
         for (q, t, gt, ty, flt) in EVAL4]
(DATA / "eval_lab4.json").write_text(
    json.dumps(eval4, ensure_ascii=False, indent=2), encoding="utf-8")

# ---- 文档 metadata 映射（M5 用；doc_id -> 标签）----
DOC_META = {
    "kalium_k":  {"专业组": "生化组", "仪器": "cobas c702", "类别": "电解质", "版本": "v2.1"},
    "crea":      {"专业组": "生化组", "仪器": "cobas c702", "类别": "肾功能", "版本": "v2.1"},
    "hba1c":     {"专业组": "糖代谢", "仪器": "Bio-Rad D-100", "类别": "糖代谢", "版本": "v1.3"},
    "crp":       {"专业组": "生化组", "仪器": "cobas c702", "类别": "炎症", "版本": "v2.0"},
    "glucose":   {"专业组": "生化组", "仪器": "cobas c702", "类别": "糖代谢", "版本": "v2.1"},
    "troponin":  {"专业组": "免疫组", "仪器": "cobas e601", "类别": "心肌标志", "版本": "v1.5"},
    "tsh":       {"专业组": "免疫组", "仪器": "cobas e601", "类别": "甲状腺", "版本": "v1.5"},
    "coag_pt":   {"专业组": "凝血组", "仪器": "Sysmex CS-5100", "类别": "凝血", "版本": "v1.2"},
}
(DATA / "m4" / "doc_meta.json").write_text(
    json.dumps(DOC_META, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"✅ CN docs={len(CN_DOCS)}  EN docs={len(EN_DOCS)}  eval3={len(eval3)}  eval4={len(eval4)}")
