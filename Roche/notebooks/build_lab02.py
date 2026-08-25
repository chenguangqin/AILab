#!/usr/bin/env python3
"""生成 lab_02_chunking.ipynb（开源栈版 · 检验科场景）。

用法：python3 build_lab02.py
程序化生成，避免手写 JSON 转义 bug。参考 build_lab01.py 风格。
"""
from __future__ import annotations
import nbformat as nbf
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

md = new_markdown_cell
code = new_code_cell
cells = []

cells.append(md("""# Lab 2 · Chunking 不是切豆腐 — 多种切法对比 + 复杂 PDF

|     |     |
| --- | --- |
| **模块** | M3 · Chunking 策略与复杂文档处理 |
| **时长** | 50 min（切+建库 15 + 对比 25 + PDF 实战/复盘 10） |
| **形态** | 完整动手 |
| **关键产出** | 3 种切法效果对比表 + 真实 PDF 解析难点体感 |
| **技术栈** | LangChain splitters + Qdrant + Bedrock（全程本地，无 S3/控制台） |"""))

cells.append(md("""## 1. 背景与目标

M2 Lab 1 留下的坑：问 **"血钾的危急值上下限"** 这类**阈值表**问题时，RAG 答不全——因为整篇文档粗放入库/默认定长切片**把阈值表切碎了**。

本 Lab 做两件事：
1. 用 LangChain 的 3 种 splitter 对同一份**含表格的混排 SOP** 切片，对比检索效果；
2. 加载真实复杂 PDF（ISO 15189 / CNAS 规则），**亲历版面/表格解析的坑**。

**核心认知**：切法是决策不是默认；而复杂 PDF 的解析质量是 RAG 的地基。"""))

cells.append(md("""## 2. 环境准备

依赖：`pip install langchain-text-splitters langchain-experimental langchain-aws langchain-qdrant qdrant-client pymupdf pandas`
（`unstructured` 可选，用于对比 PDF 解析）"""))

cells.append(code("""import pandas as pd
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter
from langchain_core.documents import Document

from common import (
    load_text, load_pdf, build_vectorstore, retrieve,
    get_embeddings, show_chunks,
)

raw = load_text("m3/mixed.md")
print(f"混排 SOP 长度：{len(raw)} 字符")
print(raw[:300], "...")"""))

cells.append(md("""## 3. 步骤 1 — 三种切法

- **Fixed-size**：`RecursiveCharacterTextSplitter`，按字符定长切（会切碎表格）
- **结构分块**：`MarkdownHeaderTextSplitter`，按 #/##/### 标题切（表格整体保留）
- **语义分块**：`SemanticChunker`（langchain-experimental，可选；需嵌入模型）"""))

cells.append(code("""# --- 切法 A：Fixed-size（定长）---
fixed_splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=30)
fixed_docs = fixed_splitter.create_documents([raw])

# --- 切法 B：按 Markdown 结构 ---
md_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")]
)
struct_docs = md_splitter.split_text(raw)

# --- 切法 C：语义分块（可选，依赖 langchain-experimental + 嵌入）---
try:
    from langchain_experimental.text_splitter import SemanticChunker
    sem_splitter = SemanticChunker(get_embeddings())
    sem_docs = sem_splitter.create_documents([raw])
except Exception as e:
    print(f"[语义分块跳过] {type(e).__name__}: {e}")
    sem_docs = None

print(f"Fixed-size 切出片段：{len(fixed_docs)}")
print(f"结构分块  切出片段：{len(struct_docs)}")
print(f"语义分块  切出片段：{len(sem_docs) if sem_docs else '(跳过)'}")"""))

cells.append(md("""### 观察切片形态

对比"危急值阈值表"这段在两种切法下的完整性——Fixed-size 很可能把表格切成好几段。"""))

cells.append(code("""def find_chunk(docs, keyword):
    hits = [d.page_content for d in docs if keyword in d.page_content]
    return hits

print("=== Fixed-size 里含 '血钾' 的片段 ===")
for c in find_chunk(fixed_docs, "血钾"):
    print(repr(c[:180]), "\\n")

print("=== 结构分块 里含 '血钾' 的片段 ===")
for c in find_chunk(struct_docs, "血钾"):
    print(repr(c[:180]), "\\n")"""))

cells.append(md("""## 4. 步骤 2 — 各自建向量库

同一份文档、三种切法，分别建 Qdrant 向量库（内存，秒级；嵌入统一用 Titan——这是 M4 的引子）。"""))

cells.append(code("""stores = {}
stores["Fixed-size"] = build_vectorstore(fixed_docs, collection="lab2_fixed")
stores["结构分块"]   = build_vectorstore(struct_docs, collection="lab2_struct")
if sem_docs:
    stores["语义分块"] = build_vectorstore(sem_docs, collection="lab2_semantic")
print("已建向量库：", list(stores.keys()))"""))

