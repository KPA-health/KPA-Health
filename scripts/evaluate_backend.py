import httpx
import asyncio

async def test_api():
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=60.0) as client:
        res = await client.get("/health")
        print("Health:", res.json())
        
        res = await client.get("/api/catalog")
        print("Catalog:", len(res.json()["metrics"]), "metrics")

        # Test KPI template
        res = await client.get("/api/kpis?metric_id=admissions_count")
        print("KPI Admissions:", res.json()["status"], "rows:", len(res.json()["rows"]))

        # Test Query NLP Hybrid Template
        res = await client.post("/api/query", json={
            "question": "¿Cuántos ingresos hubo en total?",
            "model_profile": "qwen_local"
        })
        print("Query Admissions Template:", res.json()["status"], res.json()["source"])

        # Test Query NLP Fallback
        res = await client.post("/api/query", json={
            "question": "Dame los ingresos detallados de forma incorrecta para probar el LLM",
            "model_profile": "qwen_local"
        })
        print("Query LLM Reject:", res.json()["status"], res.json()["source"])

        res = await client.post("/api/query", json={
            "question": "Lista la distribución de triage de todos los pacientes",
            "model_profile": "qwen_local"
        })
        print("Query LLM Valid (Template match):", res.json()["status"], res.json()["source"])

        res = await client.post("/api/query", json={
            "question": "Agrupa los ingresos por via y dime la cantidad en cada grupo",
            "model_profile": "qwen_local"
        })
        print("Query NL2SQL (Real LLM):", res.json()["status"], res.json()["source"], "Msg:", res.json()["message"])
        if res.json()["status"] == "ok":
            print("Rows returned:", len(res.json()["rows"]))
        elif res.json().get("sql"):
            print("SQL returned:", res.json()["sql"])

if __name__ == '__main__':
    asyncio.run(test_api())
