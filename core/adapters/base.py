"""Engine Adapter ABC and Registry for Cloyst AI Gateway.

Provides normalized interfaces for local engines (vLLM, Ollama, llama.cpp, SGLang, TGI)
and optional air-gap-aware cloud fallbacks.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from core.config import settings


class EngineAdapter(ABC):
    """Abstract Base Class for all engine adapters."""

    name: str = "base"
    supports_streaming: bool = True
    supports_tools: bool = True
    supports_embeddings: bool = False
    is_cloud: bool = False

    @abstractmethod
    def build_chat_url(self, host: str, port: int) -> str:
        """Construct the backend chat completion URL."""
        pass

    @abstractmethod
    def transform_chat_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Transform OpenAI-standard payload to engine-specific parameters if needed."""
        pass

    def build_embeddings_url(self, host: str, port: int) -> Optional[str]:
        """Construct embeddings URL if supported."""
        return None

    def transform_embeddings_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return payload

    def parse_chat_response(self, data: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        """Normalize engine response into standard OpenAI chat completion object."""
        return data


class VLLMAdapter(EngineAdapter):
    """vLLM engine adapter: high-performance native OpenAI-compatible API."""

    name = "vllm"
    supports_streaming = True
    supports_tools = True
    supports_embeddings = True
    is_cloud = False

    def build_chat_url(self, host: str, port: int) -> str:
        return f"http://{host}:{port}/v1/chat/completions"

    def build_embeddings_url(self, host: str, port: int) -> str:
        return f"http://{host}:{port}/v1/embeddings"

    def transform_chat_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # vLLM natively adheres to OpenAI spec
        return payload


class OllamaAdapter(EngineAdapter):
    """Ollama local engine adapter: maps between OpenAI and Ollama formats."""

    name = "ollama"
    supports_streaming = True
    supports_tools = True
    supports_embeddings = True
    is_cloud = False

    def build_chat_url(self, host: str, port: int) -> str:
        return f"http://{host}:{port}/api/chat"

    def build_embeddings_url(self, host: str, port: int) -> str:
        return f"http://{host}:{port}/api/embeddings"

    def transform_chat_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Ollama requires tool arguments in message history to be dicts, not JSON strings
        clean_payload = dict(payload)
        messages = clean_payload.get("messages", [])
        for m in messages:
            for tc in m.get("tool_calls", []):
                fn = tc.get("function", {})
                if isinstance(fn.get("arguments"), str):
                    try:
                        fn["arguments"] = json.loads(fn["arguments"])
                    except Exception:
                        pass
        return clean_payload

    def parse_chat_response(self, data: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        if "choices" in data:
            return data

        msg = data.get("message", {})
        raw_tool_calls = msg.get("tool_calls") or []
        formatted_tool_calls = []
        for i, tc in enumerate(raw_tool_calls):
            fn = tc.get("function", {})
            args = fn.get("arguments", {})
            args_str = json.dumps(args) if isinstance(args, dict) else str(args)
            formatted_tool_calls.append({
                "id": tc.get("id") or f"call_{i}_{int(data.get('created_at', 0) or 0)}",
                "index": i,
                "type": "function",
                "function": {
                    "name": fn.get("name"),
                    "arguments": args_str,
                },
            })

        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)
        return {
            "id": f"chatcmpl-ollama-{int(data.get('created_at', 0) or 0)}",
            "object": "chat.completion",
            "model": model_name,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": msg.get("content") or "",
                    "tool_calls": formatted_tool_calls if formatted_tool_calls else None,
                },
                "finish_reason": "tool_calls" if formatted_tool_calls else "stop",
            }],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }


class LlamaCppAdapter(EngineAdapter):
    """llama.cpp local server adapter."""

    name = "llama.cpp"
    supports_streaming = True
    supports_tools = True
    supports_embeddings = True
    is_cloud = False

    def build_chat_url(self, host: str, port: int) -> str:
        return f"http://{host}:{port}/v1/chat/completions"

    def build_embeddings_url(self, host: str, port: int) -> str:
        return f"http://{host}:{port}/v1/embeddings"

    def transform_chat_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return payload


class SGLangAdapter(EngineAdapter):
    """SGLang high-throughput engine adapter."""

    name = "sglang"
    supports_streaming = True
    supports_tools = True
    supports_embeddings = True
    is_cloud = False

    def build_chat_url(self, host: str, port: int) -> str:
        return f"http://{host}:{port}/v1/chat/completions"

    def build_embeddings_url(self, host: str, port: int) -> str:
        return f"http://{host}:{port}/v1/embeddings"

    def transform_chat_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return payload


class TGIAdapter(EngineAdapter):
    """HuggingFace Text Generation Inference (TGI) adapter."""

    name = "tgi"
    supports_streaming = True
    supports_tools = False
    supports_embeddings = False
    is_cloud = False

    def build_chat_url(self, host: str, port: int) -> str:
        return f"http://{host}:{port}/v1/chat/completions"

    def transform_chat_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return payload


class GenericOpenAIAdapter(EngineAdapter):
    """Generic OpenAI-compatible adapter (LM Studio, LocalAI, vLLM, etc.)."""

    name = "generic"
    supports_streaming = True
    supports_tools = True
    supports_embeddings = True
    is_cloud = False

    def build_chat_url(self, host: str, port: int) -> str:
        return f"http://{host}:{port}/v1/chat/completions"

    def build_embeddings_url(self, host: str, port: int) -> str:
        return f"http://{host}:{port}/v1/embeddings"

    def transform_chat_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return payload


class OptionalCloudAdapter(EngineAdapter):
    """Cloud fallback adapter: automatically disabled when air_gap_mode is active."""

    name = "cloud"
    is_cloud = True

    def __init__(self, endpoint_url: str):
        self.endpoint_url = endpoint_url

    def build_chat_url(self, host: str, port: int) -> str:
        if settings.air_gap_mode:
            raise PermissionError(
                "Air-Gap Violation: Outbound cloud adapter is disabled in air-gap mode."
            )
        return self.endpoint_url

    def transform_chat_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if settings.air_gap_mode:
            raise PermissionError("Air-Gap Violation: Cloud calls prohibited.")
        return payload


class AdapterRegistry:
    """Registry for looking up and instantiating engine adapters."""

    def __init__(self):
        self._adapters: Dict[str, EngineAdapter] = {
            "vllm": VLLMAdapter(),
            "ollama": OllamaAdapter(),
            "llama.cpp": LlamaCppAdapter(),
            "llamacpp": LlamaCppAdapter(),
            "sglang": SGLangAdapter(),
            "tgi": TGIAdapter(),
            "generic": GenericOpenAIAdapter(),
            "openai": GenericOpenAIAdapter(),
        }

    def register(self, engine_type: str, adapter: EngineAdapter) -> None:
        self._adapters[engine_type.lower()] = adapter

    def get(self, engine_type: Optional[str]) -> EngineAdapter:
        if not engine_type:
            return self._adapters["generic"]
        return self._adapters.get(engine_type.lower(), self._adapters["generic"])


adapter_registry = AdapterRegistry()

