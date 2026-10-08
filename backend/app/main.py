from pathlib import Path
from uuid import uuid4
import io
import json
import os
import re
import csv
import pandas as pd
from pptx import Presentation
from docx import Document

import fitz  # PyMuPDF
import pytesseract

from PIL import Image, ImageEnhance, ImageFilter

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware


# ============================================================
# APPLICATION
# ============================================================

app = FastAPI(
    title="ParseAnything API",
    description="Universal Document Ingestion System",
    version="0.8.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# TESSERACT CONFIGURATION
# ============================================================

TESSERACT_PATH = os.environ.get("TESSERACT_PATH", "tesseract")

if os.path.exists(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


# ============================================================
# PROJECT DIRECTORIES
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

UPLOAD_DIR = (
    PROJECT_ROOT
    / "data"
    / "uploads"
)

PROCESSED_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
)

UPLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

PROCESSED_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# FILE CONFIGURATION
# ============================================================

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".xlsx",
    ".xls",
    ".csv",
    ".pptx",
    ".docx",
}

MAX_FILE_SIZE = 20 * 1024 * 1024


# ============================================================
# OCR QUALITY CONFIGURATION
# ============================================================

MIN_TEXT_LENGTH = 2

MIN_BBOX_WIDTH = 3.0

MIN_BBOX_HEIGHT = 3.0

MIN_BBOX_AREA = 20.0

MIN_MEANINGFUL_CONFIDENCE = 0.25

LOW_CONFIDENCE_THRESHOLD = 0.70

MEDIUM_CONFIDENCE_THRESHOLD = 0.90


# ============================================================
# TABLE QUALITY CONFIGURATION
# ============================================================

MIN_TABLE_ROWS = 1

MIN_TABLE_COLUMNS = 2

TABLE_REVIEW_THRESHOLD = 0.70


# ============================================================
# CONFIDENCE CLASSIFICATION
# ============================================================

def classify_confidence(
    confidence: float,
) -> str:

    if confidence >= 0.90:
        return "high"

    if confidence >= 0.70:
        return "medium"

    return "low"


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_ocr_text(
    text: str,
) -> str:

    text = str(text)

    text = text.replace(
        "\n",
        " ",
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


# ============================================================
# SYMBOL-ONLY DETECTION
# ============================================================

def is_symbol_only(
    text: str,
) -> bool:

    if not text:
        return True

    return not bool(
        re.search(
            r"[A-Za-z0-9]",
            text,
        )
    )


# ============================================================
# MEANINGFUL OCR TEXT DETECTION
# ============================================================

def is_meaningful_text(
    text: str,
    confidence: float,
) -> bool:

    text = normalize_ocr_text(
        text
    )

    if not text:
        return False

    if len(text) < MIN_TEXT_LENGTH:

        if (
            len(text) == 1
            and re.match(
                r"[A-Za-z0-9]",
                text,
            )
            and confidence >= 0.70
        ):
            return True

        return False

    if is_symbol_only(text):
        return False

    alphanumeric_count = len(
        re.findall(
            r"[A-Za-z0-9]",
            text,
        )
    )

    if (
        confidence
        < MIN_MEANINGFUL_CONFIDENCE
    ):

        if alphanumeric_count < 2:
            return False

    punctuation_count = len(
        re.findall(
            r"[^A-Za-z0-9\s]",
            text,
        )
    )

    total_characters = len(
        text
    )

    if total_characters > 0:

        punctuation_ratio = (
            punctuation_count
            / total_characters
        )

        if (
            punctuation_ratio > 0.80
            and confidence < 0.70
        ):
            return False

    return True


# ============================================================
# BOUNDING BOX QUALITY CHECK
# ============================================================

def is_valid_bbox(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
) -> bool:

    width = x1 - x0

    height = y1 - y0

    area = width * height

    if width < MIN_BBOX_WIDTH:
        return False

    if height < MIN_BBOX_HEIGHT:
        return False

    if area < MIN_BBOX_AREA:
        return False

    return True


# ============================================================
# ROOT
# ============================================================

@app.get("/")
async def root():

    return {
        "message": (
            "ParseAnything API is running"
        ),
        "status": "success",
        "version": "0.8.0",
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get(
    "/api/health"
)
async def health_check():

    tesseract_available = os.path.exists(
        TESSERACT_PATH
    )

    return {
        "status": "healthy",
        "service": "ParseAnything API",
        "ocr": (
            "available"
            if tesseract_available
            else "unavailable"
        ),
    }


# ============================================================
# DOCUMENT UPLOAD
# ============================================================

@app.post(
    "/api/documents/upload"
)
async def upload_document(
    file: UploadFile = File(...)
):

    if not file.filename:

        raise HTTPException(
            status_code=400,
            detail=(
                "No filename provided."
            ),
        )

    original_name = Path(
        file.filename
    ).name

    extension = Path(
        original_name
    ).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:

        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type: "
                f"{extension}. "
                f"Supported types: "
                f"{', '.join(sorted(ALLOWED_EXTENSIONS))}"
            ),
        )

    file_data = await file.read()

    if len(file_data) > MAX_FILE_SIZE:

        raise HTTPException(
            status_code=413,
            detail=(
                "File is larger than "
                "the 20 MB limit."
            ),
        )

    document_id = (
        f"doc_{uuid4().hex[:12]}"
    )

    stored_filename = (
        f"{document_id}{extension}"
    )

    stored_path = (
        UPLOAD_DIR
        / stored_filename
    )

    try:

        stored_path.write_bytes(
            file_data
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to save uploaded "
                f"file: {str(error)}"
            ),
        )

    return {

        "status": "uploaded",

        "message": (
            "Document uploaded successfully."
        ),

        "document": {

            "id": document_id,

            "original_filename": (
                original_name
            ),

            "stored_filename": (
                stored_filename
            ),

            "file_type": extension,

            "mime_type": file.content_type,

            "size_bytes": len(
                file_data
            ),

            "size_kb": round(
                len(file_data) / 1024,
                2,
            ),

            "processing_status": (
                "uploaded"
            ),
        },
    }


