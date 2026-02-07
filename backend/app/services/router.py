from typing import Any

CHANNEL_ROUTES: dict[str, dict[str, Any]] = {
    "expenses": {"pipeline": "expense", "required_fields": ["amount"]},
    "travel": {"pipeline": "travel", "required_fields": ["destination", "dates"]},
    "vendor-requests": {"pipeline": "vendor", "required_fields": ["vendor_name"]},
    "maintenance": {"pipeline": "maintenance", "required_fields": []},
    "ask-policy": {"pipeline": "sop_qa", "required_fields": []},
}


def route_channel(channel: str | None) -> dict[str, Any]:
    if not channel:
        return {"pipeline": "general", "required_fields": [], "intake_tier": 2}
    channel_key = channel.strip().lower()
    if channel_key in CHANNEL_ROUTES:
        data = CHANNEL_ROUTES[channel_key]
        return {**data, "intake_tier": 1}
    return {"pipeline": "general", "required_fields": [], "intake_tier": 2}
