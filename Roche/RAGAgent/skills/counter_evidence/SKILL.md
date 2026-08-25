---
name: counter-evidence-search
version: 1.0.0
description: 主动比较不同前处理工位，寻找反对“单一工位故障”假设的证据
risk_level: read_only
max_steps: 1
allowed_scripts:
  - run.py
references:
  - reasoning.md
---

# 反对证据搜索

在形成候选原因前必须运行。比较各工位表现，避免只寻找支持当前假设的证据。

