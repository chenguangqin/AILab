#!/usr/bin/env python3
"""生成 lab_09_1_graph_kb.ipynb（进阶：LLM 自动抽取三元组建图 · 全开源）。"""
from __future__ import annotations
import nbformat as nbf
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

md, code = new_markdown_cell, new_code_cell
cells = []

cells.append(md("""# Lab 9.1 · GraphRAG 进阶 — 用 LLM 自动抽取三元组建图（全开源）

|     |     |
| --- | --- |
| **模块** | M10 · GraphRAG（进阶） |
| **时长** | 45 min（演示 + 动手） |
| **形态** | 演示 + 动手 |
| **技术栈** | Bedrock Claude（实体关系抽取 + 生成）+ NetworkX（图，本地）|
| **关键产出** | 从 SOP 文档**自动**抽三元组建图，对比"手搓图谱"的自动化程度 |

> **本 Lab 已从"云托管原生 GraphRAG"改为全开源方案**：不使用任何托管图数据库/托管 GraphRAG 服务。
> 生产落地若需持久化 + 并发，用 **Neo4j（可本地部署）** 替换内存 NetworkX 即可，抽取与检索逻辑不变。"""))

cells.append(md("""## 1. 背景：图谱从哪来？

Lab 9 的图谱是**人工建**的（`_build_graph.py` 手写节点和边）——准，但贵、难维护。
另一条路：**让 LLM 从文档里自动抽取实体和关系（三元组）**，自动建图。

- 优点：省人力、可随文档更新自动重建
- 代价：**必须人工抽检**（LLM 抽取会有噪声/错边），业界经验约"自动 70% + 人工校验 30%"

本 Lab 用 `data/kb` 的 4 份检验科 SOP，让 Claude 抽三元组，建成 NetworkX 图并检索。"""))

cells.append(md("""## 2. 环境准备
生成/抽取走 Bedrock Claude；图用 NetworkX。"""))

cells.append(code("""import json, re
from collections import Counter
import networkx as nx
from common import invoke_llm, docs_from_dir

docs = docs_from_dir("kb")
print("待抽取文档：", [d.metadata["source"] for d in docs])"""))

cells.append(md("""## 3. 步骤 1 — 用 LLM 抽取三元组

给每份 SOP 一个抽取提示，要求输出 JSON 数组 `[{"s":主体,"r":关系,"o":客体}]`。
**关系类型受控**（给 LLM 一个允许的关系清单），避免关系爆炸——这是抽取质量的关键。"""))

cells.append(code('''ALLOWED_REL = ["检测项目", "使用仪器", "使用试剂", "危急值阈值",
               "受干扰于", "遵循规则", "定义于", "引用标准", "处理流程"]

EXTRACT_PROMPT = """你是检验科知识工程师。从下面的 SOP 文本抽取实体关系三元组。
只用这些关系类型：{rels}
输出严格的 JSON 数组，每项形如 {{"s":"主体","r":"关系","o":"客体"}}，不要多余文字。

【SOP 文本】
{text}

【JSON】"""

def extract_triples(text: str) -> list[dict]:
    raw = invoke_llm(
        EXTRACT_PROMPT.format(rels="、".join(ALLOWED_REL), text=text[:4000]),
        model="gen_main", max_tokens=1500, temperature=0.0,
    )
    m = re.search(r"\\[.*\\]", raw, re.S)   # 容错：截取 JSON 数组
    if not m:
        return []
    try:
        return [t for t in json.loads(m.group(0)) if {"s", "r", "o"} <= set(t)]
    except json.JSONDecodeError:
        return []

all_triples = []
for d in docs:
    ts = extract_triples(d.page_content)
    print(f"  {d.metadata['source']}: 抽出 {len(ts)} 条三元组")
    all_triples.extend(ts)
print(f"\\n合计 {len(all_triples)} 条。抽样：")
for t in all_triples[:8]:
    print("   ", t)'''))

cells.append(md("""## 4. 步骤 2 — 从三元组建 NetworkX 图"""))

cells.append(code("""Gauto = nx.DiGraph()
for t in all_triples:
    Gauto.add_node(t["s"]); Gauto.add_node(t["o"])
    Gauto.add_edge(t["s"], t["o"], edge_type=t["r"])
print(f"自动图谱：{len(Gauto.nodes)} 节点 / {len(Gauto.edges)} 边")
print("关系类型分布：", dict(Counter(d['edge_type'] for _,_,d in Gauto.edges(data=True))))"""))

cells.append(md("""## 5. 步骤 3 — 在自动图谱上检索问答
复用"实体识别 → 邻域扩展 → 序列化 → LLM"的子图检索思路。"""))

cells.append(code('''def match(query, Gr):
    return [n for n in Gr.nodes if len(str(n)) >= 2 and str(n) in query]

def subgraph_facts(query, Gr, radius=2):
    seeds = match(query, Gr)
    UG = Gr.to_undirected()
    nodes = set()
    for s in seeds:
        if s in UG:
            nodes |= set(nx.ego_graph(UG, s, radius=radius).nodes)
    sub = Gr.subgraph(nodes)
    facts = sorted({f"{u} --{d['edge_type']}--> {v}" for u,v,d in sub.edges(data=True)})
    return seeds, "\\n".join(facts)

def graph_answer(query, Gr):
    seeds, facts = subgraph_facts(query, Gr)
    prompt = ("只依据下面图谱事实回答，事实没有的不要编。\\n\\n"
              f"【图谱事实】\\n{facts}\\n\\n【问题】{query}\\n【回答】")
    return {"seeds": seeds, "answer": invoke_llm(prompt, model="gen_main", max_tokens=500)}

r = graph_answer("血钾会受哪些因素干扰？危急值阈值是多少？", Gauto)
print("命中实体：", r["seeds"])
print(r["answer"])'''))

cells.append(md("""## 6. 复盘 — 手搓 vs 自动抽取 vs 生产落地

| 维度 | Lab 9 手搓（`_build_graph.py`） | Lab 9.1 LLM 自动抽取 |
|------|------------------------------|---------------------|
| 准确性 | 高（人工定义） | 中（需人工抽检纠错） |
| 人力 | 高 | 低（可随文档自动重建） |
| 关系一致性 | 强（schema 受控） | 依赖"受控关系清单"约束 |
| 适合 | 核心稳定知识（阈值/仪器/规则） | 快速覆盖大量文档 |

**生产落地建议（罗氏本地部署）**：
- 内存 NetworkX 适合演示/小图；生产需持久化 + 并发时，用 **Neo4j（可完全本地部署，开源社区版）**，抽取与子图检索逻辑不变。
- **务必保留人工校验环节**：LLM 抽的三元组进图前经专业组抽检，错边会污染所有依赖它的查询——这与检验科"规则需人审确权"的要求一致。"""))

cells.append(md("""## 7. 扩展任务
1. 给 `EXTRACT_PROMPT` 加 few-shot 示例，观察抽取一致性提升。
2. 抽取后做**去重/规范化**（"血钾"/"K"/"钾"归一），对比图连通性变化。
3. 把自动图谱与 Lab 9 手搓图谱做差异比对，找出 LLM 漏抽/错抽的边（人工校验雏形）。
4. 用 Neo4j（本地 docker）替换 NetworkX，把三元组写入并用 Cypher 查询。"""))

nb = new_notebook(cells=cells, metadata={
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"}})
with open("lab_09_1_graph_kb.ipynb", "w", encoding="utf-8") as f:
    nbf.write(nb, f)
print(f"✅ written lab_09_1_graph_kb.ipynb  cells={len(cells)}")
