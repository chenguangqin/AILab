"""
一次性生成 Lab 1 / Lab 2 / Lab 3 的 Jupyter Notebook。
- 复用 common.py 中的所有工具（不重复造轮子）
- 控制台优先 + boto3 兜底（可选脚本路径）
- 所有 AWS 资源都用 # TODO 占位变量

运行：
    cd /Users/qcguang/Desktop/courses/RAG/notebooks
    python3 _build_labs.py
"""

from __future__ import annotations
import nbformat as nbf
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------- helpers

def md(src: str) -> dict:
    return nbf.v4.new_markdown_cell(src.strip("\n"))

def code(src: str) -> dict:
    return nbf.v4.new_code_cell(src.strip("\n"))

def make_notebook(cells: list[dict]) -> nbf.NotebookNode:
    nb = nbf.v4.new_notebook()
    nb["cells"] = cells
    nb["metadata"] = {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "name": "python",
            "version": "3.11",
        },
    }
    return nb

def save(nb: nbf.NotebookNode, name: str) -> Path:
    fp = OUT_DIR / name
    nbf.write(nb, fp)
    return fp


# =============================================================================
# Lab 1 · 跑通你的第一个客服机器人
# =============================================================================

LAB1_CELLS = [
    md("""
# Lab 1 · 跑通你的第一个客服机器人

|     |     |
| --- | --- |
| **模块** | M2 · 搭起第一个 RAG（Knowledge Bases 跑通） |
| **时长** | 40 min（演示 5 + 学员动手 30 + 复盘 5） |
| **形态** | 完整动手 |
| **角色** | 跨境电商客服 RAG MVP |
| **关键产出** | 一个能问 FAQ 的客服机器人雏形 + 一份"裸 LLM vs RAG"对比表 |
"""),

    md("""
## 1. 背景与目标

**场景**：跨境电商客服每天回答大量重复 FAQ（退换货、物流、会员、支付）。我们用 Bedrock Knowledge Bases 把 FAQ 文档变成一个能"开卷答题"的助手。

**数据**：4 份预备好的 FAQ Markdown（讲师已置于 S3，学员只需挑选自己的桶）：
- `faq-returns.md`（退换货）
- `faq-shipping.md`（物流）
- `faq-membership.md`（会员）
- `faq-payment.md`（支付）

**预期体感**：
- 第一次亲手把"文档摄入 → 切片 → 向量化 → 索引 → 检索 → 生成"6 步在控制台跑通
- 同一组中文问题，**裸 LLM** 与 **RAG** 的回答会有显著差异
- 引用（Citations）让回答可追溯

**要发现的坑**：
- 商品规格类问题（"iPhone 15 Pro 电池容量"）即使有 RAG 仍然答得糙 → **引出 M3 Chunking**
- 默认 Chunking 把表格拦腰切断，是后面要解决的核心问题
"""),

    md("""
## 2. 环境准备

> **前置条件**
> - 已配置 AWS 凭证（`aws configure` 或环境变量 `AWS_REGION` / `AWS_PROFILE`）
> - 已在 Bedrock 控制台开通：`Claude 3.5 Sonnet`、`Titan Text Embeddings v2`
> - IAM 角色具备 `AmazonBedrockFullAccess` + S3 读权限

填写下面 4 个 `# TODO` 变量后再执行其余 cell。
"""),

    code("""
# === 必改：学员根据自己环境修改下列占位符 ===
S3_BUCKET     = "rag-training-yourname"      # TODO 你自己的 S3 桶（已存在或可创建）
S3_PREFIX     = "faqs/"                      # TODO 上传 FAQ 用的 prefix
KB_NAME       = "kb-ecommerce-faq-v1"        # TODO 你的 KB 名字（可自由命名）
KB_ID         = "REPLACE_ME"                 # TODO 控制台创建 KB 后回填（kb-xxxxxxxxxxxx）
DATA_SOURCE_ID = "REPLACE_ME"                # TODO 控制台创建后回填（在 KB 详情页 Data sources 标签）

# === 通用导入（来自共享 common.py，不要重复造轮子）===
import boto3
import json
import pandas as pd
from IPython.display import display, Markdown

from common import (
    REGION, MODEL_IDS,
    s3_client, bedrock_runtime, bedrock_agent, bedrock_agent_runtime,
    invoke_claude, kb_retrieve, kb_retrieve_and_generate,
    show_chunks, side_by_side, wait_for_kb_sync,
    load_text,
)

print(f"AWS Region : {REGION}")
print(f"Bucket     : {S3_BUCKET}")
print(f"KB name    : {KB_NAME}")
print(f"KB id      : {KB_ID}")
"""),

    md("""
## 3. 步骤 1 — 把 4 份 FAQ 上传到 S3

**对应原理**：6 步流程的第 [1] 步「文档摄入」。

讲师已经把数据放到 `notebooks/data/faq/` 下，下面的 cell 会把它们 push 到你的 S3 桶。  
如果桶不在，请先到控制台 S3 创建（Region 必须与 Bedrock 一致）。
"""),

    code("""
from pathlib import Path

LOCAL_FAQ_DIR = Path("data/faq")  # 讲师预备的本地数据目录
files = [
    "faq-returns.md",
    "faq-shipping.md",
    "faq-membership.md",
    "faq-payment.md",
]

s3 = s3_client()
for fname in files:
    local = LOCAL_FAQ_DIR / fname
    if not local.exists():
        print(f"[WARN] 本地缺少 {local}，请向讲师索取数据包后再运行。")
        continue
    key = S3_PREFIX + fname
    s3.upload_file(str(local), S3_BUCKET, key)
    print(f"  uploaded → s3://{S3_BUCKET}/{key}")

# 列出确认
resp = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=S3_PREFIX)
for obj in resp.get("Contents", []):
    print(f"    s3 obj: {obj['Key']}  ({obj['Size']} bytes)")
"""),

    md("""
## 4. 步骤 2 — 创建 Knowledge Base（推荐控制台）

**对应原理**：6 步流程的第 [2][3][4] 步——切片 + 向量化 + 索引。

### 4.1 推荐路径：控制台一键创建（5–8 min）

> Bedrock → **Knowledge Bases** → **Create knowledge base**
>
> | 字段 | 推荐值 |
> | --- | --- |
> | Name | `kb-ecommerce-faq-v1` |
> | IAM role | *Create and use a new service role* |
> | Data source | S3，选 `s3://YOUR_BUCKET/faqs/` |
> | **Chunking strategy** | **Default**（≈ 300 tokens, 20% overlap） |
> | **Embeddings model** | **Titan Text Embeddings v2** |
> | **Vector store** | **Quick create**（OpenSearch Serverless） |
>
> 创建完成后回到本 Notebook，把 `KB_ID` / `DATA_SOURCE_ID` 回填到 cell 2。

### 4.2 可选脚本路径（boto3，仅给开发学员备用）

下面这个 cell 默认 **不会执行**（被 `if False` 包住），因为创建 KB 涉及 IAM 角色 / OpenSearch 集合，控制台一键完成更稳妥。如果你确实想脚本化，把 `False` 改成 `True` 并补全 IAM/集合参数。
"""),

    code("""
# 可选脚本路径：boto3 创建 KB（推荐控制台，本 cell 默认跳过）
if False:
    agent = bedrock_agent()
    # 1. 这里假设你已经预先准备好了 OpenSearch Serverless 集合 + IAM 角色
    KB_ROLE_ARN          = "arn:aws:iam::ACCOUNT:role/AmazonBedrockExecutionRoleForKB"  # TODO
    OSS_COLLECTION_ARN   = "arn:aws:aoss:REGION:ACCOUNT:collection/COLLECTION_ID"       # TODO
    OSS_VECTOR_INDEX     = "bedrock-knowledge-base-default-index"                       # TODO
    create_resp = agent.create_knowledge_base(
        name=KB_NAME,
        roleArn=KB_ROLE_ARN,
        knowledgeBaseConfiguration={
            "type": "VECTOR",
            "vectorKnowledgeBaseConfiguration": {
                "embeddingModelArn":
                    f"arn:aws:bedrock:{REGION}::foundation-model/{MODEL_IDS['titan_text_v2']}",
            },
        },
        storageConfiguration={
            "type": "OPENSEARCH_SERVERLESS",
            "opensearchServerlessConfiguration": {
                "collectionArn": OSS_COLLECTION_ARN,
                "vectorIndexName": OSS_VECTOR_INDEX,
                "fieldMapping": {
                    "vectorField": "bedrock-knowledge-base-default-vector",
                    "textField":   "AMAZON_BEDROCK_TEXT_CHUNK",
                    "metadataField": "AMAZON_BEDROCK_METADATA",
                },
            },
        },
    )
    print("created kb id =", create_resp["knowledgeBase"]["knowledgeBaseId"])
else:
    print("已跳过：请按 4.1 在控制台创建 KB，然后把 KB_ID / DATA_SOURCE_ID 填到 cell 2。")
"""),

    md("""
## 5. 步骤 3 — 触发 Sync（让数据真正进库）

控制台创建 KB 后只是建了"壳"——必须点 **Sync now** 才会真正切片 + 向量化 + 写索引。  
也可以用下面的 cell 触发并轮询直到完成（共享工具 `wait_for_kb_sync`）。
"""),

    code("""
assert KB_ID != "REPLACE_ME", "请先回到 cell 2 回填 KB_ID / DATA_SOURCE_ID"
assert DATA_SOURCE_ID != "REPLACE_ME"

status = wait_for_kb_sync(KB_ID, DATA_SOURCE_ID, max_wait=900, poll=15)
print("\\n最终状态:", status)
"""),

    md("""
## 6. 步骤 4 — 3 个中文问题：裸 LLM vs RAG

**对应原理**：6 步流程的第 [5][6] 步——检索 + 生成。

我们准备了 3 个中文问题，按"通用 → 跨文档 → 刁难"逐级递增：

| # | 问题 | 测试什么 |
| --- | --- | --- |
| Q1 | 退货政策是什么？多少天内可以退？ | 典型 FAQ 命中 |
| Q2 | 我下了订单怎么查物流？ | 跨文档（物流 FAQ） |
| Q3 | iPhone 15 Pro Max 的电池容量是多少？ | **故意刁难**（FAQ 没有这条） |

下面 cell 会同步发给：
1. **裸 LLM**（直接 `invoke_claude`，无任何检索）
2. **RAG**（`kb_retrieve_and_generate`，含引用）
"""),

    code("""
QUESTIONS = [
    "退货政策是什么？多少天内可以退？",
    "我下了订单怎么查物流？",
    "iPhone 15 Pro Max 的电池容量是多少？",
]

records = []
for i, q in enumerate(QUESTIONS, 1):
    print(f"\\n=========== Q{i}: {q} ===========")

    # 1) 裸 LLM
    bare = invoke_claude(
        prompt=q,
        system="你是跨境电商客服助手。基于你已知的信息回答用户问题，请尽量简短。",
        max_tokens=400,
    )

    # 2) RAG（KB.RetrieveAndGenerate）
    rag_resp = kb_retrieve_and_generate(KB_ID, q, model="claude_sonnet", top_k=4)
    rag_text = rag_resp["output"]["text"]
    citations = rag_resp.get("citations", [])
    cite_uris = []
    for c in citations:
        for ref in c.get("retrievedReferences", []):
            uri = ref.get("location", {}).get("s3Location", {}).get("uri", "")
            if uri and uri not in cite_uris:
                cite_uris.append(uri)

    # 控制台直观对比
    side_by_side(f"裸 LLM | Q{i}", bare, f"RAG | Q{i}", rag_text, width=55)
    print("引用来源：", cite_uris or "(无)")

    records.append({
        "Q#":      f"Q{i}",
        "问题":    q,
        "裸 LLM":  bare,
        "RAG":     rag_text,
        "引用":    "; ".join(cite_uris) if cite_uris else "(无)",
    })
"""),

    md("""
## 7. 对比表（一图看清）

把 3 个问题 × 2 路答案 + 引用整理到一张 DataFrame 上，方便复盘讨论。
"""),

    code("""
df = pd.DataFrame(records)
# 让长文本在 Notebook 里完整折行
pd.set_option("display.max_colwidth", 200)
display(df)
"""),

    md("""
## 8. 复盘讨论

**应该看到的**：
- **Q1 退货政策**：RAG 给出准确条款 + 引用，裸 LLM 编造"7 天 / 15 天"。
- **Q2 物流查询**：RAG 指向你 FAQ 里的实际入口，裸 LLM 给通用流程。
- **Q3 电池容量**：RAG 应当回答"知识库未提及"（或答得很糙）；裸 LLM 凭记忆瞎答。

**核心收获**：
1. RAG 把"答得对"从"碰运气"变成"有依据"。
2. RAG 不是魔法，**知识库里没有的问题**它一样答不出来。
3. **引用（Citations）是 RAG 的命脉**——没有它客服无法审计。

**关键的"坑"**：
- 你大概率发现：FAQ 里**有**商品规格的相关段，但 RAG 召回不全 → **默认 Chunking 把表格切碎了**。
- 这正是 **下一节 M3** 的入口：Chunking 不是切豆腐。
"""),

    md("""
## 9. 扩展任务（开发背景学员可选）

1. **改 Top-K**：把 `kb_retrieve_and_generate(..., top_k=4)` 调到 1 / 8 / 12，看回答质量与引用条数变化。
2. **裸检索**：用 `kb_retrieve(KB_ID, q, top_k=5)` + `show_chunks(...)` 单独看检索结果，**不**走 LLM。这是排查 RAG 问题的第一步——先看检索对不对。
3. **更换生成模型**：把 `model="claude_sonnet"` 换成 `claude_haiku`，对比延迟与质量。
4. **自定义 Prompt 模板**：给 `kb_retrieve_and_generate` 传 `prompt_template="..."`，加上"基于以下检索片段...如果未涉及请回答'知识库未提及'"。这是 M7 的预热。
5. **批量评估雏形**：自己写 5–10 个问题 + 期望要点，用 `invoke_claude` 让 LLM 自动判分（"回答中是否包含 ...?"），形成一个最小评估闭环。这是 M9 的预热。
"""),
]


