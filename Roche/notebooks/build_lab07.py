#!/usr/bin/env python3
"""生成 lab_07_multiturn_query_rewrite.ipynb（开源栈版 · 检验科场景）。
程序化生成，避免手写 JSON 转义 bug。参考 build_lab01.py。"""
from __future__ import annotations
import nbformat as nbf
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

md, code = new_markdown_cell, new_code_cell
cells = []

cells.append(md("""# Lab 7 · 多轮对话 + Query 改写

|     |     |
| --- | --- |
| **模块** | M8 · 多轮对话 + Query 改写 |
| **时长** | 40 min（Step1 10 + Step2 5 + Step3 15 + Step4 10） |
| **形态** | 完整动手 |
| **关键产出** | 一个能听懂上下文的检验科助手 + Query 改写前后召回对比 |
| **技术栈** | Bedrock Claude（gen_fast 做改写）· Qdrant · LangChain |"""))

cells.append(md("""## 1. 背景与目标

真实科室咨询是多轮的，且大量省略与指代（"他"、"之前"、"要不要复查"）。单轮 RAG 直接拿最后一句去检索会翻车。本 Lab 亲手体验 **Query 改写**这个"开关性"功能：

- **不改写**：第 3 轮"那要不要复查"检索翻车
- **改写后**：把它补全成"血钾偏高（危急值）结果是否需要复查"，召回立刻恢复

复用前面的检验科 SOP 知识库（`data/kb`）。"""))

cells.append(md("""## 2. 环境准备

依赖：`pip install langchain-aws langchain-qdrant qdrant-client langchain-community`
前置：Bedrock Claude + Titan 已开通。"""))

cells.append(code("""from common import docs_from_dir, build_vectorstore, retrieve, invoke_llm, show_chunks, side_by_side

docs = docs_from_dir("kb")
vs = build_vectorstore(docs, collection="kb_lab7")
print(f"知识库就绪，文档数={len(docs)}")

# 统一测试对话（便于对比）
DIALOG = [
    "这个患者血钾偏高",
    "他之前的结果呢",
    "那要不要复查",     # ← 关键观察点
]"""))

cells.append(md("""## 3. Step 1+2 — 不做改写的多轮循环（看翻车）

朴素多轮：每轮直接拿"当前这句原文"去检索，历史只用于生成。观察第 3 轮"那要不要复查"检索到什么。"""))

cells.append(code("""def answer_with_history(history, query, context):
    hist_text = "\\n".join(f"{r}: {t}" for r, t in history)
    prompt = (f"你是检验科知识助手。基于【检索片段】并结合【对话历史】回答最新问题，"
              f"关键结论标注 [片段N] 来源；片段没有就说'知识库未找到相关依据'。\\n\\n"
              f"【对话历史】\\n{hist_text}\\n\\n【检索片段】\\n{context}\\n\\n【最新问题】{query}\\n\\n【回答】")
    return invoke_llm(prompt, model="gen_main", max_tokens=400)

history = []
print("======== 不做改写 ========")
for i, turn in enumerate(DIALOG, 1):
    hits = retrieve(vs, turn, top_k=4)        # 直接用原文检索
    top_src = hits[0]["metadata"].get("source", "?") if hits else "(空)"
    ctx = "\\n\\n".join(f"[片段{j}] {h['content']['text'][:300]}" for j, h in enumerate(hits, 1))
    ans = answer_with_history(history, turn, ctx)
    print(f"\\n[第{i}轮] 用户: {turn}")
    print(f"  检索 Top-1 来源: {top_src}")
    print(f"  回答: {ans[:160]}...")
    history.append(("用户", turn)); history.append(("助手", ans))"""))

cells.append(md("""### 观察第 3 轮的裸检索（不走 LLM）

先看检索对不对，是排查 RAG 问题的第一步。"""))

cells.append(code("""print("第3轮原文『那要不要复查』的裸检索结果：")
show_chunks(retrieve(vs, "那要不要复查", top_k=5))"""))

cells.append(md("""## 4. Step 3 — 加入 Query 改写（gen_fast）

在检索之前，用便宜档模型把当前这句结合历史改写成独立完整的检索 Query。改写只用于检索，不用于生成。"""))

