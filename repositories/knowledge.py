"""
CortexReview Platform - Knowledge Repository (RAG)

Implements vector similarity search for context-aware code reviews.
Uses Supabase pgvector for storing and retrieving code embeddings
(Constitution V - RAG Implementation).

Architecture:
- KnowledgeRepository: Main class for context retrieval
- search_context(): Vector similarity search with configurable threshold
- Connection pooling via Supabase client
- Graceful degradation when Supabase unavailable
"""

import time

from loguru import logger
from openai import OpenAI
from supabase import Client

from utils.config import Config
from utils.metrics import (
    rag_match_count,
    rag_retrieval_failure_total,
    rag_retrieval_latency_seconds,
    rag_retrieval_success_total,
)


class KnowledgeRepository:
    """
    Repository for RAG context retrieval using Supabase pgvector.

    Provides vector similarity search to find relevant code patterns
    from repository history for context-aware reviews.

    Attributes:
        supabase: Supabase client for database operations
        openai: OpenAI client for embedding generation
        config: Application configuration
    """

    def __init__(self, supabase: Client, config: Config):
        """
        Initialize KnowledgeRepository.

        Args:
            supabase: Supabase client instance
            config: Application configuration
        """
        self.supabase = supabase
        self.config = config
        self.openai = OpenAI(
            api_key=config.effective_llm_api_key,
            base_url=config.effective_llm_base_url,
        )
        logger.info("KnowledgeRepository initialized")

    def search_context(
        self,
        query_text: str,
        repo_id: str,
        match_threshold: float | None = None,
        match_count: int | None = None,
    ) -> list[dict]:
        """
        Search knowledge base for relevant context using vector similarity.

        Args:
            query_text: Query text (e.g., diff content)
            repo_id: Repository identifier for filtering
            match_threshold: Similarity threshold (0.0-1.0), defaults to config.RAG_THRESHOLD
            match_count: Number of matches to return, defaults to config.RAG_MATCH_COUNT_MIN

        Returns:
            List of context chunks with metadata:
            [
                {
                    "id": int,
                    "content": str,
                    "metadata": dict,
                    "similarity": float,
                    "citation": str  # e.g., "See src/auth.py:45"
                }
            ]

        Raises:
            Exception: Propagates Supabase errors (caller handles graceful fallback)
        """
        start_time = time.time()
        match_threshold = match_threshold or self.config.RAG_THRESHOLD
        match_count = match_count or self.config.RAG_MATCH_COUNT_MIN

        try:
            # 1. Generate embedding for query
            query_embedding = self._generate_embedding(query_text[:2000])  # Limit token usage

            if not query_embedding:
                logger.warning(f"Failed to generate embedding for {repo_id}")
                return []

            # 2. Call Supabase RPC function for vector similarity search
            response = self.supabase.rpc(
                "match_knowledge",
                {
                    "query_embedding": query_embedding,
                    "match_threshold": match_threshold,
                    "match_count": match_count,
                    "repo_id_filter": repo_id,  # Optional: filter by repo
                },
            ).execute()

            # 3. Process results
            results = []
            if response.data:
                for row in response.data:
                    results.append(
                        {
                            "id": row.get("id"),
                            "content": row.get("content"),
                            "metadata": row.get("metadata", {}),
                            "similarity": row.get("similarity", 0.0),
                            "citation": self._format_citation(row.get("metadata", {})),
                        }
                    )

            # 4. Record metrics
            latency = time.time() - start_time
            rag_retrieval_latency_seconds.labels(repo_id=repo_id).observe(latency)
            rag_match_count.labels(repo_id=repo_id).observe(len(results))
            rag_retrieval_success_total.labels(repo_id=repo_id).inc()

            logger.bind(
                repo_id=repo_id,
                matches_found=len(results),
                latency_ms=int(latency * 1000),
            ).info(f"RAG context retrieval completed: {len(results)} matches")

            return results

        except Exception as e:
            latency = time.time() - start_time
            rag_retrieval_failure_total.labels(repo_id=repo_id, reason=type(e).__name__).inc()
            logger.error(f"RAG context retrieval failed: {e}")
            raise

    def _generate_embedding(self, text: str) -> list[float] | None:
        """
        Generate embedding vector using OpenAI API.

        Args:
            text: Text to embed

        Returns:
            List of floats representing embedding vector, or None if failed
        """
        try:
            response = self.openai.embeddings.create(
                model=self.config.EMBEDDING_MODEL,
                input=text,
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return None

    def _format_citation(self, metadata: dict) -> str:
        """
        Format citation string from metadata.

        Args:
            metadata: Metadata dict from knowledge base entry

        Returns:
            Citation string like "See src/auth.py:45" or "See PR #42"
        """
        file_path = metadata.get("file_path", "")
        line_number = metadata.get("line_number", "")
        pr_number = metadata.get("pr_number", "")

        if pr_number:
            return f"See PR #{pr_number}"
        elif file_path and line_number:
            return f"See {file_path}:{line_number}"
        elif file_path:
            return f"See {file_path}"
        else:
            return "See repository history"


def create_knowledge_repository(supabase: Client, config: Config) -> KnowledgeRepository | None:
    """
    Factory function to create KnowledgeRepository with validation.

    Args:
        supabase: Supabase client instance
        config: Application configuration

    Returns:
        KnowledgeRepository instance if Supabase configured, None otherwise
    """
    if not supabase:
        logger.warning("Supabase client not configured, RAG disabled")
        return None

    if not config.RAG_ENABLED:
        logger.info("RAG disabled via configuration")
        return None

    return KnowledgeRepository(supabase, config)
