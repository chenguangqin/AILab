# RAG 工程化落地实战 · Lab Notebook 包（开源栈版 · 罗氏检验科）

> 13 个动手实验的 Jupyter notebook。配套讲义脚本在 `../script/roche/`（罗氏检验科版；原电商版仍保留在 `../script/*.md`，pptx 在 `../ppt/` 未改动）。
>
> **技术栈**：生成 = Bedrock Claude Sonnet 4.6；嵌入 = Bedrock Titan v2；**其余全部开源、可本地部署**——向量库 Qdrant、框架 LangChain、编排 LangGraph、重排 bge-reranker（本地）、图谱 NetworkX、评估 RAGAs。产品真正本地部署时把嵌入切 bge-m3、生成切本地 Qwen/vLLM，检索代码不变。

## 文件清单

| Lab | 文件 | 模块 | 场景 | 形态 |
|-----|------|------|------|------|
| 1 | `lab_01_first_rag.ipynb` | M2 第一个 RAG | 检验科知识助手跑通 | 完整动手 |
| 2 | `lab_02_chunking.ipynb` | M3 Chunking | SOP 切法对比 + **复杂 PDF 解析** | 完整动手 |
| 3 | `lab_03_embedding_multilingual.ipynb` | M4 Embedding 选型 | **中英医学术语混杂**（Titan vs bge-m3）| 完整动手 |
| 4 | `lab_04_retrieval_trio.ipynb` | M5 检索三板斧 | Hybrid + Metadata + 本地 Rerank | 完整动手 |
| 5 | `lab_05_multimodal.ipynb` | M6 多模态（**弱化**）| 手填记录表识别 + 判定留规则 | 演示型 |
| 6 | `lab_06_prompt_templates.ipynb` | M7 Prompt/引用 | 抑制幻觉 + 不下诊断 | 完整动手 |
| 7 | `lab_07_multiturn_query_rewrite.ipynb` | M8 多轮+改写 | 患者结果多轮指代消解 | 完整动手 |
| 8 | `lab_08_evaluation.ipynb` | M9 评估（**RAGAs**）| 四指标 + 合成基线 | 完整动手 |
| 9 | `lab_09_graphrag_demo.ipynb` | M10 GraphRAG（手搓）| 项目-试剂-仪器-规则图谱 | 演示型 |
| 9.1 | `lab_09_1_graph_kb.ipynb` | M10 GraphRAG（LLM 自动建图）| 三元组抽取建图 | 演示+动手 |
| 10 | `lab_10_agentic.ipynb` | M11 Agentic（**LangGraph**）| 审核 Agent · 不自动放行 | 完整动手 |
| 11 | `lab_11_bad_case_loop.ipynb` | M12 Bad Case 闭环 | 审核误判归因→改进→回归 | 完整动手 |
| 12 | `lab_12_safety_cost.ipynb` | M13 安全+成本 | 开源护栏（PII/不诊断/越狱）| 完整动手 |

## 环境准备

```bash
pip install -r requirements.txt
# AWS 凭证（EC2 实例角色 / aws configure / 环境变量）
export AWS_REGION=us-west-2
export BEDROCK_CHAT_MODEL_ID=us.anthropic.claude-sonnet-4-6      # common.py 默认已是此值
export BEDROCK_EMBED_MODEL_ID=amazon.titan-embed-text-v2:0
python3 check_models.py          # 开课前用最小真实调用验证 Bedrock 可调
CHECK_LOCAL=1 python3 check_models.py   # 另验本地开源模型（bge / qdrant）可导入
```

- 向量库默认 **Qdrant 内存模式**（零运维）；EC2 上用真实容器时设 `RAG_QDRANT_URL=http://localhost:6333`。
- 嵌入默认 Titan；设 `RAG_EMBED_PROVIDER=local` 或按 Lab 传 `provider="local"` 切本地 **bge-m3**（首次下载权重）。

## 共享工具 `common.py`（开源栈支点，勿随意改动）

