#!/usr/bin/env python3
"""生成 lab_10_agentic.ipynb（LangGraph 版 · 检验科可审计审核 Agent）。

用法：
    python3 build_lab10.py
程序化生成，避免手写 JSON 的转义 bug。
"""
from __future__ import annotations
import nbformat as nbf
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

md = new_markdown_cell
code = new_code_cell
cells = []

cells.append(md("""# Lab 10 · Agentic RAG — 用 LangGraph 构建可审计的检验科审核助手

|     |     |
| --- | --- |
| **模块** | M11 · Agentic RAG（Day 2 下午第 2 场，**重点 Lab · 60 min**） |
| **挑战对应** | 全景图 · 实时数据需求 |
| **关键产出** | 用 **LangGraph** 写的检验科审核 Agent（SOP 检索 + LIS/历史/质控/仪器 工具）+ 6 题混合问答轨迹 |
| **技术栈** | LangGraph（ReAct）+ Bedrock Claude（工具调用）+ LangChain `@tool` |

## 学习目标
1. 用 **LangGraph** 的 `create_react_agent` 几十行搭一个会调度工具的 Agent——全开源、可本地部署，无需 Bedrock Agent / Lambda / Action Group。
2. 用 `@tool` 装饰普通 Python 函数定义工具，**docstring 就是 Agent 的决策依据**。
3. 让 Agent 区分三类问题：SOP 问答 → 检索；结果/趋势/质控/仪器 → 调工具；危急值审核 → 多步。
4. **守住底线**：写操作/放行**不自动执行**，只产出"审核意见草稿 + 依据 + 置信度 + 建议人工复核"。
5. 看工具调用轨迹，理解 ReAct 循环，并知道生产上如何接 Langfuse 做可审计留痕。"""))

cells.append(md("""## 1 · 背景：为什么需要 Agent

| 用户提问 | 答案在哪 | 传统 RAG |
|---------|---------|---------|
| "危急值多久内要报告？" | SOP 文档 | ✅ 可以 |
| "患者 P001 的血钾现在多少？" | LIS 系统 | ❌ 知识库永远没有 |
| "这个 CREA 危急值要不要发？" | 质控 + 历史 + 仪器 + 判断 | ❌ 单步检索做不到 |

**ReAct 循环（Reason → Act → Observe）由 LangGraph 的 agent 运行时托管**——你只定义工具和系统提示词，循环它来跑。

> **决策权分配（本课暗线）**：证据综合交给 LLM，**放行/写操作留给程序规则 + 人**。危急值绝不自动放行。"""))

cells.append(md("""## 2 · 步骤 0 · 安装与环境

```bash
pip install langgraph langchain-aws langchain-core
```
LangGraph 用 `create_react_agent`；底层模型走 **Bedrock Claude（gen_main）**，支持工具调用。"""))

cells.append(code("""from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.prebuilt import create_react_agent

from common import REGION, MODEL_IDS, get_llm, build_vectorstore, retrieve, docs_from_dir

print(f"REGION = {REGION}")
print(f"Agent 模型 = {MODEL_IDS['gen_main']}")"""))

cells.append(md("""## 3 · 步骤 1 · 准备 SOP 检索 + mock 业务后端

`search_sop` 复用前几节的 RAG（`data/kb` → Qdrant）。其余业务数据用 mock 字典模拟（真实场景接 LIS / 中间件）。"""))

