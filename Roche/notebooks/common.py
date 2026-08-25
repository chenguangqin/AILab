"""
RAG 工程化落地实战 — Lab 共享工具（开源栈版 · 罗氏检验科场景）
====================================================================

设计原则（与本课程"厂商中立 + 可本地部署"承诺一致）：

- **生成模型走 Bedrock Claude**（培训环境已开通），但通过 LangChain 的
  `ChatBedrockConverse` 封装 —— 换成本地 Ollama / vLLM 只改一行 `get_llm()`。
- **其余全部开源、可在医院本地/EC2 部署**：
    向量库   → Qdrant          (langchain-qdrant + qdrant-client)
    嵌入     → Bedrock Titan（默认，培训环境有）/ BAAI/bge-m3（本地可落地，一行切换）
    重排     → BAAI/bge-reranker-v2-m3（本地 cross-encoder，不依赖任何托管服务）
    编排     → LangGraph（Agentic RAG，Lab 10）
    评估     → RAGAs（Lab 8）
    图谱     → NetworkX（Lab 9）

- **模型边界（"除 Bedrock 模型外全部开源"）**：
    生成 = Bedrock Claude；嵌入 = Bedrock Titan（可切 bge-m3）；重排 = 本地开源。
    → 罗氏产品真正本地部署时，把嵌入切到 bge-m3、生成切到本地 Qwen/vLLM 即可，
      检索/重排/编排/评估代码一字不改。这正是"技能可带走"的落点。

使用前请确认：
- 已配置 AWS 凭证（EC2 实例角色 / aws configure / 环境变量）
- Bedrock 已开通 Claude（生成）与 Titan Embeddings（嵌入）
- 开课前跑一遍 `python3 check_models.py` 用最小真实调用验证模型可调
- 依赖见本目录 requirements 说明 / README.md
"""

from __future__ import annotations

import functools
import json
import os
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------
# 全局配置
# --------------------------------------------------------------------

REGION = os.environ.get("AWS_REGION", "us-west-2")

# 嵌入 provider 默认值：培训环境用 Bedrock Titan；本地/离线演示可设为 "local"（bge-m3）。
# 也可在调用 get_embeddings(provider=...) 时按 Lab 需要临时覆盖。
EMBED_PROVIDER = os.environ.get("RAG_EMBED_PROVIDER", "bedrock")  # "bedrock" | "local"

# 模型 ID 速查
# --------------------------------------------------------------------
# 说明：本环境生成模型 = Bedrock Claude Sonnet 4.6；嵌入 = Bedrock Titan V2。
#   可用环境变量覆盖（学员本地/换环境时）：
#     BEDROCK_CHAT_MODEL_ID   (默认 us.anthropic.claude-sonnet-4-6)
#     BEDROCK_EMBED_MODEL_ID  (默认 amazon.titan-embed-text-v2:0)
#   嵌入 Titan V2（dim 1024）与本地开源 bge-m3（同为 dim 1024）互换无需改索引维度。
_CHAT_ID  = os.environ.get("BEDROCK_CHAT_MODEL_ID", "us.anthropic.claude-sonnet-4-6")
_EMBED_ID = os.environ.get("BEDROCK_EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")

MODEL_IDS = {
    # ---- 生成（Bedrock Claude Sonnet 4.6，实测可用）----
    "claude_main":  _CHAT_ID,

    # ---- 生成档位语义键（各 Lab 统一引用这三个，切模型只改这里）----
    # 本环境仅确认 Sonnet 4.6 可用；如另开通 haiku/opus，可把 fast/strong 指过去。
    "gen_fast":     _CHAT_ID,   # 快/省档（如开通 us.anthropic.claude-haiku-4-5 可换）
    "gen_main":     _CHAT_ID,   # 默认主力 = Sonnet 4.6
    "gen_strong":   _CHAT_ID,   # 强推理档（如开通 us.anthropic.claude-opus-4-6 可换）

    # ---- 嵌入 ----
    "titan_text_v2": _EMBED_ID,                               # Bedrock 默认（培训环境）
    "bge_m3":        "BAAI/bge-m3",                            # 本地开源、多语言、中文强、on-prem 可落地

    # ---- 重排（本地开源 cross-encoder）----
    "bge_reranker":  "BAAI/bge-reranker-v2-m3",
}

# 数据目录约定（讲师统一打包）
DATA_DIR = Path(__file__).resolve().parent / "data"

# Qdrant 存储位置：默认进程内内存库（课程规模足够、零运维）；
# 生产/EC2 用真实容器时设 RAG_QDRANT_URL=http://localhost:6333。
QDRANT_URL = os.environ.get("RAG_QDRANT_URL", "")  # 空 = 内存模式

# --------------------------------------------------------------------
# 生成模型（Bedrock Claude，经 LangChain 封装 → provider 无关）
# --------------------------------------------------------------------

