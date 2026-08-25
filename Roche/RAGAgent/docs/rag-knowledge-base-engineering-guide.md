# RAG知识库工程与评估指南

> 版本：0.1  
> 日期：2026-08-25  
> 适用范围：Roche检验科相关RAG、文档审核、智能问数与报告审核实验  
> 原则：证据可定位、规则可审计、评估可重复、模型结论不越权

---

## 1. 文档目的

本文整理课程设计和Lab 0讨论中形成的工程结论，回答以下问题：

1. 文档如何解析、切分并写入知识库；
2. Evidence ID、Chunk ID和向量库Payload分别是什么；
3. 如何制作RAG评估数据集；
4. Recall、MRR、nDCG、Citation Recall等指标如何计算；
5. RAGAS、LLM-as-a-Judge和确定性指标如何分工；
6. 复杂排版PDF、扫描件、表格、公式和流程图应该如何处理；
7. 在医院本地算力受限的条件下，怎样形成可落地的技术路线。

本文描述的是工程方法，不对医学、ISO15189符合性或根因结论作专业有效性声明。

---

## 2. 总体架构

一个可审计的RAG系统至少包含三条链路。

### 2.1 知识库构建链路

```text
原始文件
  -> 文件安全检查
  -> 文档类型识别
  -> 文本/OCR/版面解析
  -> Evidence Block
  -> Chunk生成
  -> Metadata补充
  -> Embedding
  -> 向量与Payload入库
  -> Index Manifest
```

### 2.2 在线查询链路

```text
用户问题
  -> 意图识别
  -> Query改写
  -> 权限与范围过滤
  -> 向量/BM25召回
  -> 重排
  -> 上下文组装
  -> LLM生成或拒答
  -> 引用与Grounding检查
```

Lab 0使用LangGraph编排在线查询链路：

```text
START
  -> intent
  -> rewrite
  -> retrieve
  -> rerank
  -> generate
  -> END
```

### 2.3 离线评估链路

```text
Evaluation Dataset
  -> 批量调用同一Compiled Graph
  -> 检索/排序/引用确定性指标
  -> 可选RAGAS
  -> 可选LLM Judge
  -> Langfuse Score
  -> 配置对比与发布闸门
```

在线请求和离线评估必须调用同一份业务Graph，避免“生产运行一套代码、评估运行另一套代码”。

---

## 3. Document、Evidence与Chunk

### 3.1 三个概念

| 概念 | 含义 | 生命周期 |
|---|---|---|
| Document | 一份原始文件或逻辑文档 | 源数据级 |
| Evidence Block | 可独立定位、审核和引用的原始证据单元 | 跨索引版本稳定 |
| Chunk | 为检索和上下文窗口生成的技术切分单元 | 可以随切分策略变化 |

关键原则：

> Evidence ID属于原始证据，不应依赖某一次Chunk策略。

例如：

```text
Document:
  sop-refrigerator-v2

Evidence Block:
  sop-v2-temp-limit

Chunks:
  fixed-v1-chunk-003
  structure-v2-chunk-017
```

两次切分产生不同Chunk，但都应能映射回同一个Evidence Block。

### 3.2 推荐Evidence Block结构

```json
{
  "evidence_id": "sop-v2-temp-limit",
  "document_id": "sop-refrigerator-v2",
  "document_version": "2.0",
  "status": "active",
  "effective_date": "2026-07-01",
  "page": 5,
  "bbox": [72, 140, 510, 230],
  "block_type": "clause",
  "title": "4.2 温度范围",
  "text": "试剂冰箱日常运行温度不得高于5°C。",
  "source_start": 120,
  "source_end": 180,
  "confidence": 1.0
}
```

扫描件还应记录：

- OCR引擎和版本；
- OCR置信度；
- 原始图片URI；
- 页码、区域和单元格坐标；
- 是否经过人工复核。

### 3.3 Markdown Front Matter

当前教学文档使用YAML Front Matter保存文档元信息：

```markdown
---
document_id: sop-refrigerator-v2
document_type: sop
version: "2.0"
effective_date: "2026-07-01"
status: active
department: laboratory
page: 5
---

# 试剂冰箱温度管理SOP

## [sop-v2-temp-limit] 4.2 温度范围

试剂冰箱日常运行温度不得高于5°C。
```

Front Matter会从正文中移除并保存在Metadata中：

- 不直接参与正文Embedding；
- 不直接作为LLM上下文；
- 可用于过滤、引用、审计和版本控制。

当前实现中：

