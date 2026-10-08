# ParseAnything

### Universal Document Ingestion System

ParseAnything is an intelligent document ingestion system designed to extract, structure, and verify information from different types of documents through a unified processing pipeline.

It supports documents such as PDFs, scanned PDFs, DOCX, PPTX, XLSX, XLS, CSV, and images.

---

## Overview

Traditional document extraction systems often treat an entire document as plain text.

ParseAnything follows an **element-aware extraction approach**.

The system identifies different content types such as:

- Text
- Tables
- Scanned content
- OCR content
- Structured spreadsheet data
- Presentation content

Each content type is routed to an appropriate extraction method.

The extracted information is then converted into structured blocks with confidence scores and source traceability.

---

## Processing Pipeline

```text
Upload
   ↓
Document Detection
   ↓
Content Detection
   ↓
Element-Aware Routing
   ↓
Specialized Extraction
   ↓
Reading Order Reconstruction
   ↓
Structured Output
   ↓
Confidence Scoring
   ↓
Source Traceability
   ↓
JSON / Markdown
Key Features
- Multi-format document ingestion
- Native PDF text extraction
- OCR for scanned documents
- Table extraction
- DOCX paragraph and table extraction
- PPTX slide and table extraction
- XLSX spreadsheet extraction
- CSV table extraction
- Confidence scoring
- Low-confidence review flags
- Page / slide / sheet traceability
- Bounding-box information for supported document elements
- Structured JSON output
- Markdown-ready structured content
- Simple web-based interface
Supported Formats
Format	Processing Method
PDF	PyMuPDF
Scanned PDF	Tesseract OCR
DOCX	python-docx
PPTX	python-pptx
XLSX	pandas + openpyxl
XLS	pandas + xlrd
CSV	pandas
PNG / JPG	OCR pipeline


Confidence Classification
ParseAnything assigns confidence levels to extracted content.
Confidence	Classification
≥ 90%	High
70–89%	Medium
< 70%	Low / Review Required


The system is designed to flag uncertain content instead of silently guessing.
Source Traceability
Each extracted block can be associated with its source information, including:
- Page or slide number
- Bounding box where available
- Extraction method
- Confidence score
- Review status
This allows users to verify extracted information against the original document.
The goal is 100% traceability, meaning extracted blocks can be traced back to their source location and extraction metadata. It does not claim 100% extraction accuracy.

Technology Stack
Backend
- Python
- FastAPI
- Uvicorn
- PyMuPDF
- Tesseract OCR
- pandas
- openpyxl
- xlrd
- python-docx
- python-pptx
Frontend
- React
- TypeScript
- Vite
- CSS
Project Architecture
ParseAnything/
│
├── backend/
│   ├── app/
│   │   └── main.py
│   ├── data/
│   │   ├── uploads/
│   │   └── processed/
│   └── .venv/
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── App.css
│   │   └── index.css
│   ├── package.json
│   └── vite.config.ts
│
├── data/
│   └── processed/
│
├── .gitignore
└── README.md

Setup
1. Clone the Repository
git clone https://github.com/srivarthini09/ParseAnything.git
cd ParseAnything

2. Backend Setup
cd backend
python -m venv .venv

Activate the virtual environment on Windows:
.\.venv\Scripts\Activate.ps1

Install dependencies:
pip install fastapi "uvicorn[standard]" python-multipart pandas openpyxl xlrd python-pptx python-docx

Start the backend:
python -m uvicorn app.main:app --reload --port 8001

Backend:
http://localhost:8001

3. Tesseract OCR Setup
ParseAnything uses Tesseract OCR for scanned document processing.
Install Tesseract OCR and make sure the executable is available on the system.
Example Windows installation path:
C:\Program Files\Tesseract-OCR\tesseract.exe

4. Frontend Setup
Open a new terminal:
cd frontend
npm install
npm run dev

Open the Vite URL shown in the terminal.
Example:
http://localhost:5178

Example Extraction Result
For a sample two-page PDF, the system can produce structured results such as:
{
  "file_type": "pdf",
  "processing_status": "completed",
  "total_pages": 2,
  "total_blocks": 23,
  "total_text_blocks": 22,
  "total_table_blocks": 1,
  "confidence_summary": {
    "high": 23,
    "medium": 0,
    "low": 0,
    "review_required": 0
  }
}

Design Principles
1. Element-Aware Processing
Different document elements require different extraction strategies.
2. Structured Output
The system converts extracted information into structured blocks instead of returning raw text alone.
3. Confidence-Aware Extraction
Uncertain content is identified and flagged for review.
4. Source Traceability
Extracted information remains connected to its original document location.
5. Verification Before Trust
Users can compare structured results with the original document.
Current Scope
Currently supported:
- PDF documents
- Scanned PDFs
- DOCX documents
- PPTX presentations
- XLSX spreadsheets
- XLS spreadsheets
- CSV files
- Image-based OCR workflows
Future Enhancements
Potential future improvements include:
- Advanced multi-column reading-order reconstruction
- Chart and figure understanding
- Mathematical equation extraction
- Handwriting recognition
- Large-scale batch processing
- Advanced document editing
- Additional OCR languages
- More specialized document parsers
Demo Workflow
1. Upload a document
2. Detect document type
3. Detect content elements
4. Extract using the appropriate method
5. Generate structured blocks
6. Calculate confidence
7. Flag uncertain content
8. Verify source traceability
9. Display structured results

Why ParseAnything?
ParseAnything focuses on more than simply converting documents into text.
It combines:
Document Understanding + Specialized Extraction + Structured Data + Confidence + Traceability
This makes extracted information easier to inspect, verify, and integrate into downstream systems.
Repository
GitHub:
https://github.com/srivarthini09/ParseAnything
License
No open-source license has been specified for this project yet.