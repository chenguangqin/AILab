from roche_agent.analytics import AnalyticsRepository


def run(context, params):
    repository = AnalyticsRepository(context["db_path"])
    errors = repository.pediatric_error_types()
    return {
        "skill": "preprocessing-error-analysis",
        "evidence_id": "analytics:errors:pediatric-peak",
        "error_types": errors,
        "interpretation": "错误类型用于提出下一步调查假设，不直接证明根因。",
    }