- `document_id`用于文档和引用标识；
- `status`用于`active_only`过滤和重排；
- `page`、`region`用于引用定位；
- `version`、`effective_date`会保留，但尚未自动执行版本优先级判断。

用户可能直接询问的重要信息，应同时在正文中明确表达，不能只存在于Front Matter。

### 3.4 推荐Chunk Payload

生产级向量库Payload应包含：

```json
{
  "chunk_id": "chunk-017",
  "document_id": "sop-refrigerator-v2",
  "text": "4.2 温度范围\n试剂冰箱日常运行温度不得高于5°C。",
  "contained_evidence_ids": ["sop-v2-temp-limit"],
  "parent_id": "sop-v2-section-4",
  "metadata": {
    "document_type": "sop",
    "version": "2.0",
    "status": "active",
    "effective_date": "2026-07-01",
    "page": 5,
    "bbox": [72, 140, 510, 230]
  }
}
```

当前Lab 0是简化实现：

- 使用`QdrantClient(":memory:")`；
- Qdrant Payload只保存`chunk_index`；
- Chunk正文和Metadata保存在Python进程内；
- 服务重启后重新建库。

后续应切换到磁盘Local Mode，并将完整Payload写入Qdrant：

```python
QdrantClient(path="artifacts/qdrant/<index_version>")
```

---

## 4. Evidence ID与Chunk映射

### 4.1 为什么不能在召回后再用正则判断

正确流程是：

```text
建库时解析Evidence
  -> Chunk Metadata携带Evidence ID
  -> 召回后直接读取Metadata
  -> 与黄金评估集精确匹配
```

正则表达式可以用于解析Markdown标记，但不应在召回后重新猜测证据归属。

### 4.2 当前Fixed策略的限制

当前Fixed策略按字符切分，然后在每个切片中查找：

```markdown
## [evidence-id] 标题
```

可能出现：

```text
Chunk A：标题和Evidence ID
Chunk B：对应正文
```

此时Evidence ID与正文被拆开。Overlap只能降低风险，不能保证正确。

表格行ID通常由结构解析器生成。例如：

```text
temp-log-aug::table::2026-08-12
```

Fixed切分不生成该行ID，即使召回了整张表，也可能无法在评估中得到命中。

因此，当前Fixed与Structure的指标差异中包含“Evidence映射方式不同”的影响，不能全部解释为检索算法差异。

### 4.3 推荐实现

先解析稳定Evidence Block，再执行Chunk策略：

```text
Document
  -> Evidence Blocks
  -> Fixed/Structure/Parent-Child Chunker
  -> Chunk.contained_evidence_ids
```

建库后生成映射：

```json
{
  "sop-v2-temp-limit": ["chunk-017"],
  "temp-log-aug::table::2026-08-12": ["chunk-031"]
}
```

必须执行以下完整性检查：

1. 评估集中的每个Evidence ID至少映射到一个Chunk；
2. 每个Chunk都能回到原始Document和位置；
3. Evidence正文不能只保留标题而丢失主体；
4. 一个超长Evidence被拆分时，所有子Chunk应保留父Evidence ID和Part信息；
5. 重建索引后输出孤立Evidence、重复ID和冲突ID报告。

---

## 5. 常见文档切分策略

### 5.1 策略总览

| 策略 | 做法 | 适用场景 | 主要风险 |
|---|---|---|---|
| Fixed | 按字符或Token定长切分 | 快速基线、无结构文本 | 切断条款、句子和表格 |
| Recursive | 标题、段落、句子、Token逐级降级 | 通用文档 | 不理解业务边界 |
| Sentence/Paragraph | 按自然语言边界切分 | FAQ、说明文档 | 长度不均 |
| Structure | 按章节、条款、列表、表格行切分 | SOP、法规、标准 | 依赖解析质量 |
| Parent-Child | 小块检索，返回父级上下文 | 长制度、手册 | 索引关系更复杂 |
| Sliding Window | 每个单元附带前后窗口 | 上下文依赖文本 | 数据重复、Token增加 |
| Semantic | 根据相邻句向量相似度确定边界 | 无标题长文本 | 成本高、阈值不稳定 |
| Proposition | LLM拆成独立事实命题 | 高精度事实问答 | 成本和幻觉风险 |
| Contextual Chunk | 为Chunk补充文档背景后再索引 | 相似条款较多 | 建库成本增加 |
| Domain-specific | 表格按行、代码按函数、日志按事件 | 结构化领域数据 | 需要多套解析器 |

### 5.2 Fixed切分

```text
chunk_size = 500
chunk_overlap = 50
step = 450
```

