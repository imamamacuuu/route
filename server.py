import asyncio
import logging
from aiohttp import web
from .config import PORT, HOST
from .auth import auth_middleware
from .proxy_pool import proxy_pool
from .api import (
    handle_models,
    handle_model_retrieve,
    handle_chat_completions,
    handle_healthz,
    handle_proxy_refresh,
    handle_proxy_rotate,
    handle_test_provider,
    handle_update_settings
)
from .ui.views import (
    render_dashboard,
    render_status_partial,
    render_ping_partial,
    render_models_partial,
    render_models_select_partial,
    render_proxies_partial,
    render_proxy_current_partial
)

logger = logging.getLogger("route.server")

async def options_handler(request: web.Request):
    return web.Response(headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS, HEAD",
        "Access-Control-Allow-Headers": "Authorization, Content-Type, HX-Request, HX-Target, HX-Current-URL",
    })

async def on_startup(app: web.Application):
    app["proxy_task"] = asyncio.create_task(proxy_pool.background_worker())
    logger.info("Background proxy worker task launched.")

async def on_cleanup(app: web.Application):
    if "proxy_task" in app:
        app["proxy_task"].cancel()

def create_app() -> web.Application:
    app = web.Application(middlewares=[auth_middleware])

    # CORS Preflight
    app.router.add_route("OPTIONS", "/{tail:.*}", options_handler)

    # UI Dashboard & HTMX Partials
    app.router.add_get("/", render_dashboard)

    app.router.add_get("/partials/status", render_status_partial)
    app.router.add_get("/partials/ping", render_ping_partial)
    app.router.add_get("/partials/models", render_models_partial)
    app.router.add_get("/partials/models-select", render_models_select_partial)
    app.router.add_get("/partials/proxies", render_proxies_partial)
    app.router.add_get("/partials/proxy-current", render_proxy_current_partial)

    # Core Health & API Endpoints
    app.router.add_get("/healthz", handle_healthz)

    app.router.add_get("/v1/models", handle_models)
    app.router.add_get("/models", handle_models)
    app.router.add_get("/v1/models/{model_id:.*}", handle_model_retrieve)
    app.router.add_get("/models/{model_id:.*}", handle_model_retrieve)
    app.router.add_post("/v1/chat/completions", handle_chat_completions)
    app.router.add_post("/chat/completions", handle_chat_completions)

    # Proxy Rotation & Testing
    app.router.add_post("/api/proxy/refresh", handle_proxy_refresh)
    app.router.add_post("/api/proxy/rotate", handle_proxy_rotate)
    app.router.add_post("/api/proxy/test-provider", handle_test_provider)
    app.router.add_post("/api/settings", handle_update_settings)

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    return app

def run():
    app = create_app()
    logger.info(f"Starting Modular Route Gateway Server on {HOST}:{PORT}")
    web.run_app(app, host=HOST, port=PORT, print=None)
