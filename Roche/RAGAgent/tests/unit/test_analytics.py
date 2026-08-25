import sqlite3

import pytest

from roche_agent.analytics import AnalyticsRepository, import_operations_csv
from roche_agent.analytics.repository import validate_readonly_sql


@pytest.fixture
def analytics_db(tmp_path, project_root):
    path = tmp_path / "operations.db"
    result = import_operations_csv(
        project_root / "data" / "analytics" / "raw" / "lab_operations_2026-08.csv",
        path,
    )
    assert result["row_count"] == 1426
    return path


def test_import_and_expected_pediatric_peak_pattern(analytics_db):
    repository = AnalyticsRepository(analytics_db)
    cohorts = {row["cohort"]: row for row in repository.pediatric_peak_comparison()}
    assert cohorts["儿科早高峰"]["error_rate_pct"] > 20
    assert cohorts["其他来源早高峰"]["error_rate_pct"] < 10
    errors = repository.pediatric_error_types()
    assert errors[0]["error_type"] == "样本量不足"


def test_readonly_sql_rejects_mutation_and_adds_limit(analytics_db):
    with pytest.raises(ValueError):
        validate_readonly_sql("DELETE FROM specimens")
    safe = validate_readonly_sql("SELECT * FROM specimens")
    assert "LIMIT 200" in safe
    repository = AnalyticsRepository(analytics_db)
    assert len(repository.query("SELECT * FROM specimens")) == 200
    connection = sqlite3.connect(analytics_db)
    try:
        assert connection.execute("SELECT COUNT(*) FROM specimens").fetchone()[0] == 1426
    finally:
        connection.close()