| 类别 | 函数 |
|------|------|
| 生成 | `get_llm(model)` · `invoke_llm(prompt, system=…)`（`model="gen_main"`=Sonnet 4.6）|
| 嵌入 | `get_embeddings(provider="bedrock"\|"local")` · `embed_text` |
| 向量库 | `build_vectorstore(docs, collection)` · `retrieve(vs, query, top_k)` |
| 一站式 | `rag_answer(vs, query)` → `{answer, contexts, hits}` |
| 重排 | `rerank(query, docs, top_n)`（本地 bge-reranker-v2-m3）|
| 数据 | `docs_from_dir(relpath)` · `load_pdf(relpath)` · `load_text` · `load_eval_set` |
| 展示 | `show_chunks` · `side_by_side` |

> 原 AWS Knowledge Bases 版备份在 `common_aws_kb.py.bak`（仅存档，不参与本课）。

## 数据布局（`data/`）

| 路径 | 用途 | Lab |
|------|------|-----|
| `kb/*.md` | 检验科 SOP 知识库（危急值/质控/拒收/审核）| 1,6,7,10,11 |
| `m3/mixed.md` + `pdf/*.pdf` | 混排 SOP + 真实复杂 PDF（ISO15189/CNAS）| 2 |
| `m4/cn_docs/*` `m4/en_docs/*` `eval_lab3.json` | 中英术语混杂 + 跨语言评估 | 3 |
| `eval_lab4.json` `m4/doc_meta.json` | 检索三板斧评估 + metadata | 4 |
| `multimodal/`（现场 PIL 生成）| 模拟记录表图 | 5 |
| `eval_30.json` | 30 题合成评估集（含 ground_truth）| 8, 11 |
| `lab_graph.gpickle`（`_build_graph.py` 生成）| 检验科关系图谱 | 9, 9.1 |
| `bad_cases.json` | 10 条审核 bad case | 11 |

> **遗留（未使用）**：`faq/`、`m4/cn_products/`、`m4/en_policies/`、`multimodal/products+user_uploads/`、`ecommerce_graph.gpickle`、`_build_evals.py`、`_build_images.py` 是原电商课数据，本版**未使用**，保留以备参考，可自行清理。

## 重新生成 notebook

每个 lab 由 `build_labXX.py` 程序化生成（nbformat，避免 JSON 转义 bug）：

```bash
python3 build_lab01.py        # 单个
for f in build_lab*.py; do python3 "$f"; done   # 全部
python3 -W ignore -c "import nbformat,glob; [nbformat.validate(nbformat.read(f,as_version=4)) for f in glob.glob('lab_*.ipynb')]; print('all valid')"
```

## 已知坑 / 开课前 smoke-test 清单

- **未实跑**：所有 notebook 仅做 nbformat 结构校验（构建环境无 AWS 凭证）。填好 Bedrock 后请在 EC2 逐个 smoke-test，重点：lab_01（连通）、lab_08（RAGAs）、lab_10（LangGraph Agent）。
- **RAGAs 版本**（lab_08）：列名默认 `question/answer/contexts/ground_truth`；新版可能需 `user_input/response/retrieved_contexts/reference`——按 EC2 上 pinned 版本核一次。
- **LangGraph 版本**（lab_10）：`create_react_agent` 的系统提示参数名随版本为 `prompt` / `state_modifier` / `messages_modifier`，核对实测版本。
- **本地模型权重**：bge-m3 / bge-reranker-v2-m3 首次调用下载（学员运行时，非构建期）。
- **`gen_fast` 暂等于 `gen_main`**（都指 Sonnet 4.6）：本环境仅确认 Sonnet 可用；开通 Haiku/Opus 后在 `common.MODEL_IDS` 把 fast/strong 指过去，M13 的档位路由收益才显现。
- **多模态**（lab_05）为演示型：模拟表用 ASCII/数字规避 PIL 中文字体问题；真实手写中文更难，建议 PaddleOCR + 人工复核。

## 教学建议

- 混合受众：开发学员跑通+改参数+做扩展任务；业务学员关注"改参数→看输出→填对比表→讨论"。
- 每个 Lab 末尾有「复盘讨论」+「扩展任务」，复盘必做、扩展选做。
- 暗线贯穿：**检索/生成的每一步都可埋点 Langfuse、可审计**；**决策权分配**（哪些交程序、哪些交 LLM）在 M10/M11/M13 显性收口，接罗氏三天 Agent 课。
