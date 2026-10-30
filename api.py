import asyncio
import json
import logging
import time
from aiohttp import web
from .config import MODELS, MODEL_MAP
from .proxy_pool import proxy_pool
from .upstreams import route_and_execute
from .auth import runtime_settings

logger = logging.getLogger("route.api")

async def handle_models(request: web.Request) -> web.Response:
    data = [
        {
            "id": m["id"],
            "object": "model",
            "created": int(time.time()),
            "owned_by": m["provider"],
            "permission": [],
            "root": m["id"],
            "parent": None,
        }
        for m in MODELS
    ]
    return web.json_response({"object": "list", "data": data}, headers={"Access-Control-Allow-Origin": "*"})

async def handle_model_retrieve(request: web.Request) -> web.Response:
    model_id = request.match_info.get("model_id", "")
    if model_id in MODEL_MAP:
        m = MODEL_MAP[model_id]
        return web.json_response({
            "id": m["id"],
            "object": "model",
            "created": int(time.time()),
            "owned_by": m["provider"],
            "permission": [],
            "root": m["id"],
            "parent": None,
        }, headers={"Access-Control-Allow-Origin": "*"})
    return web.json_response({
        "error": {
            "message": f"The model '{model_id}' does not exist",
            "type": "invalid_request_error",
            "param": "model",
            "code": "model_not_found"
        }
    }, status=404, headers={"Access-Control-Allow-Origin": "*"})

async def handle_chat_completions(request: web.Request) -> web.StreamResponse:
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"error": {"message": "Invalid JSON body"}}, status=400)

    stream = bool(payload.get("stream", False))
    resp, session, used_proxy = await route_and_execute(payload, stream)

    if resp.status != 200:
        err_body = await resp.text()
        await session.close()
        return web.Response(
            text=err_body,
            status=resp.status,
            content_type="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )

    # SSE Streaming mode
    if stream:
        stream_resp = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": "text/event-stream; charset=utf-8",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "X-Route-Proxy": used_proxy or "direct",
            }
        )
        await stream_resp.prepare(request)

        try:
            async for chunk, _ in resp.content.iter_chunks():
                if chunk:
                    await stream_resp.write(chunk)
        except Exception as e:
            logger.debug(f"Stream aborted: {e}")
        finally:
            await resp.release()
            await session.close()
            await stream_resp.write_eof()
        return stream_resp

    # Non-streaming JSON mode
    resp_bytes = await resp.read()
    await resp.release()
    await session.close()
    return web.Response(
        body=resp_bytes,
        status=200,
        content_type="application/json",
        headers={
            "Access-Control-Allow-Origin": "*",
            "X-Route-Proxy": used_proxy or "direct"
        }
    )

async def handle_healthz(request: web.Request) -> web.Response:
    return web.json_response({
        "status": "ok",
        "service": "route-gateway",
        "active_proxies": proxy_pool.count(),
        "total_models": len(MODELS),
        "timestamp": int(time.time()),
    }, headers={"Access-Control-Allow-Origin": "*"})

async def handle_proxy_refresh(request: web.Request) -> web.Response:
    asyncio.create_task(proxy_pool.harvest())
    if request.headers.get("HX-Request") == "true":
        from .ui.views import render_status_partial
        return await render_status_partial(request)
    return web.json_response({"message": "Proxy harvest initiated."})

async def handle_proxy_rotate(request: web.Request) -> web.Response:
    current = await proxy_pool.rotate()
    count = proxy_pool.count()

    if request.headers.get("HX-Request") == "true":
        from .ui.views import format_proxy_current_html
        return web.Response(text=format_proxy_current_html(current, count), content_type="text/html")

    return web.json_response({
        "status": "rotated",
        "current_proxy": current,
        "pool_count": count
    })

async def handle_test_provider(request: web.Request) -> web.Response:
    provider = "kilo"
    if request.content_type == "application/json":
        try:
            body = await request.json()
            provider = body.get("provider", "kilo")
        except Exception:
            pass
    elif request.can_read_body:
        try:
            post_data = await request.post()
            provider = post_data.get("provider", "kilo")
        except Exception:
            pass
    else:
        provider = request.query.get("provider", "kilo")

    provider = str(provider).strip().lower()
    probe_models = {
        "zen": "mimo-v2.6-flash-free",
        "kilo": "kilo-auto/free",
        "llm7": "default",
        "ovh": "ovh/gpt-oss-20b"
    }
    model = probe_models.get(provider, "kilo-auto/free")
    test_payload = {
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 12
    }

    t0 = time.perf_counter()
    status_code = 500
    latency = 0.0
    preview = ""
    used_proxy = None

    try:
        resp, session, used_proxy = await route_and_execute(test_payload, stream=False)
        status_code = resp.status
        latency = round((time.perf_counter() - t0) * 1000, 1)
        raw_text = await resp.text()
        await resp.release()
        await session.close()

        try:
            parsed = json.loads(raw_text)
            if "choices" in parsed and parsed["choices"]:
                msg = parsed["choices"][0].get("message", {})
                preview = msg.get("content") or msg.get("reasoning") or raw_text[:80]
            elif "error" in parsed:
                err = parsed["error"]
                preview = err.get("message") if isinstance(err, dict) else str(err)
            else:
                preview = raw_text[:80]
        except Exception:
            preview = raw_text[:80]
    except Exception as e:
        latency = round((time.perf_counter() - t0) * 1000, 1)
        status_code = 502
        preview = str(e)

    preview_clean = (preview or "").replace("\n", " ").strip()
    if len(preview_clean) > 90:
        preview_clean = preview_clean[:90] + "..."

    proxy_label = used_proxy.replace("http://", "") if used_proxy else "DIRECT"

    if request.headers.get("HX-Request") == "true":
        badge_cls = "badge-emerald" if status_code == 200 else ("badge-warn" if status_code == 429 else "badge-danger")
        html = f"""<div class="probe-result-card">
  <div class="probe-meta-row">
    <span class="badge {badge_cls}">{status_code}</span>
    <span class="probe-stat">{latency} ms</span>
    <span class="probe-proxy">{proxy_label}</span>
  </div>
  <div class="probe-snippet">{preview_clean or "No response body"}</div>
</div>"""
        return web.Response(text=html, content_type="text/html")

    return web.json_response({
        "provider": provider,
        "model": model,
        "status": status_code,
        "latency_ms": latency,
        "proxy": proxy_label,
        "preview": preview_clean
    })

async def handle_update_settings(request: web.Request) -> web.Response:
    try:
        body = await request.json()
        if "api_key" in body:
            new_key = str(body["api_key"]).strip()
            runtime_settings["api_key"] = new_key
            logger.info(f"Custom API credentials updated to: {new_key if new_key else '(cleared)'}")
        return web.json_response({
            "status": "updated",
            "api_key": runtime_settings["api_key"],
            "basic_auth": "configured" if runtime_settings.get("user") else "disabled",
            "has_custom_key": bool(runtime_settings["api_key"])
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)
