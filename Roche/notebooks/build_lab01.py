#!/usr/bin/env python3
"""生成 lab_01_first_rag.ipynb（开源栈版 · 检验科场景）。

用法：
    python3 build_lab01.py
程序化生成，避免手写 JSON 的转义 bug。修改内容后重跑即可覆盖。
"""
from __future__ import annotations
import nbformat as nbf
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

md = new_markdown_cell
code = new_code_cell
cells = []

cells.append(md("""# Lab 1 · 跑通你的第一个检验科知识助手

|     |     |
| --- | --- |
| **模块** | M2 · 搭起第一个 RAG（LangChain + Qdrant 跑通） |
| **时长** | 40 min（演示 5 + 学员动手 30 + 复盘 5） |
| **形态** | 完整动手 |
| **角色** | 检验科知识助手 MVP |
| **关键产出** | 一个能问检验科 SOP 的知识助手雏形 + 一份"裸 LLM vs RAG"对比表 |
| **技术栈** | Bedrock Claude（生成）+ Titan（嵌入）+ Qdrant（向量库，本地）+ LangChain |"""))

cells.append(md("""## 1. 背景与目标

**场景**：检验科每天被大量重复问题占用（危急值流程、质控失控怎么处理、标本能不能收、报告怎么审核）。这些答案都写在科室 SOP 里，但翻文档慢。我们把 SOP 变成一个能"开卷答题"、**带来源引用**的知识助手。

**数据**：4 份检验科 SOP（`data/kb/` 下，讲师已备）：
- `危急值管理.md`
- `室内质控.md`
- `标本采集与拒收.md`
- `报告审核与复检.md`

**预期体感**：
- 第一次亲手把"文档加载 → 切片 → 向量化 → 索引 → 检索 → 生成"6 步跑通——**全程开源、可本地部署**，无需任何托管知识库服务。
- 同一组中文问题，**裸 LLM** 与 **RAG** 的回答差异显著。
- **引用（来源）让回答可追溯**——这正是检验科/GxP 文化要求的"任何结论都要能证明其依据"。

**要发现的坑**：
- 问"血钾的危急值阈值是多少"时，RAG 可能答不全 → 因为**默认定长切片把危急值阈值表拦腰切断**，检索只命中半张表 → **引出 M3 Chunking**。"""))

cells.append(md("""## 2. 环境准备

> **前置条件**
> - 已配置 AWS 凭证（EC2 实例角色 / `aws configure` / 环境变量）
> - Bedrock 已开通：**Claude（生成）** 与 **Titan Text Embeddings v2（嵌入）**
> - 依赖：`pip install langchain-aws langchain-qdrant qdrant-client langchain-community pandas`
> - 开课前建议先跑 `python3 check_models.py` 确认 Bedrock 模型可调

本 Lab **不需要** S3 / 控制台 / OpenSearch / IAM 建角色——向量库用进程内 Qdrant，零运维。"""))

cells.append(code("""import pandas as pd
from IPython.display import display

from common import (
    REGION, MODEL_IDS, EMBED_PROVIDER,
    docs_from_dir, build_vectorstore, retrieve, rag_answer,
    invoke_llm, show_chunks, side_by_side,
)

print(f"AWS Region     : {REGION}")
print(f"生成模型 (gen_main): {MODEL_IDS['gen_main']}")
print(f"嵌入 provider    : {EMBED_PROVIDER}  (bedrock=Titan / local=bge-m3)")"""))

cells.append(md("""## 3. 步骤 1 — 加载知识库文档

**对应原理**：6 步流程的第 [1] 步「文档加载」。

`docs_from_dir("kb")` 把 `data/kb/` 下的 4 份 Markdown 读成 LangChain `Document` 列表，每个带 `source` 元数据（后面引用溯源要用）。"""))

cells.append(code("""docs = docs_from_dir("kb")   # 读取 data/kb/*.md
print(f"加载文档数：{len(docs)}")
for d in docs:
    print(f"  - {d.metadata['source']}  ({len(d.page_content)} 字符)")"""))

cells.append(md("""## 4. 步骤 2 — 建向量库（切片 + 向量化 + 索引，一行搞定）

**对应原理**：6 步流程的第 [2][3][4] 步——切片 → 向量化 → 索引。

`build_vectorstore()` 内部：用默认切片把文档切成片段 → 调 **Titan** 嵌入成向量 → 写入 **Qdrant**（默认进程内内存库）。

> **本节故意用"整篇文档 = 一个 Document"直接入库**（即最粗的切法），目的就是为了 M3 的"打脸"：等会儿你会看到阈值表类问题答不全。M3 我们再动切片的刀。"""))

cells.append(code("""vs = build_vectorstore(docs, collection="kb_lab1")
print("✅ 向量库就绪（Qdrant，内存模式）。可以开始检索/问答了。")"""))