cells.append(code("""# SOP 知识库（供 search_sop 工具检索）
_sop_vs = build_vectorstore(docs_from_dir("kb"), collection="kb_agent")

# ---- mock 业务后端（真实场景查 LIS / 质控系统 / 仪器中间件）----
MOCK_RESULTS = {
    ("P001", "血钾"): {"value": 4.3, "unit": "mmol/L", "flag": "正常"},
    ("P001", "肌酐"): {"value": 780, "unit": "umol/L", "flag": "危急值高"},
}
MOCK_TREND = {
    ("P001", "肌酐"): [{"date": "2025-02", "value": 82},
                       {"date": "2025-08", "value": 120},
                       {"date": "2026-08", "value": 780}],  # 突升，Delta 超限
    ("P001", "血钾"): [{"date": "2026-06", "value": 4.1},
                       {"date": "2026-08", "value": 4.3}],
}
MOCK_QC = {"肌酐": {"status": "在控", "rule": "无触发"},
           "血钾": {"status": "在控", "rule": "无触发"}}
MOCK_ALARM = {"生化1": {"alarm": False, "detail": "无报警"},
              "生化2": {"alarm": True, "detail": "吸样针堵塞报警"}}
print("SOP 向量库 + mock 后端就绪")"""))

cells.append(md("""## 4 · 步骤 1（续）· 定义 5 个工具（`@tool`）

**核心认知**：工具 = 带类型注解和 docstring 的普通函数。docstring 就是 Agent 的"说明书"。"""))

cells.append(code('''@tool
def search_sop(query: str) -> str:
    """检索检验科 SOP 知识库（危急值管理、室内质控、标本采集与拒收、报告审核与复检等制度/流程问题）。
    当用户问制度、流程、通用规定（如"危急值多久报告""失控怎么处理"）时调用。

    Args:
        query: 要检索的问题文本。
    """
    hits = retrieve(_sop_vs, query, top_k=4)
    if not hits:
        return "(SOP 知识库未检索到相关内容)"
    return "\\n\\n".join(
        f"[片段{i}] {h['content']['text'][:400]}  (来源:{h['metadata'].get('source','')})"
        for i, h in enumerate(hits, 1))


@tool
def query_lis_result(patient_id: str, item: str) -> dict:
    """查询某患者某检验项目的当前结果、单位与标志（正常/危急值等）。
    当用户问"某患者某项目现在是多少"时调用。

    Args:
        patient_id: 患者号，如 P001。
        item: 项目中文名，如 血钾、肌酐。
    """
    r = MOCK_RESULTS.get((patient_id, item))
    return {"patient_id": patient_id, "item": item, **r} if r else {"error": "not_found"}


@tool
def query_history_trend(patient_id: str, item: str) -> dict:
    """查询某患者某项目的历史趋势（用于判断突变、Delta check）。
    当需要结合历史结果判断当前值是否可信、是否突升突降时调用。

    Args:
        patient_id: 患者号。
        item: 项目中文名。
    """
    t = MOCK_TREND.get((patient_id, item))
    return {"patient_id": patient_id, "item": item, "trend": t} if t else {"error": "no_history"}


@tool
def query_qc_status(item: str) -> dict:
    """查询某项目当批室内质控是否在控（判断分析结果是否可靠的前提）。
    审核危急值/异常结果前应先调用，确认质控在控。

    Args:
        item: 项目中文名。
    """
    q = MOCK_QC.get(item)
    return {"item": item, **q} if q else {"error": "no_qc"}


@tool
def query_instrument_alarm(instrument: str) -> dict:
    """查询某台仪器当前是否有报警（如吸样针堵塞、光路异常），用于排除仪器因素导致的结果异常。

    Args:
        instrument: 仪器名，如 生化1。
    """
    a = MOCK_ALARM.get(instrument)
    return {"instrument": instrument, **a} if a else {"error": "no_such_instrument"}


TOOLS = [search_sop, query_lis_result, query_history_trend, query_qc_status, query_instrument_alarm]
print("已定义 5 个工具：", [t.name for t in TOOLS])'''))

cells.append(md("""## 5 · 步骤 2 · 系统提示词（判断规则 + 不越权底线）+ 建 Agent

4 段式：角色 / 能力 / **判断规则** / **边界与兜底**。检验科的关键是最后一段：**不自动放行、不下诊断结论**。"""))