# =============================================================================
# Lab 2 · 同一份文档，三种切法
# =============================================================================

LAB2_CELLS = [
    md("""
# Lab 2 · 同一份文档，三种切法

|     |     |
| --- | --- |
| **模块** | M3 · Chunking 不是切豆腐 |
| **时长** | 50 min（建 KB 等待 ~15 + 测试对比 ~30 + 复盘 5） |
| **形态** | 完整动手 |
| **角色** | 跨境电商混合内容（规格表 + 政策 + 长 FAQ）的 chunking 策略对比 |
| **关键产出** | 5 题 × 3 策略 = 15 次检索的对比矩阵 + 一个引出 M4 的隐藏发现 |
"""),

    md("""
## 1. 背景与目标

**场景**：M2 Lab 1 的客服机器人在「商品规格」类问题上答得很糙——根因不在生成，**在切法**。这一节用同一份混合文档做 3 个 KB，让你亲眼看到"切法决定一切"。

**数据**：1 份混合文档（约 6000 字，讲师预备）：
- 商品规格表（iPhone 15 Pro / 三星 S24 等多个型号）
- 政策条款（退货政策含 5 类例外情形）
- 长 FAQ（10 条，部分答案 > 500 字）

**预期体感**：
- 同一份文档，仅切法不同，**同一个问题** 答案可以从"完美"到"完全错"
- **Hierarchical** 在电商混合内容场景整体胜出
- 即使 chunking 调对了，**中文问题在 Titan v2 上仍有"答非所问"** → 引出 M4

**要发现的坑**：
- Fixed-size 把表格拦腰切——表头与值分到不同 chunk
- Semantic 对结构化内容（表格）也无效
- **隐藏的坑**：切法对了，**还有一个 Embedding 跨语言的坑** → M4
"""),

    md("""
## 2. 环境准备

填写 `# TODO` 变量。本 Lab 需要 **3 个 KB**——推荐在控制台并行启动，等摄入完成（每个约 5–10 min）。
"""),

    code("""
# === 必改：3 个 KB 的 ID，全部从控制台创建后回填 ===
S3_BUCKET            = "rag-training-yourname"          # TODO
S3_PREFIX            = "m3-mixed-doc/"                  # TODO

# 三种切法各对应一个 KB（控制台创建时选不同 Chunking strategy）
KB_FIXED_ID          = "REPLACE_ME"   # TODO Fixed-size（300 tokens / 10% overlap）
KB_FIXED_DS_ID       = "REPLACE_ME"

KB_HIER_ID           = "REPLACE_ME"   # TODO Hierarchical
KB_HIER_DS_ID        = "REPLACE_ME"

KB_SEMANTIC_ID       = "REPLACE_ME"   # TODO Semantic
KB_SEMANTIC_DS_ID    = "REPLACE_ME"

# === 通用导入 ===
import boto3
import json
import pandas as pd
from IPython.display import display

from common import (
    REGION, MODEL_IDS,
    s3_client, bedrock_agent, bedrock_agent_runtime,
    kb_retrieve, kb_retrieve_and_generate,
    show_chunks, wait_for_kb_sync, load_text,
)

KB_VARIANTS = {
    "Fixed-size":   {"id": KB_FIXED_ID,    "ds": KB_FIXED_DS_ID},
    "Hierarchical": {"id": KB_HIER_ID,     "ds": KB_HIER_DS_ID},
    "Semantic":     {"id": KB_SEMANTIC_ID, "ds": KB_SEMANTIC_DS_ID},
}

print("REGION:", REGION)
for name, v in KB_VARIANTS.items():
    print(f"  {name:14s} → kb={v['id']}  ds={v['ds']}")
"""),

    md("""
## 3. 步骤 1 — 上传混合文档到 S3

讲师已将文档放到 `notebooks/data/m3/mixed.md`，这里把它推到 S3。  
**注意**：3 个 KB 共用同一个 S3 prefix——切法不同但**输入相同**，才能做公平对比。
"""),

    code("""
from pathlib import Path

LOCAL_FILE = Path("data/m3/mixed.md")
if not LOCAL_FILE.exists():
    print(f"[WARN] 本地缺少 {LOCAL_FILE}，请向讲师索取 m3 数据包。")
else:
    s3 = s3_client()
    key = S3_PREFIX + LOCAL_FILE.name
    s3.upload_file(str(LOCAL_FILE), S3_BUCKET, key)
    print(f"uploaded → s3://{S3_BUCKET}/{key}")
"""),

    md("""
## 4. 步骤 2 — 在控制台并行创建 3 个 KB

> ⚠️ 控制台一次只能编辑一个，但**摄入是异步**的——**先点 3 次 Create，再统一等**。

### 4.1 控制台路径

> Bedrock → Knowledge Bases → **Create knowledge base** ×3
>
> | KB 名 | Chunking strategy | 关键参数 |
> | --- | --- | --- |
> | `kb-m3-fixed`   | **Fixed-size chunking** | size=300 tokens, overlap=10% |
> | `kb-m3-hier`    | **Hierarchical chunking** | parent=1500, child=300, overlap=60 |
> | `kb-m3-semantic`| **Semantic chunking** | breakpoint percentile threshold=95 |
>
> **三个 KB 都使用**：
> - Embeddings：**Titan Text Embeddings v2**（这是埋的"M4 引子"）
> - Vector store：**Quick create**（OpenSearch Serverless）
> - 同一个 S3 prefix `s3://YOUR_BUCKET/m3-mixed-doc/`

创建完成后**逐个**回填上面的 `KB_*_ID` / `KB_*_DS_ID`。

### 4.2 可选脚本路径

仅给已有 IAM role + OSS collection 的开发学员，仍推荐控制台。
"""),

    code("""
# 可选脚本路径：boto3 创建 3 个 KB（默认跳过）
if False:
    agent = bedrock_agent()
    KB_ROLE_ARN        = "arn:aws:iam::ACCOUNT:role/AmazonBedrockExecutionRoleForKB"  # TODO
    OSS_COLLECTION_ARN = "arn:aws:aoss:REGION:ACCOUNT:collection/COLLECTION_ID"       # TODO

    chunking_specs = {
        "kb-m3-fixed": {
            "chunkingStrategy": "FIXED_SIZE",
            "fixedSizeChunkingConfiguration": {"maxTokens": 300, "overlapPercentage": 10},
        },
        "kb-m3-hier": {
            "chunkingStrategy": "HIERARCHICAL",
            "hierarchicalChunkingConfiguration": {
                "levelConfigurations": [
                    {"maxTokens": 1500},
                    {"maxTokens": 300},
                ],
                "overlapTokens": 60,
            },
        },
        "kb-m3-semantic": {
            "chunkingStrategy": "SEMANTIC",
            "semanticChunkingConfiguration": {
                "maxTokens": 300,
                "bufferSize": 1,
                "breakpointPercentileThreshold": 95,
            },
        },
    }
    # 详细的 create_knowledge_base + create_data_source 参数请参考官方文档。
    # 提示：每个 KB 创建后都要 start_ingestion_job()——这就是 wait_for_kb_sync 做的事。
    print("此处省略具体 boto3 参数，推荐在控制台完成。")
else:
    print("已跳过：请按 4.1 在控制台创建 3 个 KB，然后回填 cell 2 的 6 个 ID。")
"""),

    md("""
## 5. 步骤 3 — 等待 3 个 KB 同步完成

如果是控制台创建并已点 **Sync now**，可以跳过 cell；否则下面 cell 帮你触发 + 轮询。
"""),

    code("""
for name, v in KB_VARIANTS.items():
    if v["id"] == "REPLACE_ME":
        print(f"[skip] {name}: KB_ID 还未填写")
        continue
    print(f"\\n--- {name} ({v['id']}) 同步状态 ---")
    status = wait_for_kb_sync(v["id"], v["ds"], max_wait=900, poll=15)
    print(f"  ★ 终态: {status}")
"""),

    md("""
## 6. 步骤 4 — 5 道压力测试题 × 3 个 KB

5 道题每一道都对应一种典型坑：

| # | 问题 | 测试什么 | 预期翻车策略 |
| --- | --- | --- | --- |
| Q1 | iPhone 15 Pro 的电池容量是多少？ | 商品规格表（表头-值） | Fixed-size |
| Q2 | 退货政策的所有例外情形有哪些？ | 政策条款（主条款+例外） | Fixed-size、Semantic |
| Q3 | 我买的商品 30 天后能退吗？ | 政策条款（跨段落） | Fixed-size |
| Q4 | 国际订单的物流时效一般多久？ | 长 FAQ（答案完整度） | Fixed-size |
| Q5 | 三星 S24 和 iPhone 15 Pro 哪个屏幕大？ | 跨多个规格表（多块召回） | 全部都有挑战 |

下面 cell 对每道题在 **3 个 KB** 上分别跑一次 `kb_retrieve_and_generate`（含 LLM 生成）和 `kb_retrieve`（只看检索片段），方便归因。
"""),

    code("""
QUESTIONS = [
    "iPhone 15 Pro 的电池容量是多少？",
    "退货政策的所有例外情形有哪些？",
    "我买的商品 30 天后能退吗？",
    "国际订单的物流时效一般多久？",
    "三星 S24 和 iPhone 15 Pro 哪个屏幕大？",
]

ready = {name: v for name, v in KB_VARIANTS.items() if v["id"] != "REPLACE_ME"}
assert ready, "至少需要回填一个 KB_ID 才能开始评测"

records = []
for qi, q in enumerate(QUESTIONS, 1):
    print(f"\\n========================  Q{qi}: {q}  ========================")
    row = {"Q#": f"Q{qi}", "问题": q}
    for name, v in ready.items():
        # 1) 检索 Top-3 看片段
        chunks = kb_retrieve(v["id"], q, top_k=3)
        # 2) RAG 一站式生成
        gen = kb_retrieve_and_generate(v["id"], q, model="claude_sonnet", top_k=4)
        ans = gen["output"]["text"]
        top_score = chunks[0].get("score", 0.0) if chunks else 0.0

        print(f"\\n--- {name} | top1_score={top_score:.4f} ---")
        print(ans[:500])
        row[f"{name} · 答案"] = ans
        row[f"{name} · top1"] = round(top_score, 4)
    records.append(row)
"""),

    md("""
## 7. 对比 / 表格

把 5 题 × 3 策略全量答案放到一张 DataFrame 上。  
**填表的同时建议你手动加 3 列主观评分**：检索是否命中（✅/⚠️/❌）、答案完整度（1-5）、整体可用性。
"""),

    code("""
df = pd.DataFrame(records)
pd.set_option("display.max_colwidth", 280)
display(df)

# 单独看 top-1 相似度（数值层面的横向对比）
score_cols = [c for c in df.columns if c.endswith("· top1")]
print("\\nTop-1 相似度对比：")
display(df[["Q#", "问题"] + score_cols])
"""),

    md("""
## 8. 复盘讨论

**预期发现**：

| 问题 | Fixed-size | Hierarchical | Semantic |
| --- | --- | --- | --- |
| Q1 规格表 | ❌ 残缺 | ✅ 完整 | ⚠️ 部分 |
| Q2 政策例外 | ❌ 漏例外 | ✅ 完整 | ⚠️ 漏 1-2 条 |
| Q3 跨段政策 | ❌ 缺前提 | ✅ 完整 | ✅ 完整 |
| Q4 长 FAQ | ⚠️ 截断 | ✅ 完整 | ✅ 完整 |
| Q5 跨表对比 | ❌ 单边召回 | ⚠️ 父块过大 | ❌ 单边召回 |

**核心结论**：
1. **Hierarchical 在电商混合内容场景整体胜出**——「子块检索 + 父块给 LLM」同时拿到了精度与上下文。
2. **Fixed-size 不是没用**，是不适合带表格 / 条款的电商客服场景。叙述性纯文本它很稳。
3. **Semantic 计算成本高，但对结构化（表格）依然无效**——语义模型看不懂"表头 vs 表值"的视觉结构。

**判断坑在哪**：
- 用 `kb_retrieve` 单独看检索片段——如果**Top-1 检索就错了**，问题在 Chunking + Embedding；
- 如果**检索片段对，但 LLM 答错**，问题在 Prompt（M7）；
- 这一节我们看到的大部分 Bad Case 都属于**前者**。

**隐藏的坑（关键发现）**：
- 即使切法选 Hierarchical，**有些中文问题的 Top-1 仍是"答非所问"**——
- 用 Top-1 score 看：检索分数高但内容不沾边 = **向量空间没对齐**
- **这不是切法问题，是 Embedding 模型问题**：Titan Text v2 英文优化，中文偏差大
- → **下一节 M4** 我们换 Embedding 模型，专攻这个坑
"""),

    md("""
## 9. 扩展任务（开发背景学员可选）

1. **改 Fixed-size 块大小**：在控制台把 Fixed-size KB 重建为 size=800 / overlap=15%，再跑一遍 5 题——看是否解决"表格切碎"。（预期：缓解但没根治）
2. **看 Hierarchical 父块原文**：用 `show_chunks(kb_retrieve(KB_HIER_ID, q, top_k=3))` 直接打印片段，对比父子块文本长度。
3. **加 Metadata（M3 ↔ M5 桥梁）**：在数据预处理阶段给每段加上 `{"section": "退货政策", "category": "phone"}`，下一节 Lab 4 就能用 Metadata Filter。
4. **写一个最小回归集**：把上面 5 题写进 `data/eval_lab2.json`，每题加 `expected_keywords`，写 10 行 Python 自动判分（包含期望关键词即得分），用同一个脚本跑 3 个 KB，输出"Hit@K + 完整度"两列指标。
5. **故意拉长文档**：把 mixed.md 复制 5 份让索引膨胀，观察 Hierarchical 索引体积 vs Fixed-size 的差别（成本预估）。
"""),
]


