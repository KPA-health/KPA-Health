from pydantic import BaseModel, Field
from typing import Optional, Any, List, Dict

class QueryFilters(BaseModel):
    start: Optional[str] = None
    end: Optional[str] = None

class QueryRequest(BaseModel):
    question: str = Field(..., max_length=2000)
    model_profile: str = "qwen_local"
    filters: Optional[QueryFilters] = None

class QueryResponse(BaseModel):
    request_id: str
    status: str
    message: str
    metric_id: Optional[str] = None
    source: str
    model_profile: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    reference_date: Optional[str] = None
    timezone: str
    dataset_version: str
    catalog_version: str
    data_cutoff: Optional[str] = None
    unit: Optional[str] = None
    columns: List[str] = []
    rows: List[Dict[str, Any]] = []
    coverage: Optional[str] = None
    warnings: List[str] = []
    truncated: bool = False
    timings_ms: Dict[str, float] = {}
    chart: Optional[Dict[str, Any]] = None
