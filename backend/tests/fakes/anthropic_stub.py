"""A stand-in for the Anthropic API.

Not a mock inside the app: an ASGI app the real Anthropic SDK talks to over a real
HTTP stack, so the request shape, the structured-output plumbing and the response
parsing are all genuinely exercised. Between this and production, only the host and
the credential differ - which is the claim "just add your API key" has to rest on.
"""

import json

from fastapi import FastAPI, Request

app = FastAPI()
seen: list[dict] = []
# Flipped by a test to exercise the refusal path.
STOP_REASON = "end_turn"


@app.post("/v1/messages")
async def messages(request: Request) -> dict:
    body = await request.json()
    seen.append(body)

    schema = (body.get("output_config") or {}).get("format", {}).get("schema")
    if schema:
        # Structured output: answer with something that satisfies the schema the SDK
        # sent, so `messages.parse` really validates it. Enums arrive as $refs into
        # $defs, which is exactly the part a naive fake gets wrong.
        defs = schema.get("$defs", {})

        def resolve(spec: dict) -> dict:
            ref = spec.get("$ref")
            if ref and ref.startswith("#/$defs/"):
                return defs.get(ref.split("/")[-1], {})
            return spec

        props = schema.get("properties", {})
        payload: dict = {}
        for name, raw in props.items():
            spec = resolve(raw)
            if "enum" in spec:
                payload[name] = spec["enum"][0]
            elif spec.get("type") == "array":
                payload[name] = []
            elif spec.get("type") == "integer":
                payload[name] = 25
            elif spec.get("type") == "boolean":
                payload[name] = False
            elif spec.get("anyOf"):
                options = [resolve(option) for option in spec["anyOf"]]
                enum = next((o["enum"][0] for o in options if "enum" in o), None)
                payload[name] = enum
            else:
                payload[name] = f"fake {name}"
        # Something recognisable for the fields the app displays.
        if "why_wrong" in payload:
            payload["why_wrong"] = "You solved for 3x and stopped there."
            payload["topic"] = "linear equations"
        if "section" in payload and isinstance(payload["section"], list):
            payload["section"] = ["math"]
        text = json.dumps(payload)
    else:
        text = "Three of your four misses are concept gaps in circles."

    return {
        "id": "msg_fake",
        "type": "message",
        "role": "assistant",
        "model": body.get("model", "claude-opus-5"),
        "content": [{"type": "text", "text": text}],
        "stop_reason": STOP_REASON,
        "stop_details": (
            {"type": "refusal", "category": "other", "explanation": "declined"}
            if STOP_REASON == "refusal"
            else None
        ),
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 10},
    }


@app.get("/seen")
async def what_was_sent() -> dict:
    return {"count": len(seen), "requests": seen}


def reset() -> None:
    seen.clear()
