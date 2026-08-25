from roche_agent.contracts import IndexConfig
from roche_agent.retrieval.documents import chunk_documents, load_markdown_documents


def test_structure_chunks_preserve_clause_and_table_ids(project_root):
    documents = load_markdown_documents(project_root / "data" / "iso" / "documents")
    chunks = chunk_documents(documents, IndexConfig(chunk_strategy="structure"))
    ids = {chunk.chunk_id for chunk in chunks}
    assert "sop-v2-temp-limit" in ids
    assert "temp-log-aug::table::2026-08-12" in ids
    assert "appointment-li-ming" in ids


def test_fixed_chunks_record_contained_evidence_ids(project_root):
    documents = load_markdown_documents(project_root / "data" / "iso" / "documents")
    chunks = chunk_documents(
        documents,
        IndexConfig(chunk_strategy="fixed", chunk_size=500, chunk_overlap=50),
    )
    contained = {
        evidence_id
        for chunk in chunks
        for evidence_id in chunk.metadata["contained_evidence_ids"]
    }
    assert "sop-v2-temp-limit" in contained

