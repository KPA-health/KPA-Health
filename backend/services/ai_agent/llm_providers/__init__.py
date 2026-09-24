"""
Proveedores de LLM intercambiables (patrón Strategy) y su fábrica (switch Local/Nube).

- base.py                        Contrato LLMProvider y errores comunes.
- ollama_provider.py             Modelos locales servidos por Ollama (Qwen3).
- gemini_provider.py             Google Gemini (nube).
- openai_compatible_provider.py  LM Studio, vLLM, OpenRouter, Groq, OpenAI...
- provider_factory.py            Devuelve el proveedor configurado para "local" o "cloud".
"""
