PRAGMA foreign_keys = ON;

-- Загруженные исходные файлы.
CREATE TABLE documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_uid TEXT NOT NULL UNIQUE,
    original_filename TEXT NOT NULL,
    file_format TEXT NOT NULL CHECK (file_format IN ('PDF', 'DOCX')),
    storage_path TEXT NOT NULL,
    sha256 TEXT NOT NULL UNIQUE,
    has_text_layer INTEGER CHECK (has_text_layer IN (0, 1)),
    processing_status TEXT NOT NULL DEFAULT 'new'
        CHECK (processing_status IN ('new', 'processing', 'processed', 'needs_review', 'error')),
    uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Нормализованные сведения о договоре: одна запись на документ.
CREATE TABLE contracts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL UNIQUE,
    contract_type TEXT,
    contract_number TEXT,
    contract_date TEXT,                 -- ISO 8601: YYYY-MM-DD
    amount NUMERIC CHECK (amount >= 0),
    currency TEXT NOT NULL DEFAULT 'RUB',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

-- Организации, ИП и физические лица хранятся отдельно и не дублируются.
CREATE TABLE parties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    normalized_name TEXT NOT NULL UNIQUE,
    party_type TEXT NOT NULL
        CHECK (party_type IN ('organization', 'individual_entrepreneur', 'person', 'unknown'))
);

-- Связь договора со сторонами. Позволяет хранить любые отраслевые роли.
CREATE TABLE contract_parties (
    contract_id INTEGER NOT NULL,
    party_id INTEGER NOT NULL,
    role_code TEXT NOT NULL,
    role_label TEXT NOT NULL,
    PRIMARY KEY (contract_id, party_id, role_code),
    FOREIGN KEY (contract_id) REFERENCES contracts(id) ON DELETE CASCADE,
    FOREIGN KEY (party_id) REFERENCES parties(id) ON DELETE RESTRICT
);

-- Каждый запуск конвейера: версия алгоритма, модель, время и ошибка.
CREATE TABLE processing_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    pipeline_version TEXT NOT NULL,
    extraction_model TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('running', 'success', 'error')),
    error_message TEXT,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

-- Не только итог, но и исходный фрагмент, метод и уверенность.
CREATE TABLE extraction_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    field_name TEXT NOT NULL,
    raw_value TEXT,
    normalized_value TEXT,
    page_number INTEGER,
    source_context TEXT,
    extraction_method TEXT NOT NULL,
    confidence REAL CHECK (confidence BETWEEN 0 AND 1),
    is_verified INTEGER NOT NULL DEFAULT 0 CHECK (is_verified IN (0, 1)),
    FOREIGN KEY (run_id) REFERENCES processing_runs(id) ON DELETE CASCADE
);

CREATE INDEX idx_documents_status ON documents(processing_status);
CREATE INDEX idx_contract_number ON contracts(contract_number);
CREATE INDEX idx_contract_date ON contracts(contract_date);
CREATE INDEX idx_contract_amount ON contracts(amount);
CREATE INDEX idx_contract_parties_role ON contract_parties(role_code);
CREATE INDEX idx_extraction_run_field ON extraction_results(run_id, field_name);