优点：

- 实现简单；
- 速度快；
- 容易建立Baseline。

缺点：

- 不理解标题和正文；
- 可能切开表格行；
- Chunk可能过大，引用不精确；
- Overlap会增加重复向量和上下文。

### 5.3 Recursive切分

```text
标题
  -> 段落
  -> 句子
  -> Token
```

优先保持较大语义单元，仅在超长时继续拆分。它比Fixed稳定，但仍需要先识别表格、公式等特殊块。

### 5.4 Structure切分

按Markdown/PDF结构生成：

```text
section
clause
list_item
table_row
cell
figure
formula
```

当前Lab 0中，Structure切分会：

- 使用`## [evidence-id]`作为条款Evidence；
- 将标题和正文保存在同一个Chunk；
- 将Markdown表格按行切分；
- 使用第一列生成稳定表格行ID。

当前实现中，`chunk_size`和`chunk_overlap`对Structure策略不生效。

### 5.5 Parent-Child

```text
Parent：SOP 4.3异常处理完整章节
  Child A：通知负责人
  Child B：隔离试剂
  Child C：创建偏差记录
```

检索Child提高精度，生成时返回Parent保留上下文。适合：

- SOP；
- ISO条款；
- 技术手册；
- 检验项目说明。

### 5.6 Semantic切分

计算相邻句子Embedding相似度：

```text
相似度稳定 -> 同一Chunk
相似度显著下降 -> 新Chunk
```

适合没有明确标题的长文本。缺点是：

- 建库成本高；
- 阈值受Embedding模型影响；
- 同一文档在模型升级后边界可能变化；
- 可审计性弱于结构切分。

### 5.7 Proposition切分

将复合句拆成原子命题：

```text
原文：
温度超过5°C时不得标记为合格，应通知负责人并隔离试剂。

命题：
温度超过5°C时不得标记为合格。
温度超过5°C时应通知负责人。
温度超过5°C时应隔离试剂。
```

生成命题不能替代原文证据。必须保存：

- 原文；
- 命题；
- 原文Evidence ID；
- 生成模型和Prompt版本；
- 人工复核状态。

### 5.8 Roche场景推荐路由

| 文档类型 | 推荐主策略 | 补充策略 |
|---|---|---|
| SOP、制度、ISO文件 | Structure + Parent-Child | 超长条款递归切分 |
| 手填记录表 | 表格行/单元格 | OCR低置信度人工复核 |
| 检验报告 | 报告章节 + 检验项目行 | 患者趋势独立结构化查询 |
| 仪器日志 | 单条事件或时间窗口 | 错误码关键词索引 |
| 普通说明文档 | Recursive | 必要时Semantic |
| 无结构扫描件 | Layout + OCR + Recursive | 保存页图和坐标 |
| 流程图 | 图结构 + 文本摘要 | 保留原图和节点/边 |

不要为全部文档设置一种全局切分器。应先识别文档类型，再选择解析和切分策略。

---

## 6. 复杂PDF处理

### 6.1 先区分PDF类型

| 类型 | 特征 | 主处理方式 |
|---|---|---|
| Born-digital | 可选中文字，有原生文本层 | 原生文本和坐标优先 |
| Scanned | 页面本质是图片 | 页面渲染 + OCR |
| Hybrid | 部分页面有文本，部分为图片 | 逐页判断并组合 |
| Form-based | 表单、复选框、签名、印章 | Layout + 表单专用解析 |

不能对所有PDF统一执行OCR。Born-digital PDF直接OCR可能降低精度并破坏阅读顺序。

### 6.2 推荐离线解析Pipeline

```text
文件接收
  -> 文件类型、大小、加密和安全检查
  -> 页级分类
  -> 原生文本抽取
  -> 页面渲染
  -> OCR和版面分析
  -> Reading Order恢复
  -> 表格/公式/图片/流程图专用处理
  -> 多路结果对齐
  -> Evidence Block
  -> 质量闸门
  -> 人工复核队列
  -> 知识库发布
```

推荐保存三层产物：

1. 原始文件；
2. 页面级中间产物，包括图片、OCR和Layout JSON；
3. 可索引Evidence Block。

### 6.3 多栏和复杂排版

常见错误是直接按PDF内部字符顺序拼接，导致：

- 左右栏交叉；
- 页眉页脚进入正文；
- 脚注插入主句；
- 图注与图片分离；
- 标题与下一章节错配。

需要使用Layout Block：

