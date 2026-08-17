# 罗氏 · 大模型微调实操

LLM 微调课程的实操 lab。任务贯穿：**临床短句 → 结构化 JSON 抽取**。

## 文件

| 文件 | 说明 |
|---|---|
| `EF_compare_hf_vs_unsloth.ipynb` | 微调 Qwen3-0.6B，对比「不微调 vs 微调」与「HuggingFace vs unsloth」 |

## 这个 lab 回答两个问题

1. **微调值不值？** 同一留出集上比三档：base 零样本 / base 少样本(3例) / 微调后。
   关键设计：指令给了字段名却**不说 `sex` 要归一成 `M/F`** —— base 只能猜（栽在这个隐含约定 + 输出干净度），微调把约定内化 → 精确匹配大幅提升。演绎「行为/格式用微调 + 免长 prompt 降本降延迟」。
2. **框架 HF vs unsloth 差多少？** 同数据、同 LoRA 配置、同步数下比训练时间 / 峰值显存 / 上手成本。

## 运行环境

- **目标**：AWS SageMaker Notebook，单卡 **T4（16G 显存）**
- **T4 硬约束**：精度用 **fp16**（不支持 bf16）；注意力用 **sdpa**（不支持 FlashAttention-2）
- 仅用开源框架（transformers / trl / peft / unsloth），**不依赖 SageMaker SDK**，可在任意带 GPU（≥8G）环境运行
- 两条框架路线各写成独立脚本、子进程运行：显存测量干净，且 unsloth 的 monkey-patch 不污染 HF 路线

## 怎么跑

打开 `EF_compare_hf_vs_unsloth.ipynb`，从上往下按节运行：
环境自检 → 装依赖（装完 unsloth **重启 kernel**）→ 生成数据 → 配置 → 基线评估 → 训练 HF → 训练 unsloth → 对比 → 判质。