cells.append(md("""## 5. 步骤 3 — 同一组问题，多种切法对比

5 个压力测试问题，每个都对应一种典型坑。我们看每种切法的 Top-3 检索里是否包含正确答案的关键信息。"""))

cells.append(code("""# (问题, 判定命中的关键词——出现即认为检索到了关键信息)
QUESTIONS = [
    ("血钾的危急值上下限分别是多少？", ["2.8", "6.5"]),
    ("危急值报告有哪些要求和例外？", ["10 分钟", "例外"]),
    ("标本采集后送检超 3 小时，血糖还能测吗？", ["代谢", "氟化钠"]),
    ("室内质控 1_3s 失控后的处理步骤有哪些？", ["停发", "定标"]),
    ("儿科与成人的危急值阈值有何不同？", ["儿科", "新生儿"]),
]

def hit(text, keys):
    return all(k in text for k in keys)

rows = []
for q, keys in QUESTIONS:
    row = {"问题": q}
    for name, vs in stores.items():
        hits = retrieve(vs, q, top_k=3)
        joined = " ".join(h["content"]["text"] for h in hits)
        row[name] = "✅ 命中" if hit(joined, keys) else "❌ 缺失"
    rows.append(row)

df = pd.DataFrame(rows)
pd.set_option("display.max_colwidth", 40)
df"""))

cells.append(md("""## 6. 复盘（切法差异）

**预期**：
- 阈值表题（Q1）、跨表对比题（Q5）：Fixed-size 常"❌ 缺失"（表被切碎），结构分块更完整。
- 长流程题（Q4）、条款例外题（Q2）：Fixed-size 易截断，结构/语义分块更完整。

**结论**：检验科 SOP + 表格场景，**结构分块（或父子分块）整体最佳**。切法是决策不是默认。

> 单独看某题的检索原文：`show_chunks(retrieve(stores["Fixed-size"], "血钾 危急值", top_k=3))`"""))

cells.append(md("""## 7. 步骤 4 — 复杂 PDF 解析实战（检验科的硬骨头）

真实 SOP/标准多是复杂排版 PDF。先用 PyMuPDF 加载，看看**表格/多栏版面被解析成什么样**——这是 RAG 的"地基"，解析阶段丢的信息，后面切法再好也救不回。"""))

cells.append(code("""pages = load_pdf("pdf/ISO15189.pdf")
print(f"ISO15189.pdf 页数：{len(pages)}")

# 打印中间某页，观察版面/表格是否错乱（行列错位、跨栏串行）
sample = pages[len(pages)//2]
print("=== 某页 PyMuPDF 解析结果（前 800 字）===")
print(sample.page_content[:800])"""))

cells.append(code("""# 可选：对比 unstructured 的版面感知解析（需 pip install "unstructured[pdf]"，较慢）
try:
    from langchain_community.document_loaders import UnstructuredPDFLoader
    u_pages = UnstructuredPDFLoader("data/pdf/ISO15189.pdf", mode="elements").load()
    print(f"unstructured 解析出元素：{len(u_pages)}")
    print(u_pages[0].page_content[:300])
except Exception as e:
    print(f"[unstructured 跳过] {type(e).__name__}: {e}")
    print("提示：pip install 'unstructured[pdf]'（需 poppler 等系统依赖）")"""))

cells.append(md("""## 8. 复盘讨论

1. **切法决定检索**：同一文档、同一问题，切法不同，答案从"完整"到"完全错"。
2. **解析是地基**：复杂 PDF 的表格常被解析乱（行列错位/跨栏串行）——这是检验科 RAG 最容易被忽视、却最致命的一环。
3. **隐藏的坑（引出 M4）**：即使切法对了，中英混杂术语的问题检索仍可能答非所问——问题出在 **Embedding**。

## 9. 扩展任务

1. 改 `chunk_size` 到 800 再跑 Q1/Q4，看阈值表/长流程召回变化。
2. 用 `ParentDocumentRetriever` 实现父子分块（小块检索、大块给 LLM），对比 Q5 跨表题。
3. 用 `unstructured` 的 `partition_pdf(strategy="hi_res")` 提取表格，对比 PyMuPDF 的纯文本抽取。
4. 换本地嵌入：`build_vectorstore(struct_docs, collection="lab2_local", provider="local")`（bge-m3），对比检索——这就是 on-prem 落地形态。
5. 给结构分块的 chunk 打 Metadata（章节名已在 `metadata` 里），为 M5 的元数据过滤做准备。"""))

nb = new_notebook(cells=cells, metadata={
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"},
})

OUT = "lab_02_chunking.ipynb"
with open(OUT, "w", encoding="utf-8") as f:
    nbf.write(nb, f)
print(f"✅ written {OUT}  cells={len(cells)}")
