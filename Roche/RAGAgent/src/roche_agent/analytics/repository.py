from __future__ import annotations

import csv
import sqlite3
from pathlib import Path
from typing import Any

import sqlglot
from sqlglot import exp


SCHEMA = """
CREATE TABLE specimens (
    specimen_id TEXT PRIMARY KEY,
    collection_date TEXT NOT NULL,
    weekday TEXT NOT NULL,
    collection_time TEXT NOT NULL,
    collection_period TEXT NOT NULL,
    source_department TEXT NOT NULL,
    patient_type TEXT NOT NULL,
    specimen_type TEXT NOT NULL,
    specialty_group TEXT NOT NULL,
    test_count INTEGER NOT NULL,
    target_tat_minutes INTEGER NOT NULL
);

CREATE TABLE process_metrics (
    specimen_id TEXT PRIMARY KEY REFERENCES specimens(specimen_id),
    received_time TEXT NOT NULL,
    preprocessing_start TEXT NOT NULL,
    preprocessing_end TEXT NOT NULL,
    preprocessing_minutes INTEGER NOT NULL,
    instrument_time TEXT NOT NULL,
    report_time TEXT NOT NULL,
    tat_minutes INTEGER NOT NULL,
    timed_out INTEGER NOT NULL
);

CREATE TABLE preprocessing_events (
    specimen_id TEXT PRIMARY KEY REFERENCES specimens(specimen_id),
    status TEXT NOT NULL,
    error_type TEXT,
    workstation TEXT NOT NULL,
    operator_id TEXT NOT NULL
);

CREATE TABLE instrument_assignments (
    specimen_id TEXT PRIMARY KEY REFERENCES specimens(specimen_id),
    instrument_id TEXT NOT NULL
);

CREATE TABLE metric_definitions (
    metric_name TEXT PRIMARY KEY,
    expression TEXT NOT NULL,
    description TEXT NOT NULL
);

CREATE INDEX idx_specimens_period ON specimens(collection_period);
CREATE INDEX idx_specimens_source ON specimens(source_department);
CREATE INDEX idx_preprocessing_status ON preprocessing_events(status);
"""


def import_operations_csv(csv_path: str | Path, db_path: str | Path) -> dict[str, Any]:
    output = Path(db_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    connection = sqlite3.connect(output)
    try:
        connection.executescript(SCHEMA)
        with Path(csv_path).open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        connection.executemany(
            """
            INSERT INTO specimens VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["标本ID"],
                    row["日期"],
                    row["星期"],
                    row["采集时间"],
                    row["采集时段"],
                    row["来源科室/采血点"],
                    row["患者类型"],
                    row["标本类型"],
                    row["检验专业组"],
                    int(row["检验项目数"]),
                    int(row["目标TAT_分钟"]),
                )
                for row in rows
            ],
        )
        connection.executemany(
            """
            INSERT INTO process_metrics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["标本ID"],
                    row["签收时间"],
                    row["前处理开始"],
                    row["前处理完成"],
                    int(row["前处理耗时_分钟"]),
                    row["上机时间"],
                    row["报告时间"],
                    int(row["TAT_分钟"]),
                    int(row["是否超时"] == "是"),
                )
                for row in rows
            ],
        )
        connection.executemany(
            "INSERT INTO preprocessing_events VALUES (?, ?, ?, ?, ?)",
            [
                (
                    row["标本ID"],
                    row["前处理状态"],
                    row["前处理报错类型"] or None,
                    row["前处理工位"],
                    row["操作人"],
                )
                for row in rows
            ],
        )
        connection.executemany(
            "INSERT INTO instrument_assignments VALUES (?, ?)",
            [(row["标本ID"], row["仪器编号"]) for row in rows],
        )
        connection.executemany(
            "INSERT INTO metric_definitions VALUES (?, ?, ?)",
            [
                (
                    "average_tat",
                    "AVG(process_metrics.tat_minutes)",
                    "采集到报告的平均分钟数",
                ),
                (
                    "preprocessing_error_rate",
                    "AVG(preprocessing_events.status = '报错')",
                    "前处理报错标本占比",
                ),
                (
                    "timeout_rate",
                    "AVG(process_metrics.timed_out)",
                    "TAT超过目标TAT的标本占比",
                ),
            ],
        )
        connection.commit()
        return {
            "row_count": len(rows),
            "tables": [
                "specimens",
                "process_metrics",
                "preprocessing_events",
                "instrument_assignments",
                "metric_definitions",
            ],
            "db_path": str(output),
        }
    finally:
        connection.close()


