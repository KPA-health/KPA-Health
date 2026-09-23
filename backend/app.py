import time
import uuid
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Any, Dict
from backend.settings import settings
from backend.contracts import QueryRequest, QueryResponse
from backend.query.dates import get_reference_date, resolve_dates
from backend.query.router import route_query
from backend.query.executor import execute_readonly_query, PolicyViolationError, QueryTimeoutError
from backend.query.catalog import catalog

app = FastAPI(title="KPA HIS Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {
        "status": "up",
        "database": "ok",
        "mode": "hybrid"
    }

@app.get("/api/catalog")
def get_catalog():
    return {
        "version": catalog.version,
        "metrics": catalog.list_metrics()
    }

@app.get("/api/models")
def get_models():
    with open(settings.profiles_config_path, "r") as f:
        profiles = yaml.safe_load(f)
    
    enabled_profiles = {}
    for k, v in profiles.get("profiles", {}).items():
        if v.get("enabled"):
            enabled_profiles[k] = {
                "provider": v.get("provider"),
                "model": v.get("model"),
                "capabilities": v.get("capabilities")
            }
    return enabled_profiles

@app.post("/api/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest):
    start_time = time.time()
    req_id = str(uuid.uuid4())
    
    # Resolving dates
    filters_dict = request.filters.model_dump(exclude_unset=True) if request.filters else {}
    start_dt, end_dt = resolve_dates(filters_dict.get("start"), filters_dict.get("end"))
    ref_dt = get_reference_date()

    # Route query
    status, msg, used_filters, metric_id, sql, params, source, unit = await route_query(
        request.question, request.model_profile, filters_dict
    )

    rows = []
    columns = []
    warnings = []
    truncated = False

    if status == "ok" and sql:
        try:
            rows, columns = execute_readonly_query(sql, params)
        except PolicyViolationError as e:
            status = "reject"
            msg = "Query blocked by policy."
            warnings.append(str(e))
        except QueryTimeoutError as e:
            status = "unavailable"
            msg = "Query timed out."
            warnings.append(str(e))
        except Exception as e:
            status = "reject"
            msg = "Execution error."
            warnings.append(str(e))

    end_time = time.time()
    timings = {
        "total_ms": (end_time - start_time) * 1000
    }

    return QueryResponse(
        request_id=req_id,
        status=status,
        message=msg,
        metric_id=metric_id,
        source=source,
        model_profile=request.model_profile if source == "local" else None,
        filters=used_filters,
        reference_date=ref_dt.isoformat(),
        timezone=settings.timezone,
        dataset_version="v1",
        catalog_version=catalog.version,
        unit=unit,
        columns=columns,
        rows=rows,
        warnings=warnings,
        truncated=truncated,
        timings_ms=timings
    )

@app.get("/api/kpis", response_model=QueryResponse)
async def kpis_endpoint(metric_id: str, start: str = None, end: str = None):
    # Reuse query logic
    filters = {}
    if start: filters["start"] = start
    if end: filters["end"] = end
    
    request = QueryRequest(
        question=f"Métrica {metric_id}", # Hacky fallback to trigger template
        model_profile="qwen_local",
        filters=filters
    )
    
    # We can skip routing if metric_id is provided directly but let's just do a direct call to template.
    from backend.query.catalog import generate_template_sql
    sql, params = generate_template_sql(metric_id, filters)
    
    if not sql:
        raise HTTPException(status_code=404, detail="Metric not found")
        
    start_time = time.time()
    req_id = str(uuid.uuid4())
    ref_dt = get_reference_date()
    
    rows, columns = [], []
    warnings = []
    status = "ok"
    msg = "KPI loaded"
    unit = catalog.get_metric(metric_id).get("unit")
    
    try:
        rows, columns = execute_readonly_query(sql, params)
    except Exception as e:
        status = "reject"
        msg = "Execution error."
        warnings.append(str(e))

    end_time = time.time()
    
    return QueryResponse(
        request_id=req_id,
        status=status,
        message=msg,
        metric_id=metric_id,
        source="template",
        filters=filters,
        reference_date=ref_dt.isoformat(),
        timezone=settings.timezone,
        dataset_version="v1",
        catalog_version=catalog.version,
        unit=unit,
        columns=columns,
        rows=rows,
        warnings=warnings,
        truncated=False,
        timings_ms={"total_ms": (end_time - start_time) * 1000}
    )