# ============================================================
# NATIVE PDF TEXT EXTRACTION
# ============================================================

def extract_native_text(
    page,
):

    blocks = []

    page_blocks = page.get_text(
        "blocks"
    )

    page_blocks = sorted(
        page_blocks,
        key=lambda block: (
            round(block[1], 2),
            round(block[0], 2),
        ),
    )

    for block in page_blocks:

        x0, y0, x1, y1, text = (
            block[:5]
        )

        block_type = (
            block[6]
            if len(block) > 6
            else 0
        )

        cleaned_text = (
            text.strip()
        )

        if not cleaned_text:
            continue

        if block_type == 0:
            content_type = "text"
        else:
            content_type = "unknown"

        confidence = 0.98

        blocks.append(
            {
                "type": content_type,

                "content": cleaned_text,

                "bbox": [
                    round(x0, 2),
                    round(y0, 2),
                    round(x1, 2),
                    round(y1, 2),
                ],

                "confidence": confidence,

                "confidence_level": (
                    classify_confidence(
                        confidence
                    )
                ),

                "review_required": False,

                "extraction_method": (
                    "native_pdf"
                ),
            }
        )

    return blocks


# ============================================================
# OCR IMAGE PREPROCESSING
# ============================================================

def preprocess_ocr_image(
    image: Image.Image,
):

    image = image.convert(
        "L"
    )

    contrast = ImageEnhance.Contrast(
        image
    )

    image = contrast.enhance(
        1.6
    )

    image = image.filter(
        ImageFilter.SHARPEN
    )

    return image


# ============================================================
# OCR EXTRACTION
# ============================================================

def extract_ocr_text(
    page,
):

    zoom = 3.0

    matrix = fitz.Matrix(
        zoom,
        zoom,
    )

    pixmap = page.get_pixmap(
        matrix=matrix,
        alpha=False,
    )

    image_bytes = (
        pixmap.tobytes(
            "png"
        )
    )

    try:

        image = Image.open(
            io.BytesIO(
                image_bytes
            )
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to convert PDF "
                f"page to image: {str(error)}"
            ),
        )

    image = preprocess_ocr_image(
        image
    )

    try:

        ocr_data = (
            pytesseract.image_to_data(
                image,
                output_type=(
                    pytesseract.Output.DICT
                ),
                config=(
                    "--oem 3 --psm 3"
                ),
                lang="eng",
            )
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "OCR processing failed: "
                f"{str(error)}"
            ),
        )

    lines = {}

    number_of_words = len(
        ocr_data.get(
            "text",
            [],
        )
    )

    for index in range(
        number_of_words
    ):

        raw_text = (
            ocr_data[
                "text"
            ][index]
        )

        text = normalize_ocr_text(
            raw_text
        )

        if not text:
            continue

        try:

            confidence = float(
                ocr_data[
                    "conf"
                ][index]
            )

        except (
            ValueError,
            TypeError,
        ):

            confidence = 0.0

        if confidence < 0:
            confidence = 0.0

        if confidence > 100:
            confidence = 100.0

        normalized_confidence = (
            confidence / 100.0
        )

        x = int(
            ocr_data[
                "left"
            ][index]
        )

        y = int(
            ocr_data[
                "top"
            ][index]
        )

        width = int(
            ocr_data[
                "width"
            ][index]
        )

        height = int(
            ocr_data[
                "height"
            ][index]
        )

        x1 = x + width

        y1 = y + height

        if not is_valid_bbox(
            x,
            y,
            x1,
            y1,
        ):
            continue

        if not is_meaningful_text(
            text,
            normalized_confidence,
        ):
            continue

        page_number = (
            ocr_data[
                "page_num"
            ][index]
        )

        block_number = (
            ocr_data[
                "block_num"
            ][index]
        )

        paragraph_number = (
            ocr_data[
                "par_num"
            ][index]
        )

        line_number = (
            ocr_data[
                "line_num"
            ][index]
        )

        line_key = (
            page_number,
            block_number,
            paragraph_number,
            line_number,
        )

        if line_key not in lines:

            lines[line_key] = {

                "words": [],

                "confidences": [],

                "x0": x,

                "y0": y,

                "x1": x1,

                "y1": y1,
            }

        lines[
            line_key
        ][
            "words"
        ].append(
            text
        )

        lines[
            line_key
        ][
            "confidences"
        ].append(
            confidence
        )

        lines[
            line_key
        ][
            "x0"
        ] = min(
            lines[
                line_key
            ][
                "x0"
            ],
            x,
        )

        lines[
            line_key
        ][
            "y0"
        ] = min(
            lines[
                line_key
            ][
                "y0"
            ],
            y,
        )

        lines[
            line_key
        ][
            "x1"
        ] = max(
            lines[
                line_key
            ][
                "x1"
            ],
            x1,
        )

        lines[
            line_key
        ][
            "y1"
        ] = max(
            lines[
                line_key
            ][
                "y1"
            ],
            y1,
        )

    blocks = []

    for line in lines.values():

        content = normalize_ocr_text(
            " ".join(
                line["words"]
            )
        )

        if not content:
            continue

        if is_symbol_only(
            content
        ):
            continue

        if len(content) < MIN_TEXT_LENGTH:

            if not (
                len(content) == 1
                and re.match(
                    r"[A-Za-z0-9]",
                    content,
                )
            ):
                continue

        confidences = (
            line[
                "confidences"
            ]
        )

        if confidences:

            average_confidence = (
                sum(confidences)
                / len(confidences)
            )

        else:

            average_confidence = 0.0

        normalized_confidence = (
            average_confidence
            / 100.0
        )

        normalized_confidence = max(
            0.0,
            min(
                1.0,
                normalized_confidence,
            ),
        )

        confidence_level = (
            classify_confidence(
                normalized_confidence
            )
        )

        x0 = (
            line["x0"]
            / zoom
        )

        y0 = (
            line["y0"]
            / zoom
        )

        x1 = (
            line["x1"]
            / zoom
        )

        y1 = (
            line["y1"]
            / zoom
        )

        if not is_valid_bbox(
            x0,
            y0,
            x1,
            y1,
        ):
            continue

        blocks.append(
            {
                "type": "text",

                "content": content,

                "bbox": [
                    round(x0, 2),
                    round(y0, 2),
                    round(x1, 2),
                    round(y1, 2),
                ],

                "confidence": round(
                    normalized_confidence,
                    2,
                ),

                "confidence_level": (
                    confidence_level
                ),

                "review_required": (
                    normalized_confidence
                    < LOW_CONFIDENCE_THRESHOLD
                ),

                "extraction_method": (
                    "tesseract_ocr"
                ),
            }
        )

    blocks.sort(
        key=lambda block: (
            block[
                "bbox"
            ][1],
            block[
                "bbox"
            ][0],
        )
    )

    return blocks


