from typing import Tuple

def prepare_llm7_payload(payload: dict) -> Tuple[str, dict, dict]:
    url = "https://api.llm7.io/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer unused"
    }
    body = dict(payload)
    return url, headers, body