```json
{
  "page": 8,
  "block_type": "paragraph",
  "bbox": [72, 180, 290, 420],
  "reading_order": 12,
  "text": "..."
}
```

处理规则：

1. 检测标题、正文、列表、表格、图片、公式、页眉和页脚；
2. 根据栏位置和连通关系恢复阅读顺序；
3. 删除重复页眉页脚，但保留页码映射；
4. 将脚注与引用位置关联，而不是任意拼接；
5. 每个Block保留页码和Bounding Box。

### 6.4 扫描件和手写表格

推荐流程：

```text
图像方向校正
  -> 去噪/裁边/透视校正
  -> 表格和文本区域检测
  -> 印刷体/手写体OCR
  -> 单元格结构恢复
  -> 字段规则校验
  -> 低置信度人工复核
```

不应只保存OCR文本，还应保存：

- 原始页图；
- OCR文本；
- 字符或单元格坐标；
- OCR置信度；
- 原图裁剪；
- 人工修订前后值。

例如：

```json
{
  "evidence_id": "temp-log-2026-08-14-D9",
  "page": 1,
  "table_cell": "D9",
  "ocr_text": "9",
  "ocr_confidence": 0.42,
  "normalized_value": null,
  "requires_human_review": true
}
```

### 6.5 表格

表格不能仅转换为一段以空格分隔的文本。应保存：

```json
{
  "table_id": "temp-log-aug",
  "page": 1,
  "headers": ["日期", "时间", "温度", "人工判定"],
  "rows": [
    {
      "row_id": "2026-08-12",
      "cells": {
        "日期": "2026-08-12",
        "时间": "09:00",
        "温度": "7°C",
        "人工判定": "合格"
      }
    }
  ]
}
```

需要处理：

- 合并单元格；
- 多级表头；
- 跨页表格；
- 行列颠倒；
- 单位位于表头而不在数据单元格；
- 空单元格和续行；
- 表下注释。

推荐建立两级索引：

- Parent：完整表格说明和表头；
- Child：单行或单元格Evidence。

Born-digital表格可优先尝试原生线条/字符解析；扫描表格使用Layout/OCR模型。无论使用哪种工具，都必须基于黄金表格样本验证行列和合并单元格准确率。

### 6.6 公式

公式应保存双重表示：

```json
{
  "formula_id": "formula-egfr-01",
  "latex": "...",
  "plain_text": "eGFR equals ...",
  "variables": {
    "Scr": "serum creatinine"
  },
  "page": 12,
  "bbox": [90, 240, 480, 310],
  "image_uri": "..."
}
```

处理原则：

1. Born-digital PDF优先读取原始字符和Math对象；
2. 图片公式使用数学OCR转换为LaTeX；
3. 同时保留公式图片，便于审计；
4. 单位、上下标、分母和括号必须单独校验；
5. 公式用于计算前必须由程序解析和测试，不能直接让LLM口算。

### 6.7 流程图

仅对流程图执行OCR会丢失箭头和拓扑关系。建议保存：

```json
{
  "diagram_id": "review-flow-01",
  "page": 16,
  "nodes": [
    {"id": "n1", "type": "start", "text": "收到报告"},
    {"id": "n2", "type": "decision", "text": "是否命中危急值规则"},
    {"id": "n3", "type": "action", "text": "转人工复核"}
  ],
  "edges": [
    {"source": "n1", "target": "n2", "label": ""},
    {"source": "n2", "target": "n3", "label": "是"}
  ],
  "summary": "收到报告后先检查危急值规则，命中时转人工复核。",
  "image_uri": "...",
  "confidence": 0.86
}
```

推荐处理：

1. 检测并裁剪图形区域；
2. OCR节点文字和边标签；
3. 检测形状、箭头方向和连接点；
4. 生成节点/边图结构；
5. 使用视觉语言模型生成辅助摘要；
6. 将图结构、摘要和原图共同保存；
7. 对低置信度边和循环进入人工复核。

视觉语言模型的描述不能作为唯一证据。审核时必须能够回到原始页面和流程图区域。

### 6.8 图片、图表、签名和印章

| 类型 | 建议表示 |
|---|---|
| 普通图片 | 图片裁剪 + 图注 + OCR + VLM描述 |
| 柱状图/折线图 | 标题、坐标轴、图例、数据点、原图 |
| 签名 | 是否存在、位置、人工确认状态，不自动推断身份 |
| 印章 | 印章区域、OCR文本、置信度、人工复核 |
| 勾选框 | 选中状态、字段名、坐标、置信度 |

对于合规和医学场景，模型不能根据模糊签名或印章自动确认人员身份。