# ============================================================
# TABLE CELL NORMALIZATION
# ============================================================

def normalize_table_cell(
    value,
):

    if value is None:
        return ""

    text = str(value)

    text = text.replace(
        "\n",
        " ",
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


# ============================================================
# TABLE DATA CLEANING
# ============================================================

def clean_table_data(
    table_data,
):

    cleaned_rows = []

    if not table_data:
        return cleaned_rows

    for row in table_data:

        if row is None:
            continue

        cleaned_row = [
            normalize_table_cell(
                cell
            )
            for cell in row
        ]

        if not any(
            cell != ""
            for cell in cleaned_row
        ):
            continue

        cleaned_rows.append(
            cleaned_row
        )

    return cleaned_rows


# ============================================================
# TABLE CONFIDENCE CALCULATION
# ============================================================

def calculate_table_confidence(
    table_rows,
    column_count,
):

    if not table_rows:
        return 0.0

    total_cells = (
        len(table_rows)
        * max(column_count, 1)
    )

    non_empty_cells = 0

    for row in table_rows:

        for cell in row:

            if normalize_table_cell(
                cell
            ):

                non_empty_cells += 1

    if total_cells == 0:
        return 0.0

    cell_fill_ratio = (
        non_empty_cells
        / total_cells
    )

    row_score = min(
        len(table_rows) / 2.0,
        1.0,
    )

    column_score = min(
        column_count / 2.0,
        1.0,
    )

    confidence = (
        0.50 * cell_fill_ratio
        + 0.25 * row_score
        + 0.25 * column_score
    )

    confidence = max(
        0.0,
        min(
            1.0,
            confidence,
        ),
    )

    return round(
        confidence,
        2,
    )


# ============================================================
# TABLE EXTRACTION
# ============================================================

def extract_tables(
    page,
    page_number,
):

    table_blocks = []

    try:

        table_finder = (
            page.find_tables()
        )

        tables = (
            table_finder.tables
        )

    except Exception:

        return table_blocks

    for table_index, table in enumerate(
        tables,
        start=1,
    ):

        try:

            extracted_data = (
                table.extract()
            )

        except Exception:

            continue

        cleaned_rows = (
            clean_table_data(
                extracted_data
            )
        )

        if not cleaned_rows:
            continue

        column_count = max(
            (
                len(row)
                for row in cleaned_rows
            ),
            default=0,
        )

        if (
            len(cleaned_rows)
            < MIN_TABLE_ROWS
        ):
            continue

        if (
            column_count
            < MIN_TABLE_COLUMNS
        ):
            continue

        # ----------------------------------------------------
        # First row is treated as the header.
        # ----------------------------------------------------

        headers = [
            normalize_table_cell(
                cell
            )
            for cell in cleaned_rows[
                0
            ]
        ]

        data_rows = []

        for row in cleaned_rows[
            1:
        ]:

            padded_row = list(
                row
            )

            if len(
                padded_row
            ) < column_count:

                padded_row.extend(
                    [""] *
                    (
                        column_count
                        - len(
                            padded_row
                        )
                    )
                )

            elif len(
                padded_row
            ) > column_count:

                padded_row = (
                    padded_row[
                        :column_count
                    ]
                )

            data_rows.append(
                padded_row
            )

        # ----------------------------------------------------
        # Bounding box
        # ----------------------------------------------------

        bbox = list(
            table.bbox
        )

        if len(bbox) != 4:
            continue

        x0 = float(
            bbox[0]
        )

        y0 = float(
            bbox[1]
        )

        x1 = float(
            bbox[2]
        )

        y1 = float(
            bbox[3]
        )

        if not is_valid_bbox(
            x0,
            y0,
            x1,
            y1,
        ):
            continue

        # ----------------------------------------------------
        # Confidence
        # ----------------------------------------------------

        confidence = (
            calculate_table_confidence(
                cleaned_rows,
                column_count,
            )
        )

        confidence_level = (
            classify_confidence(
                confidence
            )
        )

        review_required = (
            confidence
            < TABLE_REVIEW_THRESHOLD
        )

        # ----------------------------------------------------
        # Structured table block
        # ----------------------------------------------------

        table_block = {

            "type": "table",

            "content": {

                "headers": headers,

                "rows": data_rows,

                "row_count": len(
                    data_rows
                ),

                "column_count": (
                    column_count
                ),
            },

            "page": page_number,

            "reading_order": None,

            "bbox": [
                round(x0, 2),
                round(y0, 2),
                round(x1, 2),
                round(y1, 2),
            ],

            "confidence": confidence,

            "confidence_level": (
                confidence_level
            ),

            "review_required": (
                review_required
            ),

            "extraction_method": (
                "pymupdf_table_extractor"
            ),

            "table_index": (
                table_index
            ),
        }

        table_blocks.append(
            table_block
        )

    return table_blocks


# ============================================================
# REMOVE TEXT BLOCKS INSIDE TABLE REGIONS
# ============================================================

def point_inside_bbox(
    bbox,
    x,
    y,
):

    return (
        bbox[0] <= x <= bbox[2]
        and
        bbox[1] <= y <= bbox[3]
    )


def block_overlaps_table(
    block_bbox,
    table_bbox,
):

    bx0, by0, bx1, by1 = (
        block_bbox
    )

    tx0, ty0, tx1, ty1 = (
        table_bbox
    )

    overlap_x = (
        max(
            0,
            min(
                bx1,
                tx1,
            )
            - max(
                bx0,
                tx0,
            ),
        )
    )

    overlap_y = (
        max(
            0,
            min(
                by1,
                ty1,
            )
            - max(
                by0,
                ty0,
            ),
        )
    )

    overlap_area = (
        overlap_x
        * overlap_y
    )

    block_area = (
        max(
            0,
            bx1 - bx0,
        )
        *
        max(
            0,
            by1 - by0,
        )
    )

    if block_area <= 0:
        return False

    overlap_ratio = (
        overlap_area
        / block_area
    )

    return (
        overlap_ratio >= 0.50
    )


def remove_text_inside_tables(
    text_blocks,
    table_blocks,
):

    if not table_blocks:
        return text_blocks

    filtered_blocks = []

    for block in text_blocks:

        block_bbox = block[
            "bbox"
        ]

        inside_table = False

        for table in table_blocks:

            table_bbox = table[
                "bbox"
            ]

            if block_overlaps_table(
                block_bbox,
                table_bbox,
            ):

                inside_table = True

                break

        if not inside_table:

            filtered_blocks.append(
                block
            )

    return filtered_blocks


# ============================================================
# ASSIGN READING ORDER
# ============================================================

def assign_reading_order(
    blocks,
):

    sorted_blocks = sorted(
        blocks,
        key=lambda block: (
            block[
                "bbox"
            ][1],
            block[
                "bbox"
            ][0],
        ),
    )

    for index, block in enumerate(
        sorted_blocks,
        start=1,
    ):

        block[
            "reading_order"
        ] = index

    return sorted_blocks
    # ============================================================
# PPTX EXTRACTION
# ============================================================

def extract_pptx_content(file_path):
    """
    Extract text and tables from a PowerPoint presentation.
    Each slide is treated as a source page.
    """

    try:
        presentation = Presentation(file_path)

    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=f"Unable to read PPTX file: {str(error)}",
        )

    blocks = []
    block_counter = 1

    for slide_index, slide in enumerate(
        presentation.slides,
        start=1,
    ):
        slide_items = []

        for shape in slide.shapes:

            # ------------------------------------------------
            # TEXT
            # ------------------------------------------------
            if hasattr(shape, "text") and shape.text.strip():

                text_content = shape.text.strip()

                slide_items.append({
                    "type": "text",
                    "content": text_content,
                    "shape": shape,
                })

            # ------------------------------------------------
            # TABLE
            # ------------------------------------------------
            if getattr(shape, "has_table", False):

                table = shape.table

                headers = []

                for cell in table.rows[0].cells:
                    headers.append(
                        normalize_spreadsheet_cell(
                            cell.text
                        )
                    )

                rows = []

                for row in list(table.rows)[1:]:
                    rows.append([
                        normalize_spreadsheet_cell(
                            cell.text
                        )
                        for cell in row.cells
                    ])

                slide_items.append({
                    "type": "table",
                    "headers": headers,
                    "rows": rows,
                    "row_count": len(rows),
                    "column_count": len(headers),
                    "shape": shape,
                })

        # ----------------------------------------------------
        # CREATE STRUCTURED BLOCKS
        # ----------------------------------------------------

        for item in slide_items:

            if item["type"] == "text":

                confidence = 0.95

                blocks.append({
                    "id": f"block_{block_counter:04d}",
                    "type": "text",
                    "content": item["content"],
                    "page": slide_index,
                    "slide_number": slide_index,
                    "reading_order": block_counter,
                    "bbox": None,
                    "confidence": confidence,
                    "confidence_level": classify_confidence(
                        confidence
                    ),
                    "review_required": False,
                    "extraction_method": "python_pptx",
                })

                block_counter += 1

            elif item["type"] == "table":

                confidence = 0.95

                blocks.append({
                    "id": f"block_{block_counter:04d}",
                    "type": "table",
                    "content": {
                        "headers": item["headers"],
                        "rows": item["rows"],
                        "row_count": item["row_count"],
                        "column_count": item["column_count"],
                    },
                    "page": slide_index,
                    "slide_number": slide_index,
                    "reading_order": block_counter,
                    "bbox": None,
                    "confidence": confidence,
                    "confidence_level": classify_confidence(
                        confidence
                    ),
                    "review_required": False,
                    "extraction_method": "python_pptx",
                    "table_index": block_counter,
                })

                block_counter += 1

    return {
        "slide_count": len(
            presentation.slides
        ),
        "blocks": blocks,
    }
    # =========================================
