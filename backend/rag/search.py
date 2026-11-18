from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.orm import Session
from rag.config import DEFAULT_TOP_K
from rag.config import DOC_APPROVAL_POLICY
from rag.config import DOC_CLAIMS_GUIDELINES
from rag.config import DOC_CUSTOMER_POLICY
from rag.config import DOMAIN_ALL
from rag.config import EMBEDDING_BATCH_SIZE
from rag.config import EMBEDDING_MODEL
from rag.config import MAX_TOP_K
from rag.config import QUERY_PREFIX
from rag.models import DocumentChunk

# The model is loaded once, because loading it takes several seconds
_embedding_model = None


def get_embedding_model():
    """Load the embedding model the first time it is needed."""
    global _embedding_model

    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer

        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)

    return _embedding_model


def embed_texts(texts):
    """Turn a list of texts into a list of normalized vectors."""
    model = get_embedding_model()
    vectors = model.encode(
        texts,
        batch_size=EMBEDDING_BATCH_SIZE,
        normalize_embeddings=True,
    )

    result = []
    for vector in vectors:
        result.append(vector.tolist())
    return result


def embed_query(query):
    """Turn a search question into one vector."""
    vectors = embed_texts([QUERY_PREFIX + query])
    return vectors[0]


def make_citation_label(chunk):
    """Build a short label such as 'Clause D.2 (section 3.2), page 8'."""
    if chunk.clause_code and chunk.clause_number:
        label = f"Clause {chunk.clause_code} (section {chunk.clause_number})"
    elif chunk.clause_number:
        label = f"Section {chunk.clause_number}"
    else:
        label = chunk.heading

    if chunk.page_end != chunk.page_number:
        return f"{label}, pages {chunk.page_number}-{chunk.page_end}"
    return f"{label}, page {chunk.page_number}"


def chunk_to_citation(chunk, distance):
    """Convert a chunk and its distance into a dictionary agents can cite."""
    return {
        "chunk_id": chunk.id,
        "document_type": chunk.document_type,
        "source_file": chunk.source_file,
        "policy_number": chunk.policy_number,
        "product": chunk.product,
        "version": chunk.version,
        "section_title": chunk.section_title,
        "clause_number": chunk.clause_number,
        "clause_code": chunk.clause_code,
        "heading": chunk.heading,
        "page_number": chunk.page_number,
        "page_end": chunk.page_end,
        "citation": make_citation_label(chunk),
        "score": round(1.0 - float(distance), 4),
        "text": chunk.content,
    }


def search_chunks(db: Session, query, document_type, insurance_domain=None, policy_number=None, top_k=DEFAULT_TOP_K):
    """Search one document type and return the best matching chunks as citations."""
    if not query or not query.strip():
        return []

    # Never return more than the maximum, and always at least one
    limit = max(1, min(top_k, MAX_TOP_K))

    vector = embed_query(query.strip())
    distance = DocumentChunk.embedding.cosine_distance(vector)

    statement = select(DocumentChunk, distance.label("distance"))
    statement = statement.where(DocumentChunk.document_type == document_type)

    if policy_number is not None:
        statement = statement.where(DocumentChunk.policy_number == policy_number)

    # Internal documents hold rules for one line plus rules that apply to every line
    if insurance_domain is not None:
        statement = statement.where(
            or_(
                DocumentChunk.insurance_domain == insurance_domain,
                DocumentChunk.insurance_domain == DOMAIN_ALL,
            )
        )

    statement = statement.order_by(distance).limit(limit)
    rows = db.execute(statement).all()

    citations = []
    for chunk, chunk_distance in rows:
        citations.append(chunk_to_citation(chunk, chunk_distance))
    return citations


def search_customer_policy(db, policy_number, query, top_k=DEFAULT_TOP_K):
    """Search the wording and schedule of one customer's policy only."""
    return search_chunks(
        db,
        query,
        DOC_CUSTOMER_POLICY,
        policy_number=policy_number,
        top_k=top_k,
    )


def search_claims_guidelines(db, insurance_domain, query, top_k=DEFAULT_TOP_K):
    """Search the internal claims handling guidelines for one insurance line."""
    return search_chunks(
        db,
        query,
        DOC_CLAIMS_GUIDELINES,
        insurance_domain=insurance_domain,
        top_k=top_k,
    )


def search_approval_policy(db, insurance_domain, query, top_k=DEFAULT_TOP_K):
    """Search the internal approval and decision policy for one insurance line."""
    return search_chunks(
        db,
        query,
        DOC_APPROVAL_POLICY,
        insurance_domain=insurance_domain,
        top_k=top_k,
    )


def search_approval_requirements(db, insurance_line, query, top_k=8):
    """Search approval requirements for one insurance line."""
    return search_approval_policy(
        db,
        insurance_line,
        query,
        top_k=top_k,
    )
