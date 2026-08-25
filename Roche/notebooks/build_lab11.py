#!/usr/bin/env python3
"""生成 lab_11_bad_case_loop.ipynb（开源栈版 · 检验科场景）。
程序化生成，避免手写 JSON 转义 bug。修改后重跑覆盖。"""
from __future__ import annotations
import nbformat as nbf
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

md, code = new_markdown_cell, new_code_cell
cells = []

cells.append(md("""# Lab 11 · Bad Case 闭环 — 检验科知识助手的持续优化

|     |     |
| --- | --- |
| **模块** | M12 · 自进化 RAG + Bad Case 闭环 |
| **时长** | 35 min（归因 10 + 改进 15 + 回归 10） |
| **形态** | 完整动手（分组） |
| **关键产出** | 一次完整的"收集 → 归因 → 改进 → 回归验证"闭环 + 改进对比表 |
| **技术栈** | LangChain + Qdrant + Bedrock Claude（全开源栈，本地可跑） |

**闭环纪律**：**没有归因就别动手，没有回归集就别上线。**"""))

cells.append(md("""## 1. 背景

检验科知识助手上线后，每天会有答错/答不全的 Bad Case 涌进来。本 Lab 用 10 条真实感 Bad Case，走一遍工程化闭环：
- **① 收集**：`data/bad_cases.json`（已备）
- **② 归因**：三类根因——**检索问题 / 生成问题 / 知识库缺失**
- **③ 改进**：按归因对症下药
- **④ 回归验证**：复用 M9 的评估集，确认"修好目标 case 且不引入新错"

> **归因铁律**：先看检索 Top-K。正确内容根本没召回 → 改 Prompt 一万遍也没用。"""))

cells.append(md("""## 2. 环境准备与建库"""))

cells.append(code("""import json
import pandas as pd
from IPython.display import display

from common import (
    docs_from_dir, build_vectorstore, retrieve, rag_answer, invoke_llm, DATA_DIR,
)

# 建知识库（复用 4 份检验科 SOP）
docs = docs_from_dir("kb")
vs = build_vectorstore(docs, collection="kb_lab11")
print(f"知识库就绪：{len(docs)} 份 SOP")

# 载入 Bad Case
bad_cases = json.loads((DATA_DIR / "bad_cases.json").read_text(encoding="utf-8"))
print(f"Bad Case：{len(bad_cases)} 条")"""))

cells.append(md("""## 3. 步骤 ① + ② — 逐条归因（先看检索，再下结论）

对每条 Bad Case：
1. 用 `retrieve` 看 Top-K 检索片段（**不走 LLM**）；
2. 判断根因：
   - **检索问题**：Top-K 里没有正确依据（召回失败 / 表被切碎）
   - **生成问题**：Top-K 里有正确依据，但回答跑偏
   - **知识库缺失**：知识库根本没有这内容"""))

cells.append(code("""def show_topk(q, k=3):
    hits = retrieve(vs, q, top_k=k)
    for i, h in enumerate(hits, 1):
        src = h["metadata"].get("source", "")
        print(f"  #{i} [{src}] {h['content']['text'][:120].strip()}...")
    return hits

for c in bad_cases:
    print("="*80)
    print(f"[{c['id']}] {c['question']}")
    print(f"  ❌ 错误回答：{c['bad_answer']}")
    print(f"  检索 Top-3：")
    show_topk(c["question"])
    print(f"  💡 参考归因：{c['suspected_category']}  —— {c['note']}")"""))

cells.append(md("""### 归因小结（学员填写）

对照上面的检索结果，把 10 条归类。这是**分组讨论**环节——业务同学主导判断，开发同学核对检索。

| 归因类别 | Bad Case 编号 | 判断依据 |
|---------|-------------|---------|
| 检索问题 | （填） | Top-K 未含正确依据 |
| 生成问题 | （填） | Top-K 有依据但答错 |
| 知识库缺失 | （填） | Top-K 全不相关 |"""))

cells.append(md("""## 4. 步骤 ③ — 现场改进（从 3 类中选 2 类实施）

### 改进 A · 生成问题 → 收紧 Prompt（以 BC06 为例）
BC06 检索命中了"从采集时间起算"，但模型答成接收时间。用更严格的 Prompt 强制"只依据片段、逐字对齐关键数值"。"""))

cells.append(code("""STRICT_PROMPT = '''你是检验科知识助手。只依据下列【检索片段】回答，逐字核对关键数值与条件，不得改写或凭常识补充。
片段没有明确写到的，回答"知识库中未找到明确依据"。在关键结论后用 [片段N] 标注来源。

【检索片段】
{context}

【问题】
{question}

【回答】'''

q = "标本超时的时限从什么时候开始算？"
before = rag_answer(vs, q)["answer"]
after  = rag_answer(vs, q, prompt_template=STRICT_PROMPT)["answer"]
print("改进前：", before, "\\n")
print("改进后：", after)"""))

cells.append(md("""### 改进 B · 检索问题 → 加 metadata 过滤 / 提高 top_k（以 BC08 Delta check 为例）
BC08 未召回报告审核 SOP 中的 Delta check 段。演示两种低成本改进：提高 `top_k`、按来源过滤到相关 SOP。"""))

