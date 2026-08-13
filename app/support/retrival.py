#  Retrieval helpers 
from .ingest import co, supabase,chunk_text, embed_chunks, upsert_chunks
import os

def embed_query(query: str) -> list[float]:
    """
    Embed a user query.
    NOTE: input_type must be "search_query" here, NOT "search_document".
    Cohere trained the model to treat these differently; mixing them silently
    degrades retrieval quality without any error.
    """
    response = co.embed(
        texts           = [query],
        model           = "embed-english-v3.0",
        input_type      = "search_query",
        embedding_types = ["float"]
    )
    return response.embeddings.float_[0]


def vector_search(query_embedding: list[float], match_count: int = 5) -> list[dict]:
    """
    Call the match_documents RPC function in Supabase (pgvector similarity search).
    Returns rows sorted by cosine similarity — order here is relevance, not chunk order.
    """
    result = supabase.rpc(
        "match_documents",
        {"query_embedding": query_embedding, "match_count": match_count}
    ).execute()
    return result.data


def fetch_with_siblings(chunk_index: int, filename: str) -> str:
    """
    After a vector hit on chunk N, also pull chunk N-1 and N+1 from the same file.
    This recovers context that may have been split across a chunk boundary.
    The three chunks are returned as a single merged string, in order.
    """
    indices = [chunk_index - 1, chunk_index, chunk_index + 1]
    result  = supabase.table("documents") \
        .select("content, chunk_index") \
        .eq("filename", filename) \
        .in_("chunk_index", indices) \
        .order("chunk_index") \
        .execute()

    return " ".join(row["content"] for row in result.data)


def retrieve_context(query: str, match_count: int = 5) -> str:
    """
    Full retrieval pipeline:
      1. Embed the query
      2. Vector search → top-k hits
      3. For each hit, fetch its siblings for fuller context
      4. Deduplicate and join into one context string for the LLM
    """
    query_embedding = embed_query(query)
    hits            = vector_search(query_embedding, match_count)

    seen    = set()
    context_parts = []

    for hit in hits:
        chunk_index = hit["chunk_index"]
        filename    = hit["filename"]
        key         = (filename, chunk_index)

        if key in seen:
            continue
        seen.add(key)

        # Mark siblings as seen too so we don't double-include them
        seen.add((filename, chunk_index - 1))
        seen.add((filename, chunk_index + 1))

        passage = fetch_with_siblings(chunk_index, filename)
        context_parts.append(f"[Source: {os.path.basename(filename)}, chunk {chunk_index}]\n{passage}")

    return "\n\n---\n\n".join(context_parts)


if __name__ == "__main__":
    query = "Who is kim dokja?"
    context = retrieve_context(query)
    print(f"Retrieved context:\n{context}")