# DOCX EXTRACTION
# =========================================

def extract_docx_content(file_path):
    """
    Extract text and tables from a Word document.
    Each paragraph and table is treated as a structured block.
    """

    try:
        document = Document(file_path)

    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=f"Unable to read DOCX file: {str(error)}"
        )

    blocks = []
    block_counter = 1
    reading_order = 1

    # Extract paragraphs
    for paragraph in document.paragraphs:

        text = paragraph.text.strip()

        if text:
            blocks.append({
                "id": f"block_{block_counter:04d}",
                "type": "text",
                "content": text,
                "page": 1,
                "reading_order": reading_order,
                "bbox": None,
                "confidence": 0.95,
                "confidence_level": classify_confidence(0.95),
                "review_required": False,
                "extraction_method": "python_docx"
            })

            block_counter += 1
            reading_order += 1

    # Extract tables
    for table_index, table in enumerate(document.tables, start=1):

        rows = []

        for row in table.rows:

            cells = []

            for cell in row.cells:
                cells.append(
                    cell.text.strip()
                )

            rows.append(cells)

        if not rows:
            continue

        headers = rows[0]
        data_rows = rows[1:]

        blocks.append({
            "id": f"block_{block_counter:04d}",
            "type": "table",
            "content": {
                "headers": headers,
                "rows": data_rows
            },
            "page": 1,
            "reading_order": reading_order,
            "bbox": None,
            "confidence": 0.95,
            "confidence_level": classify_confidence(0.95),
            "review_required": False,
            "extraction_method": "python_docx",
            "table_index": table_index,
            "row_count": len(data_rows),
            "column_count": len(headers)
        })

        block_counter += 1
        reading_order += 1

    return {
        "paragraph_count": len([
            p for p in document.paragraphs
            if p.text.strip()
        ]),
        "table_count": len(document.tables),
        "blocks": blocks
    }
