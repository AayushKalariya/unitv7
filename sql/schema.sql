-- Supabase / Postgres schema for Orb Assistant RAG.
-- Run this once in the Supabase SQL editor (or via psql) after creating the project.
--
-- Embedding dimension defaults to 384 (fastembed BAAI/bge-small-en-v1.5).
-- If you switch EMBEDDING_MODEL, update vector(384) everywhere below to match
-- the new model's dimension and re-run.

create extension if not exists vector;

-- One row per uploaded file.
create table if not exists rag_documents (
    id          uuid primary key default gen_random_uuid(),
    session_id  text        not null,
    filename    text        not null,
    n_chunks    int         not null default 0,
    created_at  timestamptz not null default now()
);

create index if not exists rag_documents_session_idx
    on rag_documents (session_id);

-- One row per chunk, with its embedding.
create table if not exists rag_chunks (
    id           uuid primary key default gen_random_uuid(),
    document_id  uuid        not null references rag_documents(id) on delete cascade,
    session_id   text        not null,
    filename     text        not null,
    chunk_index  int         not null,
    content      text        not null,
    embedding    vector(384) not null,
    created_at   timestamptz not null default now()
);

create index if not exists rag_chunks_session_idx
    on rag_chunks (session_id);

-- Approximate-nearest-neighbour index (cosine distance).
create index if not exists rag_chunks_embedding_idx
    on rag_chunks using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- Similarity search. Pass filter_session_id = null to search across all sessions.
create or replace function match_rag_chunks(
    query_embedding    vector(384),
    match_count        int  default 5,
    filter_session_id  text default null
)
returns table (
    id           uuid,
    document_id  uuid,
    session_id   text,
    filename     text,
    content      text,
    similarity   float
)
language sql stable
as $$
    select
        c.id,
        c.document_id,
        c.session_id,
        c.filename,
        c.content,
        1 - (c.embedding <=> query_embedding) as similarity
    from rag_chunks c
    where filter_session_id is null or c.session_id = filter_session_id
    order by c.embedding <=> query_embedding
    limit match_count;
$$;
