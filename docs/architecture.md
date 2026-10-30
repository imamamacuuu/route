# Architecture Specification: route

## 1. Overview

`route` is an asynchronous reverse proxy designed to translate OpenAI-compatible completions API calls into vendor-specific upstream inference calls while rotating egress requests through validated public HTTPS proxies.

```
                              [Client]
                                 |
                                 v
                       +-------------------+
                       |  aiohttp Server   |
                       |  (port 17070)     |
                       +---------+---------+
                                 |
                        +--------v--------+
                        | Auth Middleware |
                        +--------+--------+
                                 |
                        +--------v--------+
                        | URL Dispatcher  |
                        +---+---------+---+
                            |         |
          +-----------------+         +-----------------+
          |                                             |
          v                                             v
  [Admin Dashboard / HTMX]                    [OpenAI Completions API]
  - UI Template Rendering                     - Request Normalization
  - Dynamic Settings Sync                     - Upstream Selector
  - Pool Telemetry Views                      - Proxy Rotation Injector
                                                        |
                                                        v
                                              [Upstream Adapter]
                                              - zen
                                              - kilo
                                              - llm7
                                              - ovh
                                                        |
                                                        v
                                           [ProxyPool / Direct Egress]
                                                        |
                                                        v
                                            [Upstream Inference Node]
```

## 2. Component Breakdown

### 2.1 Server Core (`server.py`, `main.py`)
- Framework: `aiohttp.web`
- Event loop: Standard Python `asyncio`
- Lifecycle hooks:
  - `on_startup`: Launches background proxy worker (`ProxyPool.background_worker()`).
  - `on_cleanup`: Gracefully cancels worker tasks.
- Routes:
  - UI: `/`, `/partials/*`
  - Health: `/healthz`
  - OpenAI v1 API: `/v1/models`, `/models`, `/v1/chat/completions`, `/chat/completions`
  - Operations: `/api/proxy/refresh`, `/api/proxy/rotate`, `/api/proxy/test-provider`, `/api/settings`

### 2.2 Authentication Layer (`auth.py`)
- Evaluated via `auth_middleware` on all routes except `/`, `/healthz`, and `/static/*`.
- Header support:
  - `Authorization: Bearer <token>`: Validated against `runtime_settings["bearer"]`, `runtime_settings["user"]:runtime_settings["pass"]`, or `runtime_settings["api_key"]`.
  - `Authorization: Basic <base64>`: Validated against `runtime_settings["user"]` and `runtime_settings["pass"]`.
  - Fallback query parameters: `?key=` or `?auth=`.
- Dynamic settings mutation: `/api/settings` accepts JSON payload `{"api_key": "<value>"}` to mutate in-memory API key without restarting process.

### 2.3 Proxy Harvesting & Rotation Subsystem (`proxy_pool.py`)
- **Sources**: 6 remote text feeds containing IP:PORT strings.
- **Harvesting Strategy**:
  1. Concurrently fetches candidate proxy feeds using `aiohttp.ClientSession`.
  2. Parses IPv4:PORT combinations via regex `\b(?:\d{1,3}\.){3}\d{1,3}:\d{2,5}\b`.
  3. Validates candidate proxies concurrently via an `asyncio.Semaphore(50)`.
  4. Validation probe sends an HTTPS GET to `https://cloudflare.com/cdn-cgi/trace` with a 5.0 second total timeout.
  5. Live proxies matching status 200 and containing `h=cloudflare.com` are stored in an in-memory list `self.proxies`.
- **Rotation Strategy**:
  - `get_proxy()`: Returns a random choice from verified proxies.
  - `rotate()`: Pops the current head and appends to tail (atomic round-robin) or returns direct if empty.
  - `report_failure(proxy)`: Removes malfunctioning proxy from active set to prevent retrying bad nodes.

### 2.4 Upstream Dispatcher & Adapters (`upstreams/`)
Translates standard OpenAI request bodies to target provider requirements:

- **Zen (`zen.py`)**:
  - Target: `https://opencode.ai/zen/v1/chat/completions`
  - Headers: Generates dynamic anonymous session UUIDs and browser-like user agent.
- **KiloCode (`kilo.py`)**:
  - Target: `https://api.kilo.ai/api/gateway/chat/completions`
  - Headers: Standard bearer/gateway proxy headers.
- **LLM7 (`llm7.py`)**:
  - Target: `https://api.llm7.io/v1/chat/completions`
  - Headers: Injects anonymous authorization tokens.
- **OVHcloud (`ovh.py`)**:
  - Target: `https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/chat/completions`
  - Direct upstream execution for open-weights endpoints.

## 3. Streaming Flow & Resource Math

### SSE Streaming Lifespan
1. Client POSTs to `/v1/chat/completions` with `"stream": true`.
2. Dispatcher acquires a proxy from `ProxyPool`.
3. Upstream connection established via `aiohttp.ClientSession(timeout=ClientTimeout(total=120))`.
4. Downstream `web.StreamResponse` initiated with `Content-Type: text/event-stream`.
5. Chunks transferred via `resp.content.iter_chunks()` without full body buffering.
6. Upon completion or client abort, connection released and session closed.

### Memory Calculations
- Event loop + aiohttp base: ~25 MB RSS.
- Proxy pool storage (up to 500 candidate strings): < 1 MB.
- Active streaming request buffer: ~64 KB per concurrent stream.
- Total idle RSS target: ~35 MB.
- Total active load RSS (20 concurrent streams): ~45-55 MB.