# ============================================================
# EXCEL EXTRACTION
# ============================================================

def extract_excel_tables(file_path):
    """
    Extract Excel workbook sheets into structured table blocks.
    """

    try:
        excel_file = pd.ExcelFile(
            file_path,
            engine="openpyxl"
        )

    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=f"Unable to read Excel file: {str(error)}",
        )

    tables = []

    for sheet_index, sheet_name in enumerate(
        excel_file.sheet_names
    ):
        dataframe = pd.read_excel(
            file_path,
            sheet_name=sheet_name,
            dtype=str,
            keep_default_na=False,
            engine="openpyxl",
        )

        headers = [
            normalize_spreadsheet_cell(column)
            for column in dataframe.columns
        ]

        rows = []

        for row in dataframe.itertuples(
            index=False,
            name=None,
        ):
            cleaned_row = [
                normalize_spreadsheet_cell(value)
                for value in row
            ]

            rows.append(cleaned_row)

        row_count = len(rows)
        column_count = len(headers)

        total_cells = max(
            row_count * max(column_count, 1),
            1,
        )

        non_empty_cells = sum(
            1
            for row in rows
            for cell in row
            if cell != ""
        )

        cell_fill_ratio = (
            non_empty_cells / total_cells
        )

        confidence = round(
            max(
                0.90,
                min(0.99, cell_fill_ratio),
            ),
            2,
        )

        tables.append({
            "sheet_index": sheet_index + 1,
            "sheet_name": sheet_name,
            "headers": headers,
            "rows": rows,
            "row_count": row_count,
            "column_count": column_count,
            "confidence": confidence,
        })

    return tables
# ============================================================
# CSV EXTRACTION
# ============================================================

def normalize_spreadsheet_cell(value):
    """Convert a CSV cell value into clean text."""
    if value is None:
        return ""

    if pd.isna(value):
        return ""

    return str(value).strip()


def extract_csv_tables(file_path):
    """
    Extract a CSV file into a structured table.
    """

    try:
        dataframe = pd.read_csv(
            file_path,
            dtype=str,
            keep_default_na=False,
        )

    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=f"Unable to read CSV file: {str(error)}",
        )

    headers = [
        normalize_spreadsheet_cell(column)
        for column in dataframe.columns
    ]

    rows = []

    for row in dataframe.itertuples(
        index=False,
        name=None,
    ):
        cleaned_row = [
            normalize_spreadsheet_cell(value)
            for value in row
        ]

        rows.append(cleaned_row)

    column_count = len(headers)
    row_count = len(rows)

    total_cells = max(
        row_count * max(column_count, 1),
        1,
    )

    non_empty_cells = sum(
        1
        for row in rows
        for cell in row
        if cell != ""
    )

    cell_fill_ratio = (
        non_empty_cells / total_cells
    )

    confidence = round(
        max(
            0.90,
            min(0.99, cell_fill_ratio),
        ),
        2,
    )

    return {
        "headers": headers,
        "rows": rows,
        "row_count": row_count,
        "column_count": column_count,
        "confidence": confidence,
    }
# ============================================================
# EXCEL DOCUMENT PROCESSING
# ============================================================
# ============================================================
# PPTX DOCUMENT PROCESSING
# ============================================================

