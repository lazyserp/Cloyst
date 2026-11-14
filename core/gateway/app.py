import os
import json
import socket
import httpx
import time
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.db.session import get_db, init_db
from core.gateway.schema import AnthropicMessageRequest, ChatCompletionRequest
from core.db.models import ApiKeyRecord, AuditLogRecord, DeploymentRecord, NodeRecord
from core.security.keys import verify_api_key
from core.gateway.limiter import InMemoryRateLimiter

rate_limiter = InMemoryRateLimiter(requests_per_minute=60, burst=10)
bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)

app = FastAPI(title="Cloyst AI Gateway", version="0.1.0")
init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def extract_message_text(m) -> str:
    """Extract plain text from message object or dict, including multimodal/block structures."""
    content = m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "")
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict):
                parts.append(str(b.get("text", "")))
            else:
                parts.append(str(b))
        return " ".join(parts)
    return str(content or "")


def is_local_host(host: str) -> bool:
    if host in ["127.0.0.1", "localhost", "0.0.0.0"]:
        return True
    try:
        if host.lower() == socket.gethostname().lower():
            return True
        for info in socket.getaddrinfo(socket.gethostname(), None):
            if host == info[4][0]:
                return True
    except Exception:
        pass
    return False


def resolve_target_host(host: str) -> str:
    """Translate target host to localhost/host.docker.internal when target is local machine."""
    if is_local_host(host):
        if os.path.exists("/.dockerenv") or os.environ.get("RUNNING_IN_DOCKER") == "1":
            return "host.docker.internal"
        return "127.0.0.1"
    return host


def get_current_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_api_key: str | None = Depends(api_key_header),
    db: Session = Depends(get_db),
) -> ApiKeyRecord:
    """Enforce API key authentication via Bearer token or x-api-key header."""
    raw_key = None
    if credentials and credentials.credentials:
        raw_key = credentials.credentials
    elif x_api_key:
        raw_key = x_api_key
    elif "x-api-key" in request.headers:
        raw_key = request.headers["x-api-key"]
    elif "authorization" in request.headers:
        auth = request.headers["authorization"]
        if auth.lower().startswith("bearer "):
            raw_key = auth[7:].strip()

    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header. Expected 'Bearer <api_key>' or 'x-api-key: <api_key>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    api_key_record = verify_api_key(raw_key, db)
    if not api_key_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, revoked, or expired API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return api_key_record


@app.get("/health")
async def health():
    """Gateway health check."""
    return {"status": "healthy", "service": "cloyst-gateway"}


@app.get("/v1/models")
def list_models(db: Session = Depends(get_db)):
    """List all models currently running in the database."""
    stmt = select(DeploymentRecord.model_id).where(DeploymentRecord.status == "running")
    active_models = db.scalars(stmt).all()
    return {
        "object": "list",
        "data": [
            {"id": model_id, "object": "model", "owned_by": "cloyst"}
            for model_id in active_models
        ],
    }


