#!/usr/bin/env python3
"""生成 lab_09_graphrag_demo.ipynb（检验科 GraphRAG 演示 · NetworkX 手搓）。"""
from __future__ import annotations
import nbformat as nbf
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

md, code = new_markdown_cell, new_code_cell
cells = []

cells.append(md("""# Lab 9 · GraphRAG（手搓演示）— 关系型问题：纯向量 vs 图增强

|     |     |
| --- | --- |
| **模块** | M10 · GraphRAG（当向量检索撞上"关系型问题"） |
| **时长** | 45 min（演示 15 + 动手 20 + 复盘 10） |
| **形态** | **演示型 Lab** |
| **技术栈** | NetworkX（开源图，本地）+ Bedrock Claude（生成）+ Qdrant（向量基线对照） |
| **关键产出** | 纯向量 vs 图增强检索的效果对比 + "用/不用图"的决策体感 |"""))

cells.append(md("""## 1. 背景：检验科的"关系型问题"

检验科很多问题是**跨实体多跳关系**，纯向量检索抓不全，例如：
- "**CREA 结果异常**，可能涉及哪些**仪器因素**和**质控规则**？"（项目→仪器→因素；项目→质控规则）
- "哪些项目**既受溶血影响、又设有危急值**？"（集合运算）
- "室内质控**失控规则**定义在哪份 SOP、又**引用哪个外部标准**？"（规则→SOP→标准，多跳）

这些问题的答案分散在多份 SOP 的不同段落里，向量检索召回的是"片段堆叠"而非"关系连接"。我们把检验科知识建成一张图谱，让检索"沿着关系走"。

> 图谱已由 `data/_build_graph.py` 预构建为 `data/lab_graph.gpickle`（项目/仪器/试剂/危急值/干扰/质控规则/SOP/标准）。本 Lab **不建图**，直接体验图能干什么。"""))

cells.append(md("""## 2. 环境准备
`pip install networkx`（其余依赖见 requirements.txt）。生成走 Bedrock Claude。"""))

cells.append(code("""import pickle
from pathlib import Path
import re
import pandas as pd
import networkx as nx

from common import invoke_llm, rag_answer, build_vectorstore, docs_from_dir, DATA_DIR

G = pickle.loads((DATA_DIR / "lab_graph.gpickle").read_bytes())
print(f"图谱：{len(G.nodes)} 节点 / {len(G.edges)} 边")
from collections import Counter
print("节点类型：", dict(Counter(d['node_type'] for _, d in G.nodes(data=True))))"""))

cells.append(md("""## 3. 步骤 1（演示）— 图谱结构一览
看看节点类型和几条"三元组"边——这就是给 LLM 的结构化事实（对比向量 RAG 给的是文档片段）。"""))

cells.append(code("""REL = {
    "MEASURED_BY": "由仪器检测", "USES_REAGENT": "使用试剂",
    "HAS_CRITICAL_VALUE": "设有危急值", "AFFECTED_BY": "受干扰于",
    "GOVERNED_BY": "遵循SOP", "HAS_FACTOR": "存在仪器因素",
    "MONITORED_BY": "受质控规则监控", "DEFINED_IN": "定义于", "REF_STANDARD": "引用标准",
}

def triple_str(u, v, d):
    return f"{u} --{REL.get(d['edge_type'], d['edge_type'])}--> {v}"

print("示例三元组（前 15 条）：")
for u, v, d in list(G.edges(data=True))[:15]:
    print("  ", triple_str(u, v, d))"""))

cells.append(md("""## 4. 步骤 2（演示）— 子图检索：实体识别 → 邻域扩展 → 序列化

**路线 A（子图检索）三步**：
1. `match_entities`：把用户问题里的词映射到图谱节点（实体识别）
2. `ego_subgraph`：从命中节点向外扩展 N 跳，取邻域子图
3. `serialize`：把子图写成三元组文本，喂给 LLM"""))

