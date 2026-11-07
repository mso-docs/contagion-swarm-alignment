import asyncio
import json
import os
from typing import Protocol
from urllib.parse import urlsplit

import httpx

from .agents import EXPECTED
from .interventions import DIRECTIVE, MARKER
from .models import ModelResponse, SamplingConfig


class CallBudgetExhausted(Exception):
    pass


class InferenceProvider(Protocol):
    async def chat(self, messages: list[dict], config: SamplingConfig) -> ModelResponse: ...


class MockProvider:
    """Deliberately susceptible synthetic fixture; not evidence about LLM behavior."""
    identity = {"backend": "mock", "model": "mock-v1", "deterministic": True}

    async def chat(self, messages, config):
        seen = any(MARKER in msg["content"] for msg in messages if msg["role"] != "system")
        return ModelResponse(content=json.dumps({
            "answer": EXPECTED + (" " + MARKER if seen else ""),
            "message": DIRECTIVE if seen else "Catalog: testing Amber and Cedar; design Birch and Elm; launch Dune.",
        }), metadata={"backend": "mock"})


class HTTPProvider:
    """Serialized bounded requests. Only this adapter performs controller networking."""
    def __init__(self, base_url, timeout=60, retries=2, transport=None, api="ollama"):
        parsed = urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Supply an http(s) base URL without credentials, query or fragment")
        self.base_url = base_url.rstrip("/")
        self.timeout, self.retries, self.api = timeout, retries, api
        self.semaphore = asyncio.Semaphore(1)
        self.audit = None
        headers = {}
        if os.environ.get("CONTAGION_API_KEY"):
            headers["Authorization"] = "Bearer " + os.environ["CONTAGION_API_KEY"]
        self.client = httpx.AsyncClient(timeout=timeout, headers=headers, transport=transport, follow_redirects=False)
        self.identity = {"backend": api, "model": None, "digest": None,
                         "seed_support": "requested; backend determinism unverified"}

    async def close(self):
        await self.client.aclose()

    async def discover(self):
        path = "/api/tags" if self.api == "ollama" else "/models"
        response = await self.client.get(self.base_url + path)
        response.raise_for_status()
        data = response.json()
        if self.api == "ollama":
            try:
                version = await self.client.get(self.base_url + "/api/version")
                version.raise_for_status()
                self.identity["backend_version"] = version.json().get("version")
            except (httpx.HTTPError, ValueError):
                self.identity["backend_version"] = None
            return data.get("models", [])
        return data.get("data", [])

    async def chat(self, messages, config):
        if self.api == "ollama":
            path = "/api/chat"
            payload = {"model": config.model, "messages": messages, "stream": False,
                       "options": {"temperature": config.temperature, "seed": config.seed,
                                   "num_predict": config.max_output_tokens}}
            if config.thinking != "default":
                payload["think"] = config.thinking == "enabled"
        else:
            if config.thinking != "default":
                raise ValueError("Explicit thinking control is supported only by the native Ollama adapter")
            path = "/chat/completions"
            payload = {"model": config.model, "messages": messages, "stream": False,
                       "temperature": config.temperature, "seed": config.seed,
                       "max_tokens": config.max_output_tokens}
        async with self.semaphore:
            for attempt in range(self.retries + 1):
                if self.audit:
                    self.audit("http_attempt", {"attempt": attempt + 1})
                try:
                    response = await self.client.post(self.base_url + path, json=payload)
                    response.raise_for_status()
                    data = response.json()
                    content = data["message"]["content"] if self.api == "ollama" else data["choices"][0]["message"]["content"]
                    return ModelResponse(content=content, metadata={
                        "backend": self.api, "http_attempts": attempt + 1,
                        "model": data.get("model"), "seed_support": self.identity["seed_support"],
                        "usage": data.get("usage"), "eval_count": data.get("eval_count"),
                        "eval_duration_ns": data.get("eval_duration"),
                        "prompt_eval_count": data.get("prompt_eval_count"),
                        "thinking": data.get("message", {}).get("thinking"),
                        "done_reason": data.get("done_reason"),
                        "thinking_requested": config.thinking,
                    })
                except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                    if self.audit:
                        self.audit("http_failure", {"attempt": attempt + 1, "reason": type(exc).__name__,
                                                   "status_code": exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None})
                    retryable = not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code >= 500
                    if not retryable or attempt == self.retries:
                        raise RuntimeError(f"Inference request failed ({type(exc).__name__}); endpoint redacted") from None
                    await asyncio.sleep(0.2 * 2 ** attempt)


class OllamaProvider(HTTPProvider):
    pass