# ==========================================
# 1. OpenAI-Compatible Chat Completions API
# ==========================================
@app.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    api_key: ApiKeyRecord = Depends(get_current_api_key),
    db: Session = Depends(get_db),
):
    """Route chat completions dynamically to the active engine port from the database."""
    start_time = time.perf_counter()

    stmt = select(DeploymentRecord).where(
        DeploymentRecord.model_id == request.model,
        DeploymentRecord.status == "running",
    )
    deployment = db.scalar(stmt)

    allowed, retry_after = rate_limiter.check(api_key.id)
    if not allowed:
        audit_log = AuditLogRecord(
            api_key_id=api_key.id,
            model_id=request.model,
            project_id=api_key.project_id,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error_message=f"Rate limit exceeded. Retry after {retry_after}s.",
        )
        db.add(audit_log)
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(int(retry_after) or 1)},
        )

    if not deployment:
        audit_log = AuditLogRecord(
            api_key_id=api_key.id,
            model_id=request.model,
            status_code=status.HTTP_404_NOT_FOUND,
            project_id=api_key.project_id,
            error_message=f"Model {request.model} is not currently running",
        )
        db.add(audit_log)
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{request.model}' is not currently running in Cloyst.",
        )

    node = db.get(NodeRecord, deployment.node_id)
    raw_host = node.ip_address if (node and node.ip_address) else "127.0.0.1"
    host = resolve_target_host(raw_host)
    backend_url = f"http://{host}:{deployment.port}/v1/chat/completions"
    payload = request.model_dump(exclude_none=True)

    # 1. Real-time SSE Streaming Mode
    if request.stream:
        # If client passes tools, adapt cleanly to avoid local backend streaming bugs
        if request.tools:
            is_ollama = (deployment.port == 11434)
            target_url = f"http://{host}:{deployment.port}/api/chat" if is_ollama else backend_url
            payload["stream"] = False

            if is_ollama:
                # Ollama's /api/chat expects function.arguments in message history to be a dict, not a string
                for msg_item in payload.get("messages", []):
                    for tc in msg_item.get("tool_calls", []):
                        fn = tc.get("function", {})
                        if isinstance(fn.get("arguments"), str):
                            try:
                                fn["arguments"] = json.loads(fn["arguments"])
                            except Exception:
                                pass

            async with httpx.AsyncClient(timeout=120.0) as client:
                try:
                    resp = await client.post(target_url, json=payload)
                    if resp.status_code >= 400:
                        raise HTTPException(status_code=resp.status_code, detail=f"Inference engine returned status {resp.status_code}: {resp.text}")
                    data = resp.json()
                except httpx.ConnectError:
                    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Inference engine on port {deployment.port} unreachable")

            if is_ollama:
                msg = data.get("message", {})
                content = msg.get("content") or ""
                raw_tool_calls = msg.get("tool_calls") or []
                formatted_tool_calls = []
                for i, tc in enumerate(raw_tool_calls):
                    fn = tc.get("function", {})
                    args = fn.get("arguments", {})
                    args_str = json.dumps(args) if isinstance(args, dict) else str(args)
                    formatted_tool_calls.append({
                        "id": tc.get("id") or f"call_{i}_{int(time.time())}",
                        "index": i,
                        "type": "function",
                        "function": {
                            "name": fn.get("name"),
                            "arguments": args_str
                        }
                    })
                choices = [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content,
                        "tool_calls": formatted_tool_calls if formatted_tool_calls else None
                    },
                    "finish_reason": "tool_calls" if formatted_tool_calls else "stop"
                }]
                prompt_tokens = data.get("prompt_eval_count", 0)
                completion_tokens = data.get("eval_count", 0)
                total_tokens = prompt_tokens + completion_tokens
            else:
                choices = data.get("choices", [])
                usage = data.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)

            async def tool_stream_generator():
                created = int(time.time())
                cmpl_id = data.get("id", f"chatcmpl-{int(time.time())}")
                model_name = data.get("model", request.model)

                for choice in choices:
                    idx = choice.get("index", 0)
                    msg = choice.get("message", {})
                    content = msg.get("content") or ""
                    tool_calls = msg.get("tool_calls")
                    finish_reason = choice.get("finish_reason", "stop")

                    if tool_calls:
                        c1 = {
                            "id": cmpl_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model_name,
                            "choices": [{
                                "index": idx,
                                "delta": {
                                    "role": "assistant",
                                    "tool_calls": tool_calls
                                },
                                "finish_reason": None
                            }]
                        }
                        yield f"data: {json.dumps(c1)}\n\n".encode("utf-8")

                        c2 = {
                            "id": cmpl_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model_name,
                            "choices": [{
                                "index": idx,
                                "delta": {},
                                "finish_reason": finish_reason or "tool_calls"
                            }]
                        }
                        yield f"data: {json.dumps(c2)}\n\n".encode("utf-8")
                    else:
                        c1 = {
                            "id": cmpl_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model_name,
                            "choices": [{
                                "index": idx,
                                "delta": {
                                    "role": "assistant",
                                    "content": content
                                },
                                "finish_reason": None
                            }]
                        }
                        yield f"data: {json.dumps(c1)}\n\n".encode("utf-8")

                        c2 = {
                            "id": cmpl_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model_name,
                            "choices": [{
                                "index": idx,
                                "delta": {},
                                "finish_reason": finish_reason or "stop"
                            }]
                        }
                        yield f"data: {json.dumps(c2)}\n\n".encode("utf-8")

                usage_chunk = {
                    "id": cmpl_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model_name,
                    "choices": [],
                    "usage": {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens
                    }
                }
                yield f"data: {json.dumps(usage_chunk)}\n\n".encode("utf-8")
                yield b"data: [DONE]\n\n"

                latency_ms = (time.perf_counter() - start_time) * 1000.0
                audit_log = AuditLogRecord(
                    api_key_id=api_key.id,
                    model_id=request.model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    project_id=api_key.project_id,
                    latency_ms=round(latency_ms, 2),
                    status_code=200,
                )
                db.add(audit_log)
                db.commit()

            return StreamingResponse(
                tool_stream_generator(),
                media_type="text/event-stream"
            )

        if "stream_options" not in payload:
            payload["stream_options"] = {"include_usage": True}

        client = httpx.AsyncClient(timeout=120.0)
        try:
            req = client.build_request(
                "POST",
                backend_url,
                json=payload,
                headers={"Accept": "text/event-stream"},
            )
            response = await client.send(req, stream=True)
            if response.status_code >= 400:
                status_c = response.status_code
                err_text = (await response.aread()).decode("utf-8", errors="ignore")
                await response.aclose()
                await client.aclose()
                raise HTTPException(status_code=status_c, detail=f"Inference engine returned error status {status_c}: {err_text}")

            async def stream_generator():
                prompt_tokens = 0
                completion_tokens = 0
                total_tokens = 0
                text_buffer = ""

                try:
                    async for chunk in response.aiter_raw():
                        yield chunk
                        try:
                            text_buffer += chunk.decode("utf-8", errors="ignore")
                            while "\n" in text_buffer:
                                line, text_buffer = text_buffer.split("\n", 1)
                                line = line.strip()
                                if line.startswith("data:") and not line.startswith("data: [DONE]"):
                                    data_str = line[5:].strip()
                                    if data_str:
                                        chunk_json = json.loads(data_str)
                                        if "usage" in chunk_json and isinstance(chunk_json["usage"], dict):
                                            u = chunk_json["usage"]
                                            prompt_tokens = u.get("prompt_tokens") or u.get("input_tokens") or prompt_tokens
                                            completion_tokens = u.get("completion_tokens") or u.get("output_tokens") or completion_tokens
                                            total_tokens = u.get("total_tokens") or (prompt_tokens + completion_tokens)
                                        elif "message" in chunk_json and isinstance(chunk_json["message"], dict):
                                            u = chunk_json["message"].get("usage", {})
                                            prompt_tokens = u.get("input_tokens", prompt_tokens)
                                            completion_tokens = u.get("output_tokens", completion_tokens)
                                            total_tokens = prompt_tokens + completion_tokens
                                        elif "choices" in chunk_json and len(chunk_json["choices"]) > 0:
                                            delta = chunk_json["choices"][0].get("delta", {})
                                            if delta.get("content"):
                                                completion_tokens += 1
                        except Exception:
                            pass
                finally:
                    await response.aclose()
                    await client.aclose()
                    latency_ms = (time.perf_counter() - start_time) * 1000.0

                    if prompt_tokens == 0:
                        prompt_tokens = sum(
                            max(1, len(extract_message_text(m)) // 4)
                            for m in request.messages
                        )
                    if total_tokens == 0:
                        total_tokens = prompt_tokens + completion_tokens

                    audit_log = AuditLogRecord(
                        api_key_id=api_key.id,
                        model_id=request.model,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens,
                        project_id=api_key.project_id,
                        latency_ms=round(latency_ms, 2),
                        status_code=200,
                    )
                    db.add(audit_log)
                    db.commit()

            return StreamingResponse(
                stream_generator(),
                status_code=response.status_code,
                media_type="text/event-stream",
            )
        except httpx.ConnectError:
            await client.aclose()
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            audit_log = AuditLogRecord(
                api_key_id=api_key.id,
                model_id=request.model,
                latency_ms=round(latency_ms, 2),
                project_id=api_key.project_id,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                error_message=f"Inference engine for '{request.model}' on port {deployment.port} is unreachable.",
            )
            db.add(audit_log)
            db.commit()

            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Inference engine for '{request.model}' on port {deployment.port} is unreachable.",
            )

    # 2. Standard Buffered JSON Mode
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                backend_url,
                json=payload,
            )

            data = response.json()
            usage = data.get("usage", {})
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            audit_log = AuditLogRecord(
                api_key_id=api_key.id,
                model_id=request.model,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                latency_ms=round(latency_ms, 2),
                project_id=api_key.project_id,
                status_code=response.status_code,
            )
            db.add(audit_log)
            db.commit()
            return data

        except httpx.ConnectError:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            audit_log = AuditLogRecord(
                api_key_id=api_key.id,
                model_id=request.model,
                latency_ms=round(latency_ms, 2),
                project_id=api_key.project_id,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                error_message=f"Inference engine for '{request.model}' on port {deployment.port} is unreachable.",
            )
            db.add(audit_log)
            db.commit()

            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Inference engine for '{request.model}' on port {deployment.port} is unreachable.",
            )


