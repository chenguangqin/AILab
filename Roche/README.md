# 罗氏 · 大模型微调实操

LLM 微调课程的实操 lab。任务贯穿：**临床短句 → 结构化 JSON 抽取**。基座 Qwen3-0.6B，环境 AWS SageMaker T4（16G）。

## 文件

| 文件 | 讲什么 |
|---|---|
| `EF_compare_hf_vs_unsloth.ipynb` | **微调入门 + 框架对比**。简单任务（唯一隐含约定 sex→M/F），few-shot 也够用 → 讲**能力阶梯**：轻手段够用就先用；微调价值 = 零样本达到 few-shot 质量、**省示例 token（降本降延迟）**。含 base/HF/unsloth 三方对比、train/val 过拟合曲线。 |
| `EF_finetune_advantage.ipynb` | **微调的质量优势**。硬任务：三重隐含约定（sex→M/F、检验项名→内部代码 T01…T08、flag 词→字母 L/H/N），**代码 8 种 > few-shot 的 3 个示例** → few-shot 覆盖不全、达不到满分，微调见过全部数据 → ~100%。体现「约定类别多、杂」时微调质量碾压 few-shot。 |

两个 notebook 共享同一套流水线（base 对照 / HF 微调 / unsloth 微调 / 对比 / 判质），只有数据任务不同。

## 运行环境

- **目标**：AWS SageMaker Notebook，单卡 **T4（16G 显存）**
- **T4 硬约束**：精度用 **fp16**（不支持 bf16）；注意力用 **sdpa**（不支持 FlashAttention-2）
- 仅用开源框架（transformers / trl / peft / unsloth），**不依赖 SageMaker SDK**，可在任意带 GPU（≥8G）环境运行
- 全部代码**内联在 cell 里执行**；每个方案用函数封装，跑完 `free()` 清显存

## 怎么跑

任选一个 notebook，从上往下按节运行：
安装依赖（装完 unsloth **重启 kernel**）→ 环境自检 → 配置 → 生成数据 → 工具函数 → base 对照 → HF 微调 → unsloth 微调 → 对比 → 判质。

⚠️ **HF 必须在 unsloth 之前跑**（unsloth import 会 patch trl）。改了 notebook 后若结果没变，多为 Jupyter 自动保存覆盖了 git 更新——先在 Jupyter 里 Close and Halt，再 `git reset --hard origin/main`，重开后 Restart & Run All。

## RAG + Agent课程

三天RAG与企业Agent工程实验位于 [`RAGAgent/`](RAGAgent/README.md)，包含：

- 完整RAG构建、查询、评估Pipeline；
- Qdrant Local Mode、Bedrock Claude/Titan适配；
- Langfuse与RAGAS评估；
- LangGraph Workflow/ReAct/Skill实验；
- 客户模拟检验科运行数据和根因调查；
- 本地测试、Workshop脚本及Capstone材料。