def validate_readonly_sql(sql: str) -> str:
    statements = sqlglot.parse(sql, read="sqlite")
    if len(statements) != 1:
        raise ValueError("exactly one SQL statement is allowed")
    statement = statements[0]
    if not isinstance(statement, exp.Select):
        raise ValueError("only SELECT statements are allowed")
    forbidden = (
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Drop,
        exp.Create,
        exp.Alter,
        exp.Command,
    )
    if any(statement.find(item) for item in forbidden):
        raise ValueError("mutating SQL is not allowed")
    if statement.args.get("limit") is None:
        statement = statement.limit(200)
    return statement.sql(dialect="sqlite")


class AnalyticsRepository:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        safe_sql = validate_readonly_sql(sql)
        connection = sqlite3.connect(self.db_path, timeout=3)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA query_only = ON")
            cursor = connection.execute(safe_sql, params)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            connection.close()

    def overview(self) -> dict[str, Any]:
        return self.query(
            """
            SELECT
              COUNT(*) AS specimen_count,
              ROUND(AVG(pm.preprocessing_minutes), 2) AS avg_preprocessing_minutes,
              ROUND(AVG(pm.tat_minutes), 2) AS avg_tat_minutes,
              ROUND(100.0 * AVG(pm.timed_out), 2) AS timeout_rate_pct,
              ROUND(100.0 * AVG(pe.status = '报错'), 2) AS error_rate_pct
            FROM specimens s
            JOIN process_metrics pm USING (specimen_id)
            JOIN preprocessing_events pe USING (specimen_id)
            """
        )[0]

    def profile_dimension(self, dimension: str, minimum_count: int = 10) -> list[dict[str, Any]]:
        allowed = {
            "collection_date": "s.collection_date",
            "collection_period": "s.collection_period",
            "source_department": "s.source_department",
            "patient_type": "s.patient_type",
            "specialty_group": "s.specialty_group",
            "workstation": "pe.workstation",
            "operator_id": "pe.operator_id",
        }
        if dimension not in allowed:
            raise ValueError(f"unsupported dimension: {dimension}")
        column = allowed[dimension]
        return self.query(
            f"""
            SELECT
              {column} AS dimension_value,
              COUNT(*) AS specimen_count,
              ROUND(AVG(pm.preprocessing_minutes), 2) AS avg_preprocessing_minutes,
              ROUND(AVG(pm.tat_minutes), 2) AS avg_tat_minutes,
              ROUND(100.0 * AVG(pm.timed_out), 2) AS timeout_rate_pct,
              ROUND(100.0 * AVG(pe.status = '报错'), 2) AS error_rate_pct
            FROM specimens s
            JOIN process_metrics pm USING (specimen_id)
            JOIN preprocessing_events pe USING (specimen_id)
            GROUP BY {column}
            HAVING COUNT(*) >= {int(minimum_count)}
            ORDER BY avg_preprocessing_minutes DESC
            """
        )

    def pediatric_peak_comparison(self) -> list[dict[str, Any]]:
        return self.query(
            """
            SELECT
              CASE
                WHEN s.source_department = '儿科门诊采血窗口'
                 AND s.collection_period = '07-10 早高峰'
                THEN '儿科早高峰'
                WHEN s.collection_period = '07-10 早高峰'
                THEN '其他来源早高峰'
                ELSE '非早高峰'
              END AS cohort,
              COUNT(*) AS specimen_count,
              ROUND(AVG(pm.preprocessing_minutes), 2) AS avg_preprocessing_minutes,
              ROUND(AVG(pm.tat_minutes), 2) AS avg_tat_minutes,
              ROUND(100.0 * AVG(pe.status = '报错'), 2) AS error_rate_pct
            FROM specimens s
            JOIN process_metrics pm USING (specimen_id)
            JOIN preprocessing_events pe USING (specimen_id)
            GROUP BY cohort
            ORDER BY error_rate_pct DESC
            """
        )

    def pediatric_error_types(self) -> list[dict[str, Any]]:
        return self.query(
            """
            SELECT
              pe.error_type,
              COUNT(*) AS error_count
            FROM specimens s
            JOIN preprocessing_events pe USING (specimen_id)
            WHERE s.source_department = '儿科门诊采血窗口'
              AND s.collection_period = '07-10 早高峰'
              AND pe.status = '报错'
            GROUP BY pe.error_type
            ORDER BY error_count DESC
            """
        )

    def counter_evidence(self) -> list[dict[str, Any]]:
        return self.query(
            """
            SELECT
              pe.workstation,
              COUNT(*) AS specimen_count,
              ROUND(AVG(pm.preprocessing_minutes), 2) AS avg_preprocessing_minutes,
              ROUND(100.0 * AVG(pe.status = '报错'), 2) AS error_rate_pct
            FROM process_metrics pm
            JOIN preprocessing_events pe USING (specimen_id)
            GROUP BY pe.workstation
            ORDER BY avg_preprocessing_minutes DESC
            """
        )