# ==========================================
# 2. Anthropic Messages API (Claude Code)
# ==========================================
@app.post("/v1/messages")
async def messages(
    request: AnthropicMessageRequest,
    api_key: ApiKeyRecord = Depends(get_current_api_key),
    db: Session = Depends(get_db),
):
    """Route Anthropic Messages API requests dynamically to the active engine port."""
    start_time = time.perf_counter()

    stmt = select(DeploymentRecord).where(
        DeploymentRecord.model_id == request.model,
        DeploymentRecord.status == "running",
    )
    deployment = db.scalar(stmt)

    allowed, retry_after = rate_limiter.check(api_key.id)
    if not allowed:
        audit_log = AuditLogRecord(
            api_key_id=api_key.id,
            model_id=request.model,
            project_id=api_key.project_id,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error_message=f"Rate limit exceeded. Retry after {retry_after}s.",
        )
        db.add(audit_log)
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(int(retry_after) or 1)},
        )

    if not deployment:
        audit_log = AuditLogRecord(
            api_key_id=api_key.id,
            model_id=request.model,
            status_code=status.HTTP_404_NOT_FOUND,
            project_id=api_key.project_id,
            error_message=f"Model {request.model} is not currently running",
        )
        db.add(audit_log)
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{request.model}' is not currently running in Cloyst.",
        )

    node = db.get(NodeRecord, deployment.node_id)
    raw_host = node.ip_address if (node and node.ip_address) else "127.0.0.1"
    host = resolve_target_host(raw_host)
    backend_url = f"http://{host}:{deployment.port}/v1/messages"
    payload = request.model_dump(exclude_none=True)

    # 1. Real-time SSE Streaming Mode
    if request.stream:
        if "stream_options" not in payload:
            payload["stream_options"] = {"include_usage": True}

        client = httpx.AsyncClient(timeout=120.0)
        try:
            req = client.build_request(
                "POST",
                backend_url,
                json=payload,
                headers={"Accept": "text/event-stream"},
            )
            response = await client.send(req, stream=True)
            if response.status_code >= 400:
                status_c = response.status_code
                err_text = (await response.aread()).decode("utf-8", errors="ignore")
                await response.aclose()
                await client.aclose()
                raise HTTPException(status_code=status_c, detail=f"Inference engine returned error status {status_c}: {err_text}")

            async def stream_generator():
                prompt_tokens = 0
                completion_tokens = 0
                total_tokens = 0
                text_buffer = ""

                try:
                    async for chunk in response.aiter_raw():
                        with open("/tmp/last_chunks.log", "ab") as f:
                            f.write(chunk)
                        yield chunk
                        try:
                            text_buffer += chunk.decode("utf-8", errors="ignore")
                            while "\n" in text_buffer:
                                line, text_buffer = text_buffer.split("\n", 1)
                                line = line.strip()
                                if line.startswith("data:") and not line.startswith("data: [DONE]"):
                                    data_str = line[5:].strip()
                                    if data_str:
                                        chunk_json = json.loads(data_str)
                                        if "usage" in chunk_json and isinstance(chunk_json["usage"], dict):
                                            u = chunk_json["usage"]
                                            prompt_tokens = u.get("prompt_tokens") or u.get("input_tokens") or prompt_tokens
                                            completion_tokens = u.get("completion_tokens") or u.get("output_tokens") or completion_tokens
                                            total_tokens = u.get("total_tokens") or (prompt_tokens + completion_tokens)
                                        elif "message" in chunk_json and isinstance(chunk_json["message"], dict):
                                            u = chunk_json["message"].get("usage", {})
                                            prompt_tokens = u.get("input_tokens", prompt_tokens)
                                            completion_tokens = u.get("output_tokens", completion_tokens)
                                            total_tokens = prompt_tokens + completion_tokens
                                        elif "choices" in chunk_json and len(chunk_json["choices"]) > 0:
                                            delta = chunk_json["choices"][0].get("delta", {})
                                            if delta.get("content"):
                                                completion_tokens += 1
                        except Exception:
                            pass
                finally:
                    await response.aclose()
                    await client.aclose()
                    latency_ms = (time.perf_counter() - start_time) * 1000.0

                    if prompt_tokens == 0:
                        prompt_tokens = sum(
                            max(1, len(extract_message_text(m)) // 4)
                            for m in request.messages
                        )
                    if total_tokens == 0:
                        total_tokens = prompt_tokens + completion_tokens

                    audit_log = AuditLogRecord(
                        api_key_id=api_key.id,
                        model_id=request.model,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens,
                        project_id=api_key.project_id,
                        latency_ms=round(latency_ms, 2),
                        status_code=200,
                    )
                    db.add(audit_log)
                    db.commit()

            return StreamingResponse(
                stream_generator(),
                status_code=response.status_code,
                media_type="text/event-stream",
            )
        except httpx.ConnectError:
            await client.aclose()
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            audit_log = AuditLogRecord(
                api_key_id=api_key.id,
                model_id=request.model,
                latency_ms=round(latency_ms, 2),
                project_id=api_key.project_id,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                error_message=f"Inference engine for '{request.model}' on port {deployment.port} is unreachable.",
            )
            db.add(audit_log)
            db.commit()

            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Inference engine for '{request.model}' on port {deployment.port} is unreachable.",
            )

    # 2. Standard Buffered JSON Mode
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                backend_url,
                json=payload,
            )

            data = response.json()
            usage = data.get("usage", {})
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            prompt_toks = usage.get("input_tokens") or usage.get("prompt_tokens", 0)
            comp_toks = usage.get("output_tokens") or usage.get("completion_tokens", 0)
            total_toks = prompt_toks + comp_toks

            audit_log = AuditLogRecord(
                api_key_id=api_key.id,
                model_id=request.model,
                prompt_tokens=prompt_toks,
                completion_tokens=comp_toks,
                total_tokens=total_toks,
                latency_ms=round(latency_ms, 2),
                project_id=api_key.project_id,
                status_code=response.status_code,
            )
            db.add(audit_log)
            db.commit()
            return data

        except httpx.ConnectError:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            audit_log = AuditLogRecord(
                api_key_id=api_key.id,
                model_id=request.model,
                latency_ms=round(latency_ms, 2),
                project_id=api_key.project_id,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                error_message=f"Inference engine for '{request.model}' on port {deployment.port} is unreachable.",
            )
            db.add(audit_log)
            db.commit()

            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Inference engine for '{request.model}' on port {deployment.port} is unreachable.",
            )
