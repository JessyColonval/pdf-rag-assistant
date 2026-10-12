# pdf-rag-assistant

A Retrieval-Augmented Generation (RAG) assistant that answers questions about application documentation delivered
as PDF files, including the information that only appears in screenshots, diagrams and charts.

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

- **BM25** (`rank-bm25`) matches exact words such as button names or error codes;
- **dense embeddings** (`sentence-transformers`, local multilingual model `intfloat/multilingual-e5-small`) match
  meaning, so a reworded question still finds the right passage. Vectors are L2-normalised, so a dot product gives
  the cosine similarity.

Each method returns its 20 best passages. The two rankings are merged with Reciprocal Rank Fusion, which scores a
passage `1 / (60 + rank)` in each list and sums the scores, so a passage ranked well by both methods comes first.
The top 6 are kept.

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
