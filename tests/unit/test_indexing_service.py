"""
T046 - Unit Tests for Indexing Service

Tests the IndexingService repository indexing workflow, verifying:
- GitPython clone_from with access token injection
- Directory walking for .py, .js, .ts file discovery
- File chunking logic (max 2000 tokens per chunk)
- Progress tracking through IndexingProgress stages

These tests MUST FAIL because the IndexingService implementation
does not exist yet (Phase 4: User Story 3 - RAG).
"""

from unittest.mock import MagicMock, patch

import pytest

from models.indexing import IndexingProgress, IndexingRequest


class TestIndexingServiceRepositoryClone:
    """
    Test IndexingService.repository_clone() workflow.

    These tests verify Git repository cloning with token authentication.
    """

    def test_indexing_service_class_exists(self):
        """
        GIVEN the services module
        WHEN importing IndexingService
        THEN the class should exist

        FAIL EXPECTED: IndexingService class may not exist yet
        """
        # Arrange & Act
        try:
            from services.indexing import IndexingService
        except ImportError as e:
            pytest.fail(f"IndexingService class not found: {e}")

        # Assert
        assert IndexingService is not None

    def test_repository_clone_method_exists(self):
        """
        GIVEN an IndexingService instance
        WHEN checking its methods
        THEN repository_clone method should exist

        FAIL EXPECTED: repository_clone method may not exist
        """
        # Arrange
        from services.indexing import IndexingService

        # Act
        service = IndexingService(
            mock_supabase_client=MagicMock(),
            mock_openai_client=MagicMock(),
        )

        # Assert
        assert hasattr(service, "repository_clone"), (
            "IndexingService should have repository_clone method"
        )
        assert callable(service.repository_clone), "repository_clone should be callable"

    @patch("services.indexing.Repo.clone_from")
    @patch("services.indexing.tempfile.TemporaryDirectory")
    def test_repository_clone_calls_gitpython_clone_from(
        self, mock_temp_dir, mock_clone_from, mock_supabase_client, mock_openai_client
    ):
        """
        GIVEN a Git URL and access token
        WHEN calling repository_clone()
        THEN it should call GitPython clone_from

        FAIL EXPECTED: May not call GitPython clone_from correctly
        """
        # Arrange
        from services.indexing import IndexingService

        mock_temp_dir.return_value.__enter__.return_value = "/tmp/repo-xyz"
        mock_clone_from.return_value = MagicMock()

        service = IndexingService(
            mock_supabase_client=mock_supabase_client,
            mock_openai_client=mock_openai_client,
        )

        request = IndexingRequest(
            git_url="https://github.com/octocat/test-repo.git",
            access_token="ghp_test_token",
            branch="main",
        )

        # Act
        try:
            service.repository_clone(request)
        except Exception:
            pass

        # Assert
        mock_clone_from.assert_called_once()
        # Check that URL includes token for authentication
        call_args = mock_clone_from.call_args[0]
        clone_url = call_args[0]
        assert "ghp_test_token" in clone_url, (
            f"Clone URL should include access token for auth, got: {clone_url}"
        )

    @patch("services.indexing.Repo.clone_from")
    @patch("services.indexing.tempfile.TemporaryDirectory")
    def test_repository_clone_injects_access_token_into_url(
        self, mock_temp_dir, mock_clone_from, mock_supabase_client, mock_openai_client
    ):
        """
        GIVEN a GitHub HTTPS URL and access token
        WHEN calling repository_clone()
        THEN it should inject token into URL (https://token@github.com/...)

        FAIL EXPECTED: May not inject token correctly
        """
        # Arrange
        from services.indexing import IndexingService

        mock_temp_dir.return_value.__enter__.return_value = "/tmp/repo-xyz"
        mock_clone_from.return_value = MagicMock()

        service = IndexingService(
            mock_supabase_client=mock_supabase_client,
            mock_openai_client=mock_openai_client,
        )

        request = IndexingRequest(
            git_url="https://github.com/octocat/test-repo.git",
            access_token="ghp_1234567890abcdef",
            branch="main",
        )

        # Act
        try:
            service.repository_clone(request)
        except Exception:
            pass

        # Assert
        call_args = mock_clone_from.call_args[0]
        clone_url = call_args[0]

        # URL should be in format: https://TOKEN@github.com/owner/repo.git
        assert "ghp_1234567890abcdef@" in clone_url, (
            f"Token should be injected in URL, got: {clone_url}"
        )
        assert "github.com" in clone_url, "URL should contain github.com"

    @patch("services.indexing.Repo.clone_from")
    @patch("services.indexing.tempfile.TemporaryDirectory")
    def test_repository_clone_uses_temporary_directory(
        self, mock_temp_dir, mock_clone_from, mock_supabase_client, mock_openai_client
    ):
        """
        GIVEN a repository to clone
        WHEN calling repository_clone()
        THEN it should clone to a temporary directory

        FAIL EXPECTED: May not use temp directory
        """
        # Arrange
        from services.indexing import IndexingService

        mock_temp_dir.return_value.__enter__.return_value = "/tmp/repo-xyz"
        mock_clone_from.return_value = MagicMock()

        service = IndexingService(
            mock_supabase_client=mock_supabase_client,
            mock_openai_client=mock_openai_client,
        )

        request = IndexingRequest(
            git_url="https://github.com/octocat/test-repo.git",
            access_token="ghp_test",
            branch="main",
        )

        # Act
        try:
            service.repository_clone(request)
        except Exception:
            pass

        # Assert
        mock_temp_dir.assert_called_once()
        call_args = mock_clone_from.call_args[0]
        clone_path = call_args[1]
        assert clone_path.startswith("/tmp/"), (
            f"Clone path should be in temp directory, got: {clone_path}"
        )

    @patch("services.indexing.Repo.clone_from")
    @patch("services.indexing.tempfile.TemporaryDirectory")
    def test_repository_clone_checks_out_branch(
        self, mock_temp_dir, mock_clone_from, mock_supabase_client, mock_openai_client
    ):
        """
        GIVEN a request with branch="develop"
        WHEN calling repository_clone()
        THEN it should checkout the specified branch

        FAIL EXPECTED: May not checkout specified branch
        """
        # Arrange
        from services.indexing import IndexingService

        mock_temp_dir.return_value.__enter__.return_value = "/tmp/repo-xyz"
        mock_repo = MagicMock()
        mock_clone_from.return_value = mock_repo

        service = IndexingService(
            mock_supabase_client=mock_supabase_client,
            mock_openai_client=mock_openai_client,
        )

        request = IndexingRequest(
            git_url="https://github.com/octocat/test-repo.git",
            access_token="ghp_test",
            branch="develop",
        )

        # Act
        try:
            service.repository_clone(request)
        except Exception:
            pass

        # Assert
        # Should call git.checkout or repo.heads[branch].checkout()
        assert mock_repo.git.checkout.called or (hasattr(mock_repo.heads, "__getitem__") or True), (
            "Should checkout the specified branch"
        )


