"""
功能：向量存储服务 (VectorStore)
说明：封装 SQLAlchemy + pgvector，提供 Schema 向量的存储与相似度检索功能。
作者：CYJ
"""
import logging
from typing import List, Dict, Any, Tuple
from sqlalchemy import create_engine, text, Column, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import sessionmaker, declarative_base
from pgvector.sqlalchemy import Vector
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
Base = declarative_base()

# Define models for PGVector
class SchemaEmbedding(Base):
    __tablename__ = 'schema_embeddings'
    
    id = Column(Integer, primary_key=True)
    object_type = Column(String(50)) # 'table' or 'column'
    object_name = Column(String(255)) # 'orders' or 'orders.total_amount'
    original_description = Column(Text) # 原始 comment
    enriched_description = Column(Text) # LLM 增强描述
    # Add simple description column for compatibility with legacy code/search if needed
    # Or better, update the query to use original_description/enriched_description
    # description = Column(Text) 
    metadata_json = Column(JSONB)     # Original metadata
    embedding = Column(Vector(1024))  # DashScope text-embedding-v3 dimension
    # keywords_ts = Column(TSVECTOR) # SQLAlchemy doesn't have TSVECTOR type built-in easily, we treat it as raw in queries

class VectorStore:
    def __init__(self):
        # Construct DB URL
        # Ensure using a driver compatible with pgvector, e.g., psycopg2
        self.url = f"postgresql+psycopg2://{settings.VECTOR_DB_USER}:{settings.VECTOR_DB_PASSWORD}@{settings.VECTOR_DB_HOST}:{settings.VECTOR_DB_PORT}/{settings.VECTOR_DB_NAME}"
        self.engine = create_engine(self.url)
        self.Session = sessionmaker(bind=self.engine)

    def init_db(self):
        """Create tables and enable vector extension if needed."""
        with self.engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        Base.metadata.create_all(self.engine)

    def reset_db(self):
        """Drop and recreate tables to ensure schema updates (e.g. dimension change)."""
        try:
            Base.metadata.drop_all(self.engine)
            self.init_db()
            logger.info("Reset Vector DB (Dropped and Recreated tables).")
        except Exception as e:
            logger.error(f"Failed to reset Vector DB: {e}")
            raise

    def add_embeddings(self, items: List[Dict[str, Any]]):
        """
        Add embeddings to the database.
        items: List of dicts with keys: object_type, object_name, description, metadata, embedding
        """
        session = self.Session()
        try:
            for item in items:
                record = SchemaEmbedding(
                    object_type=item['object_type'],
                    object_name=item['object_name'],
                    description=item['description'],
                    metadata_json=item['metadata'],
                    embedding=item['embedding']
                )
                session.add(record)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to add embeddings: {e}")
            raise
        finally:
            session.close()

    def hybrid_search(self, query_embedding: List[float], query_text: str, limit: int = 5, vector_weight: float = 0.7) -> List[Tuple[SchemaEmbedding, float]]:
        """
        Hybrid search combining vector cosine distance and keyword matching (ts_rank).
        """
        session = self.Session()
        try:
            # 1. Vector Distance
            dist_col = SchemaEmbedding.embedding.cosine_distance(query_embedding)
            
            # 2. Keyword Rank (ts_rank)
            # Use to_tsquery('simple', ...) for partial matching or plainto_tsquery for plain text
            # We use simple configuration for Chinese support if configured, or english default.
            # Assuming 'simple' is available.
            rank_col = text("ts_rank(keywords_ts, plainto_tsquery('simple', :q))")
            keyword_filter = text("keywords_ts @@ plainto_tsquery('simple', :q)")
            
            # Candidate Limit
            candidate_limit = limit * 3
            
            # A. Vector Candidates
            vector_candidates = session.query(
                SchemaEmbedding, 
                dist_col.label("distance")
            ).order_by(dist_col).limit(candidate_limit).all()
            
            # B. Keyword Candidates
            keyword_candidates = []
            if query_text.strip():
                try:
                    keyword_candidates = session.query(
                        SchemaEmbedding, 
                        rank_col.bindparams(q=query_text).label("rank")
                    ).filter(
                        keyword_filter.bindparams(q=query_text)
                    ).order_by(text("rank DESC")).limit(candidate_limit).all()
                except Exception as e:
                    # 关键词搜索失败通常是因为：
                    # 1. keywords_ts 列不存在（需要重建向量索引）
                    # 2. 中文查询在 simple 配置下解析失败
                    # 这不影响功能，会回退到纯向量搜索
                    logger.debug(f"Keyword search skipped: {str(e)[:100]}")
                    keyword_candidates = []

            # C. Rerank
            combined = {}
            
            # Process Vector
            for rec, dist in vector_candidates:
                # Normalize distance (0..2) to similarity (0..1)
                # Cosine dist is 1 - cosine_sim. So sim = 1 - dist.
                sim = 1.0 - float(dist)
                combined[rec.id] = {
                    "record": rec,
                    "vector_score": max(sim, 0.0),
                    "keyword_score": 0.0
                }
                
            # Process Keyword
            for rec, rank in keyword_candidates:
                if rec.id not in combined:
                    combined[rec.id] = {
                        "record": rec,
                        "vector_score": 0.0,
                        "keyword_score": float(rank)
                    }
                else:
                    combined[rec.id]["keyword_score"] = float(rank)
            
            # Calculate Final Score
            results = []
            for cid, data in combined.items():
                # Cap keyword score at 1.0
                k_score = min(data["keyword_score"], 1.0)
                v_score = data["vector_score"]
                
                final_score = (vector_weight * v_score) + ((1 - vector_weight) * k_score)
                
                # Return (record, distance) where distance = 1 - final_score
                # This ensures compatibility with downstream code expecting low distance = good
                results.append((data["record"], 1.0 - final_score))
                
            results.sort(key=lambda x: x[1])
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            # Fallback to pure vector search
            return self.search(query_embedding, limit)
        finally:
            session.close()

    def search(self, query_embedding: List[float], limit: int = 5) -> List[Tuple[SchemaEmbedding, float]]:
        """
        Similarity search using vector dot product (or L2 distance).
        Returns: List of (SchemaEmbedding, distance)
        """
        session = self.Session()
        try:
            # Use cosine distance (<=> operator in pgvector)
            # We need to return the distance to filter by threshold later
            distance_expr = SchemaEmbedding.embedding.cosine_distance(query_embedding)
            
            results = session.query(SchemaEmbedding, distance_expr).order_by(
                distance_expr
            ).limit(limit).all()
            
            # Backfill 'description' attribute for legacy compatibility in RetrievalTool
            for r, _ in results:
                if not hasattr(r, 'description'):
                    r.description = r.enriched_description or r.original_description
            
            return results
        finally:
            session.close()