@functools.lru_cache(maxsize=8)
def get_llm(model: str = "gen_main", temperature: float = 0.0, max_tokens: int = 1024):
    """返回一个 LangChain Chat 模型对象（默认 Bedrock Claude via Converse）。

    换本地部署：把下面两行替换为
        from langchain_ollama import ChatOllama
        return ChatOllama(model="qwen2.5:14b", temperature=temperature)
    其余检索/编排/评估代码完全不变 —— 这就是"厂商中立薄封装"。
    """
    from langchain_aws import ChatBedrockConverse

    return ChatBedrockConverse(
        model=MODEL_IDS.get(model, model),
        region_name=REGION,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def invoke_llm(prompt: str, *, model: str = "gen_main",
               system: str | None = None, max_tokens: int = 1024,
               temperature: float = 0.0) -> str:
    """便捷调用：发一个 prompt，返回纯文本回答。"""
    llm = get_llm(model=model, temperature=temperature, max_tokens=max_tokens)
    messages: list[Any] = []
    if system:
        messages.append(("system", system))
    messages.append(("human", prompt))
    resp = llm.invoke(messages)
    return resp.content if isinstance(resp.content, str) else str(resp.content)


# 迁移期兼容别名（旧 Lab 里可能写了 invoke_claude）
invoke_claude = invoke_llm

# --------------------------------------------------------------------
# 嵌入（Bedrock Titan 默认 / bge-m3 本地开源，一行切换）
# --------------------------------------------------------------------

@functools.lru_cache(maxsize=4)
def get_embeddings(provider: str | None = None):
    """返回 LangChain Embeddings 对象。

    provider="bedrock" → Bedrock Titan（培训环境默认）
    provider="local"   → BAAI/bge-m3（HuggingFace，本地/离线；首次会下载权重）
    provider=None      → 用全局 EMBED_PROVIDER（默认 "bedrock"）
    两者维度均为 1024，互换不需重建向量库维度。
    """
    provider = provider or EMBED_PROVIDER
    if provider == "local":
        from langchain_huggingface import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(
            model_name=MODEL_IDS["bge_m3"],
            encode_kwargs={"normalize_embeddings": True},
        )
    # 默认 Bedrock Titan
    from langchain_aws import BedrockEmbeddings
    return BedrockEmbeddings(model_id=MODEL_IDS["titan_text_v2"], region_name=REGION)


def embed_text(text: str, *, provider: str | None = None) -> list[float]:
    """把一段文本编码成向量（便于讲清嵌入原理时单条演示）。"""
    return get_embeddings(provider).embed_query(text)

# --------------------------------------------------------------------
# 向量库（Qdrant，本地/内存，开源）
# --------------------------------------------------------------------

def _qdrant_client():
    """构造 Qdrant 客户端：默认内存模式（零运维），设 RAG_QDRANT_URL 则连真实服务。"""
    from qdrant_client import QdrantClient
    if QDRANT_URL:
        return QdrantClient(url=QDRANT_URL)
    return QdrantClient(location=":memory:")


def build_vectorstore(docs, *, collection: str = "rag_lab",
                      provider: str | None = None):
    """把一批 LangChain Document 建成 Qdrant 向量库并返回 vectorstore。

    docs: list[langchain_core.documents.Document]（含 page_content 与 metadata）
    返回: langchain_qdrant.QdrantVectorStore，可直接 .as_retriever() 或 similarity_search。
    """
    from langchain_qdrant import QdrantVectorStore
    embeddings = get_embeddings(provider)
    kwargs: dict[str, Any] = {"collection_name": collection}
    if QDRANT_URL:
        kwargs["url"] = QDRANT_URL
    else:
        kwargs["location"] = ":memory:"
    return QdrantVectorStore.from_documents(docs, embedding=embeddings, **kwargs)


def retrieve(vectorstore, query: str, *, top_k: int = 5,
             filter_: Any = None) -> list[dict]:
    """向量检索：返回 Top-K 片段，结构与旧 kb_retrieve 对齐，方便讲义/展示复用。

    返回: [{"score": float, "content": {"text": ...}, "metadata": {...}}, ...]
    """
    hits = vectorstore.similarity_search_with_score(query, k=top_k, filter=filter_)
    out = []
    for doc, score in hits:
        out.append({
            "score": float(score),
            "content": {"text": doc.page_content},
            "metadata": doc.metadata or {},
        })
    return out

# --------------------------------------------------------------------
# 重排（本地开源 bge-reranker-v2-m3，cross-encoder）
# --------------------------------------------------------------------

@functools.lru_cache(maxsize=1)
def _reranker():
    from sentence_transformers import CrossEncoder
    return CrossEncoder(MODEL_IDS["bge_reranker"])


def rerank(query: str, documents: list[str], *, top_n: int = 5) -> list[dict]:
    """对候选文档按与 query 的相关性重排（本地模型，无需任何托管服务）。

    参数：
        documents: 待重排的文本列表。
        top_n:     返回条数。
    返回：
        [{"index": 原始下标, "score": 相关性分数}, ...]，按分数降序。
    """
    if not documents:
        return []
    model = _reranker()
    scores = model.predict([(query, d) for d in documents])
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    return [{"index": i, "score": float(s)} for i, s in ranked[:top_n]]

# --------------------------------------------------------------------
# 一站式 RAG：检索 + 生成（带引用），替代旧的 kb_retrieve_and_generate
# --------------------------------------------------------------------

_DEFAULT_RAG_PROMPT = """你是罗氏检验科的知识助手。严格依据下面的【检索片段】回答问题。
规则：
- 只用检索片段中的信息，不要编造；片段里没有就明说"知识库中未找到相关依据"。
- 在关键结论后用 [片段N] 标注来源。
- 回答专业、简洁、面向检验科专业人员。

【检索片段】
{context}

【问题】
{question}

【回答】"""


def rag_answer(vectorstore, query: str, *, model: str = "gen_main",
               top_k: int = 5, prompt_template: str | None = None) -> dict:
    """检索 + 生成一站式。返回 {answer, contexts}（contexts 便于评估/溯源）。"""
    hits = retrieve(vectorstore, query, top_k=top_k)
    context = "\n\n".join(
        f"[片段{i}] {h['content']['text']}" for i, h in enumerate(hits, 1)
    )
    tmpl = prompt_template or _DEFAULT_RAG_PROMPT
    answer = invoke_llm(tmpl.format(context=context, question=query), model=model)
    return {"answer": answer, "contexts": [h["content"]["text"] for h in hits],
            "hits": hits}

# --------------------------------------------------------------------
# 展示与对比（沿用旧版，纯 stdout，稳定可靠）
# --------------------------------------------------------------------

def show_chunks(chunks: list[dict], *, max_chars: int = 200) -> None:
    """打印检索返回的片段，便于人眼对比。"""
    if not chunks:
        print("(no results)")
        return
    for i, c in enumerate(chunks, 1):
        score = c.get("score", float("nan"))
        text = c.get("content", {}).get("text", "")[:max_chars]
        src = (c.get("metadata", {}) or {}).get("source", "")
        print(f"#{i}  score={score:.4f}  src={src}")
        print(f"    {text!r}")
        print()


def side_by_side(left_title: str, left: str,
                 right_title: str, right: str, width: int = 60) -> None:
    """Notebook 输出中两栏对比（纯 stdout 版）。"""
    def wrap(s: str) -> list[str]:
        out = []
        for line in s.splitlines() or [""]:
            while len(line) > width:
                out.append(line[:width])
                line = line[width:]
            out.append(line)
        return out
    L, R = wrap(left), wrap(right)
    n = max(len(L), len(R))
    L += [""] * (n - len(L))
    R += [""] * (n - len(R))
    bar = "─" * width
    print(f"┌{bar}┬{bar}┐")
    print(f"│{left_title.ljust(width)}│{right_title.ljust(width)}│")
    print(f"├{bar}┼{bar}┤")
    for l, r in zip(L, R):
        print(f"│{l.ljust(width)}│{r.ljust(width)}│")
    print(f"└{bar}┴{bar}┘")

# --------------------------------------------------------------------
# 数据加载
# --------------------------------------------------------------------

def load_text(relpath: str) -> str:
    """加载数据文档（SOP / 标准条款 / 记录表等）。"""
    fp = DATA_DIR / relpath
    if not fp.exists():
        raise FileNotFoundError(f"数据文件不存在：{fp}")
    return fp.read_text(encoding="utf-8")


def load_eval_set(name: str = "eval_30.json") -> list[dict]:
    """加载评估集（讲师预备）。每条形如 {question, ground_truth, expected_chunks}。"""
    fp = DATA_DIR / name
    if not fp.exists():
        raise FileNotFoundError(
            f"评估集不存在：{fp}\n请向讲师索取或将文件放到 {DATA_DIR}/"
        )
    return json.loads(fp.read_text(encoding="utf-8"))


def load_pdf(relpath: str) -> list:
    """加载复杂排版 PDF（ISO15189 / CNAS 等），返回按页的 LangChain Document 列表。

    这是"能跑通"的基线加载器（PyMuPDF）；M3 会对比 unstructured / Docling 等
    更强的版面/表格解析方案 —— 复杂排版 PDF 正是检验科文档处理的核心难点。
    """
    from langchain_community.document_loaders import PyMuPDFLoader
    fp = DATA_DIR / relpath
    if not fp.exists():
        raise FileNotFoundError(f"PDF 不存在：{fp}")
    return PyMuPDFLoader(str(fp)).load()


def docs_from_dir(relpath: str, *, glob: str = "**/*.md") -> list:
    """把一个目录下的文本文件读成 LangChain Document 列表（带 source 元数据）。"""
    from langchain_core.documents import Document
    base = DATA_DIR / relpath
    docs = []
    for fp in sorted(base.glob(glob)):
        docs.append(Document(page_content=fp.read_text(encoding="utf-8"),
                             metadata={"source": str(fp.relative_to(DATA_DIR))}))
    return docs


__all__ = [
    "REGION", "MODEL_IDS", "DATA_DIR", "EMBED_PROVIDER", "QDRANT_URL",
    "get_llm", "invoke_llm", "invoke_claude",
    "get_embeddings", "embed_text",
    "build_vectorstore", "retrieve", "rerank", "rag_answer",
    "show_chunks", "side_by_side",
    "load_text", "load_eval_set", "load_pdf", "docs_from_dir",
]
