import json
from typing import Dict, Any, List
from backend.settings import settings

class SemanticCatalog:
    def __init__(self, path: str):
        with open(path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        
        self.version = self.data.get("version", "unknown")
        self.metrics = {m["metric_id"]: m for m in self.data.get("metrics", [])}

    def get_metric(self, metric_id: str) -> Dict[str, Any]:
        return self.metrics.get(metric_id)

    def list_metrics(self) -> List[Dict[str, Any]]:
        return list(self.metrics.values())

catalog = SemanticCatalog("config/semantic_catalog.json")

def generate_template_sql(metric_id: str, filters: Dict[str, Any]) -> str:
    metric = catalog.get_metric(metric_id)
    if not metric:
        return None, {}
    
    sql = metric["sql_template"]
    params = {}
    
    # Simple parameterized appending based on known dimensions
    # For a real implementation, we'd map filter names to view column names
    date_col = ""
    if metric_id == "admissions_count":
        date_col = "admission_date"
    elif metric_id == "wait_mean":
        date_col = "admission_date"
    elif metric_id == "triage_distribution":
        date_col = "triage_date"
    elif metric_id == "medication_dispensed":
        date_col = "delivery_date"
    elif metric_id == "services_by_specialty":
        date_col = "service_date"

    if filters.get("start"):
        sql += f" AND {date_col} >= :start"
        params["start"] = filters["start"]
    if filters.get("end"):
        sql += f" AND {date_col} < :end"
        params["end"] = filters["end"]

    return sql, params
