import base64
import logging
from aiohttp import web
from .config import DEFAULT_USERNAME, DEFAULT_PASSWORD, DEFAULT_BEARER_TOKEN, CUSTOM_API_KEY

logger = logging.getLogger("route.auth")

# Dynamic configured credentials storage (can be updated via /api/settings)
runtime_settings = {
    "api_key": CUSTOM_API_KEY,
    "user": DEFAULT_USERNAME,
    "pass": DEFAULT_PASSWORD,
    "bearer": DEFAULT_BEARER_TOKEN
}

def verify_credentials(auth_header: str) -> bool:
    if not auth_header:
        return False

    # 1. Bearer Token Check
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        if runtime_settings.get("bearer") and token == runtime_settings["bearer"]:
            return True
        if (runtime_settings.get("user") and runtime_settings.get("pass") and
                token == f"{runtime_settings['user']}:{runtime_settings['pass']}"):
            return True
        if runtime_settings.get("api_key") and token == runtime_settings["api_key"]:
            return True
        return False

    # 2. HTTP Basic Auth Check
    if auth_header.startswith("Basic "):
        try:
            raw = auth_header[6:].strip()
            decoded = base64.b64decode(raw).decode("utf-8")
            if ":" in decoded:
                user, pwd = decoded.split(":", 1)
                if user == runtime_settings.get("user") and pwd == runtime_settings.get("pass"):
                    return True
        except Exception:
            return False

    return False

@web.middleware
async def auth_middleware(request: web.Request, handler):
    # Allow CORS preflight and root UI without auth
    if request.method == "OPTIONS":
        return await handler(request)

    path = request.path

    # Public paths
    if path == "/" or path == "/healthz" or path.startswith("/static/"):
        return await handler(request)

    # Protected paths: /v1/*, /api/*, /partials/*
    auth_header = request.headers.get("Authorization", "")

    # Fallback to query param (?key=... or ?auth=...)
    if not auth_header:
        param_key = request.query.get("key") or request.query.get("auth")
        if param_key:
            auth_header = f"Bearer {param_key}"

    if not verify_credentials(auth_header):
        # If HTMX request, return lightweight 401 HTML prompt
        if request.headers.get("HX-Request") == "true":
            return web.Response(
                text='<div class="card" style="border-color:#ef4444;"><span style="color:#ef4444;font-weight:600;">401 Unauthorized:</span> Set valid API Key (e.g. pass:pass) in Authentication Credential above.</div>',
                status=401,
                content_type="text/html",
                headers={"WWW-Authenticate": 'Basic realm="Route Gateway"'}
            )

        return web.json_response(
            {
                "error": {
                    "message": "Invalid or missing credentials. Authenticate via Bearer token (Bearer <api_key>) or Basic Auth (admin:pass).",
                    "type": "authentication_error",
                    "code": 401
                }
            },
            status=401,
            headers={
                "WWW-Authenticate": 'Basic realm="Route Gateway"',
                "Access-Control-Allow-Origin": "*",
            }
        )

    return await handler(request)