### 6.9 本地化工具选择参考

下列工具可作为技术选型候选，不应在未评估数据前固定：

| 能力 | 可选本地工具 |
|---|---|
| 原生PDF文本与坐标 | PyMuPDF、pdfplumber、pypdf |
| 通用文档解析 | Docling、Unstructured、MinerU |
| OCR | PaddleOCR、Tesseract |
| 扫描表格/Layout | PaddleOCR PP-Structure、Layout模型 |
| Born-digital表格 | Camelot、Tabula、pdfplumber |
| 数学公式 | 数学OCR模型、MinerU相关能力 |
| 图片/流程图理解 | 本地VLM + OCR + 图结构程序 |

选择时应评价：

- 是否能完全本地部署；
- CPU/GPU和显存要求；
- 中文、手写体和医学术语表现；
- 页码和坐标是否保留；
- 是否支持批处理和失败恢复；
- 许可证和商业使用限制；
- 输出Schema是否稳定。

---

## 7. RAG评估数据集

### 7.1 当前JSONL格式

每行一条案例：

```json
{
  "case_id": "iso-dev-01",
  "split": "dev",
  "question": "现行SOP规定试剂冰箱最高温度是多少？",
  "expected_evidence_ids": ["sop-v2-temp-limit"],
  "answerable": true,
  "reference_answer": "现行SOP规定试剂冰箱温度不得高于5°C。",
  "tags": ["version", "clause"]
}
```

字段说明：

| 字段 | 含义 |
|---|---|
| `case_id` | 稳定案例ID |
| `split` | `dev`调参与`test`保留测试 |
| `question` | 用户问题 |
| `expected_evidence_ids` | 回答问题所需黄金证据 |
| `answerable` | 当前知识库是否可回答 |
| `reference_answer` | 参考答案，当前确定性检索指标不使用 |
| `tags` | 版本、表格、OCR、冲突等分类 |

### 7.2 expected_evidence_ids

`expected_evidence_ids`表示正确回答问题时应召回的原始证据。

单证据：

```json
"expected_evidence_ids": ["sop-v2-temp-limit"]
```

多证据：

```json
"expected_evidence_ids": [
  "appointment-li-ming",
  "role-register-li-ming"
]
```

如果只召回一个，Evidence Recall为：

```text
1 / 2 = 0.5
```

无法回答的问题：

```json
{
  "question": "冰箱R-02在8月20日的温度是多少？",
  "expected_evidence_ids": [],
  "answerable": false,
  "reference_answer": null
}
```

### 7.3 数据集如何制作

推荐流程：

1. 固定文档版本和Evidence Catalog；
2. 从真实工作任务抽取问题类型；
3. 由标注人员独立查找原始证据；
4. 标注最小充分证据集合；
5. 标注不可回答、冲突和低置信度案例；
6. 编写参考答案，但保留事实与建议边界；
7. 第二人复核Evidence ID和答案；
8. 按问题类型、文档和证据分层划分dev/test；
9. 冻结Dataset版本；
10. Pipeline调优过程中不得修改test标签。

不能根据当前检索器的返回结果反向制作黄金集，否则会把系统偏差写入评估数据。

### 7.4 推荐扩展格式

生产数据需要表达多条正确路径和分级相关性：

```json
{
  "case_id": "case-001",
  "question": "冰箱温度上限是多少？",
  "answerable": true,
  "acceptable_evidence_sets": [
    ["sop-v2-temp-limit"],
    ["iso-temperature-policy", "refrigerator-scope"]
  ],
  "relevance_judgments": [
    {
      "evidence_id": "sop-v2-temp-limit",
      "relevance": 3,
      "required": true
    },
    {
      "evidence_id": "sop-v2-scope",
      "relevance": 1,
      "required": false
    }
  ],
  "reference_answer": "不得高于5°C。",
  "tags": ["sop", "version"]
}
```

相关性等级示例：

```text
0 = 不相关
1 = 辅助背景
2 = 相关证据
3 = 核心证据
```

### 7.5 没有专家时能评什么

可以评价：

- 解析结构；
- Evidence ID覆盖；
- 检索和排序；
- 引用定位；
- 版本过滤；
- 规则执行；
- 工具轨迹；
- 拒答和人工升级；
- 延迟、Token和错误率。

不能宣称：

- 医学建议准确率；
- 临床审核灵敏度/特异度；
- ISO真实不符合项漏检率；
- 真实根因识别率；
- 与专家审核一致率。

---

## 8. 确定性评估指标

设：

