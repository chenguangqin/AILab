#!/usr/bin/env python3
"""生成 lab_04_retrieval_trio.ipynb（开源栈 · 检索三板斧：Hybrid + Metadata + Rerank）。"""
from __future__ import annotations
import nbformat as nbf
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

md, code = new_markdown_cell, new_code_cell
cells = []

cells.append(md("""# Lab 4 · 检索三板斧（Hybrid + Metadata + Rerank）

|     |     |
| --- | --- |
| **模块** | M5 · 检索三板斧 |
| **时长** | 50 min |
| **形态** | 完整动手 |
| **关键产出** | 四阶段优化阶梯对比表（Recall@5 / Precision@5） |
| **技术栈** | 全开源：向量(Qdrant) + BM25(langchain) + bge-reranker-v2-m3(本地) |

**M4 留下的三类坑**：① 精确串失配（试剂批号 LOT-K-20240612、仪器型号 cobas e601 被向量稀释）；② 属性错位（想查免疫组却混进生化组）；③ 似相关而非相关。本 Lab 逐步打开三板斧，看每一招的边际收益。"""))

cells.append(md("""## 1. 环境准备
> - Bedrock Titan（嵌入）
> - `pip install rank-bm25`（`BM25Retriever` 依赖）、`sentence-transformers`（bge-reranker）
> - 数据：先跑 `python3 build_m4m5_data.py`"""))

cells.append(code("""import json
from pathlib import Path
import pandas as pd

from common import docs_from_dir, build_vectorstore, retrieve, rerank, load_eval_set, DATA_DIR

# 加载文档并附加 metadata（专业组/仪器/类别/版本）
docs = docs_from_dir("m4/cn_docs") + docs_from_dir("m4/en_docs")
doc_meta = json.loads((DATA_DIR / "m4" / "doc_meta.json").read_text(encoding="utf-8"))
for d in docs:
    did = Path(d.metadata["source"]).stem
    d.metadata["doc_id"] = did
    d.metadata.update(doc_meta.get(did, {}))
print(f"文档数：{len(docs)}；示例 metadata：", docs[0].metadata)

evalset = load_eval_set("eval_lab4.json")

def metrics(get_ids_fn, evalset, k=5):
    \"\"\"传入一个 query->top-k doc_id 列表 的函数，返回平均 Recall@k / Precision@k\"\"\"
    R, P = [], []
    for item in evalset:
        got = get_ids_fn(item)[:k]
        gt = set(item["ground_truth_doc_ids"])
        inter = len(set(got) & gt)
        R.append(inter / max(1, len(gt)))
        P.append(inter / k)
    return round(sum(R)/len(R), 3), round(sum(P)/len(P), 3)"""))

cells.append(md("""## 2. 阶段 1 — 纯向量 baseline

只用向量检索（Titan 嵌入）。看精确串类问题（试剂批号/仪器型号）会怎样。"""))

cells.append(code("""vs = build_vectorstore(docs, collection="m5_dense", provider="bedrock")

def dense_ids(item):
    got = retrieve(vs, item["question"], top_k=5)
    return [h["metadata"].get("doc_id", Path(h["metadata"].get("source","")).stem) for h in got]

r1, p1 = metrics(dense_ids, evalset)
print(f"阶段1 纯向量   Recall@5={r1}  Precision@5={p1}")"""))

cells.append(md("""## 3. 阶段 2 — + Hybrid（向量 + BM25 关键词）

用 langchain 的 `BM25Retriever`（关键词/精确匹配）与向量检索器 `EnsembleRetriever` 融合。BM25 专治"试剂批号 LOT-K-20240612""cobas e601"这类精确串。"""))

cells.append(code("""from langchain_community.retrievers import BM25Retriever
from langchain.retrievers import EnsembleRetriever

bm25 = BM25Retriever.from_documents(docs); bm25.k = 20
dense_ret = vs.as_retriever(search_kwargs={"k": 20})
hybrid = EnsembleRetriever(retrievers=[bm25, dense_ret], weights=[0.5, 0.5])

def hybrid_docs(question, n=20):
    return hybrid.invoke(question)[:n]

def hybrid_ids(item):
    return [d.metadata.get("doc_id", Path(d.metadata.get("source","")).stem)
            for d in hybrid_docs(item["question"])]

r2, p2 = metrics(hybrid_ids, evalset)
print(f"阶段2 +Hybrid  Recall@5={r2}  Precision@5={p2}  （关注 exact 类题的提升）")"""))