def process_pptx_document(
    document_id,
    document_path,
):
    """
    Process a PowerPoint presentation into
    ParseAnything structured output.
    """

    extracted = extract_pptx_content(
        document_path
    )

    blocks = extracted["blocks"]

    high_count = sum(
        1
        for block in blocks
        if block["confidence_level"] == "high"
    )

    medium_count = sum(
        1
        for block in blocks
        if block["confidence_level"] == "medium"
    )

    low_count = sum(
        1
        for block in blocks
        if block["confidence_level"] == "low"
    )

    review_count = sum(
        1
        for block in blocks
        if block["review_required"]
    )

    table_count = sum(
        1
        for block in blocks
        if block["type"] == "table"
    )

    text_count = sum(
        1
        for block in blocks
        if block["type"] == "text"
    )

    slides = []

    for slide_number in range(
        1,
        extracted["slide_count"] + 1,
    ):
        slide_blocks = [
            block
            for block in blocks
            if block["slide_number"] == slide_number
        ]

        slides.append({
            "slide_number": slide_number,
            "blocks_extracted": len(slide_blocks),
            "tables_detected": sum(
                1
                for block in slide_blocks
                if block["type"] == "table"
            ),
        })

    result = {
        "document_id": document_id,
        "filename": document_path.name,
        "file_type": "pptx",

        "total_slides": extracted["slide_count"],
        "total_pages": extracted["slide_count"],

        "total_blocks": len(blocks),
        "total_text_blocks": text_count,
        "total_table_blocks": table_count,
        "total_tables": table_count,

        "processing_status": "completed",

        "pipeline": [
            "document_detection",
            "pptx_slide_detection",
            "pptx_text_extraction",
            "pptx_table_extraction",
            "structured_block_generation",
            "confidence_scoring",
            "source_traceability",
        ],

        "confidence_summary": {
            "high": high_count,
            "medium": medium_count,
            "low": low_count,
            "review_required": review_count,
        },

        "slides": slides,

        "pages": [
            {
                "page": slide["slide_number"],
                "status": "structured",
                "extraction_method": "python_pptx",
                "blocks_extracted": slide["blocks_extracted"],
                "tables_detected": slide["tables_detected"],
            }
            for slide in slides
        ],

        "blocks": blocks,
    }

    result_path = (
        PROCESSED_DIR
        / f"{document_id}.json"
    )

    try:
        result_path.write_text(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to save processed "
                f"result: {str(error)}"
            ),
        )

    return result

    # =========================================
# DOCX DOCUMENT PROCESSING
# =========================================

def process_docx_document(
    document_id,
    document_path,
):
    """
    Process a Word document into ParseAnything's
    structured result format.
    """

    extracted = extract_docx_content(
        document_path
    )

    blocks = extracted["blocks"]

    total_text_blocks = sum(
        1
        for block in blocks
        if block["type"] == "text"
    )

    total_table_blocks = sum(
        1
        for block in blocks
        if block["type"] == "table"
    )

    high_confidence = sum(
        1
        for block in blocks
        if block["confidence"] >= MEDIUM_CONFIDENCE_THRESHOLD
    )

    medium_confidence = sum(
        1
        for block in blocks
        if (
            block["confidence"] >= LOW_CONFIDENCE_THRESHOLD
            and block["confidence"] < MEDIUM_CONFIDENCE_THRESHOLD
        )
    )

    low_confidence = sum(
        1
        for block in blocks
        if block["confidence"] < LOW_CONFIDENCE_THRESHOLD
    )

    review_required = sum(
        1
        for block in blocks
        if block["review_required"]
    )

    result = {
        "document_id": document_id,
        "file_type": "docx",

        "total_pages": 1,
        "total_blocks": len(blocks),
        "total_text_blocks": total_text_blocks,
        "total_table_blocks": total_table_blocks,
        "total_tables": extracted["table_count"],

        "processing_status": "completed",

        "pipeline": [
            "document_detection",
            "docx_paragraph_extraction",
            "docx_table_extraction",
            "structured_block_generation",
            "confidence_scoring",
            "source_traceability"
        ],

        "confidence_summary": {
            "high": high_confidence,
            "medium": medium_confidence,
            "low": low_confidence,
            "review_required": review_required
        },

        "pages": [
            {
                "page": 1,
                "status": "structured",
                "extraction_method": "python_docx",
                "block_count": len(blocks),
                "table_count": total_table_blocks
            }
        ],

        "blocks": blocks
    }

    result_path = (
    PROCESSED_DIR
    / f"{document_id}.json"
)

    try:
        with open(
            result_path,
            "w",
            encoding="utf-8"
        ) as result_file:
            json.dump(
                result,
                result_file,
                indent=2,
                ensure_ascii=False
            )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to save processed "
                f"result: {str(error)}"
            )
        )

    return result

def process_excel_document(
    document_id,
    document_path,
):
    """
    Process an Excel workbook into ParseAnything's
    structured result format.
    """

    tables = extract_excel_tables(
        document_path
    )

    blocks = []
    pages = []

    for table_index, table in enumerate(
        tables,
        start=1,
    ):
        confidence = table["confidence"]

        confidence_level = classify_confidence(
            confidence
        )

        review_required = (
            confidence < TABLE_REVIEW_THRESHOLD
        )

        table_block = {
            "id": f"block_{table_index:04d}",
            "type": "table",
            "content": {
                "headers": table["headers"],
                "rows": table["rows"],
                "row_count": table["row_count"],
                "column_count": table["column_count"],
                "sheet_name": table["sheet_name"],
            },
            "page": table["sheet_index"],
            "reading_order": table_index,
            "bbox": None,
            "confidence": confidence,
            "confidence_level": confidence_level,
            "review_required": review_required,
            "extraction_method": "pandas_excel",
            "table_index": table_index,
            "sheet_name": table["sheet_name"],
            "sheet_index": table["sheet_index"],
        }

        blocks.append(table_block)

        pages.append({
            "page": table["sheet_index"],
            "sheet_name": table["sheet_name"],
            "status": "structured_table",
            "extraction_method": "pandas_excel",
            "blocks_extracted": 1,
            "tables_detected": 1,
        })

    high_count = sum(
        1
        for block in blocks
        if block["confidence_level"] == "high"
    )

    medium_count = sum(
        1
        for block in blocks
        if block["confidence_level"] == "medium"
    )

    low_count = sum(
        1
        for block in blocks
        if block["confidence_level"] == "low"
    )

    review_count = sum(
        1
        for block in blocks
        if block["review_required"]
    )

    result = {
        "document_id": document_id,
        "filename": document_path.name,
        "file_type": "xlsx",

        "total_sheets": len(tables),
        "total_pages": len(tables),

        "total_blocks": len(blocks),
        "total_text_blocks": 0,
        "total_table_blocks": len(blocks),
        "total_tables": len(blocks),

        "processing_status": "completed",

        "pipeline": [
            "document_detection",
            "excel_sheet_detection",
            "excel_table_extraction",
            "structured_block_generation",
            "confidence_scoring",
            "source_traceability",
        ],

        "confidence_summary": {
            "high": high_count,
            "medium": medium_count,
            "low": low_count,
            "review_required": review_count,
        },

        "sheets": [
            {
                "sheet_index": table["sheet_index"],
                "sheet_name": table["sheet_name"],
                "row_count": table["row_count"],
                "column_count": table["column_count"],
            }
            for table in tables
        ],

        "pages": pages,

        "blocks": blocks,
    }

    result_path = (
        PROCESSED_DIR
        / f"{document_id}.json"
    )

    try:
        result_path.write_text(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to save processed "
                f"result: {str(error)}"
            ),
        )

    return result

