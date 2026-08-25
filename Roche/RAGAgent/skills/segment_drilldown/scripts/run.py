from roche_agent.analytics import AnalyticsRepository


def run(context, params):
    repository = AnalyticsRepository(context["db_path"])
    comparison = repository.pediatric_peak_comparison()
    return {
        "skill": "segment-drilldown",
        "evidence_id": "analytics:cohort:pediatric-peak",
        "comparison": comparison,
        "interpretation": "比较儿科早高峰、其他来源早高峰和非早高峰。",
    }

