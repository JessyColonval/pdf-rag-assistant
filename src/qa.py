from typing import Optional, List, Dict, Any

import re
import json
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from src.indexing import embed, index_text, tokenize
from src.llm_usage import make_client, add_usage, get_usage

ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = ROOT / "prompts" / "answer.md"
K_CANDIDATES = 20
K_FINAL = 6
RRF_K = 60


def load_prompt() -> str:
    text = PROMPT_PATH.read_text(encoding="utf-8")
    return re.sub(r"<!--.*?-->", "", text, flags=re.S).strip()


def load_index(index_dir: str|Path) -> Dict[str, Any]:
    """
    Get the list of "passages" extracted from all documents and the matrix of vectors that encode
    those "passages".

    Parameters
    ----------
    index_dir : str|Path
        The folder containing the JSON file with the passages and the .npy file containing the
        vector matrix.

    Returns
    -------
    Dict[str, Any]
    """
    index_dir = Path(index_dir)
    with open(index_dir / "passages.jsonl", encoding="utf-8") as f:
        passages = [json.loads(line) for line in f]
    emb = np.load(index_dir / "embeddings.npy")
    bm25 = BM25Okapi([tokenize(index_text(p)) for p in passages])
    return {"passages": passages, "emb": emb, "bm25": bm25}


def search(
    index: Dict[str, Any], question: str, k: int = K_FINAL
) -> List[Dict[str, int|int|List[str]]]:
    """
    Find the k best "passages" for the question asked.

    Parameters
    ----------
        index : Dict[str, Any]
        question : str
            The question asked.
        k : int, default: K_FINAL
            The number of "passages" to keep
    Returns
    -------
    List[Dict[str, int|str|List[str]]]
        A list of the top k "passages" for the question asked.
    """
    # Proximity matrix between the passages and the question asked.
    # BM25 looks at the words they have in common.
    lex = np.asarray(index["bm25"].get_scores(tokenize(question)))

    dense = index["emb"] @ embed([question], "query")[0]

    # Keep the first K_CANDIDATES elements of 'lex' and 'dense'.
    rankings = [
        [i for i in np.argsort(-lex)[:K_CANDIDATES] if lex[i] > 0],
        list(np.argsort(-dense)[:K_CANDIDATES])
    ]

    # Calculate the scores for each "passage".
    # A passage gains 1/(60 + rank) in each ranking in which it appears.
    scores: Dict[int, float] = {}
    for ranking in rankings:
        for rank, i in enumerate(ranking):
            _id = int(i)
            scores[_id] = scores.get(_id, 0.0) + 1.0 / (RRF_K + rank + 1)

    return [
        index["passages"][i]
        for i in sorted(scores, key=scores.get, reverse=True)[:k]
    ]


def format_passages(passages: List[Dict[str, int|str|List[str]]]) -> str:
    out = []
    for n, p in enumerate(passages, 1):
        sec_msg = ""
        if p["section"]:
            sec_msg = ", section: {p['section']:}"
        meta = f"document: {p['doc_id']:}, page {p['page']:}{sec_msg:}"
        out.append(f"[{n:d}] {' > '.join(p['path']):} ({meta:})\n{p['text']:}")
    return "\n\n".join(out)


def cited_passages(
    answer: Dict[str, str|List[Dict[str, int|str|List[str]]]|Dict[str, int]]
) -> List[Dict[str, int|str|List[str]]]:
    """
    Get the numbers of the passages the LLM used to construct its response.
    We assume the LLM uses only the "[INT]" format to refer to the passages.

    Parameters
    ----------
    answer : Dict[str, str|List[Dict[str, int|str|List[str]]]|Dict[str, int]]
        The LLM's response to the question asked.

    Returns
    -------
    List[Dict[str, int|str|List[str]]]
        The list of "passages" cited by the LLM.
    """
    nums = sorted(
        {
            int(n)
            for n in re.findall(r"\[(\d+)\]", answer["text"])
        }
    )
    return [
        answer["passages"][n - 1]
        for n in nums
        if 1 <= n <= len(answer["passages"])
    ]


def ask(
    index: Dict[str, Any], question: str, model: str,
    totals: Optional[Dict[str, int]] = None
) -> Dict[str, str|List[Dict[str, int|str|List[str]]]|Dict[str, int]]:
    # Finds the best passages to send to LLMs to answer the question asked.
    passages = search(index, question)

    # Build the prompt.
    prompt = load_prompt().\
            replace("{passages}", format_passages(passages)).\
            replace("{question}", question)

    # Send the request to the LLM with the question and the "relevant" excerpts collected.
    client = make_client()
    result = client.chat.completions.create(
        model=model, temperature=0,
        messages=[{"role": "user", "content": prompt}]
    )

    # Get the number of tokens used.
    usage = get_usage(result)
    if totals is not None:
        add_usage(totals, usage)

    return {
        "text": result.choices[0].message.content.strip(),
        "passages": passages,
        "usage": usage,
        "truncated": result.choices[0].finish_reason == "length"
    }
