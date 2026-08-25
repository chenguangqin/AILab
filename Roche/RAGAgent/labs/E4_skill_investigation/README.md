# E4：Skill驱动的根因调查

## 我们提供

- 客户提供的1,426条检验科运行模拟数据；
- CSV到SQLite多表导入器；
- 只读SQL验证和语义层查询；
- `SkillRegistry`；
- 三个`SKILL.md + references + scripts`示例；
- 有步骤预算的LangGraph调查循环。

## 学员任务

1. 导入CSV并检查表结构和指标口径。
2. 阅读Skill摘要，再按需加载`SKILL.md`与reference。
3. 运行分群下钻、前处理错误分析和反对证据搜索。
4. 确认脚本不在白名单时无法执行。
5. 将结果区分为事实、候选原因、反对证据和待补数据。
6. 新增一个只读Skill，例如日期异常分析或专业组分析。

```bash
roche-lab analytics import \
  --csv data/analytics/raw/lab_operations_2026-08.csv \
  --db artifacts/lab_operations.db

roche-lab analytics investigate \
  --db artifacts/lab_operations.db \
  --question "为什么早高峰前处理耗时上升？"
```

现有数据只能支持候选原因，不能证明“儿科采血问题导致全院延迟”的因果关系。