cells.append(code("""q = "Delta check 是用来做什么的？"
print("top_k=3 检索：")
_ = [print("  ", h["metadata"].get("source"), h["content"]["text"][:60].strip()) for h in retrieve(vs, q, top_k=3)]
print("\\ntop_k=6 检索（更宽召回）：")
_ = [print("  ", h["metadata"].get("source"), h["content"]["text"][:60].strip()) for h in retrieve(vs, q, top_k=6)]
print("\\n改进后回答（top_k=6）：")
print(rag_answer(vs, q, top_k=6, prompt_template=STRICT_PROMPT)["answer"])"""))

cells.append(md("""### 改进 C · 知识库缺失 → 写工单给运营（不现场补内容）
BC03（肌钙蛋白方法学）、BC07（新生儿专用阈值表）属于知识库缺失。**正确动作不是改代码，是提工单补内容**（这是 L3 自进化的雏形）。"""))

cells.append(code('''KB_GAP_TICKET = """
# 知识库补充工单
- 触发 Bad Case：BC03 / BC07
- 缺失内容：
  1. 各项目方法学原理与性能参数（肌钙蛋白等）
  2. 特殊人群（新生儿/儿科）专用危急值阈值表
- 建议来源：厂商说明书 / 科室专用阈值 SOP
- 责任人：____   截止：____
- 补充后动作：重新 build_vectorstore 重建索引 → 回归验证
"""
print(KB_GAP_TICKET)'''))

cells.append(md("""## 5. 步骤 ④ — 回归验证（防止"按下葫芦浮起瓢"）

用 M9 的评估集做回归：修好目标 case 的同时，**原本对的题不能变错**。

> 若 `data/eval_30.json` 尚未由 M9（Lab 8）产出，本段用 `[WARN]` 容错，不会崩。"""))

cells.append(code('''def llm_judge(question, answer, ground_truth):
    """极简 LLM 判分：答案要点是否覆盖 ground_truth（0/1）。仅作回归雏形。"""
    p = (f"问题：{question}\\n参考答案要点：{ground_truth}\\n"
         f"待评回答：{answer}\\n"
         "上述回答是否覆盖了参考答案的关键要点且无明显错误？只回答 1（是）或 0（否）。")
    r = invoke_llm(p, max_tokens=4).strip()
    return 1 if r.startswith("1") else 0

eval_fp = DATA_DIR / "eval_30.json"
if not eval_fp.exists():
    print("[WARN] 未找到 data/eval_30.json（由 M9/Lab8 产出）。回归步骤跳过；")
    print("       实操中：改进前后各跑一遍评估集，对比整体得分与单题得分。")
else:
    eval_set = json.loads(eval_fp.read_text(encoding="utf-8"))[:10]  # 取前 10 题做演示
    rows = []
    for e in eval_set:
        q, gt = e["question"], e.get("ground_truth", "")
        base = rag_answer(vs, q)["answer"]
        new  = rag_answer(vs, q, prompt_template=STRICT_PROMPT)["answer"]
        rows.append({"question": q[:24],
                     "旧版": llm_judge(q, base, gt),
                     "新版": llm_judge(q, new, gt)})
    df = pd.DataFrame(rows)
    print(f"旧版得分：{df['旧版'].mean():.2f}   新版得分：{df['新版'].mean():.2f}")
    display(df)'''))

cells.append(md("""## 6. 🚪 上线门 Checklist（强制）

改完必须逐项打勾，缺一不上线：

- [ ] 修复目标 Bad Case 已通过
- [ ] 回归集整体得分 ≥ 旧版（不退化）
- [ ] 没有原本对的题变错
- [ ] 知识库缺失类已提工单（而非硬编码绕过）
- [ ] 灰度方案确定（先小流量 → 全量）

> **检验科语境**：这套"归因 + 回归 + 上线门"本质就是你们熟悉的**变更验证纪律**——任何规则/Prompt 改动都要能证明"改对了且没改坏"。"""))

cells.append(md("""## 7. 复盘 + 三层自进化成熟度

**闭环收获**：Bad Case 闭环 = "收集 → 归因 → 改进 → 回归 → 上线门"，**纪律比技巧重要**。

**自进化三层次（坦诚区分工程实践 / 研究方向）**：

| 层次 | 做什么 | 现状 |
|------|-------|------|
| **L1** 反馈驱动检索调优 | 点赞/点踩、被拒答问题 → 调权重/加 metadata | ✅ 可立刻落地 |
| **L2** 评估驱动自动优化 | 定时跑评估 → 定位低分 → 建议调参（**人工把关上线**） | 🟡 评估体系成熟后可做 |
| **L3** 日志驱动知识库更新 | 聚类"无答案"问题 → 推工单给运营（**人工写内容**） | 🔴 偏前沿，别轻易承诺 |

**边界铁律**：自动化止步于"上线生效"前一步；规则/口径的最终确权必须人工——这正是检验科可审计文化的要求。

## 8. 扩展任务
1. 把"归因 → 改进"写成可复用函数，输入 Bad Case 输出建议根因。
2. 对"知识库缺失"类：真的补一段内容进 `data/kb/`，重建索引后回归，看 BC03/BC07 是否修复。
3. 用 RAGAs（M9）替换极简 `llm_judge`，做更严谨的回归。"""))

nb = new_notebook(cells=cells, metadata={
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"},
})
OUT = "lab_11_bad_case_loop.ipynb"
with open(OUT, "w", encoding="utf-8") as f:
    nbf.write(nb, f)
print(f"✅ written {OUT}  cells={len(cells)}")
