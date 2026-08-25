# E2：从“找得到”到“判得出”

## 我们提供

- SOP、OCR JSON和人员文件；
- 已验证的教学Fact；
- `TemperatureMaxRule`与`RoleConsistencyRule`骨架；
- 低OCR置信度案例；
- Finding、RuleResult和Evidence契约。

## 学员任务

1. 对比“LLM直接判断合规”和确定性规则结果。
2. 检查Fact的来源、置信度与时间范围。
3. 执行温度规则，识别“7°C却标记合格”。
4. 执行人员职务一致性规则。
5. 确认低置信度OCR不会进入自动判定。
6. 输出包含规则版本、证据ID和人工动作的证据包。

```bash
roche-lab rules evaluate
```

规则候选可以由LLM辅助抽取，但只有经过批准的版本化规则才能进入执行路径。