def process_csv_document(
    document_id,
    document_path,
):
    """
    Process a CSV file into ParseAnything's
    structured result format.
    """

    table = extract_csv_tables(
        document_path
    )

    confidence = table["confidence"]

    confidence_level = classify_confidence(
        confidence
    )

    review_required = (
        confidence < TABLE_REVIEW_THRESHOLD
    )

    table_block = {
        "id": "block_0001",
        "type": "table",
        "content": {
            "headers": table["headers"],
            "rows": table["rows"],
            "row_count": table["row_count"],
            "column_count": table["column_count"],
        },
        "page": 1,
        "reading_order": 1,
        "bbox": None,
        "confidence": confidence,
        "confidence_level": confidence_level,
        "review_required": review_required,
        "extraction_method": "pandas_csv",
        "table_index": 1,
    }

    result = {
        "document_id": document_id,
        "filename": document_path.name,
        "file_type": "csv",
        "total_pages": 1,
        "total_blocks": 1,
        "total_text_blocks": 0,
        "total_table_blocks": 1,
        "total_tables": 1,
        "processing_status": "completed",

        "pipeline": [
            "document_detection",
            "csv_extraction",
            "structured_block_generation",
            "confidence_scoring",
            "source_traceability",
        ],

        "quality_filters": {
            "minimum_table_rows": MIN_TABLE_ROWS,
            "minimum_table_columns": MIN_TABLE_COLUMNS,
            "table_review_threshold": TABLE_REVIEW_THRESHOLD,
        },

        "confidence_summary": {
            "high": (
                1
                if confidence_level == "high"
                else 0
            ),
            "medium": (
                1
                if confidence_level == "medium"
                else 0
            ),
            "low": (
                1
                if confidence_level == "low"
                else 0
            ),
            "review_required": (
                1
                if review_required
                else 0
            ),
        },

        "pages": [
            {
                "page": 1,
                "status": "structured_table",
                "extraction_method": "pandas_csv",
                "native_character_count": sum(
                    len(cell)
                    for row in table["rows"]
                    for cell in row
                ),
                "blocks_extracted": 1,
                "tables_detected": 1,
            }
        ],

        "blocks": [
            table_block
        ],
    }

    result_path = (
        PROCESSED_DIR
        / f"{document_id}.json"
    )

    try:
        result_path.write_text(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to save processed "
                f"result: {str(error)}"
            ),
        )

    return result
# ============================================================
# PDF PROCESSING
# ============================================================