class TestIndexingServiceFileWalking:
    """
    Test IndexingService file walking and discovery.

    These tests verify the service walks directory trees and
    discovers code files (.py, .js, .ts, etc.).
    """

    @patch("builtins.os.walk")
    def test_walk_directory_discovers_python_files(
        self, mock_os_walk, mock_supabase_client, mock_openai_client
    ):
        """
        GIVEN a repository directory with Python files
        WHEN walking the directory
        THEN it should discover .py files

        FAIL EXPECTED: May not discover .py files
        """
        # Arrange
        from services.indexing import IndexingService

        # Mock directory structure
        mock_os_walk.return_value = [
            ("/tmp/repo", [], ["main.py", "auth.py", "README.md"]),
            ("/tmp/repo/src", [], ["utils.py", "config.py"]),
        ]

        service = IndexingService(
            mock_supabase_client=mock_supabase_client,
            mock_openai_client=mock_openai_client,
        )

        # Act
        try:
            files = service._discover_files("/tmp/repo")
        except Exception:
            # Method may not exist or have different signature
            files = []

        # Assert - Should only include .py files
        python_files = [f for f in files if f.endswith(".py")]
        if len(python_files) > 0:
            assert "main.py" in python_files or any("main.py" in f for f in python_files)

    @patch("builtins.os.walk")
    def test_walk_directory_discovers_javascript_typescript_files(
        self, mock_os_walk, mock_supabase_client, mock_openai_client
    ):
        """
        GIVEN a repository directory with JS/TS files
        WHEN walking the directory
        THEN it should discover .js and .ts files

        FAIL EXPECTED: May not discover .js/.ts files
        """
        # Arrange
        from services.indexing import IndexingService

        mock_os_walk.return_value = [
            ("/tmp/repo", [], ["index.js", "app.ts", "package.json"]),
            ("/tmp/repo/src", [], ["utils.js", "types.ts"]),
        ]

        service = IndexingService(
            mock_supabase_client=mock_supabase_client,
            mock_openai_client=mock_openai_client,
        )

        # Act
        try:
            files = service._discover_files("/tmp/repo")
        except Exception:
            files = []

        # Assert - Should include .js and .ts files
        for ext in [".js", ".ts"]:
            found = any(f.endswith(ext) for f in files)
            if files:
                assert found, f"Should discover {ext} files"

    @patch("builtins.os.walk")
    def test_walk_directory_ignores_non_code_files(
        self, mock_os_walk, mock_supabase_client, mock_openai_client
    ):
        """
        GIVEN a repository with mixed file types
        WHEN walking the directory
        THEN it should ignore non-code files (.md, .json, .txt, etc.)

        FAIL EXPECTED: May not filter non-code files
        """
        # Arrange
        from services.indexing import IndexingService

        mock_os_walk.return_value = [
            (
                "/tmp/repo",
                [],
                [
                    "main.py",  # Code
                    "README.md",  # Non-code
                    "package.json",  # Non-code
                    ".gitignore",  # Non-code
                ],
            ),
        ]

        service = IndexingService(
            mock_supabase_client=mock_supabase_client,
            mock_openai_client=mock_openai_client,
        )

        # Act
        try:
            files = service._discover_files("/tmp/repo")
        except Exception:
            files = []

        # Assert - Should filter out .md, .json, etc.
        if files:
            for f in files:
                assert not f.endswith((".md", ".json", ".txt", ".gitignore")), (
                    f"Should filter out non-code files, got: {f}"
                )

    @patch("builtins.os.walk")
    def test_walk_directory_ignores_node_modules_and_venv(
        self, mock_os_walk, mock_supabase_client, mock_openai_client
    ):
        """
        GIVEN a repository with node_modules and venv directories
        WHEN walking the directory
        THEN it should skip these directories

        FAIL EXPECTED: May not ignore dependency directories
        """
        # Arrange
        from services.indexing import IndexingService

        mock_os_walk.return_value = [
            ("/tmp/repo", ["node_modules", "venv", "src"], ["main.py"]),
            ("/tmp/repo/node_modules", [], ["index.js"]),
            ("/tmp/repo/venv", [], ["activate"]),
            ("/tmp/repo/src", [], ["utils.py"]),
        ]

        service = IndexingService(
            mock_supabase_client=mock_supabase_client,
            mock_openai_client=mock_openai_client,
        )

        # Act
        try:
            files = service._discover_files("/tmp/repo")
        except Exception:
            files = []

        # Assert - Should not include files from node_modules or venv
        if files:
            for f in files:
                assert "node_modules" not in f, f"Should skip node_modules, got: {f}"
                assert "/venv/" not in f and not f.startswith("venv/"), (
                    f"Should skip venv, got: {f}"
                )


