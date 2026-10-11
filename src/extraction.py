"""
Written by Jessy Colonval

Contains the function that extracts data from a PDF in order to format its content as a list of
blocks.
"""
from typing import Optional, Dict

from pathlib import Path
from pypdf import PdfReader

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import ListItem, PictureItem, SectionHeaderItem, TableItem, TextItem


def make_converter() -> DocumentConverter:
    opts = PdfPipelineOptions()
    opts.generate_picture_images = True
    opts.images_scale = 2.0
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
    )

def pdf_date(pdf_path: Path) -> Optional[str]:
    try:
        d = PdfReader(str(pdf_path)).metadata.modification_date
        if d is not None:
            return d.date().isoformat()
        return None
    except Exception:
        return None

def extract(
    pdf_path: Path, out_dir: Path, converter: DocumentConverter
) -> Dict[str, int|str|bool]:
    """
    Parameters
    ----------
    pdf_path: Path
        The path to the PDF file from which data is to be extracted.
    out_dir: Path
        The output folder where the images will be saved.
    converter: DocumentConverter
        The model used for data extraction.
        It is passed as a parameter so the model is initialized only once.

    Returns
    -------
        Dict[str, int|str|bool]
    """
    doc = converter.convert(str(pdf_path)).document
    img_dir = out_dir / "images" / pdf_path.stem
    img_dir.mkdir(parents=True, exist_ok=True)

    blocks = []
    n_fig = 0

    # Scan through the document in the order it is meant to be read and build the blocks according
    # to the type of item encountered.
    for item, _level in doc.iterate_items():
        page = None
        if item.prov is not None:
            page = item.prov[0].page_no

        if isinstance(item, SectionHeaderItem):
            blocks.append(
                {"type": "heading", "level": item.level, "text": item.text, "page": page}
            )

        elif isinstance(item, ListItem):
            blocks.append(
                {"type": "list_item", "numbered": item.enumerated, "text": item.text, "page": page}
            )

        elif isinstance(item, TableItem):
            blocks.append(
                {"type": "table", "text": item.export_to_markdown(doc=doc), "page": page}
            )

        elif isinstance(item, PictureItem):
            n_fig += 1
            fig_id = f"{pdf_path.stem}_fig{n_fig}"
            image_path = None
            img = item.get_image(doc)
            if img is not None:
                image_path = img_dir / f"{fig_id}.png"
                img.save(image_path)
            blocks.append(
                {"type": "figure", "id": fig_id, "caption": item.caption_text(doc),
                 "image_path": str(image_path) if image_path else None, "page": page}
            )

        elif isinstance(item, TextItem):
            blocks.append(
                {"type": "text", "text": item.text, "page": page}
            )

    return {"doc_id": pdf_path.stem, "pdf_date": pdf_date(pdf_path), "blocks": blocks}
