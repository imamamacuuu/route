from typing import Tuple

def prepare_kilo_payload(payload: dict) -> Tuple[str, dict, dict]:
    url = "https://api.kilo.ai/api/gateway/chat/completions"
    # ponytail: curl/8.0 bypasses Cloudflare Error 1010; upgrade to full browser UA if cf challenges
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "curl/8.0"
    }
    body = dict(payload)
    return url, headers, body
