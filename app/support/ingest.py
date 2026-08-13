import os
import cohere
from supabase import create_client
from dotenv import load_dotenv
load_dotenv()
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.environ.get("SUPABASE_SECRET_KEY")
COHERE_API_KEY = os.environ.get("COHERE_API_KEY")
CHUNK_SIZE = 200   
OVERLAP    = 40    

supabase = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)
co       = cohere.Client(COHERE_API_KEY)


#  Ingestion 

def chunk_text(text: str, filename: str) -> list[dict]:
    """Split text into overlapping word-based chunks, tagged with chunk_index."""
    words  = text.split()
    chunks = []
    i      = 0
    idx    = 0

    while i < len(words):
        chunk_words = words[i : i + CHUNK_SIZE]
        chunks.append({
            "content":     " ".join(chunk_words),
            "filename":    filename,   # top-level for easy ORDER BY / filtering
            "chunk_index": idx,        # top-level so Supabase can sort on it
            "metadata":    {"filename": filename, "chunk_index": idx}
        })
        i   += CHUNK_SIZE - OVERLAP
        idx += 1

    return chunks


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """Generate Cohere float embeddings for every chunk (search_document mode)."""
    texts    = [c["content"] for c in chunks]
    response = co.embed(
        texts            = texts,
        model            = "embed-english-v3.0",
        input_type       = "search_document",  # must differ from query-time "search_query"
        embedding_types  = ["float"]
    )
    for i, chunk in enumerate(chunks):
        chunk["embedding"] = response.embeddings.float_[i]
    return chunks


def upsert_chunks(chunks: list[dict]):
    """
    Insert chunks into Supabase in batches of 50.

    Table schema expected:
        id          bigserial primary key,
        content     text,
        embedding   vector(1024),
        filename    text,          ← promoted from metadata so ORDER BY works cleanly
        chunk_index int,           ← promoted from metadata
        metadata    jsonb
    """
    rows = [
        {
            "content":     c["content"],
            "embedding":   c["embedding"],
            "filename":    c["filename"],
            "chunk_index": c["chunk_index"],
            "metadata":    c["metadata"],
        }
        for c in chunks
    ]

    batch_size = 50
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        supabase.table("documents").insert(batch).execute()
        print(f"Upserted chunks {i} → {i + len(batch) - 1}")


import glob

def ingest_file(filepath: str):
    filename = os.path.basename(filepath)
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    print(f"Chunking {filename}...")
    chunks = chunk_text(text, filename)
    print(f"  -> {len(chunks)} chunks")

    print(f"Embedding {filename}...")
    chunks = embed_chunks(chunks)

    print(f"Upserting {filename}...")
    upsert_chunks(chunks)
    print(f"Done with {filename}\n")





if __name__ == "__main__":
    ingest_file("orv.txt")
