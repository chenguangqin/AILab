from roche_agent.analytics import AnalyticsRepository


def run(context, params):
    repository = AnalyticsRepository(context["db_path"])
    workstations = repository.counter_evidence()
    return {
        "skill": "counter-evidence-search",
        "evidence_id": "analytics:counter-evidence:workstations",
        "workstations": workstations,
        "interpretation": "检查异常是否集中在单一工位。",
    }