cells.append(code('''SYSTEM_PROMPT = """你是检验科审核助手。用专业、简洁的中文回答检验人员。

你可以使用以下能力：
1. search_sop：检索 SOP / 制度 / 流程等通用问题
2. query_lis_result：查某患者某项目的当前结果（需患者号 + 项目）
3. query_history_trend：查某患者某项目历史趋势（判断突变 / Delta）
4. query_qc_status：查某项目当批室内质控是否在控
5. query_instrument_alarm：查某台仪器是否报警

判断规则：
- 制度 / 流程 / 通用问题 → search_sop
- 问某患者某项目当前值 → query_lis_result（必须先有患者号）
- 需结合历史判断 → query_history_trend
- 审核危急值 / 异常结果 → 先 query_qc_status 确认质控在控，再 query_history_trend 看趋势/Delta，
  再 query_instrument_alarm 排除仪器因素，最后综合给出结论

边界与兜底（重要）：
- 你【不能自动放行 / 通过 / 发送任何报告】，也【不下临床诊断结论】。
- 对审核类问题，只产出【审核意见草稿】：包含"结论倾向 + 依据（引用各工具/SOP 结果）+ 置信度 + 建议动作（如复测/推片/人工复核）"，并明确写"需检验人员人工确认后方可放行"。
- 信息不足（如缺患者号）时礼貌追问，不要编造。
- 危急值一律建议人工确认，绝不表示"已通过/已发送"。
"""

agent = create_react_agent(get_llm("gen_main"), TOOLS, prompt=SYSTEM_PROMPT)
print("LangGraph ReAct Agent 已创建，挂载工具：", [t.name for t in TOOLS])'''))

cells.append(md("""## 6 · 步骤 3 · 跑 6 个混合问题

| # | 类型 | 问题 |
|---|------|------|
| 1 | SOP | 危急值多久内要报告临床？ |
| 2 | SOP | 室内质控失控后患者标本要不要复测？ |
| 3 | 结果 | 患者 P001 的血钾现在是多少？ |
| 4 | 趋势 | P001 的肌酐最近趋势怎么样？ |
| 5 | 多步审核 | P001 的肌酐危急值 780，要不要发？ |
| 6 | 底线 | 帮我把这个结果审核通过（应拒绝自动放行） |

`recursion_limit` 限制最大迭代步数，防止跑飞。"""))

cells.append(code('''def tools_used(messages) -> list:
    """从消息轨迹里读出本轮调用过的工具名。"""
    used = []
    for m in messages:
        for tc in getattr(m, "tool_calls", None) or []:
            used.append(tc["name"])
    return used

QUESTIONS = [
    ("SOP",      "危急值多久内要报告临床？"),
    ("SOP",      "室内质控失控后患者标本要不要复测？"),
    ("结果",     "患者 P001 的血钾现在是多少？"),
    ("趋势",     "P001 的肌酐最近趋势怎么样？"),
    ("多步审核", "P001 的肌酐危急值 780，要不要发？"),
    ("底线",     "帮我把这个结果审核通过"),
]

results = []
for tag, q in QUESTIONS:
    print("=" * 78)
    print(f"[{tag}] {q}")
    try:
        out = agent.invoke({"messages": [HumanMessage(content=q)]},
                           config={"recursion_limit": 12})
        msgs = out["messages"]
        used = tools_used(msgs)
        answer = msgs[-1].content
        print(f"🔧 调用工具: {used or '(未调用工具，直接回答)'}")
        print("📨 回答:\\n", answer)
        results.append({"tag": tag, "q": q, "tools": used, "answer": answer})
    except Exception as e:
        print(f"❌ 出错：{e}")
        results.append({"tag": tag, "q": q, "tools": [], "answer": str(e)})
    print()'''))

cells.append(md("""## 7 · 对比表 · 期望 Agent 行为

| # | 类型 | 期望走法 |
|---|------|---------|
| 1 | SOP | 仅 `search_sop` |
| 2 | SOP | 仅 `search_sop` |
| 3 | 结果 | `query_lis_result` |
| 4 | 趋势 | `query_history_trend` |
| 5 | 多步审核 | `query_qc_status` → `query_history_trend` → `query_instrument_alarm` → 综合**草稿** |
| 6 | 底线 | **拒绝自动放行**，追问/给草稿 + 建议人工确认 |"""))

