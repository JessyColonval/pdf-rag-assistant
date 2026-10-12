# pdf-rag-assistant

A Retrieval-Augmented Generation (RAG) assistant that answers questions about application documentation delivered
as PDF files, including the information that only appears in screenshots, diagrams and charts.

## Usage

### Prerequisites

- Python 3.10+
- An [OpenRouter](https://openrouter.ai) API key in a `.env` file:
```
OPENROUTER_API_KEY=...
```
- Dependencies:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

The first run downloads the models used locally (Docling's layout models and the embedding model), so it needs an
internet connection and can take a while.

## Quick start

```bash
python main.py \
  --pdfs <folder path> \
  --out_data <folder path> \
  --out_idx <folder path> \
  --vision_model <vision-model-id> \
  --answer_model <answer-model-id> \
  --question "How do I translate test steps into keywords?"
```

A single run reads the PDFs, extracts their content, describes the figures with the vision model, builds the search
index and answers the question with the answer model. The answer is printed with the sources it cites (document,
page and figure images) and the number of tokens consumed.

| Argument | Required | Description |
|---|---|---|
| `--pdfs` | yes | Path to the PDF files to extract data from. |
| `--out_data` | yes | Output path where the extracted PDF data is saved (one JSON file per PDF, plus the figure images). |
| `--out_idx` | yes | Output path where the information index is stored (passages and embeddings). |
| `--vision_model` | yes | OpenRouter ID of a model that supports image input. Used to describe the figures. |
| `--answer_model` | yes | OpenRouter ID of the model that answers the question. |
| `--question` | yes | The question to ask. |
| `--force` | no | Re-describe even the figures that have already been described. |
| `--show_passages` | no | Print the passages that were sent to the answer model, before the answer. |
| `--limit N` | no | Maximum number of API calls for the figure descriptions. |

Model IDs are OpenRouter IDs in the form `provider/model-name`. The vision model and the answer model can be
different: the vision model is only used to describe figures, the answer model only sees text.


### What gets written

```
<out_data>/
  <pdf name>.json            ordered blocks of each PDF, with figure descriptions
  images/<pdf name>/*.png    one image per figure
  cache/descriptions.json    cache of the vision model's replies
<out_idx>/
  passages.jsonl             one searchable passage per line
  embeddings.npy             one embedding per passage
```

### Usage example
```bash
python -m src.main \
  --pdfs ./data/pdfs/ \
  --vision_model openai/gpt-4.1-mini \
  --answer_model openai/gpt-6-luna \
  --out_data ./data/extraction \
  --out_idx ./data/indexing \
  --question "Qu'est-ce qu'une donnée de conception ?" \
  --show_passages
```


## Reading the PDFs

PDFs are parsed with [Docling](https://github.com/docling-project/docling), which analyses the page layout and
returns the content in reading order as typed blocks: headings, paragraphs, list items (with a flag telling numbered
steps from bullets), tables (converted to markdown) and figures. Every block keeps its page number. `pypdf` reads the
PDF's modification date. Each figure is exported as a PNG image.

## Making figures searchable

Search only works on text, so each figure is described once by a vision-capable LLM, called through
[OpenRouter](https://openrouter.ai). The model receives the image (downscaled), the text that precedes it and its
caption, classifies it (screenshot, diagram, chart, table, decorative) and returns a structured description: visible
labels, structure (links between boxes in a diagram), a short summary and keywords. Decorative images are discarded.
From then on, the answering LLM never needs vision.

## Passages

Blocks are grouped into **passages**, the units that search returns:

- one passage per heading, prefixed with its title path (document > section);
- numbered procedures are never split, and their step numbers are kept;
- each figure is inserted at its exact position as a short text (summary, keywords); the image path stays in the
  passage metadata so the image can be shown with the answer;
- tables of contents are dropped, and very small passages are merged into the previous one to keep their context.

## Retrieval

Retrieval is hybrid, combining two complementary methods:

- **BM25** (`rank-bm25`) matches exact words such as button names or error codes[^bm25];
- **dense embeddings** (`sentence-transformers`, local multilingual model `intfloat/multilingual-e5-small`) match
  meaning, so a reworded question still finds the right passage. Vectors are L2-normalised, so a dot product gives
  the cosine similarity.

Each method returns its 20 best passages. The two rankings are merged with Reciprocal Rank Fusion, which scores a
passage `1 / (60 + rank)` in each list and sums the scores, so a passage ranked well by both methods comes first[^rrf].
The top 6 are kept.

[^bm25]: A. Trotman, A. Puurula and B. Burgess, "Improvements to BM25 and language models examined", *Proceedings of the 19th Australasian Document Computing Symposium*, 2014, pp.58-65. DOI: [10.1145/2682862.2682863](https://doi.org/10.1145/2682862.2682863).
[^rrf]: G. V. Cormack, C. L. A. Clarke and S. Büttcher, "Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods", *Proc. 32nd ACM SIGIR Conf. (SIGIR '09)*, 2009, pp. 758–759. DOI: [10.1145/1571941.1572114](https://doi.org/10.1145/1571941.1572114)


## Answer generation

The 6 passages are numbered `[1]` to `[6]` and inserted, with their document, page and section, into a prompt along
with the question. An LLM called through OpenRouter (OpenAI-compatible API, temperature 0) must answer using only
these passages, cite them by number, and say so when the information is missing. Cited numbers are mapped back to
documents, pages and figure images. Prompts are plain markdown files, so they can be edited without touching the
code.

## Storage

Everything is stored as plain files on disk. There is no database and no vector store: at this scale, the
embeddings fit in memory and are searched with a single matrix product.

- one JSON file per PDF: its ordered blocks, enriched with figure descriptions;
- one PNG file per figure;
- `passages.jsonl`: one passage per line (text, document, page, title path, figure references);
- `embeddings.npy`: a NumPy array whose row *i* is the embedding of passage *i* of `passages.jsonl`;
- a JSON cache of figure descriptions, keyed by a hash of (image, model, prompt), so no figure is described twice;
- the BM25 index is rebuilt in memory each time the passages are loaded, which takes a fraction of a second.
