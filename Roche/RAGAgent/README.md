# Roche RAG + Agent 工程实验

面向 Roche 交付工程师的三天实践项目。课程围绕一套统一的“检验科证据调查工作台”展开：

- RAG：完整知识库构建、在线查询和评估 Pipeline；
- Agent：Workflow、ReAct 与有界 Skill 调查循环；
- 可信性：确定性规则、证据链、Human-in-the-loop；
- 评估：本地指标、RAGAS Adapter、Langfuse Dataset/Experiment/Trace；
- 部署：本地数据设施，Bedrock Claude/Titan 通过适配层接入。

详细设计见 [实验设计 Spec](docs/experiments-design-spec.md)。

RAG评估指标、数据集格式、切分策略与复杂PDF处理方法见
[RAG知识库工程与评估指南](docs/rag-knowledge-base-engineering-guide.md)。

## 环境

- Python 3.11 或 3.12
- 本地模式不需要 AWS、Langfuse、Docker
- Workshop 模式需要 Bedrock Claude 4.6 与 Titan Embeddings 权限

```bash
cd Roche/RAGAgent
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
```

使用 `uv`：

```bash
uv sync --extra dev
uv run pytest
```

## 三种运行模式

| 模式 | 用途 | 外部依赖 |
|---|---|---|
| `fake` | 单元测试与故障注入 | 无 |
| `replay` | 回放固定模型响应 | 无 |
| `bedrock` | 真实 Claude/Titan 调用 | AWS 凭证 |

复制 `.env.example` 为 `.env`，但不要提交凭证。

## 快速运行

```bash
# 启动Lab 0 LangGraph RAG实验台
roche-lab web --config labs/E0_pipeline/config.baseline.yaml

# 构建本地知识库并运行基线评估
roche-lab rag build --config labs/E0_pipeline/config.baseline.yaml
roche-lab rag evaluate --config labs/E0_pipeline/config.baseline.yaml

# 导入检验科运行数据
roche-lab analytics import \
  --csv data/analytics/raw/lab_operations_2026-08.csv \
  --db artifacts/lab_operations.db

# 运行根因调查
roche-lab analytics investigate \
  --db artifacts/lab_operations.db \
  --question "为什么早高峰前处理耗时上升？"
```

## 实验地图

| 实验 | 主题 | 主要交付 |
|---|---|---|
| E0 | 完整 RAG Pipeline 与基线 | 三链路 Trace、Baseline |
| E1 | RAG 超参数实验台 | 配置对比与指标报告 |
| E2 | 规则与证据包 | 可审计合规发现 |
| E3 | Workflow vs ReAct | 压力测试与选型 ADR |
| E4 | Skill 驱动根因调查 | 有界调查 Agent |
| E5 | Agent 评估与生产闸门 | 轨迹回归与降级 |
| CP | 分组业务迁移 | Skill/工具/规则与 Backlog |

## 评估原则

1. 检索和规则优先使用确定性真值。
2. RAGAS只作为语义指标插件，不代替业务真值。
3. Langfuse负责Trace、Dataset、Experiment和Score归档。
4. 医学模拟数据仅用于验证工程行为，不用于临床决策。