cells.append(md("""## 4. 阶段 3 — + Metadata 过滤（按专业组）

有的题带 `filter`（如 `专业组=免疫组`）。这里用**后过滤**演示概念：先 Hybrid 召回，再按 metadata 筛掉不符专业组的候选。

> 生产建议：Qdrant 支持**检索前**原生 metadata 过滤（`filter=` 传 `qdrant_client.models.Filter`），比后过滤更省算力、更准。本 Lab 用后过滤是为了讲清概念、代码更直观。"""))

cells.append(code("""def meta_filter_ids(item):
    cands = hybrid_docs(item["question"], n=20)
    flt = item.get("filter")
    if flt:
        cands = [d for d in cands if all(d.metadata.get(k) == v for k, v in flt.items())] or cands
    return [d.metadata.get("doc_id", Path(d.metadata.get("source","")).stem) for d in cands]

r3, p3 = metrics(meta_filter_ids, evalset)
print(f"阶段3 +Metadata Recall@5={r3}  Precision@5={p3}  （关注 metadata 类题噪声减少）")"""))

cells.append(md("""## 5. 阶段 4 — + Rerank（本地 bge-reranker-v2-m3）

对 Hybrid+过滤后的候选做 cross-encoder 精排，把最相关的推到前面——主要提升 **Precision@5**。用 `common.rerank`（本地开源，不依赖任何托管服务）。"""))

cells.append(code("""def rerank_ids(item):
    cands = hybrid_docs(item["question"], n=15)
    flt = item.get("filter")
    if flt:
        cands = [d for d in cands if all(d.metadata.get(k) == v for k, v in flt.items())] or cands
    texts = [d.page_content for d in cands]
    order = rerank(item["question"], texts, top_n=5)   # [{index, score}, ...]
    return [cands[o["index"]].metadata.get("doc_id",
            Path(cands[o["index"]].metadata.get("source","")).stem) for o in order]

r4, p4 = metrics(rerank_ids, evalset)
print(f"阶段4 +Rerank  Recall@5={r4}  Precision@5={p4}  （Precision 应明显上升）")"""))

cells.append(md("""## 6. 四阶段优化阶梯对比表"""))

cells.append(code("""ladder = pd.DataFrame([
    {"阶段": "1 纯向量",        "Recall@5": r1, "Precision@5": p1},
    {"阶段": "2 +Hybrid",      "Recall@5": r2, "Precision@5": p2},
    {"阶段": "3 +Metadata",    "Recall@5": r3, "Precision@5": p3},
    {"阶段": "4 +Rerank",      "Recall@5": r4, "Precision@5": p4},
])
display(ladder)"""))

cells.append(md("""## 7. 复盘 + 扩展任务

**应该看到的阶梯**（趋势一致，绝对值因数据而异）：
- Hybrid 主要救 **exact 类**（试剂批号/仪器型号）→ Recall 上台阶；
- Metadata 过滤减少跨专业组噪声 → Precision 上升；
- Rerank 把对的推到 Top-1 → Precision 明显上升。

**决策权分配视角**（呼应 Agent 主线）：Metadata 过滤是**程序确定性**逻辑（可审计、零幻觉），把"能用规则缩小的空间"交给程序，只把语义模糊部分留给向量/Rerank——企业级检索的可审计性正来自这种分工。

**扩展任务**：
1. 按 `type` 分组统计四阶段指标，验证"每招各治哪类题"。
2. 把 Metadata 换成 Qdrant 原生 `filter=`（`qdrant_client.models.Filter`）做检索前过滤，对比后过滤的算力差异。
3. 调 Ensemble 的 `weights`（如 0.3/0.7），看 Hybrid 对 exact vs semantic 的权衡。
4. Rerank 的候选 N 从 15 调到 30，Precision 是否继续升？延迟代价多大？"""))

nb = new_notebook(cells=cells, metadata={
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"}})
with open("lab_04_retrieval_trio.ipynb", "w", encoding="utf-8") as f:
    nbf.write(nb, f)
print(f"✅ written lab_04_retrieval_trio.ipynb  cells={len(cells)}")
