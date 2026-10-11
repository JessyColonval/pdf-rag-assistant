from typing import List

import json
import argparse
from pathlib import Path

from src.llm_usage import make_client, new_total, format_total, format_usage
from src.extraction import make_converter, extract
from src.describe import process_dir
from src.indexing import build_index
from src.qa import load_index, ask, cited_passages


def format_json_name(out_dir: Path, pdf_name: str) -> Path:
    return out_dir / f"{pdf_name:}.json"

def unextracted_files(files: List[str], out_dir: Path) -> List[str]:
    return [
        file
        for file in files
        if not format_json_name(out_dir, file.stem).exists()
    ]


if __name__ == "__main__":
    # Initializes the parser for the arguments accepted by this script.
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out_data", type=str, required=True,
        help="The output path where the extracted PDF files will be saved."
    )
    ap.add_argument(
        "--out_idx", type=str, required=True,
        help="The output path where the where the information index is stored."
    )
    ap.add_argument(
        "--pdfs", type=str, required=True,
        help="The path to the PDF files from which data needs to be extracted."
    )
    ap.add_argument(
        "--vision_model", type=str, required=True,
        help="OpenRouter ID of a model that supports images."
    )
    ap.add_argument(
        "--answer_model", type=str, required=True,
        help="OpenRouter ID of a model that will answer the question."
    )
    ap.add_argument(
        "--question", type=str, required=True,
        help="The question you would like to ask the LLM."
    )
    ap.add_argument(
        "--force", action="store_true",
        help="Re-describe even the figures that have already been described."
    )
    ap.add_argument("--show_passages", action="store_true")
    ap.add_argument("--limit", type=int, help="Maximum number of API calls.")
    args = ap.parse_args()

    # Create the outputs folder where the data extracted from the PDF files will be stored.
    OUT_EXTRAC = Path(args.out_data)
    OUT_INDEX = Path(args.out_idx)
    OUT_EXTRAC.mkdir(parents=True, exist_ok=True)
    OUT_INDEX.mkdir(parents=True, exist_ok=True)

    # Get all PDF files that haven't already been extracted.
    PDFS_DIR = Path(args.pdfs)
    pdfs = unextracted_files(PDFS_DIR.glob("**/*.pdf"), OUT_EXTRAC)

    # Initialize the model and extract data ONLY if there are still PDF files whose data has not
    # been extracted.
    if len(pdfs) > 0:
        converter = make_converter()  # Model initialization.

        for pdf in pdfs:
            OUT_JSON = OUT_EXTRAC / f"{pdf.stem}.json"
            result = extract(pdf, OUT_EXTRAC, converter)
            OUT_JSON.write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            n_fig = sum(b["type"] == "figure" for b in result["blocks"])
            print(f"{pdf.name:}: {len(result['blocks']):d} blocs, {n_fig:d} figures")

    else:
        print("All PDF has already been extracted.")

    #
    totals = new_total()
    n = process_dir(OUT_EXTRAC, make_client(), args.vision_model, args.limit, args.force, totals)
    print(f"{n} API calls made (cached results do not cost any tokens).")
    print(format_total(totals))

    #
    build_index(OUT_EXTRAC, OUT_INDEX)

    #
    ans = ask(load_index(OUT_INDEX), args.question, args.answer_model)

    if args.show_passages:
        print("\n=== Excerpts sent to the LLM ===")
        for n, p in enumerate(ans["passages"], 1):
            print(f"[{n}] {' > '.join(p['path'])} (p.{p['page']}) : {p['text'][:100]!r}")
        print("================================\n")

    print(f"=== LLM's Response ===\n{ans['text']:}\n======================\n")
    if ans["truncated"]:
        print("\nTruncated response (length limit reached).")

    #
    print("\n=== Sources cited ===")
    for p in cited_passages(ans):
        imgs = [
            f["image_path"]
            for f in p["figures"]
            if f.get("image_path")
        ]
        imgs_msg = ""
        if len(imgs) > 0:
            imgs_msg = f"  images: {imgs:}"
        print(f"- {p['doc_id']}, p.{p['page']}, {' > '.join(p['path'])}{imgs_msg:}")
    print("=====================")

    print(f"\nTokens: {format_usage(ans['usage'])}")
