from typing import Optional, Dict

import os
from dotenv import load_dotenv
from openai import OpenAI


def make_client():
    load_dotenv()
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY")
    )

def new_total() -> Dict[str, int]:
    return {"calls": 0, "missing": 0, "prompt": 0, "completion": 0, "total": 0}


def get_usage(response) -> Optional[Dict[str, int]]:
    u = getattr(response, "usage", None)
    if u is None:
        return None
    return {
        "prompt": u.prompt_tokens or 0,
        "completion": u.completion_tokens or 0,
        "total": u.total_tokens or 0
    }


def add_usage(total: Dict[str, int], usage: Optional[Dict[str, int]]) -> None:
    total["calls"] += 1
    if usage is None:
        total["missing"] += 1
        return
    for key in ("prompt", "completion", "total"):
        total[key] += usage[key]


def format_usage(usage: Optional[Dict[str, int]]) -> str:
    if usage is None:
        return "tokens : n/d"
    return (
        f"{usage['prompt']} input tokens + {usage['completion']} output tokens = {usage['total']}"
    )


def format_total(total: dict) -> str:
    s = (
        f"Summary: {total['calls']} LLM call(s), {total['prompt']} input tokens + "
        f"{total['completion']} output tokens = {total['total']} tokens"
    )
    if total["missing"]:
        s += f" ({total['missing']} call(s) with no usage information, not counted)"
    return s
