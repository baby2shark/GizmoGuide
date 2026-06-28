-- RAG knowledge base schema (no pgvector dependency)
-- Embeddings stored as JSONB arrays, vector search done in Python
CREATE TABLE IF NOT EXISTS knowledge_base (
    id SERIAL PRIMARY KEY,
    chunk_id TEXT UNIQUE NOT NULL,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    tokenized TEXT NOT NULL DEFAULT '',
    tags TEXT[] NOT NULL DEFAULT '{}',
    source TEXT NOT NULL DEFAULT 'mock',
    embedding JSONB,
    content_tsv tsvector,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kb_tsv ON knowledge_base USING gin(content_tsv);
CREATE INDEX IF NOT EXISTS idx_kb_category ON knowledge_base(category);
