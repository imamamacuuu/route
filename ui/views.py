import asyncio
import time
import aiohttp
from aiohttp import web
from ..config import MODELS
from ..proxy_pool import proxy_pool
from .templates import get_dashboard_html

# ponytail: simple string interpolation; upgrade to jinja2 if template logic grows
async def render_dashboard(request: web.Request) -> web.Response:
    return web.Response(text=get_dashboard_html(), content_type="text/html")

async def render_status_partial(request: web.Request) -> web.Response:
    count = proxy_pool.count()
    if count > 0:
        status_tag = f'<span class="tag tag-ok">{count} live https</span>'
    else:
        status_tag = '<span class="tag tag-warn">harvesting…</span>'

    html = f'''<div class="panel" id="status-card"
     hx-get="/partials/status"
     hx-trigger="every 12s"
     hx-swap="outerHTML">
  <div class="panel-head">
    <span class="panel-title">Proxy pool status</span>
    {status_tag}
  </div>
  <div class="data-row">
    <span class="data-label">Verified proxies</span>
    <span class="data-val">{count} nodes</span>
  </div>
  <div class="data-row">
    <span class="data-label">Rotation method</span>
    <span class="data-val">Atomic round-robin</span>
  </div>
  <div class="data-row">
    <span class="data-label">Failover</span>
    <span class="data-val">Direct egress fallback</span>
  </div>
  <div class="data-row">
    <span class="data-label">Validation target</span>
    <span class="data-val">Cloudflare https edge</span>
  </div>
  <div style="margin-top: 0.85rem; display: flex; justify-content: flex-end;">
    <button class="btn-subtle"
            hx-post="/api/proxy/refresh"
            hx-target="#status-card"
            hx-indicator="#refresh-spinner">
      <span class="htmx-indicator" id="refresh-spinner">checking </span>Harvest now
    </button>
  </div>
</div>'''
    return web.Response(text=html, content_type="text/html")

async def render_ping_partial(request: web.Request) -> web.Response:
    targets = {
        "Zen (OpenCode)": "https://opencode.ai/zen/v1/models",
        "KiloCode": "https://api.kilo.ai/api/gateway/models",
        "LLM7": "https://api.llm7.io/v1/models",
        "OVHcloud": "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/models",
    }
    results = {}

    async def check(name, url):
        t0 = time.perf_counter()
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3.0)) as s:
                async with s.get(url, ssl=False) as r:
                    latency = round((time.perf_counter() - t0) * 1000, 1)
                    results[name] = {"latency": latency, "ok": r.status in [200, 401, 403, 405]}
        except Exception:
            results[name] = {"latency": None, "ok": False}

    await asyncio.gather(*(check(k, v) for k, v in targets.items()))

    rows = []
    for name in ["Zen (OpenCode)", "KiloCode", "LLM7", "OVHcloud"]:
        data = results.get(name, {"ok": False, "latency": None})
        if data["ok"] and data["latency"]:
            tag_class = "tag-ok" if data["latency"] < 700 else "tag-cool"
            val = f'<span class="tag {tag_class}">{data["latency"]} ms</span>'
        else:
            val = '<span class="tag tag-bad">Unreachable</span>'
        rows.append(f'<div class="data-row"><span class="data-label">{name}</span><span class="data-val">{val}</span></div>')

    return web.Response(text="".join(rows), content_type="text/html")

async def render_models_partial(request: web.Request) -> web.Response:
    rows = []
    for m in MODELS:
        prov = m["provider"]
        tag_cls = "tag-ok" if prov == "zen" else ("tag-cool" if prov == "kilo" else "tag-warn")
        rows.append(f'''<tr class="model-row" data-id="{m["id"]}" data-provider="{prov}">
  <td><code>{m["id"]}</code></td>
  <td><span class="tag {tag_cls}">{prov}</span></td>
  <td><span class="tag">keyless</span></td>
</tr>''')
    return web.Response(text="".join(rows), content_type="text/html")

async def render_models_select_partial(request: web.Request) -> web.Response:
    options = []
    for m in MODELS:
        options.append(f'<option value="{m["id"]}">{m["id"]} [{m["provider"]}]</option>')
    return web.Response(text="".join(options), content_type="text/html")

async def render_proxies_partial(request: web.Request) -> web.Response:
    proxies = proxy_pool.get_all()
    if not proxies:
        return web.Response(text='<tr><td colspan="4" style="text-align:center;color:var(--color-muted);padding:1rem;">Direct fallback active (pool harvesting candidates…)</td></tr>', content_type="text/html")

    rows = []
    for p in proxies[:30]:
        lat = p["latency"]
        tag_cls = "tag-ok" if lat < 600 else "tag-cool"
        rows.append(f'''<tr class="proxy-row" data-ip="{p["ip"]}">
  <td><code>{p["ip"]}</code></td>
  <td><span class="tag {tag_cls}">{lat} ms</span></td>
  <td>{p["fails"]}</td>
  <td><span class="tag tag-ok">https</span></td>
</tr>''')
    return web.Response(text="".join(rows), content_type="text/html")

async def render_proxy_current_partial(request: web.Request) -> web.Response:
    current = await proxy_pool.get_current()
    if current:
        lat = current.get("latency", 0)
        tag_cls = "tag-ok" if lat < 600 else "tag-cool"
        text = f'<span class="tag {tag_cls}">{current.get("ip", "unknown")} ({lat} ms)</span>'
    else:
        text = '<span class="tag tag-warn">direct fallback</span>'
    return web.Response(text=text, content_type="text/html")