cells.append(md("""## 5. 步骤 3 — 3 个中文问题：裸 LLM vs RAG

**对应原理**：6 步流程的第 [5][6] 步——检索 + 生成。

3 个问题按"典型 → 跨文档 → 刁难"递增：

| # | 问题 | 测试什么 |
| --- | --- | --- |
| Q1 | 检出危急值后多久内必须报告临床？ | 典型 SOP 命中 |
| Q2 | 室内质控出现 1₃ₛ 失控，患者标本要不要复测？ | 跨文档（质控 SOP） |
| Q3 | 肌钙蛋白检测的方法学原理是什么？ | **故意刁难**（SOP 里没有这条） |

每题同步发给：**裸 LLM**（`invoke_llm`，无检索）和 **RAG**（`rag_answer`，带引用）。"""))

cells.append(code("""QUESTIONS = [
    "检出危急值后多久内必须报告临床？",
    "室内质控出现 1_3s 失控，患者标本要不要复测？",
    "肌钙蛋白检测的方法学原理是什么？",
]

records = []
for i, q in enumerate(QUESTIONS, 1):
    print(f"\\n=========== Q{i}: {q} ===========")

    # 1) 裸 LLM（无检索）
    bare = invoke_llm(
        q,
        system="你是检验科知识助手。基于你已知的信息回答，请尽量简短。",
        max_tokens=400,
    )

    # 2) RAG（检索 + 生成 + 引用）
    rag = rag_answer(vs, q, model="gen_main", top_k=4)
    rag_text = rag["answer"]
    sources = []
    for h in rag["hits"]:
        s = h["metadata"].get("source", "")
        if s and s not in sources:
            sources.append(s)

    side_by_side(f"裸 LLM | Q{i}", bare, f"RAG | Q{i}", rag_text, width=55)
    print("引用来源：", sources or "(无)")

    records.append({"Q#": f"Q{i}", "问题": q, "裸 LLM": bare,
                    "RAG": rag_text, "引用": "; ".join(sources) or "(无)"})"""))

cells.append(md("""## 6. 对比表（一图看清）"""))

cells.append(code("""df = pd.DataFrame(records)
pd.set_option("display.max_colwidth", 200)
display(df)"""))

cells.append(md("""## 7. 复盘讨论

**应该看到的**：
- **Q1 危急值报告时限**：RAG 给出准确时限（10 分钟 / 急诊 5 分钟）+ 来源；裸 LLM 可能编一个数。
- **Q2 失控复测**：RAG 指向质控 SOP 的实际规定；裸 LLM 给通用说法。
- **Q3 肌钙蛋白原理**：RAG 应回答"知识库未找到相关依据"（SOP 里确实没有）；裸 LLM 会凭记忆瞎答——这是幻觉。

**核心收获**：
1. RAG 把"答得对"从**碰运气**变成**有依据**。
2. RAG 不是魔法：**知识库里没有的，它一样答不出来**（Q3）。
3. **引用是 RAG 的命脉**——检验科要的是"可追溯、可审计"，没有来源的回答不能用。

**关键的"坑"**：
- 试着问一句 **"血钾的危急值上下限分别是多少？"**，很可能答不全或答错——因为危急值阈值是**一张表**，而我们把整篇文档粗放入库/默认切片会把表切碎，检索只命中半张。
- 这就是 **下一节 M3** 的入口：Chunking 不是切豆腐。"""))

cells.append(md("""## 8. 扩展任务（开发背景学员可选）

1. **试出那个坑**：问"血钾的危急值上下限分别是多少？""白细胞的危急值？"，观察阈值表类问题的召回。
2. **纯检索排查**：`show_chunks(retrieve(vs, "血钾 危急值", top_k=5))`——**不走 LLM**，先看检索对不对。这是排查 RAG 问题的第一步。
3. **改 Top-K**：把 `rag_answer(..., top_k=4)` 调到 1 / 8，看回答完整度与来源数变化。
4. **换生成模型**：`model="gen_fast"`（Claude 快档），对比延迟与质量。
5. **换嵌入（on-prem 预演）**：`build_vectorstore(docs, collection="kb_local", provider="local")` 用本地开源 **bge-m3** 重建，对比检索效果——这就是罗氏产品真正本地部署时的形态（Titan 换 bge-m3，其余代码不变）。
6. **自定义 Prompt**：给 `rag_answer(..., prompt_template=...)` 传更强的约束（"未涉及请回答'知识库未找到相关依据'"），这是 M7 预热。
7. **评估雏形**：写 5–10 个问题 + 期望要点，用 `invoke_llm` 让模型自动判分，形成最小评估闭环——这是 M9（RAGAs）的预热。"""))

nb = new_notebook(cells=cells, metadata={
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"},
})

OUT = "lab_01_first_rag.ipynb"
with open(OUT, "w", encoding="utf-8") as f:
    nbf.write(nb, f)
print(f"✅ written {OUT}  cells={len(cells)}")
