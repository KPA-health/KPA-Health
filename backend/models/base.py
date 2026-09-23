from pydantic import BaseModel
from typing import Optional, Dict, Any, List

class ModelResult(BaseModel):
    status: str
    sql: Optional[str] = None
    params: Dict[str, Any] = {}
    metric_id: Optional[str] = None
    filters: Dict[str, Any] = {}
    unit: Optional[str] = None
    message: str

class ModelClient:
    def generate(self, prompt: str, profile: dict) -> ModelResult:
        raise NotImplementedError
