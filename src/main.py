from typing import List, Dict

import json
import argparse
from pathlib import Path

from rich.markdown import Markdown
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.text import Text

from src.llm_usage import make_client, new_total, format_total
from src.extraction import make_converter, extract
from src.describe import process_dir
from src.indexing import build_index
from src.qa import load_index, ask, cited_passages


console = Console()

def format_json_name(out_dir: Path, pdf_name: str) -> Path:
    return out_dir / f"{pdf_name:}.json"

def unextracted_files(files: List[str], out_dir: Path) -> List[str]:
    return [
        file
        for file in files
        if not format_json_name(out_dir, file.stem).exists()
    ]

def display_passages(passages: List[Dict[str, int|int|List[str]]]) -> None:
    content = Text()

    for i_psg, psg in enumerate(passages, start=1):
        source = psg.get("doc_id", "Inconnu")
        page = psg.get("page", "?")
        path = psg.get("path", ["Sans titre"])
        title = " > ".join(path[1:])
        excerpt = psg.get("text", "")

        content.append(f"[{i_psg:d}] ", style="bold cyan")
        content.append(f"{source:}", style="bold")
        content.append(f" · p.{page:}\n", style="dim")
        content.append(f"    {title:}\n", style="bold")
        content.append(f"    {excerpt[:100]}...\n", style="dim")

    console.print(
        Panel(
            content,
            title="[bold cyan]\"Passages\" collected[/bold cyan]",
            subtitle=f"{len(passages)} passages",
            border_style="cyan",
            padding=(1, 2),
        )
    )


def display_response(response: str) -> None:
    console.print(
        Panel(
            Markdown(response),
            title="[bold green]LLM assistant[/bold green]",
            border_style="green",
            padding=(1, 2),
        )
    )


def display_metrics(input_tokens: int, output_tokens: int) -> None:
    total = input_tokens + output_tokens
    console.print(
        f"\n[dim]Tokens : {total:,} "
        f"(input: {input_tokens:,} · output: {output_tokens:,})[/dim]"
    )


def pretty_print(answer: Dict[str, str], show_passages: bool) -> None:
    if show_passages:
        display_passages(answer["passages"])

    display_response(answer["text"])
    if answer["truncated"]:
        print("\nTruncated response (length limit reached).")

    display_metrics(answer["usage"]["prompt"], answer["usage"]["completion"])


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
        "--question", type=str,
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
    index = load_index(OUT_INDEX)

    if args.question is not None:
        ans = ask(index, args.question, args.answer_model)
        pretty_print(ans, args.show_passages)

    else:
        while True:
            try:
                console.print(
                    Panel(
                        "[dim]Ask a question about the content of your documents.\n"
                        "Write [bold]exit[/bold] or [bold]quit[/bold] to quit.[/dim]",
                        title="[bold white]RAG Assistant[/bold white]",
                        border_style="white",
                        padding=(0, 2),
                    )
                )
                your_question = Prompt.ask("[bold cyan]You[/bold cyan] ❯")

                if your_question.lower() in ("exit", "quit"):
                    break

                if your_question is None:
                    continue

                ans = ask(index, your_question, args.answer_model)
                pretty_print(ans, args.show_passages)

            except (KeyboardInterrupt, EOFError):
                print("\nEnd of the session")
                break