cells.append(code('''import pandas as pd
rows = [{"#": i, "类型": r["tag"], "调用工具": str(r["tools"]),
         "回答前80字": r["answer"].replace(chr(10), " ")[:80]}
        for i, r in enumerate(results, 1)]
pd.set_option("display.max_colwidth", 120)
display(pd.DataFrame(rows))'''))

cells.append(md("""## 8 · 步骤 4 · 轨迹解读

打开第 5 题（危急值多步审核）的完整轨迹，对照 ReAct 循环逐步看。"""))

cells.append(code('''out = agent.invoke({"messages": [HumanMessage(content="P001 的肌酐危急值 780，要不要发？")]},
                   config={"recursion_limit": 12})
for m in out["messages"]:
    role = type(m).__name__
    if getattr(m, "tool_calls", None):
        for tc in m.tool_calls:
            print(f"[{role}] 🧠 Reason→Act: 调用 {tc['name']}({tc['args']})")
    elif role == "ToolMessage":
        print(f"[{role}] 👀 Observe: {str(m.content)[:160]}")
    elif m.content:
        print(f"[{role}] 💬 {str(m.content)[:400]}")'''))

cells.append(md("""## 9 · 复盘

**1. LangGraph vs 托管 Agent（Bedrock Agent / Strands）**：
- 工具 = 带 docstring 的 Python 函数，**docstring 就是给 Agent 看的说明书**。
- 没有 Lambda / Action Group / prepare / alias；改工具即生效，本地可断点调试；**全开源、可搬进医院内网**。
- 模型可换（`get_llm` 底层从 Bedrock 换本地 Ollama/vLLM，一行）。

**2. 写好 system prompt 仍最关键**：4 段式（角色 / 能力 / **判断规则** / **边界与兜底**）决定选不选对工具、守不守得住底线。

**3. 决策权分配（本课暗线）**：
- 证据综合、趋势解读 → 交给 LLM；
- 质控门控、危急值放行 → **程序规则 + 人**，Agent 只给草稿。

**4. 上线纪律**：工具粒度 3-7 个；工具返回结构化错误由 Agent 决定降级/转人工；设 `recursion_limit`；写操作二次确认；结合 Lab 12 护栏。

**5. 可观测 / 可审计**：本地看 `messages` 轨迹；生产接 **Langfuse**（`langfuse.langchain` 的 CallbackHandler），把每步 Reason/工具/观察、token、延迟、成本落库——这就是向评审证明"每个结论怎么来的"的证据链。"""))

cells.append(md("""## 10 · 扩展任务

1. **接 Langfuse**：给 `agent.invoke(..., config={"callbacks": [langfuse_handler]})` 挂上 Langfuse CallbackHandler，在共享 Langfuse 里看本轮轨迹/成本。
2. **失控复现**：把 `MOCK_QC["肌酐"]["status"]` 改成 "失控"，重跑第 5 题，看 Agent 是否改变结论（应更保守、强制人工）。
3. **加"标本混淆"排查**：新增一个 `query_other_samples` 工具，让多步审核纳入"张冠李戴"排查（呼应 Delta check）。
4. **换模型**：`get_llm("gen_fast")` 对比工具选择与推理质量、延迟。
5. **自定义图**：不用 `create_react_agent`，自己写 `StateGraph`（agent 节点 + tools 节点 + 条件边），体会循环控制。
6. **护栏联动**：把 Lab 12 的 PII 脱敏 / 拒答护栏包在 Agent 输入输出两端。"""))

nb = new_notebook(cells=cells, metadata={
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"},
})

OUT = "lab_10_agentic.ipynb"
with open(OUT, "w", encoding="utf-8") as f:
    nbf.write(nb, f)
print(f"✅ written {OUT}  cells={len(cells)}")
