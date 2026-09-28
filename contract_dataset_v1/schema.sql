PRAGMA foreign_keys = ON;

CREATE TABLE documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_uid TEXT NOT NULL UNIQUE,
    original_filename TEXT NOT NULL,
    file_format TEXT NOT NULL CHECK (file_format IN ('PDF', 'DOCX')),
    uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processing_status TEXT NOT NULL DEFAULT 'new'
        CHECK (processing_status IN ('new', 'processed', 'error'))
);

CREATE TABLE contracts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL UNIQUE,
    contract_number TEXT,
    contract_date TEXT,
    customer_name TEXT,
    contractor_name TEXT,
    amount_rub NUMERIC,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE TABLE extraction_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    field_name TEXT NOT NULL,
    raw_value TEXT,
    normalized_value TEXT,
    extraction_method TEXT NOT NULL,
    confidence REAL CHECK (confidence BETWEEN 0 AND 1),
    is_verified INTEGER NOT NULL DEFAULT 0 CHECK (is_verified IN (0, 1)),
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE INDEX idx_contract_number ON contracts(contract_number);
CREATE INDEX idx_contract_date ON contracts(contract_date);
CREATE INDEX idx_extraction_document ON extraction_results(document_id);

