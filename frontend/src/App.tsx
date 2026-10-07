import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
} from "react";

import "./App.css";

const API_BASE_URL = "http://localhost:8001";

type ConfidenceLevel = "high" | "medium" | "low";

type TextBlock = {
  id: string;
  type: "text";
  content: string;
  page: number;
  reading_order?: number | null;
  bbox: number[];
  confidence: number;
  confidence_level: ConfidenceLevel;
  review_required: boolean;
  extraction_method: string;
};

type TableContent = {
  headers: string[];
  rows: string[][];
  row_count: number;
  column_count: number;
};

type TableBlock = {
  id: string;
  type: "table";
  content: TableContent;
  page: number;
  reading_order?: number | null;
  bbox: number[];
  confidence: number;
  confidence_level: ConfidenceLevel;
  review_required: boolean;
  extraction_method: string;
  table_index?: number;
};

type DocumentBlock = TextBlock | TableBlock;

type ConfidenceSummary = {
  high: number;
  medium: number;
  low: number;
  review_required: number;
};

type PageResult = {
  page: number;
  status: string;
  extraction_method: string;
  native_character_count: number;
  block_count?: number;
  table_count?: number;
};

type ProcessedDocument = {
  document_id: string;
  filename: string;
  file_type: string;
  total_pages: number;
  total_blocks: number;
  total_text_blocks?: number;
  total_table_blocks?: number;
  total_tables?: number;
  processing_status: string;
  confidence_summary: ConfidenceSummary;
  pages: PageResult[];
  blocks: DocumentBlock[];
};