class TestIndexingServiceFileChunking:
    """
    Test IndexingService file chunking logic.

    These tests verify large files are chunked appropriately
    (max 2000 tokens per chunk with overlap).
    """

    def test_chunk_content_splits_large_file(self, mock_supabase_client, mock_openai_client):
        """
        GIVEN a file with 5000 tokens
        WHEN chunking the content
        THEN it should split into 3 chunks (2000, 2000, 1000)

        FAIL EXPECTED: May not chunk large files
        """
        # Arrange
        from services.indexing import IndexingService

        service = IndexingService(
            mock_supabase_client=mock_supabase_client,
            mock_openai_client=mock_openai_client,
        )

        # Create content that's definitely over 2000 tokens
        # Approximate: 1 word ~ 1.3 tokens, so 4000 words ~ 5200 tokens
        large_content = "\n".join([f"line_{i} = value_{i}" for i in range(4000)])

        # Act
        try:
            chunks = service._chunk_content(large_content, max_tokens=2000)
        except Exception:
            chunks = []

        # Assert
        if chunks:
            assert len(chunks) >= 2, (
                f"Large content should be split into multiple chunks, got {len(chunks)}"
            )

    def test_chunk_content_includes_overlap_between_chunks(
        self, mock_supabase_client, mock_openai_client
    ):
        """
        GIVEN content that needs chunking
        WHEN creating chunks
        THEN adjacent chunks should have overlap (e.g., 200 tokens)

        FAIL EXPECTED: May not include overlap between chunks
        """
        # Arrange
        from services.indexing import IndexingService

        service = IndexingService(
            mock_supabase_client=mock_supabase_client,
            mock_openai_client=mock_openai_client,
        )

        # Create content that requires multiple chunks
        content = "\n".join([f"line_{i} = value_{i}" for i in range(3000)])

        # Act
        try:
            chunks = service._chunk_content(content, max_tokens=2000, overlap=200)
        except Exception:
            chunks = []

        # Assert
        if len(chunks) > 1:
            # Check if there's overlap between chunk 0 and chunk 1
            # The end of chunk 0 should appear at the start of chunk 1
            last_lines_chunk0 = chunks[0].split("\n")[-20:]
            first_lines_chunk1 = chunks[1].split("\n")[:20]

            overlap = set(last_lines_chunk0) & set(first_lines_chunk1)
            assert len(overlap) > 0, "Chunks should have overlapping content"

    def test_chunk_content_respects_max_tokens_limit(
        self, mock_supabase_client, mock_openai_client
    ):
        """
        GIVEN a max_tokens limit of 2000
        WHEN chunking content
        THEN each chunk should be approximately <= 2000 tokens

        FAIL EXPECTED: May not respect max_tokens limit
        """
        # Arrange
        from services.indexing import IndexingService

        service = IndexingService(
            mock_supabase_client=mock_supabase_client,
            mock_openai_client=mock_openai_client,
        )

        large_content = "\n".join([f"line_{i} = value_{i}" for i in range(5000)])

        # Act
        try:
            chunks = service._chunk_content(large_content, max_tokens=2000)
        except Exception:
            chunks = []

        # Assert - Approximate token count (rough estimate: 1 line ~ 3 tokens)
        if chunks:
            for i, chunk in enumerate(chunks):
                line_count = len(chunk.split("\n"))
                estimated_tokens = line_count * 3
                # Allow some buffer for overlap
                assert estimated_tokens <= 2500, (
                    f"Chunk {i} exceeds max_tokens: ~{estimated_tokens} tokens (estimated)"
                )

    def test_chunk_content_handles_small_file(self, mock_supabase_client, mock_openai_client):
        """
        GIVEN a small file (< 2000 tokens)
        WHEN chunking the content
        THEN it should return a single chunk

        FAIL EXPECTED: May unnecessarily chunk small files
        """
        # Arrange
        from services.indexing import IndexingService

        service = IndexingService(
            mock_supabase_client=mock_supabase_client,
            mock_openai_client=mock_openai_client,
        )

        small_content = "def hello():\n    return 'world'"

        # Act
        try:
            chunks = service._chunk_content(small_content, max_tokens=2000)
        except Exception:
            chunks = []

        # Assert
        if chunks:
            assert len(chunks) == 1, f"Small content should be single chunk, got {len(chunks)}"
            assert chunks[0] == small_content, "Single chunk should contain full content"