- `G(q)`：问题`q`的黄金Evidence ID集合；
- `R_K(q)`：Top-K召回Evidence ID序列；
- `C(q)`：最终附加到回答中的Citation ID集合；
- `rel_i`：排名`i`结果的相关性等级。

### 8.1 Evidence Recall@K

```text
Recall@K(q) = |G(q) ∩ R_K(q)| / |G(q)|
```

意义：应找到的证据中找到了多少。

例如：

```text
Gold      = {A, B}
Retrieved = {A, C, D}
Recall    = 1 / 2 = 0.5
```

当前项目的`Evidence Recall`实际由配置的召回和重排数量决定，报告名称尚未显式携带`@K`。

### 8.2 Hit Rate@K

```text
Hit@K(q) = 1，若G(q) ∩ R_K(q)非空
           0，其他情况
```

它只判断是否至少找到一条相关证据，不关心多证据覆盖率。

### 8.3 Precision@K

```text
Precision@K(q) = |G(q) ∩ R_K(q)| / K
```

意义：返回结果中有多少是相关证据。多证据和可接受证据路径需要先定义清楚。

### 8.4 MRR

```text
RR(q) = 1 / 第一个正确Evidence的排名
MRR   = 所有问题RR的平均值
```

例如正确证据排第三：

```text
RR = 1 / 3 = 0.333
```

如果没有召回正确证据，RR为0。

MRR主要衡量“第一个正确结果是否靠前”，不评价后续正确证据。

### 8.5 nDCG

标准分级相关性版本：

```text
DCG@K = Σ (2^rel_i - 1) / log2(i + 1)
nDCG  = DCG / IDCG
```

当前项目使用二元相关性的简化版本：

```text
相关结果得分 = 1 / log2(i + 1)
不相关结果得分 = 0
```

nDCG同时考虑：

- 是否召回；
- 排名是否靠前；
- 在扩展格式中可支持分级相关性。

### 8.6 Citation Recall

```text
Citation Recall(q) = |G(q) ∩ C(q)| / |G(q)|
```

意义：黄金证据中有多少被附加为最终引用。

当前Lab 0的Citation是根据选中的Chunk自动生成，不是从LLM回答文本中反向解析。因此它评价“系统附加的引用”，尚不能证明LLM每个陈述都与引用严格对应。

### 8.7 Citation Precision

```text
Citation Precision(q) = |G(q) ∩ C(q)| / |C(q)|
```

当前项目尚未实现。生产系统应同时看Recall和Precision，防止通过附加大量引用提高Recall。

### 8.8 Abstention Accuracy

```text
预期拒答 = not answerable
Abstention Accuracy = 系统拒答状态是否与预期一致
```

需要覆盖：

- 知识库无答案；
- 证据冲突；
- OCR置信度不足；
- 关键数据缺失；
- 权限不足。

### 8.9 Context Chars

```text
Context Chars = 进入生成节点的Chunk正文字符总数
```

它不是Token数，也不包含完整Prompt。用途是作为本地、模型无关的上下文成本近似值。

生产环境还应记录：

- Input Tokens；
- Output Tokens；
- Embedding Tokens；
- 模型调用次数；
- P50/P95延迟；
- 单案例费用；
- 缓存命中率。

### 8.10 指标示例

原5文档、8条dev案例的Fixed Baseline曾得到：

```text
Evidence Recall:
(1 + 0 + 0 + 1 + 1 + 1 + 1 + 1) / 8 = 0.750

Citation Recall:
(1 + 0 + 0 + 0 + 0.5 + 0 + 0 + 0) / 8 = 0.1875

Mean Context Chars:
7342 / 8 = 917.75
```

这些数字属于特定数据、索引和配置快照。文档、Embedding、切分或Top-K变化后必须重新计算。

---

## 9. 文档解析质量指标

复杂文档不能只评价最终问答。应在解析层建立独立黄金集。

### 9.1 OCR

- Character Error Rate；
- Word Error Rate；
- 数字准确率；
- 单位准确率；
- 低置信度升级率；
- 关键字段漏检率。

医学和记录表中，数字、正负号、小数点、单位和参考范围应单独统计，不能只看总体字符准确率。

### 9.2 Layout

- Block类型准确率；
- Reading Order准确率；
- 标题层级准确率；
- 页眉页脚移除准确率；
- Page/BBox定位完整率；
- 跨页内容连接准确率。

### 9.3 表格

- 表格检测Recall；
- 行列结构准确率；
- Cell文本准确率；
- 合并单元格准确率；
- Header关联准确率；
- 跨页表格拼接准确率；
- Row Evidence ID稳定率。

