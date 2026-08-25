#!/usr/bin/env python3
"""生成 lab_08_evaluation.ipynb（开源栈版 · 检验科 · RAGAs）。
程序化生成，避免手写 JSON 转义 bug。参考 build_lab01.py。"""
from __future__ import annotations
import nbformat as nbf
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

md, code = new_markdown_cell, new_code_cell
cells = []

cells.append(md("""# Lab 8 · 评估体系（RAGAs 开源）

|     |     |
| --- | --- |
| **模块** | M9 · 评估体系 |
| **时长** | 50 min |
| **形态** | 完整动手（重点） |
| **关键产出** | 一份 30 题 RAGAs 报告 + 3 个 Bad Case 归因 + 优化方向 |
| **技术栈** | RAGAs（开源）+ Bedrock Claude 作评审 LLM + Titan 作评审嵌入 |"""))

cells.append(md("""## 1. 背景与目标

把"感觉答得还行"变成"具体多少分"。用 **RAGAs（开源）** 对前面搭的检验科 RAG 跑 4 个核心指标：

- 检索：**context_precision** / **context_recall**
- 生成：**faithfulness** / **answer_relevancy**

**诚实评估**：`data/eval_30.json` 是**合成种子集**（用 SOP 造的问题+参考答案），绝对分数别当真理，**看优化前后的相对变化**；后续让检验科专家在此基础上审定成黄金集（见复盘）。"""))

cells.append(md("""## 2. 环境准备

依赖：`pip install ragas datasets langchain-aws langchain-qdrant qdrant-client langchain-community`

> RAGAs 需要一个"评审 LLM + 嵌入"。本课用 Bedrock Claude / Titan 包一层传给 RAGAs——**不依赖任何托管评估服务**，评审模型换本地 Qwen 只改 `get_llm`。
> RAGAs 会对每题多次调用评审 LLM，30 题可能需要几分钟，请耐心等。"""))

cells.append(code("""from common import docs_from_dir, build_vectorstore, rag_answer, load_eval_set
import pandas as pd

evalset = load_eval_set("eval_30.json")
print(f"评估集题数：{len(evalset)}")
print("主题分布：")
print(pd.Series([e["category"] for e in evalset]).value_counts())
print("难度分布：")
print(pd.Series([e.get("difficulty", "?") for e in evalset]).value_counts())"""))

cells.append(md("""## 3. 步骤 2 — 用你的 RAG 现跑出 answer + contexts

评估需要每题的：问题、RAG 的回答、RAG 实际检索到的片段、参考答案。前两项/检索片段由 `rag_answer` 现跑得到。"""))

cells.append(code("""docs = docs_from_dir("kb")
vs = build_vectorstore(docs, collection="kb_lab8")

questions, answers, contexts, references = [], [], [], []
for i, e in enumerate(evalset, 1):
    r = rag_answer(vs, e["question"], model="gen_main", top_k=4)
    questions.append(e["question"])
    answers.append(r["answer"])
    contexts.append(r["contexts"])          # RAG 实际检索到的片段
    references.append(e["ground_truth"])
    if i % 10 == 0:
        print(f"  已跑 {i}/{len(evalset)} 题")
print("RAG 跑完，准备评估数据集。")"""))

cells.append(md("""## 4. 步骤 3 — 跑 RAGAs 四指标

> 下面用 RAGAs 的通用列名（question / answer / contexts / ground_truth）。
> 若你的 ragas 版本报列名错误，请改成 user_input / response / retrieved_contexts / reference。"""))

cells.append(code("""from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from common import get_llm, get_embeddings

ds = Dataset.from_dict({
    "question": questions,
    "answer": answers,
    "contexts": contexts,
    "ground_truth": references,
})

judge_llm = LangchainLLMWrapper(get_llm(model="gen_main", max_tokens=1024))
judge_emb = LangchainEmbeddingsWrapper(get_embeddings())

result = evaluate(
    ds,
    metrics=[context_precision, context_recall, faithfulness, answer_relevancy],
    llm=judge_llm,
    embeddings=judge_emb,
)
print(result)
df = result.to_pandas()
df.head()"""))

cells.append(md("""## 5. 步骤 4 — 找最低分 3 题 + 归因

**归因决策树**：
```
某题低分 → 检索分(precision/recall)低？
   ├─是 → 检索问题 → 回 M3(切片)/M4(嵌入)/M5(Hybrid+Rerank)
   └─否 → 生成分低？
          ├─faithfulness 低 → 幻觉 → M7 Prompt
          └─answer_relevancy 低 → 偏题 → M8 改写
```"""))

cells.append(code("""metric_cols = [c for c in ["context_precision", "context_recall", "faithfulness", "answer_relevancy"] if c in df.columns]
print("各指标均值：")
print(df[metric_cols].mean().round(3))

df["_min_metric"] = df[metric_cols].min(axis=1)
worst = df.sort_values("_min_metric").head(3)
print("\\n==== 得分最低的 3 题（逐一归因）====")
for _, row in worst.iterrows():
    print("\\n问题：", row["question"])
    for c in metric_cols:
        print(f"  {c}: {row[c]:.3f}")
    print("  → 归因提示：检索分低=回M3-M5；faithfulness低=回M7；answer_relevancy低=回M8")"""))

cells.append(md("""## 6. 复盘 + 诚实评估落地 + 扩展任务

**复盘**：
- 先看 faithfulness（生死线，建议 ≥0.90），再看其余（体感线 ≥0.75）。
- 低分题按归因决策树定位到具体模块——评估的价值是把"哪里不好"翻译成"改哪儿"。

**诚实评估落地（重点）**：
- 本次是**合成基线**，绝对分数别当真理，做任何优化（换切片/嵌入/加 Rerank/改 Prompt）都重跑本集，**比相对变化**。
- 让检验科专家把合成集里的**争议样本 + 线上 Bad Case** 审定成黄金集，先攒 **20-50 条**；模板字段：`问题 / 参考答案 / 关键依据条款 / 难度 / 主题 / 专家签注`。

**扩展任务**：
1. **对比实验**：分别用"整篇入库"和"结构化切片"建库，重跑本集，看 context_recall 的 delta。
2. **换评审模型**：把 judge 换成 `gen_strong`，看分数稳定性（注意 LLM-as-Judge 的位置/冗长偏好）。
3. **只跑免标注指标**：只算 faithfulness + answer_relevancy（不需 ground_truth），演示"对线上真实流量持续评估"。
4. **回归集雏形**：把本集中最低分 3 题固化为回归用例，改进后必须不退化。"""))

nb = new_notebook(cells=cells, metadata={
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"},
})
OUT = "lab_08_evaluation.ipynb"
with open(OUT, "w", encoding="utf-8") as f:
    nbf.write(nb, f)
print(f"written {OUT} cells={len(cells)}")
