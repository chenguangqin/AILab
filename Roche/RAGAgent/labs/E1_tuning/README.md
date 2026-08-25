# E1：RAG 超参数实验台

## 我们提供

- E0 的完整 Pipeline；
- 集中式 `PipelineConfig`；
- 结构感知切分、BM25/向量融合和轻量重排；
- 确定性指标与可选 RAGAS Adapter；
- Langfuse Experiment/Score 接入点。

## 学员任务

每轮只修改一个变量：

1. `chunk_strategy/chunk_size/chunk_overlap`
2. `query_rewrite`
3. `retrieval_top_k`
4. `hybrid_alpha`
5. `rerank_candidate_k/rerank_top_n`
6. `min_relevance_score/max_context_chars`

先在 `dev` 上选择候选配置，再运行 `test`。说明Recall、MRR、引用、拒答、Token和延迟之间的取舍。

```bash
roche-lab rag evaluate \
  --config labs/E1_tuning/config.optimized.yaml \
  --split dev

roche-lab rag sweep \
  --matrix labs/E1_tuning/experiment_matrix.yaml
```

不要用RAGAS单一分数决定方案，也不要在看过测试集后继续调参。

Workshop中需要额外运行语义指标时：

```bash
roche-lab rag evaluate \
  --config labs/E1_tuning/config.workshop-optimized.yaml \
  --split test \
  --ragas
```

该命令会调用Bedrock评审模型和Embedding，默认实验不启用。