### 9.4 流程图

- 节点检测Precision/Recall；
- 节点文字OCR准确率；
- Edge方向准确率；
- Edge标签准确率；
- 图连通性准确率；
- 低置信度人工升级率。

---

## 10. RAGAS

### 10.1 当前使用的指标

当前项目可选运行：

- Faithfulness；
- Answer Relevancy。

命令：

```bash
roche-lab rag evaluate \
  --config labs/E0_pipeline/config.workshop.yaml \
  --split dev \
  --ragas
```

### 10.2 Faithfulness

典型过程：

```text
回答
  -> 拆成Statements
  -> 根据Retrieved Context逐条执行NLI判断
  -> 计算得到支持的Statements比例
```

Faithfulness评价回答是否被上下文支持，不等于医学正确性。

### 10.3 Answer Relevancy

评价回答是否切中用户问题。它不能判断引用是否正确，也不能替代业务专家。

### 10.4 RAGAS的工程风险

- Judge输出可能不满足Schema；
- 长回答会生成大量NLI Statements；
- 输出Token不足会截断JSON；
- 模型升级后评分分布可能变化；
- 30名学员并发会导致Bedrock限流；
- Judge与被评模型相同时可能存在自评偏差。

项目默认配置：

```dotenv
RAGAS_MAX_TOKENS=4096
RAGAS_MAX_WORKERS=2
RAGAS_MAX_RETRIES=3
RAGAS_TIMEOUT_SECONDS=180
```

解析失败时：

- 单项Metric记录为`null`；
- 其他案例和确定性指标继续完成；
- `ragas.summary.failed_metrics`列出失败问题；
- 不能忽略失败率只报告平均分。

---

## 11. LLM-as-a-Judge

LLM Judge适合评价难以完全程序化的维度：

- 答案是否完整；
- 是否遵循回答格式；
- 是否区分事实、假设和建议；
- 是否存在无证据因果断言；
- 建议是否引用了业务约束。

推荐使用结构化Rubric：

```json
{
  "grounded": {
    "score": 0,
    "reason": ""
  },
  "complete": {
    "score": 0,
    "reason": ""
  },
  "causal_language_safe": {
    "score": 0,
    "reason": ""
  }
}
```

使用原则：

1. Judge Prompt和模型版本必须固定；
2. 用专家小样本校准Judge；
3. 对关键案例定期人工抽检；
4. 记录解析失败率和Judge重试次数；
5. 不让LLM Judge为医学结论“自证正确”；
6. 架构选型优先看确定性指标，再参考Judge。

当前Lab 0尚未接入自定义LLM Judge。

---

## 12. Langfuse、RAGAS与本地指标分工

| 能力 | 组件 |
|---|---|
| Trace、Span、延迟、Token | Langfuse |
| Dataset、Experiment、Score归档 | Langfuse |
| 人工Annotation | Langfuse |
| Recall、MRR、nDCG、引用、拒答 | 本地确定性指标 |
| Faithfulness、Answer Relevancy | RAGAS |
| 业务Rubric评价 | 可选LLM Judge |
| 医学与ISO有效性 | 领域专家 |

推荐流程：

```text
Dataset
  -> 同一Pipeline批量运行
  -> 确定性指标
  -> 可选RAGAS
  -> 可选LLM Judge
  -> Score写入Langfuse
  -> 配置对比
  -> 人工审批发布
```

Langfuse是实验和可观测平台，不是评分算法本身。RAGAS是指标引擎，不是Trace平台。

---

## 13. 索引与查询参数

### 13.1 修改后必须重建索引

- 文档内容；
- 文档解析器；
- Evidence Block定义；
- Chunk策略；
- Chunk大小和Overlap；
- Embedding模型；
- Embedding预处理；
- 向量距离度量；
- 写入Payload的Metadata结构。

### 13.2 通常无需重建索引

- Query改写；
- Retrieval Top-K；
- Hybrid Alpha；
- Rerank Candidate K；
- Rerank Top-N；
- Min Relevance Score；
- 生成Prompt；
- 生成模型参数；
- 拒答阈值。

### 13.3 Index Manifest

每次建库应保存：

```json
{
  "index_version": "lab0-af1914814d",
  "data_version": "iso-training-v1",
  "document_hashes": {},
  "parser_version": "parser-v1",
  "chunk_strategy": "structure",
  "chunk_config": {},
  "embedding_model": "amazon.titan-embed-...",
  "vector_backend": "qdrant-local",
  "document_count": 5,
  "evidence_count": 15,
  "chunk_count": 15,
  "built_at": "2026-08-25T..."
}
```

