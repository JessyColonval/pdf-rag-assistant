from typing import List, Dict

import json
import re
from pathlib import Path
from sentence_transformers import SentenceTransformer
import numpy as np

MAX_CHARS = 1500
MIN_CHARS = 400
EMBED_MODEL = "intfloat/multilingual-e5-small"
SKIP_HEADINGS = re.compile(r"^\W*(sommaire|table des mati[èe]res)\W*$", re.I)
META_LINE = re.compile(r"^(Espace|Section|Type)\s*:\s*(.*)$")
_MODEL = None


def tokenize(text: str) -> List[str]:
    """
    Split a text into a list of lowercase words.

    Parameters
    ----------
    text : str
        The text to be split.

    Returns
    -------
    List[str]
        The list of lowercase words in the order they appear in the given text.
    """
    return re.findall(r"\w+", text.lower())


def figure_text(block: Dict[str, bool|int|str]) -> str:
    """
    Format part of the image's information so that the parts deemed important are used for indexing,
    i.e., the abstract and keywords.

    Parameters
    ----------
    block : Dict[str, bool|int|str]

    Returns
    -------
    str
    """
    # Convert the figure description format into a dictionary.
    fields = dict(re.findall(r"^([A-Z_]+):\s*(.*)$", block["description"], re.M))

    # Include only the abstract, keywords, and structure if the image is a schematic diagram.
    parts = [fields.get("RESUME"), fields.get("MOTS_CLES")]
    if block.get("figure_type") == "schema":
        parts.append(fields.get("STRUCTURE"))

    text = " ".join(p for p in parts if p)
    return f"[Figure {block.get('figure_type', '')}] {text:}".strip()


def merge_small(passages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Merge all passages within the same section that are considered too short.

    Parameters
    ----------
    passages : List[Dict[str, str]]
        A list of passages from a document.

    Returns
    -------
    Dict[str, str]
        A new list of passages, with the smallest ones merged together.
    """
    out = []
    for p in passages:
        # Get the last passage stored in the result.
        prev = None
        if len(out) > 0:
            prev = out[-1]

        # Merge the last saved passage with the current one if:
        # - the current passage is too short;
        # - both passages are in the same section;
        # - and the combined length of these two passages does not exceed the desired maximum size.
        if prev is not None \
                and len(p["text"]) < MIN_CHARS \
                and prev["path"][0] == p["path"][0] \
                and len(prev["text"]) + len(p["text"]) <= MAX_CHARS:

            # The new merged passage then contains:
            # - the sum of the figures present in both passages;
            # - the text is: [TEXT_1st_PASSAGE]\n\n[TITLE_2nd_PASSAGE]\n[TEXT_2nd_PASSAGE]
            title = ""
            if len(p["path"]) > 1:
                title = f"{p['path'][-1]:}\n"
            prev["text"] = f"{prev['text']}\n\n{title:}{p['text']:}"
            prev["figures"] += p["figures"]

        # Otherwise, the current passage remains unchanged.
        else:
            out.append(p)

    # Add the source document from which each passage is taken.
    for i, p in enumerate(out):
        p["id"] = f"{p['doc_id']}#{i}"

    return out


def build_passages(
    doc: Dict[str, str|List[Dict[str, bool|int|str]]]
) -> List[Dict[str, int|str|List[str]]]:
    """
    Organizes the data in the document, which is in block form, into a list called a "passage".
    A "passage" is the set of data contained in a section of the original document.
    These "passages" are limited in size, and a single "passage" can contain the content of several
    "sections" if they are too small.

    Parameters
    ----------
    doc : Dict[str, Dict[str, str|Dict[str, bool|int|str]]
        The representation of a PDF document after this data has been extracted.
        It takes the following form:
        {
            "doc_id": str,
            "pdf_date": str,
            "blocks": List[Dict[str, bool|int|str]]
        }

    Returns
    -------
    List[Dict[str, int|str|List[str]]
        The list of passages extracted from the given document.
        It takes the following form:
        {
            "doc_id": str,
            "page": int,
            "path": List[str],
            "section": str,
            "text": str,
            "figures": List[str]
        }
    """
    doc_id, passages = doc["doc_id"], []
    doc_title, section = doc_id, None
    heading, page, lines, figs, size, n = None, None, [], [], 0, 0

    def flush():
        nonlocal lines, figs, size, n
        text = "\n".join(lines).strip()
        if text and not (heading and SKIP_HEADINGS.match(heading)):
            path = [doc_title] + ([heading] if heading and heading != doc_title else [])
            passages.append(
                {
                    "doc_id": doc_id, "page": page,
                    "path": path, "section": section,
                    "text": text, "figures": figs
                }
            )
        lines, figs, size, n = [], [], 0, 0

    for block in doc["blocks"]:
        # A new title closes the "passage" currently under construction and adds it to the list of
        # "passages".
        # No lines are collected for the construction of a "passage".
        if block["type"] == "heading":
            flush()
            heading, page = block["text"].strip(), block["page"]
            continue

        # No formatting is required when the block contains the contents of a table or plain text.
        if block["type"] in ("text", "table"):
            line = block["text"]

        # Formats the text in a bulleted or numbered list using hyphens or numbers.
        elif block["type"] == "list_item":
            if block.get("numbered"):
                n += 1
                line = f"{n}. {block['text']}"
            else:
                line = f"- {block['text']}"

        # Format the figure's description in order to keep only a part of it.
        # Figures with no description or decorative figures are ignored.
        elif block["type"] == "figure":
            if block.get("decorative") or not block.get("description"):
                continue
            line = figure_text(block)
            figs.append({"id": block["id"], "image_path": block.get("image_path")})

        else:
            continue

        # Close the "passage" when the character limit is reached, unless doing that splits a
        # bulleted list.
        if size > MAX_CHARS and block["type"] != "list_item":
            flush()

        # If there is no line, then the last "passage" has been saved and a new one will be
        # created. The page number of the next "passage" will be that of its 1st line.
        if not lines:
            page = block["page"]

        if block["type"] not in ("list_item", "figure"):
            n = 0

        lines.append(line)
        size += len(line)

    # Build the last “passage” with the latest data from the document.
    flush()

    return merge_small(passages)


def index_text(p: dict) -> str:
    return " > ".join(p["path"]) + "\n" + p["text"]


def embed(texts: list[str], kind: str) -> np.ndarray:
    global _MODEL
    if _MODEL is None:
        _MODEL = SentenceTransformer(EMBED_MODEL)
    return np.asarray(_MODEL.encode(
        [f"{kind}: {t}" for t in texts], normalize_embeddings=True,
        batch_size=32, show_progress_bar=True)
    )


def build_index(extracted_dir: Path, index_dir: Path) -> list[dict]:
    passages = []
    for path in sorted(extracted_dir.glob("*.json")):
        passages += build_passages(json.loads(path.read_text(encoding="utf-8")))
    index_dir.mkdir(parents=True, exist_ok=True)
    with open(index_dir / "passages.jsonl", "w", encoding="utf-8") as f:
        for p in passages:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    np.save(index_dir / "embeddings.npy", embed([index_text(p) for p in passages], "passage"))
    return passages
