"""Faithful Bidirectional Translation Between OpenAI and Anthropic API Schemas.

Enables seamless cross-compatibility between Anthropic clients (e.g. Claude Code)
and OpenAI engines (vLLM, Ollama, llama.cpp, etc.), verified with golden fixtures.
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, Tuple


def openai_to_anthropic_request(openai_req: Dict[str, Any]) -> Dict[str, Any]:
    """Convert an OpenAI ChatCompletionRequest into an Anthropic /v1/messages request."""
    model = openai_req.get("model", "")
    messages_in = openai_req.get("messages", [])
    system_prompts: List[str] = []
    anthropic_messages: List[Dict[str, Any]] = []

    for msg in messages_in:
        role = msg.get("role")
        content = msg.get("content", "")

        if role == "system":
            if isinstance(content, list):
                text_parts = [p.get("text", "") for p in content if isinstance(p, dict)]
                system_prompts.append(" ".join(text_parts))
            elif content:
                system_prompts.append(str(content))
            continue

        if role == "tool":
            # Map OpenAI tool result to Anthropic tool_result block
            anthropic_messages.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": msg.get("tool_call_id", ""),
                    "content": str(content or ""),
                }],
            })
            continue

        if role == "assistant" and msg.get("tool_calls"):
            # Map OpenAI assistant tool calls to Anthropic tool_use blocks
            content_blocks: List[Dict[str, Any]] = []
            if content:
                content_blocks.append({"type": "text", "text": str(content)})
            for tc in msg.get("tool_calls", []):
                fn = tc.get("function", {})
                args = fn.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        pass
                content_blocks.append({
                    "type": "tool_use",
                    "id": tc.get("id", f"toolu_{int(time.time())}"),
                    "name": fn.get("name", ""),
                    "input": args if isinstance(args, dict) else {},
                })
            anthropic_messages.append({"role": "assistant", "content": content_blocks})
            continue

        # Standard user/assistant text message
        anthropic_messages.append({
            "role": role,
            "content": content if isinstance(content, list) else str(content or ""),
        })

    # Tools conversion: OpenAI function definitions -> Anthropic input_schema
    tools = None
    if openai_req.get("tools"):
        tools = []
        for t in openai_req.get("tools", []):
            if t.get("type") == "function":
                fn = t.get("function", {})
                tools.append({
                    "name": fn.get("name"),
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
                })

    out: Dict[str, Any] = {
        "model": model,
        "messages": anthropic_messages,
        "max_tokens": openai_req.get("max_tokens") or 2048,
    }
    if system_prompts:
        out["system"] = "\n\n".join(system_prompts)
    if tools:
        out["tools"] = tools
    if "temperature" in openai_req and openai_req["temperature"] is not None:
        out["temperature"] = openai_req["temperature"]
    if openai_req.get("stream"):
        out["stream"] = True

    return out


def anthropic_to_openai_request(anthropic_req: Dict[str, Any]) -> Dict[str, Any]:
    """Convert an Anthropic /v1/messages request into an OpenAI ChatCompletionRequest."""
    model = anthropic_req.get("model", "")
    messages_out: List[Dict[str, Any]] = []

    # System prompt mapping
    system = anthropic_req.get("system")
    if system:
        if isinstance(system, list):
            sys_text = " ".join([b.get("text", "") for b in system if isinstance(b, dict)])
        else:
            sys_text = str(system)
        messages_out.append({"role": "system", "content": sys_text})

    # Messages mapping
    for msg in anthropic_req.get("messages", []):
        role = msg.get("role")
        content = msg.get("content")

        if isinstance(content, list):
            text_parts = []
            tool_calls = []
            has_tool_result = False

            for block in content:
                if not isinstance(block, dict):
                    text_parts.append(str(block))
                    continue

                btype = block.get("type")
                if btype == "text":
                    text_parts.append(block.get("text", ""))
                elif btype == "tool_use":
                    tool_calls.append({
                        "id": block.get("id"),
                        "type": "function",
                        "function": {
                            "name": block.get("name"),
                            "arguments": json.dumps(block.get("input", {})),
                        },
                    })
                elif btype == "tool_result":
                    has_tool_result = True
                    t_content = block.get("content", "")
                    if isinstance(t_content, list):
                        t_content = " ".join([b.get("text", "") for b in t_content if isinstance(b, dict)])
                    messages_out.append({
                        "role": "tool",
                        "tool_call_id": block.get("tool_use_id"),
                        "content": str(t_content),
                    })

            if not has_tool_result:
                msg_dict: Dict[str, Any] = {
                    "role": role,
                    "content": " ".join(text_parts) if text_parts else None,
                }
                if tool_calls:
                    msg_dict["tool_calls"] = tool_calls
                messages_out.append(msg_dict)
        else:
            messages_out.append({"role": role, "content": str(content or "")})

    # Tools mapping: Anthropic input_schema -> OpenAI function parameters
    tools = None
    if anthropic_req.get("tools"):
        tools = []
        for t in anthropic_req.get("tools", []):
            tools.append({
                "type": "function",
                "function": {
                    "name": t.get("name"),
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {}),
                },
            })

    out: Dict[str, Any] = {
        "model": model,
        "messages": messages_out,
        "max_tokens": anthropic_req.get("max_tokens") or 2048,
    }
    if tools:
        out["tools"] = tools
    if "temperature" in anthropic_req and anthropic_req["temperature"] is not None:
        out["temperature"] = anthropic_req["temperature"]
    if anthropic_req.get("stream"):
        out["stream"] = True

    return out


def openai_to_anthropic_response(openai_resp: Dict[str, Any], model_name: str) -> Dict[str, Any]:
    """Convert an OpenAI ChatCompletion response into Anthropic Messages format."""
    choices = openai_resp.get("choices", [])
    content_blocks: List[Dict[str, Any]] = []
    stop_reason = "end_turn"

    if choices:
        c0 = choices[0]
        msg = c0.get("message", {})
        if msg.get("content"):
            content_blocks.append({"type": "text", "text": msg.get("content")})

        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function", {})
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            content_blocks.append({
                "type": "tool_use",
                "id": tc.get("id", f"toolu_{int(time.time())}"),
                "name": fn.get("name", ""),
                "input": args,
            })

        finish_reason = c0.get("finish_reason")
        if finish_reason == "tool_calls":
            stop_reason = "tool_use"
        elif finish_reason == "length":
            stop_reason = "max_tokens"
        else:
            stop_reason = "end_turn"

    usage = openai_resp.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)

    return {
        "id": openai_resp.get("id", f"msg_{int(time.time())}"),
        "type": "message",
        "role": "assistant",
        "model": model_name,
        "content": content_blocks,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
        },
    }
