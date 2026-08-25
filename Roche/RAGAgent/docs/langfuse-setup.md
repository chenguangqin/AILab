# 共享Langfuse课堂配置

## 推荐隔离方式

为6个小组分别创建Project和写入Key：

```text
roche-team-a1-iso
roche-team-a2-iso
roche-team-b1-analytics
roche-team-b2-analytics
roche-team-c1-review
roche-team-c2-review
```

每台EC2配置：

```bash
export LANGFUSE_HOST=https://...
export LANGFUSE_BASE_URL=https://...
export LANGFUSE_PUBLIC_KEY=...
export LANGFUSE_SECRET_KEY=...
export ROCHE_TEAM=team-b1
export ROCHE_STUDENT_ID=anonymous-01
```

禁止上传真实患者标识。

`LANGFUSE_BASE_URL`是新版SDK推荐变量；当前实验同时兼容
`LANGFUSE_HOST`。API Key必须在对应Project的Settings中创建。

## 同步RAG评估集

每组只需执行一次：

```bash
roche-lab langfuse sync-dataset --name roche-iso-rag-v1
```

## 必需Trace元数据

- `day`、`lab`、`team`、`scenario`
- `workflow_version`
- `index_version`
- `data_version`
- `rule_version`
- 模型ID与Prompt版本

## 课堂比较

Langfuse负责：

- 索引构建与查询Trace；
- Dataset/Experiment版本；
- 本地确定性指标和RAGAS分数归档；
- Token、延迟、错误率；
- LangGraph节点与工具调用；
- 人工Annotation。

RAGAS是可选评估器，不替代Langfuse，也不替代业务真值。