function App() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [result, setResult] = useState<ProcessedDocument | null>(null);
  const [backendOnline, setBackendOnline] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [loadingResult, setLoadingResult] = useState(false);
  const [error, setError] = useState("");
  const [statusMessage, setStatusMessage] = useState(
    "Ready to process a document."
  );

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    checkBackendHealth();
  }, []);

  async function checkBackendHealth() {
    try {
      const response = await fetch(`${API_BASE_URL}/api/health`);

      if (!response.ok) {
        throw new Error();
      }

      const data = await response.json();
      setBackendOnline(data.status === "healthy");
    } catch {
      setBackendOnline(false);
    }
  }

  function handleFileSelected(
    event: ChangeEvent<HTMLInputElement>
  ) {
    const file = event.target.files?.[0];

    if (!file) return;

    setSelectedFile(file);
    setResult(null);
    setError("");
    setStatusMessage("Document selected. Ready to process.");
  }

  async function uploadDocument(file: File): Promise<string> {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(
      `${API_BASE_URL}/api/documents/upload`,
      {
        method: "POST",
        body: formData,
      }
    );

    if (!response.ok) {
      let message = "Document upload failed.";

      try {
        const data = await response.json();
        if (data.detail) message = data.detail;
      } catch {
        // Keep default error.
      }

      throw new Error(message);
    }

    const data = await response.json();
    const id = data?.document?.id;

    if (!id) {
      throw new Error(
        "Upload succeeded, but no document ID was returned."
      );
    }

    return id;
  }

  async function processDocument(id: string) {
    const response = await fetch(
      `${API_BASE_URL}/api/documents/${id}/process`,
      {
        method: "POST",
      }
    );

    if (!response.ok) {
      let message = "Document processing failed.";

      try {
        const data = await response.json();
        if (data.detail) message = data.detail;
      } catch {
        // Keep default error.
      }

      throw new Error(message);
    }

    return response.json();
  }

  async function fetchResult(
    id: string
  ): Promise<ProcessedDocument> {
    const response = await fetch(
      `${API_BASE_URL}/api/documents/${id}/result`
    );

    if (!response.ok) {
      let message = "Unable to fetch processed result.";

      try {
        const data = await response.json();
        if (data.detail) message = data.detail;
      } catch {
        // Keep default error.
      }

      throw new Error(message);
    }

    return response.json();
  }

  async function handleProcessDocument() {
    if (!selectedFile) {
      setError("Please select a document first.");
      return;
    }

    setError("");
    setResult(null);

    try {
      setUploading(true);
      setStatusMessage("Uploading document...");

      const documentId = await uploadDocument(selectedFile);

      setUploading(false);
      setProcessing(true);

      setStatusMessage(
        "Detecting content and extracting data..."
      );

      await processDocument(documentId);

      setProcessing(false);
      setLoadingResult(true);

      setStatusMessage("Loading structured results...");

      const processedResult =
        await fetchResult(documentId);

      setLoadingResult(false);
      setResult(processedResult);

      setStatusMessage(
        "Processing completed successfully."
      );
    } catch (err) {
      setUploading(false);
      setProcessing(false);
      setLoadingResult(false);

      setError(
        err instanceof Error
          ? err.message
          : "Something went wrong."
      );

      setStatusMessage("Processing failed.");
    }
  }

  function reset() {
    setSelectedFile(null);
    setResult(null);
    setError("");
    setStatusMessage("Ready to process a document.");

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  const isBusy =
    uploading ||
    processing ||
    loadingResult;

  return (
    <div className="app-shell">

      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">P</div>

          <div>
            <div className="brand-name">
              ParseAnything
            </div>

            <div className="brand-subtitle">
              Universal Document Ingestion
            </div>
          </div>
        </div>

        <div className="backend-status">
          <span
            className={
              backendOnline
                ? "status-dot online"
                : "status-dot offline"
            }
          />

          {backendOnline
            ? "System Online"
            : "Backend Offline"}
        </div>
      </header>

      <main className="main-container">

        <section className="hero">
          <div className="hero-badge">
            AI DOCUMENT INGESTION
          </div>

          <h1>
            Turn complex documents
            <span> into structured data.</span>
          </h1>

          <p>
            Upload a document and ParseAnything detects
            text and tables, extracts structured information,
            and preserves source traceability.
          </p>
        </section>

        <section className="upload-card">

          <div className="upload-header">
            <div>
              <h2>Document Processing</h2>
              <p>
                Upload a supported document to begin.
              </p>
            </div>

            <span className="api-badge">
              API : 8001
            </span>
          </div>

          <input
            ref={fileInputRef}
            type="file"
            hidden
           accept=".pdf,.png,.jpg,.jpeg,.xlsx,.xls,.csv,.pptx,.docx"
            onChange={handleFileSelected}
          />

          <div
            className={
              selectedFile
                ? "drop-zone selected"
                : "drop-zone"
            }
            onClick={() => {
              if (!isBusy) {
                fileInputRef.current?.click();
              }
            }}
          >
            <div className="upload-icon">↑</div>

            <div className="drop-title">
              {selectedFile
                ? selectedFile.name
                : "Choose a document"}
            </div>

            <div className="drop-description">
              {selectedFile
                ? formatFileSize(selectedFile.size)
                : "PDF, images, Excel, PowerPoint or Word"}
            </div>

            {!selectedFile && (
              <button
                type="button"
                className="secondary-button"
                onClick={(event) => {
                  event.stopPropagation();
                  fileInputRef.current?.click();
                }}
              >
                Browse Files
              </button>
            )}
          </div>

          <div className="actions">
            <button
              type="button"
              className="primary-button"
              disabled={!selectedFile || isBusy}
              onClick={handleProcessDocument}
            >
              {uploading
                ? "Uploading..."
                : processing
                  ? "Processing..."
                  : loadingResult
                    ? "Loading Results..."
                    : "Process Document"}
            </button>

            {selectedFile && !isBusy && (
              <button
                type="button"
                className="reset-button"
                onClick={reset}
              >
                Clear
              </button>
            )}
          </div>

          <div className="pipeline">
            <PipelineStep
              number="01"
              label="Upload"
              active={uploading}
            />

            <span>→</span>

            <PipelineStep
              number="02"
              label="Detect & Extract"
              active={processing}
            />

            <span>→</span>

            <PipelineStep
              number="03"
              label="Structure"
              active={loadingResult}
            />

            <span>→</span>

            <PipelineStep
              number="04"
              label="Verify"
              complete={!!result}
            />
          </div>

          <div className="status-message">
            {statusMessage}
          </div>

          {error && (
            <div className="error-message">
              <strong>Processing Error</strong>
              <span>{error}</span>
            </div>
          )}
        </section>

        {result && (
          <section className="results">

            <div className="result-heading">
              <div>
                <div className="section-label">
                  PROCESSING RESULT
                </div>

                <h2>{result.filename}</h2>

                <p>
                  Document ID:{" "}
                  <code>{result.document_id}</code>
                </p>
              </div>

              <span className="completed">
                ✓ Completed
              </span>
            </div>

            <div className="summary-grid">
              <Summary
                value={result.total_pages}
                label="Pages"
              />

              <Summary
                value={result.total_blocks}
                label="Total Blocks"
              />

              <Summary
                value={
                  result.total_text_blocks ??
                  result.blocks.filter(
                    (block) => block.type === "text"
                  ).length
                }
                label="Text Blocks"
              />

              <Summary
                value={
                  result.total_tables ??
                  result.total_table_blocks ??
                  result.blocks.filter(
                    (block) => block.type === "table"
                  ).length
                }
                label="Tables"
              />

              <Summary
                value={
                  result.confidence_summary.high
                }
                label="High Confidence"
                green
              />

              <Summary
                value={
                  result.confidence_summary.review_required
                }
                label="Needs Review"
                warning={
                  result.confidence_summary.review_required > 0
                }
              />
            </div>

            <section className="confidence-card">

              <div className="confidence-header">
                <div>
                  <div className="section-label">
                    CONFIDENCE OVERVIEW
                  </div>

                  <h3>
                    Extraction Quality
                  </h3>
                </div>

                <div className="legend">
                  <Legend
                    label="High"
                    count={
                      result.confidence_summary.high
                    }
                    type="high"
                  />

                  <Legend
                    label="Medium"
                    count={
                      result.confidence_summary.medium
                    }
                    type="medium"
                  />

                  <Legend
                    label="Low"
                    count={
                      result.confidence_summary.low
                    }
                    type="low"
                  />
                </div>
              </div>

              <div className="confidence-bar">
                {result.total_blocks > 0 && (
                  <>
                    <div
                      className="bar-high"
                      style={{
                        width: `${
                          result.confidence_summary.high /
                          result.total_blocks *
                          100
                        }%`,
                      }}
                    />

                    <div
                      className="bar-medium"
                      style={{
                        width: `${
                          result.confidence_summary.medium /
                          result.total_blocks *
                          100
                        }%`,
                      }}
                    />

                    <div
                      className="bar-low"
                      style={{
                        width: `${
                          result.confidence_summary.low /
                          result.total_blocks *
                          100
                        }%`,
                      }}
                    />
                  </>
                )}
              </div>
            </section>

            <section className="content-section">

              <div className="section-heading">
                <div>
                  <div className="section-label">
                    STRUCTURED OUTPUT
                  </div>

                  <h2>Extracted Content</h2>
                </div>

                <span className="block-count">
                  {result.total_blocks} blocks
                </span>
              </div>

              <div className="blocks-list">
                {result.blocks.map((block) =>
                  block.type === "table" ? (
                    <TableCard
                      key={block.id}
                      block={block}
                    />
                  ) : (
                    <TextCard
                      key={block.id}
                      block={block}
                    />
                  )
                )}
              </div>
            </section>

            <section className="content-section">

              <div className="section-heading">
                <div>
                  <div className="section-label">
                    SOURCE TRACEABILITY
                  </div>

                  <h2>Page Processing</h2>
                </div>
              </div>

              <div className="page-grid">
                {result.pages.map((page) => (
                  <div
                    className="page-card"
                    key={page.page}
                  >
                    <strong>
                     {result.file_type === "pptx" ? "Slide" : "Page"} {page.page}
                    </strong>

                    <span className="page-status">
                      {page.status.replace(
                        /_/g,
                        " "
                      )}
                    </span>

                    <div className="page-info">
                      <div>
                        <span>Method</span>
                        <strong>
                          {formatMethod(
                            page.extraction_method
                          )}
                        </strong>
                      </div>

                      <div>
                        <span>Blocks</span>
                        <strong>
                          {page.block_count}
                        </strong>
                      </div>

                      <div>
                        <span>Tables</span>
                        <strong>
                          {page.table_count ?? 0}
                        </strong>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </section>
        )}

        {!result && !isBusy && (
          <section className="capabilities">

            <div className="section-label">
              PIPELINE CAPABILITIES
            </div>

            <div className="capability-grid">

              <Capability
                number="01"
                title="Smart Extraction"
                description="Detects native text and routes scanned pages through OCR."
              />

              <Capability
                number="02"
                title="Table Detection"
                description="Identifies structured tables and preserves rows and columns."
              />

              <Capability
                number="03"
                title="Confidence Aware"
                description="Assigns confidence levels and flags uncertain content for review."
              />

              <Capability
                number="04"
                title="Source Traceability"
                description="Every extracted block retains page and bounding-box information."
              />

            </div>
          </section>
        )}
      </main>

      <footer>
        <span>ParseAnything</span>
        <span>Universal Document Ingestion System</span>
        <span>Backend : 8001</span>
      </footer>
    </div>
  );
}


// ============================================================
// SMALL COMPONENTS
// ============================================================

function PipelineStep({
  number,
  label,
  active,
  complete,
}: {
  number: string;
  label: string;
  active?: boolean;
  complete?: boolean;
}) {
  return (
    <div
      className={
        complete
          ? "pipeline-step complete"
          : active
            ? "pipeline-step active"
            : "pipeline-step"
      }
    >
      <span>{number}</span>
      {label}
    </div>
  );
}


function Summary({
  value,
  label,
  green,
  warning,
}: {
  value: number;
  label: string;
  green?: boolean;
  warning?: boolean;
}) {
  return (
    <div
      className={`summary-card ${
        green
          ? "green"
          : warning
            ? "warning"
            : ""
      }`}
    >
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}


function Legend({
  label,
  count,
  type,
}: {
  label: string;
  count: number;
  type: string;
}) {
  return (
    <div className="legend-item">
      <i className={`legend-dot ${type}`} />
      {label}
      <strong>{count}</strong>
    </div>
  );
}


function TextCard({
  block,
}: {
  block: TextBlock;
}) {
  return (
    <article
      className={
        block.review_required
          ? "block-card review"
          : "block-card"
      }
    >
      <div className="block-header">
        <span className="type-badge text">
          TEXT
        </span>

        <span className="block-id">
          {block.id}
        </span>
      </div>

      <div className="text-content">
        {block.content}
      </div>

      <Metadata block={block} />
    </article>
  );
}


function TableCard({
  block,
}: {
  block: TableBlock;
}) {
  const columnCount =
    block.content.column_count ||
    block.content.headers.length;

  return (
    <article className="block-card table-card">

      <div className="block-header">
        <span className="type-badge table">
          TABLE
        </span>

        <span className="block-id">
          {block.id}
        </span>
      </div>

      <div className="table-container">
        <table>
          <thead>
            <tr>
              {Array.from({
                length: columnCount,
              }).map((_, index) => (
                <th key={index}>
                  {block.content.headers[index] ||
                    "—"}
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {block.content.rows.map(
              (row, rowIndex) => (
                <tr key={rowIndex}>
                  {Array.from({
                    length: columnCount,
                  }).map((_, columnIndex) => (
                    <td key={columnIndex}>
                      {row[columnIndex] || "—"}
                    </td>
                  ))}
                </tr>
              )
            )}
          </tbody>
        </table>
      </div>

      <div className="table-count">
        {block.content.row_count} rows ×{" "}
        {block.content.column_count} columns
      </div>

      <Metadata block={block} />
    </article>
  );
}


function Metadata({
  block,
}: {
  block: DocumentBlock;
}) {
  return (
    <div className="metadata">

      <Meta
       label={block.extraction_method === "python_pptx" ? "Slide" : "Page"}
        value={String(block.page)}
      />
      
      {"sheet_name" in block &&
  typeof block.sheet_name === "string" && (
    <Meta
      label="Sheet"
      value={block.sheet_name}
    />
     )}

      <Meta
        label="Bounding Box"
        value={
  block.bbox
    ? `[${block.bbox.map((n) => Number(n).toFixed(2)).join(", ")}]`
    : "Not available"
}
      />

      <Meta
        label="Confidence"
        value={`${Math.round(
          block.confidence * 100
        )}%`}
        className={block.confidence_level}
      />

      <Meta
        label="Method"
        value={formatMethod(
          block.extraction_method
        )}
      />

      <Meta
        label="Review"
        value={
          block.review_required
            ? "Required"
            : "Verified"
        }
        className={
          block.review_required
            ? "review-text"
            : "verified"
        }
      />
    </div>
  );
}


function Meta({
  label,
  value,
  className = "",
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div className="meta">
      <span>{label}</span>
      <strong className={className}>
        {value}
      </strong>
    </div>
  );
}


function Capability({
  number,
  title,
  description,
}: {
  number: string;
  title: string;
  description: string;
}) {
  return (
    <div className="capability">
      <span>{number}</span>
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  );
}


// ============================================================
// HELPERS
// ============================================================

function formatFileSize(bytes: number) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }

  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }

  return `${(
    bytes /
    (1024 * 1024)
  ).toFixed(1)} MB`;
}


function formatMethod(method: string) {
  const names: Record<string, string> = {
    native_pdf: "Native PDF",
    tesseract_ocr: "Tesseract OCR",
    pymupdf_table_extractor:
      "PyMuPDF Table",
  };

  return names[method] || method;
}


export default App;