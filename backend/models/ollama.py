import httpx
import json
import logging
from backend.models.base import ModelClient, ModelResult

class OllamaClient(ModelClient):
    async def generate(self, prompt: str, profile: dict) -> ModelResult:
        base_url = profile.get("base_url", "http://127.0.0.1:11434")
        model = profile.get("model", "qwen3:4b")
        transport = profile.get("transport", {})
        timeout = transport.get("read_timeout_s", 15)
        
        # Mapping capabilities
        options = {}
        gen = profile.get("generation", {})
        if "context_window" in gen:
            options["num_ctx"] = gen["context_window"]
        if "max_output_tokens" in gen:
            options["num_predict"] = gen["max_output_tokens"]
        if "temperature" in gen:
            options["temperature"] = gen["temperature"]
        if "thinking" in gen:
            # Although standard is `thinking` or similar, we map it as needed if Ollama supports it via options.
            pass

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": options,
            "keep_alive": gen.get("keep_alive", "30m")
        }

        if profile.get("output_mode") == "json_schema":
            payload["format"] = "json"

        # Using httpx for async
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(f"{base_url}/api/generate", json=payload)
                response.raise_for_status()
                data = response.json()
                
                resp_text = data.get("response", "")
                
                if profile.get("output_mode") == "json_schema":
                    try:
                        parsed = json.loads(resp_text)
                        return ModelResult(**parsed)
                    except json.JSONDecodeError:
                        return ModelResult(
                            status="reject", 
                            message="Model returned invalid JSON.",
                            sql=None
                        )
                else:
                    return ModelResult(
                        status="ok",
                        message="Generated via completion",
                        sql=resp_text
                    )

        except httpx.TimeoutException:
            logging.error("Ollama API timeout")
            return ModelResult(status="unavailable", message="Model timeout")
        except Exception as e:
            logging.error(f"Ollama API error: {e}")
            return ModelResult(status="unavailable", message="Model unavailable")
