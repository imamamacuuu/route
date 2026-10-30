import logging
from typing import Tuple, Optional
import aiohttp
from ..config import MODEL_MAP
from ..proxy_pool import proxy_pool
from .zen import prepare_zen_payload
from .kilo import prepare_kilo_payload
from .llm7 import prepare_llm7_payload
from .ovh import prepare_ovh_payload

logger = logging.getLogger("route.dispatcher")

def route_payload(payload: dict) -> Tuple[str, str, dict, dict]:
    model = payload.get("model", "kilo-auto/free")
    info = MODEL_MAP.get(model)
    provider = "kilo"

    if info:
        provider = info["provider"]
    elif model.startswith("ovh/"):
        provider = "ovh"
    elif model in ["codestral-latest", "minimax-m2.7", "default", "fast"]:
        provider = "llm7"
    elif ":free" in model or model.startswith("kilo-") or "openrouter" in model:
        provider = "kilo"
    else:
        provider = "zen"

    if provider == "zen":
        url, headers, body = prepare_zen_payload(payload)
    elif provider == "kilo":
        url, headers, body = prepare_kilo_payload(payload)
    elif provider == "llm7":
        url, headers, body = prepare_llm7_payload(payload)
    else:
        url, headers, body = prepare_ovh_payload(payload)

    return provider, url, headers, body

async def execute_upstream_request(provider: str, url: str, headers: dict, body: dict, stream: bool, force_proxy: Optional[str] = None):
    # ponytail: connect 1.8s + sock_read 6.0s drops frozen proxies fast; upgrade to circuit-breaker if upstream outage
    proxy_timeout = aiohttp.ClientTimeout(total=15.0, connect=1.8, sock_read=6.0)
    attempts = 0
    max_attempts = 2

    # Forced proxy mode (for testing specific proxy or explicit bypass)
    if force_proxy is not None:
        proxy = None if force_proxy == "direct" else force_proxy
        session = aiohttp.ClientSession(timeout=proxy_timeout)
        try:
            resp = await session.post(url, headers=headers, json=body, proxy=proxy, ssl=False)
            if resp.status == 200 and proxy:
                await proxy_pool.mark_success(proxy)
            return resp, session, proxy
        except Exception:
            await session.close()
            # fallback direct
            fallback_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=45.0, connect=3.5, sock_read=30.0))
            resp = await fallback_session.post(url, headers=headers, json=body, ssl=False)
            return resp, fallback_session, None

    # Normal rotation with max 2 attempts
    while attempts < max_attempts:
        attempts += 1
        proxy = await proxy_pool.get_proxy()
        if not proxy:
            break

        logger.info(f"[{provider.upper()}] Forwarding model '{body.get('model')}' | Attempt {attempts}/{max_attempts} | Proxy: {proxy}")

        session = aiohttp.ClientSession(timeout=proxy_timeout)
        try:
            resp = await session.post(url, headers=headers, json=body, proxy=proxy, ssl=False)
            if resp.status == 200:
                await proxy_pool.mark_success(proxy)
                return resp, session, proxy
            elif resp.status in [429, 403, 502, 503, 504]:
                err_text = await resp.text()
                logger.warning(f"Upstream returned {resp.status}: {err_text[:120]}. Rotating proxy...")
                await resp.release()
                await session.close()
                await proxy_pool.mark_bad(proxy)
                continue
            else:
                return resp, session, proxy
        except Exception as e:
            logger.warning(f"Proxy connect failed ({proxy}): {e}. Rotating immediately...")
            await session.close()
            await proxy_pool.mark_bad(proxy)

    # Fast fallback to direct connection
    logger.info(f"[{provider.upper()}] Fast fallback to DIRECT connection...")
    session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=45.0, connect=3.5, sock_read=30.0))
    resp = await session.post(url, headers=headers, json=body, ssl=False)
    return resp, session, None

async def route_and_execute(payload: dict, stream: bool, force_proxy: Optional[str] = None):
    provider, url, headers, body = route_payload(payload)
    return await execute_upstream_request(provider, url, headers, body, stream, force_proxy=force_proxy)