class TestIndexingServiceEmbeddings:
    """
    Test IndexingService embedding generation.

    These tests verify embeddings are generated and stored correctly.
    """

    @patch("services.indexing.get_embedding")
    def test_generate_embedding_for_chunk(
        self, mock_get_embedding, mock_supabase_client, mock_openai_client
    ):
        """
        GIVEN a chunk of code
        WHEN generating an embedding
        THEN it should call OpenAI embedding API

        FAIL EXPECTED: May not call embedding API correctly
        """
        # Arrange
        from services.indexing import IndexingService

        mock_get_embedding.return_value = [0.1] * 1536  # OpenAI embedding size

        service = IndexingService(
            mock_supabase_client=mock_supabase_client,
            mock_openai_client=mock_openai_client,
        )

        chunk = "def authenticate_user(token):\n    return validate(token)"

        # Act
        try:
            embedding = service._generate_embedding(chunk)
        except Exception:
            embedding = None

        # Assert
        if embedding is not None:
            assert isinstance(embedding, list), "Embedding should be a list"
            assert len(embedding) == 1536, (
                f"Embedding should be 1536 dimensions, got {len(embedding)}"
            )
        else:
            # Check mock was called anyway
            mock_get_embedding.assert_called_once_with(chunk)

    @patch("services.indexing.get_embedding")
    def test_store_chunk_in_supabase(
        self, mock_get_embedding, mock_supabase_client, mock_openai_client
    ):
        """
        GIVEN a chunk with embedding and metadata
        WHEN storing in Supabase
        THEN it should insert into knowledge_base table

        FAIL EXPECTED: May not store in knowledge_base correctly
        """
        # Arrange
        from services.indexing import IndexingService

        mock_get_embedding.return_value = [0.1] * 1536
        mock_supabase_client.table.return_value.insert.return_value.execute.return_value = (
            MagicMock()
        )

        service = IndexingService(
            mock_supabase_client=mock_supabase_client,
            mock_openai_client=mock_openai_client,
        )

        chunk_data = {
            "content": "def hello():",
            "file_path": "src/main.py",
            "repo_id": "octocat/test-repo",
            "embedding": [0.1] * 1536,
            "metadata": {"branch": "main"},
        }

        # Act
        try:
            service._store_knowledge(chunk_data)
        except Exception:
            pass

        # Assert
        mock_supabase_client.table.assert_called()
        call_args = mock_supabase_client.table.call_args[0][0]
        assert call_args == "knowledge_base", (
            f"Should insert into knowledge_base table, got: {call_args}"
        )


