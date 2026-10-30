# route

OpenAI-compatible keyless AI gateway with automatic proxy rotation and upstream aggregation.

Provides an OpenAI-compatible API endpoint (`/v1/chat/completions`, `/v1/models`) multiplexing requests across free/anonymous upstreams (OpenCode Zen, KiloCode, LLM7, OVHcloud) through an automated HTTPS CONNECT proxy pool.

```
                      +-----------------------------+
                      |   OpenAI SDK / Client CLI   |
                      | (Cursor, Cline, curl, python)|
                      +--------------+--------------+
                                     |
                          HTTP / HTTPS (Bearer/Basic)
                                     v
                 +---------------------------------------+
                 |       route Gateway (aiohttp)         |
                 |  - Auth Middleware                    |
                 |  - HTMX Admin Dashboard (/)           |
                 |  - Payload Normalizer & Dispatcher    |
                 +-------------------+-------------------+
                                     |
                     +---------------+---------------+
                     |                               |
       (Upstream Request)                   (Background Harvest)
                     |                               |
                     v                               v
         +-----------------------+       +-----------------------+
         | Round-Robin ProxyPool | <----+| 6x HTTPS Proxy Lists  |
         | (live HTTPS tunnels)  |       | (validation via CF)   |
         +-----------+-----------+       +-----------------------+
                     |
        +------------+------------+
        |                         |
   (via Proxy)             (Direct Fallback)
        |                         |
        +------------+------------+
                     |
                     v
   +------------------------------------+
   | Upstream AI Inference Providers    |
   | - OpenCode Zen Free Models         |
   | - KiloCode Gateway Models          |
   | - LLM7 Anonymous Models            |
   | - OVHcloud Kepler AI Models        |
   +------------------------------------+
```

## Resource Footprint & Performance

- **Runtime**: Python 3.10+ on single asyncio event loop.
- **Base Memory (RSS)**: ~35 MB idle RSS.
- **Harvesting Memory**: ~45-55 MB RSS during proxy probe sweeps (concurrency bounded to 50 parallel workers).
- **Network Overhead**: Streaming SSE chunks forwarded directly from upstream without buffering full responses into memory.

## Quickstart

### 1. Installation

```bash
git clone https://github.com/imamamacuuu/route.git
cd route
pip install -r requirements.txt
```

### 2. Environment Configuration

Copy `.env.example` or export environment variables:

```bash
cp .env.example .env
export PORT=17070
export HOST=0.0.0.0
export ROUTER_USER=admin
export ROUTER_PASS=pass
export ROUTER_BEARER=pass:pass
export API_KEY=
```

### 3. Run

```bash
python3 main.py
```

Console is available at `http://localhost:17070/`.

## Authentication

Requests require either HTTP Basic Auth or Bearer token authentication:

| Method | Header / Param | Default Value | Environment Override |
|---|---|---|---|
| Bearer Token | `Authorization: Bearer <token>` | `pass:pass` | `ROUTER_BEARER` |
| Custom API Key | `Authorization: Bearer <key>` | (none) | `API_KEY` |
| HTTP Basic | `Authorization: Basic <base64>` | `admin:pass` | `ROUTER_USER`, `ROUTER_PASS` |
| Query String | `?key=<token>` or `?auth=<token>` | (evaluated as Bearer) | |

Public paths requiring no authentication: `/`, `/healthz`, `/static/*`.

## API Usage

### Model Listing

```bash
curl -s http://localhost:17070/v1/models \
  -H "Authorization: Bearer pass:pass" | jq .
```

### Chat Completions (Non-Streaming)

```bash
curl -s -X POST http://localhost:17070/v1/chat/completions \
  -H "Authorization: Bearer pass:pass" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "kilo-auto/free",
    "messages": [{"role": "user", "content": "Ping"}]
  }' | jq .
```

### Chat Completions (SSE Streaming)

```bash
curl -N -X POST http://localhost:17070/v1/chat/completions \
  -H "Authorization: Bearer pass:pass" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "kilo-auto/free",
    "messages": [{"role": "user", "content": "Write a 3-word poem."}],
    "stream": true
  }'
```

### Python OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:17070/v1",
    api_key="pass:pass"
)

response = client.chat.completions.create(
    model="kilo-auto/free",
    messages=[{"role": "user", "content": "Hello"}],
    stream=True
)

for chunk in response:
    content = chunk.choices[0].delta.content or ""
    print(content, end="", flush=True)
```

## Supported Models Catalog

| Model ID | Name | Provider |
|---|---|---|
| `kilo-auto/free` | Kilo Auto Free | KiloCode |
| `stepfun/step-3.7-flash:free` | Step 3.7 Flash Free | KiloCode |
| `nvidia/nemotron-3.5-lightning:free` | Nemotron 3.5 Lightning | KiloCode |
| `nvidia/nemotron-3-ultra-550b-a55b:free` | Nemotron 3 Ultra 550B | KiloCode |
| `openrouter/free` | OpenRouter Free | KiloCode |
| `liquid/lfm-2.5-2.6b:free` | Liquid LFM 2.5 Free | KiloCode |
| `muse-spark-1.3-contributor-free` | Muse Spark 1.3 Free | Zen |
| `nemotron-3.5-lightning-free` | Nemotron 3.5 Lightning Free | Zen |
| `big-pickle` | Big Pickle Free | Zen |
| `cat-jam-free` | Cat Jam Free | Zen |
| `nemotron-3-ultra-free` | Nemotron 3 Ultra Free | Zen |
| `mimo-v2.6-flash-free` | MiMo v2.6 Flash Free | Zen |
| `deepseek-v4.1-flash-free` | DeepSeek v4.1 Flash Free | Zen |
| `codestral-latest` | Codestral Latest | LLM7 |
| `minimax-m2.7` | MiniMax M2.7 | LLM7 |
| `default` | Default | LLM7 |
| `fast` | Fast | LLM7 |
| `ovh/gpt-oss-120b` | OVH GPT-OSS 120B | OVHcloud |
| `ovh/gpt-oss-20b` | OVH GPT-OSS 20B | OVHcloud |
| `ovh/Qwen3.5-397B-A17B` | OVH Qwen 3.5 397B | OVHcloud |
| `ovh/Mistral-Small-3.2-24B-Instruct-2506` | OVH Mistral Small 3.2 | OVHcloud |

## Troubleshooting Runbook

### 1. 401 Unauthorized

**Symptom**: `401 Unauthorized` with `Invalid or missing credentials`.
**Verification**:
```bash
# Check current credentials accepted
curl -I http://localhost:17070/v1/models -H "Authorization: Bearer pass:pass"
```
**Fix**: Ensure `ROUTER_BEARER` matches request token or set custom `API_KEY`.

### 2. Upstream 429 / Rate Limited

**Symptom**: Upstream provider returns 429 Too Many Requests.
**Verification**: Check response header `X-Route-Proxy` to see which egress node was used.
**Fix**: Trigger proxy rotation manually via dashboard or endpoint:
```bash
curl -X POST http://localhost:17070/api/proxy/rotate \
  -H "Authorization: Bearer pass:pass"
```

### 3. Proxy Pool Starvation

**Symptom**: `active_proxies: 0` on `/healthz`.
**Verification**:
```bash
curl -s http://localhost:17070/healthz | jq .active_proxies
```
**Fix**: Trigger an immediate background harvest:
```bash
curl -X POST http://localhost:17070/api/proxy/refresh \
  -H "Authorization: Bearer pass:pass"
```
System automatically falls back to direct connection if proxy pool is empty.

## License

MIT License. See [LICENSE](LICENSE).
