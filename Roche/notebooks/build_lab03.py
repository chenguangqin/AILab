#!/usr/bin/env python3
"""生成 lab_03_embedding_multilingual.ipynb（开源栈 · 检验科 · 中英术语混杂）。"""
from __future__ import annotations
import nbformat as nbf
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

md, code = new_markdown_cell, new_code_cell
cells = []

cells.append(md("""# Lab 3 · Embedding 选型 + 中英医学术语混杂

|     |     |
| --- | --- |
| **模块** | M4 · Embedding 选型 |
| **时长** | 50 min |
| **形态** | 完整动手 |
| **关键产出** | Titan vs bge-m3 的跨语言 Recall@5 对比表 + 选型决策框架 |

**场景**：检验科文档天生中英混杂——中文 SOP/项目名，配英文标准原文（ISO 15189）、LOINC、方法学与试剂英文名（CLIA、HPLC、ISE…）。用户中文问，答案常在英文条款里；反之亦然。本 Lab 对比两种嵌入模型在这种混杂下的检索表现。

**要对比的两条路**：
- **Titan Text Embeddings v2**（`provider="bedrock"`，培训环境默认）
- **bge-m3**（`provider="local"`，本地开源、多语言、中文强）——**这就是罗氏产品本地部署时的嵌入**（Titan 不能进内网）。"""))

cells.append(md("""## 1. 环境准备
> - Bedrock 已开通 Titan Text Embeddings v2
> - 本地路径依赖：`pip install langchain-huggingface sentence-transformers`（bge-m3 首次调用会下载权重，稍慢）
> - 数据：先跑过 `python3 build_m4m5_data.py` 生成 `data/m4/` 与 `data/eval_lab3.json`"""))

cells.append(code("""import json
from pathlib import Path
import pandas as pd

from common import docs_from_dir, build_vectorstore, retrieve, load_eval_set, DATA_DIR

# 加载中英文档；doc_id 用文件名 stem，用于和评估集 ground_truth 对齐
docs = docs_from_dir("m4/cn_docs") + docs_from_dir("m4/en_docs")
for d in docs:
    d.metadata["doc_id"] = Path(d.metadata["source"]).stem
print(f"文档总数：{len(docs)}（中文 {sum(1 for d in docs if 'cn_docs' in d.metadata['source'])} + 英文 {sum(1 for d in docs if 'en_docs' in d.metadata['source'])}）")"""))

cells.append(md("""## 2. 步骤 1 — 用两种嵌入各建一套索引

同一批文档，分别用 Titan 和 bge-m3 建向量库。注意维度都是 1024，切换不影响索引结构——这正是我们在 `common.py` 里做 provider 无关封装的意义。"""))

cells.append(code("""vs_titan = build_vectorstore(docs, collection="m4_titan", provider="bedrock")
print("✅ Titan 索引就绪")

# bge-m3：本地开源嵌入（首次会下载模型权重）
vs_bge = build_vectorstore(docs, collection="m4_bge", provider="local")
print("✅ bge-m3（本地）索引就绪")"""))

cells.append(md("""## 3. 步骤 2 — 跑评估集，算 Recall@5

评估集 `eval_lab3.json` 每题标了正确文档 `ground_truth_doc_ids` 与类别（同语言 / 跨语言）。
**Recall@5**：Top-5 命中的片段里，是否包含正确文档。"""))

cells.append(code("""evalset = load_eval_set("eval_lab3.json")

def recall_at_k(vs, evalset, k=5):
    \"\"\"返回 (总体recall, 按类别recall字典, 明细列表)\"\"\"
    hits, by_cat = 0, {}
    detail = []
    for item in evalset:
        got = retrieve(vs, item["question"], top_k=k)
        got_ids = {Path(h["metadata"].get("source", "")).stem for h in got}
        hit = bool(got_ids & set(item["ground_truth_doc_ids"]))
        hits += hit
        cat = item["category"]
        by_cat.setdefault(cat, [0, 0])
        by_cat[cat][0] += hit
        by_cat[cat][1] += 1
        detail.append({"qid": item["qid"], "cat": cat, "hit": hit,
                       "q": item["question"][:30], "got": list(got_ids)[:3]})
    overall = hits / len(evalset)
    by_cat = {c: round(v[0]/v[1], 3) for c, v in by_cat.items()}
    return round(overall, 3), by_cat, detail

r_titan, cat_titan, det_titan = recall_at_k(vs_titan, evalset)
r_bge, cat_bge, det_bge = recall_at_k(vs_bge, evalset)
print("Titan  总体 Recall@5:", r_titan, " 分类:", cat_titan)
print("bge-m3 总体 Recall@5:", r_bge, " 分类:", cat_bge)"""))

cells.append(md("""## 4. 对比表"""))

cells.append(code("""rows = [
    {"模型": "Titan v2 (Bedrock)", "总体": r_titan, **cat_titan},
    {"模型": "bge-m3 (本地开源)",  "总体": r_bge,   **cat_bge},
]
display(pd.DataFrame(rows))"""))

cells.append(md("""## 5. 复盘讨论

**应该看到的**：
- **跨语言（cross_lingual）** 子集上，bge-m3 通常明显优于 Titan——中文问命中英文标准原文、英文问命中中文 SOP。
- 同语言子集两者都不错，差距主要在跨语言。
- 但**都不到 100%**：仍有"似相关而非相关"（如把肌钙蛋白的 CLIA 原理错配到 TSH 的 CLIA）→ 这是 **M5 检索三板斧** 要解决的。

**选型决策框架（5 维）**：语言覆盖 / 维度 / 上下文长度 / 成本 / 延迟。**外加检验科的硬约束：能否本地部署（数据不出内网）**——这一条直接把 bge-m3 推为产品落地首选，Titan 只在培训环境用。

**核心洞察**：嵌入是"语义匹配"不是"精确匹配"，天花板就在此；项目代码/试剂批号这类精确串，嵌入会稀释 → M5 用 Hybrid 补。"""))

cells.append(md("""## 6. 扩展任务
1. 只看 `cross_lingual` 子集，两模型差多少？把差距最大的 2 题打印出来看检索明细。
2. 把 `top_k` 从 5 调到 3 / 10，Recall 怎么变？
3. 找一个"两模型都召不回"的题，看它的文档表述和问题用词差在哪。
4. 成本/延迟对比：bge-m3 本地推理省了 API 费用，但吃本地算力——记录首次加载与单条编码耗时，估算在医院 GPU 受限下的可行性。"""))

nb = new_notebook(cells=cells, metadata={
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"}})
with open("lab_03_embedding_multilingual.ipynb", "w", encoding="utf-8") as f:
    nbf.write(nb, f)
print(f"✅ written lab_03_embedding_multilingual.ipynb  cells={len(cells)}")