@app.post(
    "/api/documents/{document_id}/process"
)
async def process_document(
    document_id: str,
):

    matching_files = list(
        UPLOAD_DIR.glob(
            f"{document_id}.*"
        )
    )

    if not matching_files:

        raise HTTPException(
            status_code=404,
            detail=(
                "Document not found."
            ),
        )

    document_path = (
        matching_files[0]
    )

    file_extension = document_path.suffix.lower()

    if file_extension == ".pptx":
        return process_pptx_document(
            document_id,
            document_path,
        )

    if file_extension == ".docx":
        return process_docx_document(
            document_id,
            document_path,
        )

    if file_extension == ".xlsx":
        return process_excel_document(
            document_id,
            document_path,
        )

    if file_extension == ".csv":
        return process_csv_document(
            document_id,
            document_path,
        )

    if file_extension != ".pdf":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Processing for {file_extension} "
                "files is not implemented yet."
            ),
        )

    try:

        pdf_document = fitz.open(
            document_path
        )

    except Exception as error:

        raise HTTPException(
            status_code=400,
            detail=(
                "Unable to open PDF: "
                f"{str(error)}"
            ),
        )

    total_pages = len(
        pdf_document
    )

    all_blocks = []

    block_counter = 1

    page_processing = []

    total_tables = 0

    for page_index in range(
        total_pages
    ):

        page = pdf_document[
            page_index
        ]

        page_number = (
            page_index + 1
        )

        # ----------------------------------------------------
        # 1. Native PDF text
        # ----------------------------------------------------

        native_blocks = (
            extract_native_text(
                page
            )
        )

        native_character_count = sum(
            len(
                block[
                    "content"
                ]
            )
            for block in native_blocks
        )

        # ----------------------------------------------------
        # 2. Table detection
        # ----------------------------------------------------

        table_blocks = (
            extract_tables(
                page,
                page_number,
            )
        )

        total_tables += len(
            table_blocks
        )

        # ----------------------------------------------------
        # 3. Select native text or OCR
        # ----------------------------------------------------

        if (
            native_character_count
            >= 20
        ):

            selected_text_blocks = (
                native_blocks
            )

            extraction_method = (
                "native_pdf"
            )

            page_status = (
                "text_detected"
            )

        else:

            selected_text_blocks = (
                extract_ocr_text(
                    page
                )
            )

            extraction_method = (
                "tesseract_ocr"
            )

            page_status = (
                "scanned_page"
            )

        # ----------------------------------------------------
        # 4. Remove text blocks that belong to tables
        # ----------------------------------------------------

        selected_text_blocks = (
            remove_text_inside_tables(
                selected_text_blocks,
                table_blocks,
            )
        )

        # ----------------------------------------------------
        # 5. Combine text + tables
        # ----------------------------------------------------

        page_blocks = []

        page_blocks.extend(
            selected_text_blocks
        )

        page_blocks.extend(
            table_blocks
        )

        # ----------------------------------------------------
        # 6. Reading order
        # ----------------------------------------------------

        page_blocks = (
            assign_reading_order(
                page_blocks
            )
        )

        # ----------------------------------------------------
        # 7. Add IDs
        # ----------------------------------------------------

        for block in page_blocks:

            structured_block = {

                "id": (
                    f"block_"
                    f"{block_counter:04d}"
                ),

                "type": block[
                    "type"
                ],

                "content": block[
                    "content"
                ],

               "page": page_number,

                "reading_order": block[
                    "reading_order"
                ],

                "bbox": block[
                    "bbox"
                ],

                "confidence": round(
                    float(
                        block[
                            "confidence"
                        ]
                    ),
                    2,
                ),

                "confidence_level": (
                    block[
                        "confidence_level"
                    ]
                ),

                "review_required": (
                    block[
                        "review_required"
                    ]
                ),

                "extraction_method": (
                    block[
                        "extraction_method"
                    ]
                ),
            }

            if block[
                "type"
            ] == "table":

                structured_block[
                    "table_index"
                ] = block[
                    "table_index"
                ]

            all_blocks.append(
                structured_block
            )

            block_counter += 1

        page_processing.append(
            {

                "page": page_number,

                "status": page_status,

                "extraction_method": (
                    extraction_method
                ),

                "native_character_count": (
                    native_character_count
                ),

                "blocks_extracted": (
                    len(
                        page_blocks
                    )
                ),

                "tables_detected": (
                    len(
                        table_blocks
                    )
                ),
            }
        )

    pdf_document.close()

    # ========================================================
    # CONFIDENCE SUMMARY
    # ========================================================

    high_confidence_blocks = sum(
        1
        for block in all_blocks
        if block[
            "confidence_level"
        ] == "high"
    )

    medium_confidence_blocks = sum(
        1
        for block in all_blocks
        if block[
            "confidence_level"
        ] == "medium"
    )

    low_confidence_blocks = sum(
        1
        for block in all_blocks
        if block[
            "confidence_level"
        ] == "low"
    )

    review_required_blocks = sum(
        1
        for block in all_blocks
        if block[
            "review_required"
        ]
    )

    text_blocks_count = sum(
        1
        for block in all_blocks
        if block[
            "type"
        ] == "text"
    )

    table_blocks_count = sum(
        1
        for block in all_blocks
        if block[
            "type"
        ] == "table"
    )

    # ========================================================
    # FINAL RESULT
    # ========================================================

    result = {

        "document_id": (
            document_id
        ),

        "filename": (
            document_path.name
        ),

        "file_type": "pdf",

        "total_pages": (
            total_pages
        ),

        "total_blocks": (
            len(all_blocks)
        ),

        "total_text_blocks": (
            text_blocks_count
        ),

        "total_table_blocks": (
            table_blocks_count
        ),

        "total_tables": (
            total_tables
        ),

        "processing_status": (
            "completed"
        ),

        "pipeline": [

            "document_detection",

            "native_text_extraction",

            "scanned_page_detection",

            "ocr_routing",

            "ocr_quality_filtering",

            "table_detection",

            "table_extraction",

            "structured_block_generation",

            "reading_order_reconstruction",

            "confidence_scoring",

            "source_traceability",
        ],

        "quality_filters": {

            "minimum_text_length": (
                MIN_TEXT_LENGTH
            ),

            "minimum_bbox_width": (
                MIN_BBOX_WIDTH
            ),

            "minimum_bbox_height": (
                MIN_BBOX_HEIGHT
            ),

            "minimum_bbox_area": (
                MIN_BBOX_AREA
            ),

            "minimum_meaningful_confidence": (
                MIN_MEANINGFUL_CONFIDENCE
            ),

            "low_confidence_threshold": (
                LOW_CONFIDENCE_THRESHOLD
            ),

            "medium_confidence_threshold": (
                MEDIUM_CONFIDENCE_THRESHOLD
            ),

            "minimum_table_rows": (
                MIN_TABLE_ROWS
            ),

            "minimum_table_columns": (
                MIN_TABLE_COLUMNS
            ),

            "table_review_threshold": (
                TABLE_REVIEW_THRESHOLD
            ),
        },

        "confidence_summary": {

            "high": (
                high_confidence_blocks
            ),

            "medium": (
                medium_confidence_blocks
            ),

            "low": (
                low_confidence_blocks
            ),

            "review_required": (
                review_required_blocks
            ),
        },

        "pages": (
            page_processing
        ),

        "blocks": (
            all_blocks
        ),
    }

    # ========================================================
    # SAVE RESULT
    # ========================================================

    result_path = (
        PROCESSED_DIR
        / f"{document_id}.json"
    )

    try:

        result_path.write_text(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to save processed "
                f"result: {str(error)}"
            ),
        )

    return result


# ============================================================
# GET PROCESSED RESULT
# ============================================================

@app.get(
    "/api/documents/{document_id}/result"
)
async def get_document_result(
    document_id: str,
):

    result_path = (
        PROCESSED_DIR
        / f"{document_id}.json"
    )

    if not result_path.exists():

        raise HTTPException(
            status_code=404,
            detail=(
                "Processed result not found."
            ),
        )

    try:

        result = json.loads(
            result_path.read_text(
                encoding="utf-8"
            )
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to read processed "
                f"result: {str(error)}"
            ),
        )

    return result