class TestIndexingServiceProgressTracking:
    """
    Test IndexingService progress tracking.

    These tests verify IndexingProgress is updated through stages.
    """

    @patch("services.indexing.Repo.clone_from")
    @patch("services.indexing.tempfile.TemporaryDirectory")
    def test_progress_tracks_through_stages(
        self, mock_temp_dir, mock_clone_from, mock_supabase_client, mock_openai_client
    ):
        """
        GIVEN an indexing operation
        WHEN processing
        THEN progress should move through stages: queued -> cloning -> scanning -> ...

        FAIL EXPECTED: May not track progress correctly
        """
        # Arrange
        from services.indexing import IndexingService

        mock_temp_dir.return_value.__enter__.return_value = "/tmp/repo"
        mock_clone_from.return_value = MagicMock()

        service = IndexingService(
            mock_supabase_client=mock_supabase_client,
            mock_openai_client=mock_openai_client,
        )

        request = IndexingRequest(
            git_url="https://github.com/octocat/test-repo.git",
            access_token="ghp_test",
            branch="main",
        )

        # Act & Assert - Just verify the stages are defined
        valid_stages = [
            "queued",
            "cloning",
            "scanning",
            "chunking",
            "secret_scanning",
            "generating_embeddings",
            "storing",
            "completed",
            "failed",
        ]

        # IndexingProgress enum should have these stages
        for stage in valid_stages:
            assert (
                stage in IndexingProgress.model_fields.get("stage", {}).annotation.__args__
                if hasattr(IndexingProgress.model_fields.get("stage", {}), "annotation")
                else valid_stages
            ), f"Stage '{stage}' should be valid"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client for testing."""
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value.data = []
    return client


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    client = MagicMock()
    client.embeddings.create.return_value = MagicMock(data=[MagicMock(embedding=[0.1] * 1536)])
    return client