# =============================================================================
# Lab 3 · 跨语言检索效果对比
# =============================================================================

LAB3_CELLS = [
    md("""
# Lab 3 · 跨语言检索效果对比（Titan v2 vs Cohere Embed Multilingual）

|     |     |
| --- | --- |
| **模块** | M4 · Embedding 选型 + 多语言挑战 |
| **时长** | 50 min（建 2 索引 ~20 + 跑测试 ~15 + 找 case ~10 + 复盘 5） |
| **形态** | 完整动手 |
| **角色** | 跨境电商：中文用户问英文政策、英文用户问中文商品 |
| **关键产出** | 中→英 / 英→中 各自的 **Recall@5** 对比表 + 3 个"似相关而非相关"的 Bad Case |
"""),

    md("""
## 1. 背景与目标

**场景**：跨境电商客户群体涵盖中/英/日/韩。M3 Lab 2 末尾我们注意到——切法选 Hierarchical 之后，**中文问题去检英文政策仍然召回率惨**。这一节就解决这件事。

**数据**（讲师预备）：
- 中文商品描述：30 篇（手机、耳机、家电类）
- 英文政策条款：20 篇（退货、物流、保修、关税）
- 测试问题集 `eval_lab3.json`：20 题 = 10 中→英 + 10 英→中，每题含 `ground_truth_doc_id`

**预期体感**：
- **Cohere Embed Multilingual v3** 在跨语言场景显著优于 Titan Text v2（典型提升 15–25 个 Recall 百分点）
- 但 Cohere 也**到不了 100%**——存在"似相关而非相关"
- 这就是 **M5 Hybrid + Metadata + Rerank** 要解决的事

**要发现的坑**：
- "似相关而非相关"：Top-1 看起来像，但其实是另一个商品的政策
- 专业术语错位："七天无理由"被对到"30-day return"
- 关键词缺失：用户问 SKU 编号，向量检索完全召不回
"""),

    md("""
## 2. 环境准备

本 Lab 需要 **2 个 KB**（同一份双语数据，分别用 Titan v2 / Cohere 建索引）。  
请确认 Bedrock 已开通 `Titan Text Embeddings v2` 和 `Cohere Embed Multilingual v3` 两个模型访问。
"""),

    code("""
# === 必改 ===
S3_BUCKET            = "rag-training-yourname"     # TODO
S3_PREFIX            = "m4-bilingual/"             # TODO

# 索引 A：Titan Text Embed v2
KB_TITAN_ID          = "REPLACE_ME"   # TODO
KB_TITAN_DS_ID       = "REPLACE_ME"

# 索引 B：Cohere Embed Multilingual v3
KB_COHERE_ID         = "REPLACE_ME"   # TODO
KB_COHERE_DS_ID      = "REPLACE_ME"

# === 通用导入 ===
import boto3
import json
import pandas as pd
from collections import defaultdict
from IPython.display import display

from common import (
    REGION, MODEL_IDS,
    s3_client, bedrock_runtime, bedrock_agent, bedrock_agent_runtime,
    embed_text, kb_retrieve, kb_retrieve_and_generate,
    show_chunks, wait_for_kb_sync, load_eval_set,
)

CANDIDATES = {
    "Titan v2":          {"id": KB_TITAN_ID,  "ds": KB_TITAN_DS_ID,  "model": "titan_text_v2"},
    "Cohere Multi v3":   {"id": KB_COHERE_ID, "ds": KB_COHERE_DS_ID, "model": "cohere_embed_multi"},
}
print("REGION:", REGION)
for name, v in CANDIDATES.items():
    print(f"  {name:18s}  kb={v['id']}  embed={MODEL_IDS[v['model']]}")
"""),

    md("""
## 3. 步骤 1 — 上传双语数据到 S3

数据位于 `notebooks/data/m4/`，包括 `cn_products/` 和 `en_policies/` 两个子目录。
"""),

    code("""
from pathlib import Path

LOCAL_DIR = Path("data/m4")
if not LOCAL_DIR.exists():
    print(f"[WARN] 缺少 {LOCAL_DIR}，请向讲师索取 m4 数据包。")
else:
    s3 = s3_client()
    n = 0
    for sub in ["cn_products", "en_policies"]:
        for fp in (LOCAL_DIR / sub).glob("*"):
            if fp.is_file():
                key = S3_PREFIX + sub + "/" + fp.name
                s3.upload_file(str(fp), S3_BUCKET, key)
                n += 1
    print(f"uploaded {n} files → s3://{S3_BUCKET}/{S3_PREFIX}")
"""),

    md("""
## 4. 步骤 2 — 控制台并行创建 2 个 KB

> Bedrock → Knowledge Bases → **Create knowledge base** ×2
>
> | KB 名 | Embedding | Chunking |
> | --- | --- | --- |
> | `kb-m4-titan`  | **Titan Text Embeddings v2** | Fixed-size 300 / 10% overlap |
> | `kb-m4-cohere` | **Cohere Embed Multilingual v3** | Fixed-size 300 / 10% overlap |
>
> **两个 KB 都使用相同的 S3 prefix**（`m4-bilingual/`）和**相同的 Chunking 策略**——只让 **Embedding 这一个变量**变。

创建完后回填 `KB_TITAN_ID` / `KB_COHERE_ID` 等 4 个 ID，然后下一 cell 等待同步。
"""),

    code("""
# 可选：boto3 创建（默认跳过；推荐控制台）
if False:
    agent = bedrock_agent()
    KB_ROLE_ARN        = "arn:aws:iam::ACCOUNT:role/AmazonBedrockExecutionRoleForKB"  # TODO
    OSS_COLLECTION_ARN = "arn:aws:aoss:REGION:ACCOUNT:collection/COLLECTION_ID"       # TODO
    for short, model_key in [("titan", "titan_text_v2"), ("cohere", "cohere_embed_multi")]:
        # ... 见 Lab 2 的 boto3 模板，仅 embeddingModelArn 不同 ...
        pass
    print("（脚本已省略，请用控制台）")
else:
    print("已跳过：请按 4 在控制台创建 2 个 KB 后回填 cell 2。")
"""),

    md("""
## 5. 步骤 3 — 等 2 个索引同步完成
"""),

    code("""
for name, v in CANDIDATES.items():
    if v["id"] == "REPLACE_ME":
        print(f"[skip] {name} 未填 KB_ID")
        continue
    print(f"\\n--- {name} ({v['id']}) ---")
    status = wait_for_kb_sync(v["id"], v["ds"], max_wait=900, poll=15)
    print(f"  ★ 终态: {status}")
"""),

    md("""
## 6. 步骤 4 — 加载评测集 + 计算 Recall@5

`eval_lab3.json` 的每条结构：
```json
{
  "qid": "q01",
  "question": "我能退货到日本吗？",
  "lang_q": "zh",
  "lang_doc": "en",
  "ground_truth_doc_ids": ["en_policies/return_japan.md"]
}
```

**Recall@5** 定义：Top-5 检索结果中，引用的 S3 URI 是否命中 `ground_truth_doc_ids` 中任一项。
"""),

    code("""
def doc_id_from_chunk(chunk: dict) -> str:
    \"\"\"从 KB 检索结果里抽出"相对 prefix 的 doc id"。\"\"\"
    uri = chunk.get("location", {}).get("s3Location", {}).get("uri", "")
    # uri 形如 s3://BUCKET/m4-bilingual/en_policies/xxx.md
    if S3_PREFIX in uri:
        return uri.split(S3_PREFIX, 1)[1]
    return uri

def recall_at_k(retrieved: list[dict], gt_ids: list[str], k: int = 5) -> int:
    \"\"\"返回 0/1：Top-K 中是否命中任一 GT 文档。\"\"\"
    seen = {doc_id_from_chunk(c) for c in retrieved[:k]}
    return int(any(g in s for s in seen for g in gt_ids) or bool(seen & set(gt_ids)))

# 加载评测集
try:
    EVAL_SET = load_eval_set("eval_lab3.json")
except FileNotFoundError as e:
    print(e)
    EVAL_SET = []

print(f"评测题数: {len(EVAL_SET)}")
print(f"  中→英: {sum(1 for x in EVAL_SET if x.get('lang_q')=='zh' and x.get('lang_doc')=='en')}")
print(f"  英→中: {sum(1 for x in EVAL_SET if x.get('lang_q')=='en' and x.get('lang_doc')=='zh')}")
"""),

    code("""
ready = {n: v for n, v in CANDIDATES.items() if v["id"] != "REPLACE_ME"}
assert ready, "至少回填一个 KB_ID"

raw_records = []
hits_by_direction = defaultdict(lambda: defaultdict(list))  # model → direction → [0/1,...]

for q in EVAL_SET:
    direction = f"{q['lang_q']}→{q['lang_doc']}"
    row = {
        "qid":       q["qid"],
        "direction": direction,
        "question":  q["question"],
        "gt_docs":   "; ".join(q["ground_truth_doc_ids"]),
    }
    for name, v in ready.items():
        chunks = kb_retrieve(v["id"], q["question"], top_k=5)
        hit = recall_at_k(chunks, q["ground_truth_doc_ids"], k=5)
        top1_doc = doc_id_from_chunk(chunks[0]) if chunks else "(empty)"
        top1_score = chunks[0].get("score", 0.0) if chunks else 0.0
        row[f"{name} · hit@5"] = hit
        row[f"{name} · top1"]  = top1_doc
        row[f"{name} · score"] = round(top1_score, 4)
        hits_by_direction[name][direction].append(hit)
    raw_records.append(row)

raw_df = pd.DataFrame(raw_records)
pd.set_option("display.max_colwidth", 200)
display(raw_df)
"""),

    md("""
## 7. 对比 / 表格 — Recall@5 by Direction

按方向（中→英 / 英→中）汇总每个模型的 Recall@5：
"""),

    code("""
summary_rows = []
for name in ready.keys():
    for direction in ["zh→en", "en→zh"]:
        hits = hits_by_direction[name][direction]
        if hits:
            recall = sum(hits) / len(hits)
            summary_rows.append({
                "Embedding": name,
                "Direction": direction,
                "N":         len(hits),
                "Recall@5":  f"{recall:.1%}",
            })
summary = pd.DataFrame(summary_rows)
display(summary)

# 透视一下，更直观
if not summary.empty:
    pivot = summary.pivot(index="Direction", columns="Embedding", values="Recall@5")
    print("\\n=== Recall@5 透视表 ===")
    display(pivot)
"""),

    md("""
## 8. 找 3 个有趣 case（人工分析）

下面 cell 自动挑出"两个模型都失败 / Cohere 救回 Titan / Top-1 似相关"的题目，  
**请你结对讨论**：每个 case 是属于"语言对齐问题"、"专业术语问题"、还是"关键词精确匹配缺失"。
"""),

    code("""
if not raw_df.empty and len(ready) >= 2:
    cols_hit = [c for c in raw_df.columns if c.endswith("hit@5")]
    # case A：所有模型都失败
    both_fail = raw_df[(raw_df[cols_hit].sum(axis=1) == 0)]
    # case B：Cohere 救回 Titan
    if "Cohere Multi v3 · hit@5" in raw_df.columns and "Titan v2 · hit@5" in raw_df.columns:
        cohere_save = raw_df[
            (raw_df["Cohere Multi v3 · hit@5"] == 1)
            & (raw_df["Titan v2 · hit@5"] == 0)
        ]
    else:
        cohere_save = pd.DataFrame()

    print("=== Case A: 两个模型都召不回 ===")
    display(both_fail[["qid", "direction", "question", "gt_docs"]].head(5))

    print("\\n=== Case B: Cohere 召回成功而 Titan 失败 ===")
    display(cohere_save[["qid", "direction", "question", "gt_docs"]].head(5))

    print("\\n=== Case C: Top-1 score 高但 hit=0（似相关而非相关）===")
    if "Cohere Multi v3 · hit@5" in raw_df.columns:
        susp = raw_df[(raw_df["Cohere Multi v3 · hit@5"] == 0)
                      & (raw_df["Cohere Multi v3 · score"] > 0.5)]
        display(susp[["qid","direction","question","gt_docs",
                      "Cohere Multi v3 · top1","Cohere Multi v3 · score"]].head(5))
"""),

    md("""
## 9. 复盘讨论

**数字层面（典型预期，实测可能浮动）**：

| Embedding | 中→英 Recall@5 | 英→中 Recall@5 |
| --- | --- | --- |
| Titan Text Embed v2 | 50–65% | 55–70% |
| Cohere Embed Multilingual v3 | 70–85% | 75–88% |

**结论**：
1. **多语言场景请直接选多语言模型**——Cohere v3 比英文优化的 Titan v2 在跨语向上典型提升 15–25 个百分点。
2. 选模型不是看 leaderboard，是看你的**业务方向**和**chunk 长度**：Cohere 上下文 512 短，得搭配 ≤ 300 token 的小 chunk。

**剩余的 3 类问题（哪怕是 Cohere 也躲不开）**：
1. **似相关而非相关**：Top-1 score 高但其实是另一个商品/地区的政策。  
2. **专业术语错位**："七天无理由"≈"30-day return" 但市场不同——语义匹配会"错配"。
3. **关键词精确匹配缺失**：SKU、订单号、型号编号——纯向量检索召不回。

**核心认知**：
> Embedding 是**语义匹配**，天花板在 80% 左右。要继续往上走，需要混合策略——这就是 **M5 检索三板斧**：Hybrid Search + Metadata Filtering + Reranking。Lab 4 我们就在 Lab 3 的基础上逐步开三板斧，看 Recall 阶梯式提升。
"""),

    md("""
## 10. 扩展任务（开发背景学员可选）

1. **直接调 `embed_text`**：用 `embed_text("退货政策", model="titan_text_v2")` 与 `embed_text("return policy", model="cohere_embed_multi")`，自己算 cosine 相似度，看跨语向量空间有多近。
2. **降维实验**：Cohere 支持 384 / 256 维度（在请求 body 里加 `embedding_types` / `output_dimension`）。重建索引，比较 Recall@5 变化与索引体积/成本。
3. **Recall@1 / @3 / @10**：把 `recall_at_k` 改 K 值，画一条 Recall vs K 的曲线——客服真实场景往往要看 Recall@3 才有意义。
4. **MRR（Mean Reciprocal Rank）**：进阶指标，反映"GT 文档在 Top-K 中的位置"，比 Recall@K 更敏感地区分两个模型。
5. **加 BGE-M3 baseline（自部署）**：在 SageMaker JumpStart 部署 BGE-M3，把 OpenSearch 索引接到自部署 endpoint，再跑一遍同一份 eval——给客户做选型决策时有第三方对比数据。
"""),
]


# =============================================================================
# 主入口
# =============================================================================

if __name__ == "__main__":
    targets = [
        ("lab_01_first_rag.ipynb", LAB1_CELLS),
        ("lab_02_chunking.ipynb", LAB2_CELLS),
        ("lab_03_embedding_multilingual.ipynb", LAB3_CELLS),
    ]
    for name, cells in targets:
        nb = make_notebook(cells)
        fp = save(nb, name)
        print(f"✅ wrote {fp}  ({len(cells)} cells)")
