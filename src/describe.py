from typing import Optional, Dict

import base64
import hashlib
import io
import json
import re
import time
from pathlib import Path

from PIL import Image

from src.llm_usage import add_usage, format_usage, get_usage

MAX_SIDE = 1024
MIN_SIDE = 64
CONTEXT_BLOCKS = 3
MAX_TOKENS = 2000

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_prompt_PATH = ROOT / "prompts" / "eyes.md"


def load_prompt(path: Path) -> str:
    text = Path(path).read_text(encoding="utf-8")
    return re.sub(r"<!--.*?-->", "", text, flags=re.S).strip()

def parse_type(text: str) -> str:
    m = re.match(r"\s*TYPE:\s*([a-z_]+)", text, re.I)
    if m is not None:
        return m.group(1).lower()
    return "inconnu"


def context_before(blocks: list[dict], i: int) -> str:
    out = []
    for b in reversed(blocks[:i]):
        if b["type"] in ("heading", "text", "list_item"):
            out.append(b["text"][:300])
            if len(out) == CONTEXT_BLOCKS:
                break
    return "\n".join(reversed(out)) or "(aucun)"


def prepare_image(path: str) -> Optional[bytes]:
    """PNG réduit à MAX_SIDE, ou None si l'image est trop petite pour valoir un appel."""
    try:
        img = Image.open(path).convert("RGB")
    except FileNotFoundError:
        return None
    if min(img.size) < MIN_SIDE:
        return None
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def describe(client, model: str, png: bytes, prompt: str) -> Dict[str, str|Dict[str, int]]:
    b64 = base64.b64encode(png).decode()
    content = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
    ]
    for attempt in range(3):
        try:
            r = client.chat.completions.create(
                model=model, temperature=0, max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": content}]
            )
            return {
                "text": r.choices[0].message.content.strip(),
                "usage": get_usage(r),
                "truncated": r.choices[0].finish_reason == "length"
            }
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def process_dir(
    out_dir: Path, client, model: str, limit: Optional[int], force: bool, totals: Dict[str, int]
) -> int:
    cache_path = out_dir / "cache" / "descriptions.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    calls = 0

    template = load_prompt(DEFAULT_prompt_PATH)

    # Iterate through all JSON files in the 'out_dir' folder
    for json_path in sorted(out_dir.glob("*.json")):
        doc = json.loads(json_path.read_text(encoding="utf-8"))
        blocks = doc["blocks"]

        # Iterate through all the blocks in the JSON file.
        for i, b in enumerate(blocks):

            # Ignore blocks that are not figures or that do not have a path to an image.
            if b["type"] != "figure" or not b.get("image_path"):
                continue

            # Ignore blocks that already have a description when the 'force' parameter is not
            # enabled.
            if "description" in b and not force:
                continue

            # Resize the image, if necessary, before sending the LLM request.
            # The type is set to 'decoratif' and the description is set to empty if no image is
            # found.
            png = prepare_image(b["image_path"])
            if png is None:
                b.update(
                    description="", figure_type="decoratif",
                    decorative=True, description_model=None
                )
                continue

            # Build the prompt that will be sent to the LLM.
            prompt = template.format(
                context=context_before(blocks, i),
                caption=b.get("caption", "aucune")
            )

            # Creates a unique key that encodes the combination of image, prompt, and model.
            # It allows to check if a generation for the current image has already been performed.
            # If not, and if the imposed limit on LLM calls has not been exceeded, then a request
            # for a description of the image is sent.
            key = hashlib.sha256(png + model.encode() + prompt.encode()).hexdigest()
            if key not in cache:
                if limit is not None and calls >= limit:
                    continue
                result = describe(client, model, png, prompt)
                cache[key] = result["text"]
                calls += 1
                if totals is not None:
                    add_usage(totals, result["usage"])
                cache_path.parent.mkdir(exist_ok=True)
                cache_path.write_text(
                    json.dumps(cache, ensure_ascii=False, indent=1),
                    encoding="utf-8"
                )

                # Print the cost of the request and warn about the token limit if it is too low.
                warn = ""
                if result["truncated"]:
                    warn = " Truncated response: Increase MAX_TOKENS"
                print(f"{b['id']:}: described ({format_usage(result['usage']):}){warn:}")

            # Add the result of the LLM request as the image description in its block.
            text = cache[key]
            ftype = parse_type(text)
            b.update(
                description=text, figure_type=ftype,
                decorative=(ftype == "decoratif"), description_model=model
            )

        json_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    return calls
