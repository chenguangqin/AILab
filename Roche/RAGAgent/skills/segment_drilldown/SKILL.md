---
name: segment-drilldown
version: 1.0.0
description: 按时段、来源科室等受治理维度比较前处理耗时、TAT和报错率
risk_level: read_only
max_steps: 1
allowed_scripts:
  - run.py
references:
  - metrics.md
---

# 分群下钻

用于确认异常集中在哪些业务分群。只能使用语义层允许的维度，不生成任意 SQL。

输出必须包含分群名称、样本量、前处理耗时、TAT和报错率。样本量不足时不得作确定性结论。

