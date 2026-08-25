# E0：LangGraph RAG 工作流与评估基线

指标公式、评估数据集、切分策略和复杂文档处理方法见
[`docs/rag-knowledge-base-engineering-guide.md`](../../docs/rag-knowledge-base-engineering-guide.md)。

## 我们提供

- LangGraph 编排的意图识别、Query 改写、检索、重排和生成链路；
- FastAPI 与静态 RAG 实验台；
- 可运行的知识库构建和后台离线评估链路；
- ISO/SOP/表格模拟文档；
- 12 条评估案例；
- 朴素但完整的 Baseline 配置；
- 本地 JSON Trace，Workshop 可切换 Langfuse。

## 学员任务

1. 启动实验台并运行一个在线查询。
2. 在 Langfuse 或本地 Trace 中观察每个 LangGraph 节点。
3. 后台运行 dev 与 test 数据集，保存 Baseline。
4. 修改查询参数，观察无需重建索引的指标变化。
5. 修改切分或 Embedding 参数，重建索引后重新评估。
6. 将错误归入解析、召回、排序、引用或生成。

## 启动实验台

```bash
roche-lab web \
  --config labs/E0_pipeline/config.baseline.yaml \
  --host 127.0.0.1 \
  --port 8000
```

浏览器访问 `http://127.0.0.1:8000`。

## CLI评估

```bash
roche-lab rag evaluate \
  --config labs/E0_pipeline/config.baseline.yaml \
  --split dev
```

Web产物位于`artifacts/lab0-web/`，CLI产物位于`artifacts/e0-baseline/`。

启用RAGAS语义指标：

```bash
roche-lab rag evaluate \
  --config labs/E0_pipeline/config.workshop.yaml \
  --split dev \
  --ragas
```

RAGAS Judge默认允许4096个输出Token并限制为2个并发任务。可通过
`RAGAS_MAX_TOKENS`、`RAGAS_MAX_WORKERS`、`RAGAS_MAX_RETRIES`和
`RAGAS_TIMEOUT_SECONDS`调整。若个别Judge输出仍无法解析，报告会将该项记为
`null`并在`ragas.summary.failed_metrics`中列出，不影响确定性指标。

Workshop中将`.env`里的Provider改为Bedrock，然后启动：

```bash
roche-lab web \
  --config labs/E0_pipeline/config.workshop.yaml \
  --host 0.0.0.0 \
  --port 8000
```

## 参数与索引生命周期

- Query改写、Top-K、混合检索权重和重排参数可以直接应用；
- 切分策略、Chunk大小、Overlap和Embedding模型变更后必须重建索引；
- 每次建库根据文档和索引参数自动生成`index_version`；
- 在线查询与后台评估调用同一份Compiled LangGraph。