cells.append(code("""def match_entities(query: str) -> list:
    seeds = []
    for n, d in G.nodes(data=True):
        name = d.get("name", str(n))
        toks = [t for t in re.split(r"[ （）():：]", name) if len(t) >= 2]
        if name in query or any(t in query for t in toks):
            seeds.append(n)
    return seeds

def ego_subgraph(seeds: list, radius: int = 2):
    UG = G.to_undirected()
    nodes = set()
    for s in seeds:
        if s in UG:
            nodes |= set(nx.ego_graph(UG, s, radius=radius).nodes)
    return G.subgraph(nodes)

def serialize(subG) -> str:
    lines = []
    for u, v, d in subG.edges(data=True):
        line = triple_str(u, v, d)
        cv = subG.nodes[v]
        if cv.get("node_type") == "CriticalValue":
            line += f"（下限 {cv.get('low')} / 上限 {cv.get('high')} {cv.get('unit')}）"
        lines.append(line)
    return "\\n".join(sorted(set(lines)))

def graph_answer(query: str, radius: int = 2) -> dict:
    seeds = match_entities(query)
    subG = ego_subgraph(seeds, radius)
    facts = serialize(subG)
    prompt = (
        "你是检验科知识助手。只依据下面的【图谱事实】回答问题，"
        "做必要的关系推理/集合运算；事实里没有的不要编。\\n\\n"
        f"【图谱事实】\\n{facts}\\n\\n【问题】{query}\\n【回答】"
    )
    ans = invoke_llm(prompt, model="gen_main", max_tokens=500)
    return {"answer": ans, "seeds": seeds, "n_facts": len(facts.splitlines())}

# 演示一次
demo = graph_answer("CREA 结果异常，可能涉及哪些仪器因素和质控规则？")
print("命中实体：", demo["seeds"])
print("子图事实条数：", demo["n_facts"])
print("图增强回答：\\n", demo["answer"])"""))

cells.append(md("""## 5. 步骤 3 — 建纯向量 RAG 基线（对照组）
用前面 Lab 的 `data/kb` SOP 文档建向量库，作为"纯向量检索"的对照。"""))

cells.append(code("""vs = build_vectorstore(docs_from_dir("kb"), collection="kb_graph_compare")
print("✅ 向量基线就绪")

def vector_answer(query: str) -> str:
    return rag_answer(vs, query, model="gen_main", top_k=5)["answer"]"""))

cells.append(md("""## 6. 步骤 4（动手）— 5 个关系型问题：向量 vs 图

按跳数递增。注意 Q1 是"边界探测"（简单问题向量也能答），Q3/Q4 是图的价值区。"""))

cells.append(code("""QUESTIONS = [
    "CREA 是用什么仪器检测的？",                          # 1 跳，简单
    "血钾（K）会受哪些干扰因素影响？",                     # 1-2 跳
    "CREA 结果异常，可能涉及哪些仪器因素和质控规则？",       # 多跳
    "哪些项目既受溶血影响、又设有危急值？",                  # 集合运算
    "室内质控的失控规则定义在哪份 SOP，又引用了哪个外部标准？", # 多跳链
]

rows = []
for i, q in enumerate(QUESTIONS, 1):
    print("=" * 78)
    print(f"Q{i}: {q}")
    va = vector_answer(q)
    ga = graph_answer(q)
    print("\\n[纯向量]\\n", va)
    print("\\n[图增强] 命中实体:", ga["seeds"])
    print(ga["answer"])
    rows.append({"Q#": f"Q{i}", "问题": q, "纯向量": va, "图增强": ga["answer"]})"""))

cells.append(md("""## 7. 对比表（学员填"完整度 1-5"与"谁赢为什么"）"""))

cells.append(code("""df = pd.DataFrame(rows)
pd.set_option("display.max_colwidth", 200)
display(df)"""))

cells.append(md("""## 8. 复盘 — 三个"不是"

- **不是替代**：关系型问题用图，语义型（FAQ/条款）用向量。Q1 向量也能答 → 不需要图。
- **不是免费**：图谱建图 + 维护是真实成本；没有评估证据（M9）不要上。
- **不是万能**：图也会答错——错在"关系建错"或"实体没匹配上"，比向量更隐蔽。

| 问题类型 | 推荐方案 |
|---------|---------|
| FAQ、SOP 条款查询 | 纯向量（M2–M5 成果） |
| 多跳关系 / 集合运算（受某干扰且有危急值） | 图谱（GraphRAG） |
| 实时数据（这个患者最新结果） | **不是 RAG 问题，是 Agent 问题** → M11 |

> 决策口诀：**先把向量检索（M5）做透 + 用评估（M9）证明关系型短板，再考虑上图。**"""))

cells.append(md("""## 9. 扩展任务
1. 改 `radius`（1/2/3）看子图大小与回答完整度、token 成本的权衡。
2. 给 `match_entities` 加同义词/别名表（如"肌酐"→CREA），提升实体识别召回。
3. 用 `pyvis` 可视化 CREA 的 2 跳邻域子图。
4. 把 `graph_answer` 包成一个"工具"，预习 M11：让 Agent 在"关系型问题"时自动调它。"""))

nb = new_notebook(cells=cells, metadata={
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"}})
with open("lab_09_graphrag_demo.ipynb", "w", encoding="utf-8") as f:
    nbf.write(nb, f)
print(f"✅ written lab_09_graphrag_demo.ipynb  cells={len(cells)}")
