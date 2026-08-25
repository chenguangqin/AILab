---
name: preprocessing-error-analysis
version: 1.0.0
description: 分析异常分群中的前处理错误类型及其数量
risk_level: read_only
max_steps: 1
allowed_scripts:
  - run.py
references:
  - error_taxonomy.md
---

# 前处理错误分析

仅在分群下钻已经发现报错率异常后使用。输出错误类型和计数，不把错误类型直接等同于最终根因。

