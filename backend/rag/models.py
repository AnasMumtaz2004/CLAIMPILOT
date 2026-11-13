from pgvector.sqlalchemy import Vector
from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from database.connection import Base
from database.models import new_id
from rag.config import EMBEDDING_DIMENSIONS


# One searchable piece (clause) of a reference document
class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(String(36), primary_key=True, default=new_id)
    document_type = Column(String, nullable=False, index=True)
    insurance_domain = Column(String, nullable=False, index=True)
    source_file = Column(String, nullable=False, index=True)
    policy_number = Column(String, nullable=True, index=True)
    product = Column(String, nullable=True)
    version = Column(String, nullable=True)
    effective_date = Column(String, nullable=True)
    section_title = Column(String, nullable=False, default="")
    clause_number = Column(String, nullable=True)
    clause_code = Column(String, nullable=True)
    heading = Column(String, nullable=False)
    page_number = Column(Integer, nullable=False)
    page_end = Column(Integer, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(EMBEDDING_DIMENSIONS), nullable=False)