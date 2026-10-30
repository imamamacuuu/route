import os

PORT = int(os.environ.get("PORT", "17070"))
HOST = os.environ.get("HOST", "0.0.0.0")

# Authentication credentials (configurable via env or runtime settings)
DEFAULT_USERNAME = os.environ.get("ROUTER_USER", "admin")
DEFAULT_PASSWORD = os.environ.get("ROUTER_PASS", "pass")
DEFAULT_BEARER_TOKEN = os.environ.get("ROUTER_BEARER", "pass:pass")
CUSTOM_API_KEY = os.environ.get("API_KEY", "")

# Keyless Model Catalog
MODELS = [
    # OpenCode Zen Free Models
    {"id": "muse-spark-1.3-contributor-free", "name": "Muse Spark 1.3 Free", "provider": "zen"},
    {"id": "nemotron-3.5-lightning-free", "name": "Nemotron 3.5 Lightning Free", "provider": "zen"},
    {"id": "big-pickle", "name": "Big Pickle Free", "provider": "zen"},
    {"id": "cat-jam-free", "name": "Cat Jam Free", "provider": "zen"},
    {"id": "nemotron-3-ultra-free", "name": "Nemotron 3 Ultra Free", "provider": "zen"},
    {"id": "mimo-v2.6-flash-free", "name": "MiMo v2.6 Flash Free", "provider": "zen"},
    {"id": "deepseek-v4.1-flash-free", "name": "DeepSeek v4.1 Flash Free", "provider": "zen"},

    # KiloCode Free Models
    {"id": "kilo-auto/free", "name": "Kilo Auto Free", "provider": "kilo"},
    {"id": "stepfun/step-3.7-flash:free", "name": "Step 3.7 Flash Free", "provider": "kilo"},
    {"id": "nvidia/nemotron-3.5-lightning:free", "name": "Nemotron 3.5 Lightning (Kilo)", "provider": "kilo"},
    {"id": "nvidia/nemotron-3-ultra-550b-a55b:free", "name": "Nemotron 3 Ultra 550B (Kilo)", "provider": "kilo"},
    {"id": "openrouter/free", "name": "OpenRouter Free (Kilo)", "provider": "kilo"},
    {"id": "liquid/lfm-2.5-2.6b:free", "name": "Liquid LFM 2.5 Free", "provider": "kilo"},

    # LLM7 Free Anonymous Models
    {"id": "codestral-latest", "name": "Codestral Latest (LLM7)", "provider": "llm7"},
    {"id": "minimax-m2.7", "name": "MiniMax M2.7 (LLM7)", "provider": "llm7"},
    {"id": "default", "name": "Default (LLM7)", "provider": "llm7"},
    {"id": "fast", "name": "Fast (LLM7)", "provider": "llm7"},

    # OVHcloud Models
    {"id": "ovh/gpt-oss-120b", "name": "OVH GPT-OSS 120B", "provider": "ovh"},
    {"id": "ovh/gpt-oss-20b", "name": "OVH GPT-OSS 20B", "provider": "ovh"},
    {"id": "ovh/Qwen3.5-397B-A17B", "name": "OVH Qwen 3.5 397B", "provider": "ovh"},
    {"id": "ovh/Mistral-Small-3.2-24B-Instruct-2506", "name": "OVH Mistral Small 3.2", "provider": "ovh"},
]

MODEL_MAP = {m["id"]: m for m in MODELS}

# Petani-Proxy Feeds (prioritizing HTTPS CONNECT capable lists)
PROXY_SOURCES = [
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
    "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/https.txt",
    "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/https.txt",
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=2500&country=all&ssl=yes&anonymity=all",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/all.txt",
]
