"""
CortexReview Platform - Repository Indexing Service

Handles repository indexing for RAG knowledge base:
- Clone repository with GitPython
- Walk directory tree for code files
- Chunk large files into manageable pieces
- Secret scanning before embedding
- Generate embeddings and store in Supabase
- Progress tracking for long-running tasks

Constitution V - RAG Implementation
Constitution XIII - Data Governance (Secret Scanning)
"""

import os
import tempfile
import time
import typing

from git import Repo
from loguru import logger
from openai import OpenAI
from supabase import Client

from models.indexing import IndexDepth, IndexingProgress
from utils.config import Config
from utils.metrics import (
    indexing_chunks_embedded_total,
    indexing_duration_seconds,
    indexing_files_processed_total,
    indexing_secrets_found_total,
)
from utils.secrets import redact_secrets


class IndexingService:
    """
    Service for indexing repositories into RAG knowledge base.

    Orchestrates the complete indexing workflow:
    1. Clone repository from Git URL
    2. Walk directory tree for code files
    3. Scan for secrets (data governance)
    4. Chunk large files
    5. Generate embeddings
    6. Store in Supabase knowledge_base table

    Attributes:
        supabase: Supabase client for database operations
        openai: OpenAI client for embedding generation
        config: Application configuration
    """

    # File extensions to index
    INDEXABLE_EXTENSIONS = {
        ".py",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".go",
        ".rs",
        ".java",
        ".kt",
        ".cpp",
        ".cc",
        ".cxx",
        ".h",
        ".hpp",
        ".c",
        ".cs",
        ".swift",
        ".rb",
        ".php",
        ".scala",
        ".clj",
        ".ex",
        ".exs",
        ".dart",
        ".lua",
        ".r",
    }

    # Directories to skip
    SKIP_DIRECTORIES = {
        ".git",
        ".github",
        "node_modules",
        "venv",
        ".venv",
        "env",
        "__pycache__",
        ".pytest_cache",
        "dist",
        "build",
        "target",
        ".idea",
        ".vscode",
        "vendor",
        "third_party",
    }

    # Maximum file size to index (bytes)
    MAX_FILE_SIZE = 1024 * 1024  # 1 MB

    # Chunk size for splitting files
    CHUNK_SIZE = 2000  # characters
    CHUNK_OVERLAP = 200  # characters

    def __init__(self, supabase: Client, config: Config):
        """
        Initialize IndexingService.

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
        logger.info("IndexingService initialized")

    def index_repository(
        self,
        repo_id: str,
        git_url: str,
        access_token: str,
        branch: str = "main",
        depth: IndexDepth = IndexDepth.DEEP,
        progress_callback=None,
    ) -> dict:
        """
        Index repository into RAG knowledge base.

        Args:
            repo_id: Repository identifier
            git_url: Git repository HTTPS URL
            access_token: Personal access token for cloning
            branch: Branch to index
            depth: Indexing mode (shallow or deep)
            progress_callback: Optional callback for progress updates

        Returns:
            dict with indexing results:
            {
                "status": "success" | "failed",
                "repo_id": str,
                "files_processed": int,
                "chunks_indexed": int,
                "secrets_found": int,
                "duration_seconds": float,
                "error": str (if failed)
            }
        """
        start_time = time.time()

        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # Stage 1: Clone repository
                self._update_progress(
                    progress_callback,
                    IndexingProgress(stage="cloning", percentage=0.0),
                )
                clone_path = self._clone_repository(git_url, access_token, branch, temp_dir)

                # Stage 2: Scan for files
                self._update_progress(
                    progress_callback,
                    IndexingProgress(stage="scanning", percentage=10.0),
                )
                files_to_index = self._scan_files(clone_path, depth)
                total_files = len(files_to_index)

                if total_files == 0:
                    logger.warning(f"No indexable files found in {repo_id}")
                    return {
                        "status": "success",
                        "repo_id": repo_id,
                        "files_processed": 0,
                        "chunks_indexed": 0,
                        "secrets_found": 0,
                        "duration_seconds": time.time() - start_time,
                    }

                # Stage 3: Process files
                chunks_indexed = 0
                secrets_found = 0

                for idx, file_path in enumerate(files_to_index):
                    try:
                        # Update progress (10% to 90%)
                        percentage = 10.0 + (idx / total_files) * 80.0
                        self._update_progress(
                            progress_callback,
                            IndexingProgress(
                                stage="chunking",
                                files_processed=idx,
                                total_files=total_files,
                                chunks_indexed=chunks_indexed,
                                percentage=percentage,
                            ),
                        )

                        # Read file content
                        with open(file_path, encoding="utf-8", errors="ignore") as f:
                            content = f.read()

                        # Skip if too large
                        if len(content) > self.MAX_FILE_SIZE:
                            logger.debug(f"Skipping large file: {file_path}")
                            continue

                        # Secret scanning (Constitution XIII)
                        redacted_content, matches = redact_secrets(
                            content, os.path.relpath(file_path, clone_path)
                        )
                        if matches:
                            secrets_found += len(matches)
                            for match in matches:
                                indexing_secrets_found_total.labels(
                                    repo_id=repo_id,
                                    secret_type=match.secret_type.value,
                                ).inc()
                            logger.warning(f"Secrets found in {file_path}, using redacted content")
                            content = redacted_content

                        # Chunk file content
                        chunks = self._chunk_content(content)

                        # Generate embeddings and store
                        for chunk_idx, chunk in enumerate(chunks):
                            if not chunk.strip():
                                continue

                            # Generate embedding
                            embedding = self._generate_embedding(chunk)
                            if not embedding:
                                continue

                            # Store in Supabase
                            relative_path = os.path.relpath(file_path, clone_path)
                            self.supabase.table("knowledge_base").insert(
                                {
                                    "repo_id": repo_id,
                                    "content": chunk,
                                    "metadata": {
                                        "file_path": relative_path,
                                        "branch": branch,
                                        "chunk_index": chunk_idx,
                                        "file_size": len(content),
                                    },
                                    "embedding": embedding,
                                }
                            ).execute()

                            chunks_indexed += 1

                        indexing_files_processed_total.labels(repo_id=repo_id).inc()

                    except Exception as e:
                        logger.error(f"Failed to index file {file_path}: {e}")
                        continue

                # Stage 4: Complete
                self._update_progress(
                    progress_callback,
                    IndexingProgress(
                        stage="completed",
                        files_processed=total_files,
                        total_files=total_files,
                        chunks_indexed=chunks_indexed,
                        percentage=100.0,
                    ),
                )

                duration = time.time() - start_time
                indexing_duration_seconds.labels(repo_id=repo_id, depth=depth.value).observe(
                    duration
                )
                indexing_chunks_embedded_total.labels(repo_id=repo_id).inc(chunks_indexed)

                logger.info(
                    f"Indexing completed: repo_id={repo_id}, "
                    f"files={total_files}, chunks={chunks_indexed}, "
                    f"secrets={secrets_found}, duration={duration:.2f}s"
                )

                return {
                    "status": "success",
                    "repo_id": repo_id,
                    "files_processed": total_files,
                    "chunks_indexed": chunks_indexed,
                    "secrets_found": secrets_found,
                    "duration_seconds": duration,
                }

            except Exception as e:
                self._update_progress(
                    progress_callback,
                    IndexingProgress(
                        stage="failed",
                        error_message=str(e),
                    ),
                )
                logger.error(f"Repository indexing failed: {e}")
                raise

    def _clone_repository(self, git_url: str, access_token: str, branch: str, temp_dir: str) -> str:
        """
        Clone repository to temporary directory.

        Args:
            git_url: Git repository HTTPS URL
            access_token: Personal access token for authentication
            branch: Branch to clone
            temp_dir: Temporary directory for cloning

        Returns:
            Path to cloned repository
        """
        # Inject access token into URL
        if "https://" in git_url:
            # https://github.com/owner/repo.git
            # -> https://token@github.com/owner/repo.git
            auth_url = git_url.replace("https://", f"https://{access_token}@")
        else:
            auth_url = git_url

        clone_path = os.path.join(temp_dir, "repo")
        logger.info(f"Cloning repository: {git_url} -> {clone_path}")

        Repo.clone_from(
            auth_url,
            clone_path,
            branch=branch,
            depth=1,  # Shallow clone for faster indexing
        )

        return clone_path

    def _scan_files(self, root_path: str, depth: IndexDepth) -> list[str]:
        """
        Scan directory tree for indexable files.

        Args:
            root_path: Root directory to scan
            depth: Indexing mode (shallow or deep)

        Returns:
            List of file paths to index
        """
        files_to_index = []

        for root, dirs, files in os.walk(root_path):
            # Skip ignored directories
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIRECTORIES]

            for file in files:
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file)[1]

                if ext in self.INDEXABLE_EXTENSIONS:
                    files_to_index.append(file_path)

        return files_to_index

    def _chunk_content(self, content: str) -> list[str]:
        """
        Split file content into chunks for embedding.

        Args:
            content: File content to chunk

        Returns:
            List of content chunks
        """
        chunks = []
        start = 0

        while start < len(content):
            end = start + self.CHUNK_SIZE
            chunk = content[start:end]

            if chunk:
                chunks.append(chunk)

            start = end - self.CHUNK_OVERLAP

        return chunks

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

    def _update_progress(self, callback: typing.Callable | None, progress: IndexingProgress) -> None:
        """
        Update progress if callback provided.

        Args:
            callback: Optional progress callback function
            progress: Current indexing progress
        """
        if callback:
            callback(progress)


def create_indexing_service(supabase: Client, config: Config) -> IndexingService | None:
    """
    Factory function to create IndexingService with validation.

    Args:
        supabase: Supabase client instance
        config: Application configuration

    Returns:
        IndexingService instance if Supabase configured, None otherwise
    """
    if not supabase:
        logger.warning("Supabase client not configured, indexing disabled")
        return None

    return IndexingService(supabase, config)
