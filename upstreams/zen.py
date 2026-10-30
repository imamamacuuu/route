import random
import string
import time
from typing import Tuple

BASE62 = string.digits + string.ascii_letters

def random_base62(n: int) -> str:
    return "".join(random.choice(BASE62) for _ in range(n))

def random_hex(n: int) -> str:
    return "".join(random.choice("0123456789abcdef") for _ in range(n))

def generate_zen_session_id() -> str:
    # ponytail: 12-bit shift matches OpenCode CLI logic; upgrade if identity persisted on disk
    current = (int(time.time() * 1000) << 12) + 1
    inverted = ((1 << 48) - 1) ^ (current & ((1 << 48) - 1))
    inv_hex = f"{inverted:012x}"
    return f"ses_{inv_hex}{random_base62(14)}"

ZEN_INJECTED_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read",
            "description": "Read file contents or directory entries.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "shell",
            "description": "Execute shell commands.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"]
            }
        }
    }
]

def prepare_zen_payload(payload: dict) -> Tuple[str, dict, dict]:
    url = "https://opencode.ai/inference/openai/v1/chat/completions"
    session_id = generate_zen_session_id()
    project_id = random_hex(40)
    trace_id = random_hex(32)
    span_id = random_hex(16)

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer public",
        "User-Agent": "opencode/latest/2.1.3/cli",
        "x-opencode-client": "cli",
        "x-opencode-project": project_id,
        "x-opencode-session": session_id,
        "x-opencode-session-id": session_id,
        "x-session-affinity": session_id,
        "b3": f"{trace_id}-{span_id}-1-{random_hex(16)}",
        "traceparent": f"00-{trace_id}-{span_id}-01",
        "x-opencode-request": f"msg_{int(time.time()):x}{random_base62(14)}",
    }

    body = dict(payload)
    messages = list(body.get("messages", []))

    # Invalidate / wrap system prompt with <env>
    env_str = "<env>\nWorking directory: /tmp\n</env>"
    has_system = False
    for m in messages:
        if m.get("role") == "system":
            if "</env>" not in m.get("content", ""):
                m["content"] = f"{env_str}\n{m.get('content', '')}"
            has_system = True
            break
    if not has_system:
        messages.insert(0, {"role": "system", "content": env_str})
    body["messages"] = messages

    # Merge required tools instead of overwriting caller custom tools
    # ponytail: append missing read/shell; add tool translation bridge if caller lacks function call parsing
    tools = list(body.get("tools") or [])
    names = {t.get("function", {}).get("name") or t.get("name") for t in tools if isinstance(t, dict)}
    for inj in ZEN_INJECTED_TOOLS:
        if inj["function"]["name"] not in names:
            tools.append(inj)
    body["tools"] = tools

    return url, headers, body