cells.append(code("""REWRITE_PROMPT = '''你是检验科咨询的 Query 改写助手。基于对话历史，把用户最新一句改写成
独立、完整、可用于知识库检索的问题。
要求：
- 替换所有指代（他/那次/之前/刚才）为具体实体或语境
- 补全隐含意图（危急值/复查/拒收/质控 等）
- 只输出改写后的一句话，不超过30字；若已独立完整则原样返回

[对话历史]
{history}

[当前问题]
{query}

[改写后的检索Query]'''

def rewrite_query(history, query):
    hist_text = "\\n".join(f"{r}: {t}" for r, t in history)
    out = invoke_llm(REWRITE_PROMPT.format(history=hist_text, query=query),
                     model="gen_fast", max_tokens=60, temperature=0.0)
    return out.strip().splitlines()[0].strip() if out.strip() else query

# 重放对话，这次检索前先改写
history = []
rewritten_q3 = None
print("======== 改写后 ========")
for i, turn in enumerate(DIALOG, 1):
    search_q = rewrite_query(history, turn)
    if i == 3:
        rewritten_q3 = search_q
    hits = retrieve(vs, search_q, top_k=4)
    top_src = hits[0]["metadata"].get("source", "?") if hits else "(空)"
    ctx = "\\n\\n".join(f"[片段{j}] {h['content']['text'][:300]}" for j, h in enumerate(hits, 1))
    ans = answer_with_history(history, turn, ctx)
    print(f"\\n[第{i}轮] 用户原文: {turn}")
    print(f"  → 改写检索Query: {search_q}")
    print(f"  检索 Top-1 来源: {top_src}")
    print(f"  回答: {ans[:160]}...")
    history.append(("用户", turn)); history.append(("助手", ans))"""))

cells.append(md("""## 5. Step 4 — 第 3 轮召回对比

把"原文检索"和"改写后检索"的 Top-5 并排，直观看召回差异（关注是否命中『报告审核与复检 / 危急值管理』）。"""))

cells.append(code("""raw = retrieve(vs, "那要不要复查", top_k=5)
rew = retrieve(vs, rewritten_q3 or "血钾偏高（危急值）结果是否需要复查", top_k=5)

def fmt(hits):
    lines = []
    for j, h in enumerate(hits, 1):
        src = h["metadata"].get("source", "?")
        lines.append(f"#{j} {src}  score={h['score']:.3f}")
    return "\\n".join(lines)

side_by_side("原文检索『那要不要复查』", fmt(raw),
             f"改写后『{rewritten_q3}』", fmt(rew), width=46)

def rel(hits):
    keys = ("报告审核", "危急值")
    return sum(1 for h in hits if any(k in h["metadata"].get("source", "") for k in keys))
print(f"\\n相关命中数(原文): {rel(raw)}/5    相关命中数(改写): {rel(rew)}/5")"""))

cells.append(md("""## 6. 复盘 + 扩展任务

**复盘**：
- 第 3 轮原文检索命中不稳/无关；改写后补全语境，召回显著回升——这就是"开关性"功能。
- 改写只用于**检索**，生成仍用完整历史，两条输入解耦。

**扩展任务**：
1. **换档对比**：把 `rewrite_query` 的 `model` 在 `gen_fast`/`gen_main` 间切换，看改写质量与延迟。
2. **加语言规范化**：在改写 Prompt 里加"纠正口语化/缩写"，测"钾高咋办""溶血的能收不"。
3. **滑动窗口**：历史只保留最近 N 轮，观察长对话下的 token 与效果权衡。
4. **Multi-Query 扩展**：让模型生成 3 个等价变体并行检索后合并去重，比较召回。
5. **失败注入**：故意不改写跑一段 5 轮对话，统计有多少轮翻车。"""))

nb = new_notebook(cells=cells, metadata={
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"},
})
OUT = "lab_07_multiturn_query_rewrite.ipynb"
with open(OUT, "w", encoding="utf-8") as f:
    nbf.write(nb, f)
print(f"written {OUT} cells={len(cells)}")
