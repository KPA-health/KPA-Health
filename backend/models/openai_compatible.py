import httpx
import json
import logging
import os
from backend.models.base import ModelClient, ModelResult

class OpenAICompatibleClient(ModelClient):
    async def generate(self, prompt: str, profile: dict) -> ModelResult:
        base_url = profile.get("base_url", "https://api.openai.com/v1")
        model = profile.get("model", "gpt-4o")
        api_key_env = profile.get("api_key_env", "OPENAI_API_KEY")
        api_key = os.environ.get(api_key_env, "")
        
        transport = profile.get("transport", {})
        timeout = transport.get("read_timeout_s", 30)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": profile.get("generation", {}).get("temperature", 0.0),
        }
        
        if profile.get("output_mode") == "json_schema":
            payload["response_format"] = {"type": "json_object"}

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                
                resp_text = data["choices"][0]["message"]["content"]
                
                if profile.get("output_mode") == "json_schema":
                    try:
                        parsed = json.loads(resp_text)
                        return ModelResult(**parsed)
                    except json.JSONDecodeError:
                        return ModelResult(status="reject", message="Model returned invalid JSON.", sql=None)
                else:
                    return ModelResult(status="ok", message="Generated via completion", sql=resp_text)

        except httpx.TimeoutException:
            logging.error("OpenAI API timeout")
            return ModelResult(status="unavailable", message="Model timeout")
        except Exception as e:
            logging.error(f"OpenAI API error: {e}")
            return ModelResult(status="unavailable", message="Model unavailable")
