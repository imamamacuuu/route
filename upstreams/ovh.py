from typing import Tuple

def prepare_ovh_payload(payload: dict) -> Tuple[str, dict, dict]:
    url = "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/chat/completions"
    # ponytail: explicit UA prevents WAF edge drop; upgrade to rotating pool if rate-limited
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "curl/8.0"
    }
    body = dict(payload)

    # Strip ovh/ prefix
    if body.get("model", "").startswith("ovh/"):
        body["model"] = body["model"][4:]

    # Sanitize messages
    clean_msgs = []
    for m in body.get("messages", []):
        msg = dict(m)
        if msg.get("role") == "developer":
            msg["role"] = "system"
        msg.pop("thought", None)
        clean_msgs.append(msg)
    body["messages"] = clean_msgs

    # Remove unsupported fields
    body.pop("thought", None)
    body.pop("preserve_thinking", None)
    body.pop("enable_thinking", None)

    return url, headers, body