评估报告必须绑定`index_version`，否则不能复现。

---

## 14. 本地运行命令

### 14.1 启动Lab 0

```bash
roche-lab web \
  --config labs/E0_pipeline/config.baseline.yaml \
  --host 127.0.0.1 \
  --port 8899
```

### 14.2 Fixed Baseline

```bash
roche-lab rag evaluate \
  --config labs/E0_pipeline/config.baseline.yaml \
  --split dev
```

结果：

```text
artifacts/e0-baseline/dev.json
```

### 14.3 参数Sweep

```bash
roche-lab rag sweep \
  --matrix labs/E1_tuning/experiment_matrix.yaml
```

结果：

```text
artifacts/e1-sweep.json
```

### 14.4 RAGAS

```bash
roche-lab rag evaluate \
  --config labs/E0_pipeline/config.workshop.yaml \
  --split dev \
  --ragas
```

---

## 15. 推荐评估分层

### 15.1 组件层

- OCR和Layout；
- Evidence抽取；
- Chunk映射；
- Embedding；
- Recall@K；
- Rerank；
- SQL和工具Schema。

### 15.2 轨迹层

- LangGraph节点顺序；
- 工具选择；
- 禁止调用；
- 最大步骤；
- 超时和重试；
- 人工升级。

### 15.3 结果层

- Evidence覆盖；
- Citation Precision/Recall；
- Faithfulness；
- Answer Relevancy；
- 拒答；
- 结构化输出；
- 事实、假设与建议边界。

### 15.4 系统层

- P50/P95延迟；
- Token；
- 模型调用数；
- 错误率；
- 限流率；
- 缓存命中；
- Trace完整率；
- 单案例成本；
- 本地CPU/GPU和内存。

---

## 16. Roche场景推荐实施路线

### 阶段1：可重复Baseline

- 固定合成文档；
- 建立Evidence ID；
- 建立20至50条初始工程评估案例；
- 使用Fixed和Structure形成对照；
- 接入Langfuse；
- 确定性指标先行。

### 阶段2：复杂文档解析

- Born-digital PDF；
- 扫描件OCR；
- 表格结构；
- 页码和BBox；
- 低置信度人工复核；
- 解析层黄金集。

### 阶段3：检索升级

- Parent-Child；
- BM25 + 向量混合检索；
- Metadata过滤；
- Rerank；
- 磁盘Qdrant；
- 完整Payload。

### 阶段4：语义评价

- RAGAS；
- 自定义LLM Judge；
- Judge校准集；
- Langfuse Experiment；
- 成本和稳定性闸门。

### 阶段5：业务专家验证

- 脱敏真实数据；
- 医学和ISO专家标注；
- 规则审批；
- 错误严重度分层；
- 影子运行；
- 人工审批后逐步上线。

---

## 17. 当前Lab 0边界

当前已经实现：

- LangGraph在线RAG工作流；
- Markdown加载；
- Fixed和Structure切分；
- Hash/Titan Embedding；
- Qdrant内存Local Mode；
- BM25混合召回；
- 轻量重排；
- Bedrock Claude生成；
- 本地确定性评估；
- 可选RAGAS；
- Langfuse Trace和Score；
- Web参数调整、重建索引和后台评估。

当前尚未实现：

- PDF、Word、Excel直接导入；
- OCR和Layout模型；
- 公式和流程图解析；
- 磁盘Qdrant和完整Payload；
- 独立Evidence Catalog；
- Fixed与Structure统一Evidence映射；
- Citation Precision；
- 可接受证据组合；
- 自定义LLM Judge；
- 上传和管理自定义评估集；
- 多轮Session ID；
- 真实医学和ISO专家黄金集。

这些限制应作为后续实验和生产Backlog，而不是在课程中隐含为已经解决。

---

## 18. 最终原则

1. 先定义Evidence，再定义Chunk；
2. Chunk可以变化，Evidence ID必须稳定；
3. 复杂文档先评价解析，再评价RAG；
4. 表格、公式和流程图需要专用表示；
5. 检索指标、语义指标和业务正确性不能混为一谈；
6. RAGAS和LLM Judge不能替代专家真值；
7. 每个评估结果必须绑定数据、索引、模型和Prompt版本；
8. 低置信度证据必须进入人工复核；
9. 生产系统必须保存原始证据位置和审计轨迹；
10. 指标提升必须说明收益、成本和失败案例，而不是只报告一个平均分。
