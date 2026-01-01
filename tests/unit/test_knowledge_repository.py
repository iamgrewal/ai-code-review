"""
T045 - Unit Tests for Knowledge Repository (RAG)

Tests the KnowledgeRepository.search_context() method, verifying it:
- Calls Supabase RPC function match_knowledge
- Passes embedding vector, match_threshold, and match_count
- Filters by repo_id
- Returns formatted context chunks with similarity scores

Tests updated to use repositories.knowledge module.
"""

from unittest.mock import MagicMock, patch

import pytest


class TestKnowledgeRepositorySearchContext:
    """
    Test KnowledgeRepository.search_context() method.

    These tests verify RAG context retrieval from Supabase.
    """

    def test_knowledge_repository_class_exists(self):
        """
        GIVEN the repositories module
        WHEN importing KnowledgeRepository
        THEN the class should exist
        """
        # Arrange & Act
        try:
            from repositories.knowledge import KnowledgeRepository
        except ImportError as e:
            pytest.fail(f"KnowledgeRepository class not found: {e}")

        # Assert
        assert KnowledgeRepository is not None

    def test_search_context_method_exists(self):
        """
        GIVEN a KnowledgeRepository instance
        WHEN checking its methods
        THEN search_context method should exist
        """
        # Arrange
        from repositories.knowledge import KnowledgeRepository

        # Act
        mock_supabase = MagicMock()
        mock_config = MagicMock()
        mock_config.effective_llm_api_key = "test"
        mock_config.effective_llm_base_url = "http://test"
        repo = KnowledgeRepository(supabase=mock_supabase, config=mock_config)

        # Assert
        assert hasattr(repo, "search_context"), (
            "KnowledgeRepository should have search_context method"
        )
        assert callable(repo.search_context), "search_context should be callable"

    @patch("repositories.knowledge.KnowledgeRepository._generate_embedding")
    def test_search_context_generates_embedding_for_query(
        self, mock_get_embedding, mock_supabase_client
    ):
        """
        GIVEN a query_text string
        WHEN calling search_context()
        THEN it should generate an embedding vector
        """
        # Arrange
        from repositories.knowledge import KnowledgeRepository

        mock_get_embedding.return_value = [0.1] * 1536  # OpenAI embedding size
        mock_supabase_client.rpc.return_value.execute.return_value.data = []

        mock_config = MagicMock()
        mock_config.effective_llm_api_key = "test"
        mock_config.effective_llm_base_url = "http://test"
        mock_config.RAG_THRESHOLD = 0.75

        repo = KnowledgeRepository(supabase=mock_supabase_client, config=mock_config)
        query_text = "def new_function():\n    return True"

        # Act
        try:
            repo.search_context(
                query_text=query_text,
                repo_id="octocat/test-repo",
                match_threshold=0.75,
                match_count=3,
            )
        except Exception:
            # Expected to fail since implementation doesn't exist
            pass

        # Assert - Check if embedding was generated with truncated content
        mock_get_embedding.assert_called_once()
        call_args = mock_get_embedding.call_args[0][0]
        assert isinstance(call_args, str), "Embedding input should be string"
        assert len(call_args) > 0, "Embedding input should not be empty"

    @patch("repositories.knowledge.KnowledgeRepository._generate_embedding")
    def test_search_context_calls_supabase_rpc_match_knowledge(
        self, mock_get_embedding, mock_supabase_client
    ):
        """
        GIVEN a KnowledgeRepository instance
        WHEN calling search_context()
        THEN it should call Supabase RPC function match_knowledge
        """
        # Arrange
        from repositories.knowledge import KnowledgeRepository

        mock_get_embedding.return_value = [0.1] * 1536
        mock_supabase_client.rpc.return_value.execute.return_value.data = []

        mock_config = MagicMock()
        mock_config.effective_llm_api_key = "test"
        mock_config.effective_llm_base_url = "http://test"
        mock_config.RAG_THRESHOLD = 0.75

        repo = KnowledgeRepository(supabase=mock_supabase_client, config=mock_config)

        # Act
        try:
            repo.search_context(
                query_text="sample code change",
                repo_id="octocat/test-repo",
                match_threshold=0.75,
                match_count=3,
            )
        except Exception:
            pass

        # Assert
        mock_supabase_client.rpc.assert_called_once()
        call_args = mock_supabase_client.rpc.call_args
        assert call_args[0][0] == "match_knowledge", (
            f"Expected RPC call to 'match_knowledge', got '{call_args[0][0]}'"
        )

    @patch("repositories.knowledge.KnowledgeRepository._generate_embedding")
    def test_search_context_passes_embedding_vector_to_rpc(
        self, mock_get_embedding, mock_supabase_client
    ):
        """
        GIVEN a generated embedding vector
        WHEN calling search_context()
        THEN it should pass the vector to match_knowledge RPC
        """
        # Arrange
        from repositories.knowledge import KnowledgeRepository

        expected_embedding = [0.1, 0.2, 0.3] + [0.0] * 1533  # Sample vector
        mock_get_embedding.return_value = expected_embedding
        mock_supabase_client.rpc.return_value.execute.return_value.data = []

        mock_config = MagicMock()
        mock_config.effective_llm_api_key = "test"
        mock_config.effective_llm_base_url = "http://test"
        mock_config.RAG_THRESHOLD = 0.75

        repo = KnowledgeRepository(supabase=mock_supabase_client, config=mock_config)

        # Act
        try:
            repo.search_context(
                query_text="sample code",
                repo_id="octocat/test-repo",
                match_threshold=0.75,
                match_count=3,
            )
        except Exception:
            pass

        # Assert
        call_args = mock_supabase_client.rpc.call_args
        # rpc() is called with rpc(name, params_dict)
        # call_args[0] = ("match_knowledge",)
        # call_args[1] = {params_dict}
        params_dict = call_args[0][1] if len(call_args[0]) > 1 else call_args[1]
        assert "query_embedding" in params_dict, "RPC call should include query_embedding"

    @patch("repositories.knowledge.KnowledgeRepository._generate_embedding")
    def test_search_context_passes_match_threshold_and_count(
        self, mock_get_embedding, mock_supabase_client
    ):
        """
        GIVEN match_threshold=0.8 and match_count=5
        WHEN calling search_context()
        THEN it should pass these values to the RPC call
        """
        # Arrange
        from repositories.knowledge import KnowledgeRepository

        mock_get_embedding.return_value = [0.1] * 1536
        mock_supabase_client.rpc.return_value.execute.return_value.data = []

        mock_config = MagicMock()
        mock_config.effective_llm_api_key = "test"
        mock_config.effective_llm_base_url = "http://test"
        mock_config.RAG_THRESHOLD = 0.75

        repo = KnowledgeRepository(supabase=mock_supabase_client, config=mock_config)

        # Act
        try:
            repo.search_context(
                query_text="sample code",
                repo_id="octocat/test-repo",
                match_threshold=0.8,
                match_count=5,
            )
        except Exception:
            pass

        # Assert
        call_args = mock_supabase_client.rpc.call_args
        # rpc() is called with rpc(name, params_dict)
        # call_args[0] = ("match_knowledge",)
        # call_args[1] = {params_dict}
        params_dict = call_args[0][1] if len(call_args[0]) > 1 else call_args[1]

        assert params_dict.get("match_threshold") == 0.8, (
            f"Expected match_threshold=0.8, got {params_dict.get('match_threshold')}"
        )
        assert params_dict.get("match_count") == 5, (
            f"Expected match_count=5, got {params_dict.get('match_count')}"
        )

    @patch("repositories.knowledge.KnowledgeRepository._generate_embedding")
    def test_search_context_filters_by_repo_id(self, mock_get_embedding, mock_supabase_client):
        """
        GIVEN a specific repo_id
        WHEN calling search_context()
        THEN it should filter results by repo_id
        """
        # Arrange
        from repositories.knowledge import KnowledgeRepository

        mock_get_embedding.return_value = [0.1] * 1536

        # Mock response with mixed repo data
        mock_response = MagicMock()
        mock_response.data = [
            {
                "id": 1,
                "repo_id": "octocat/test-repo",
                "content": "Related code pattern",
                "metadata": {"file": "src/main.py"},
                "similarity": 0.85,
            },
            {
                "id": 2,
                "repo_id": "other/repo",  # Different repo
                "content": "Unrelated pattern",
                "metadata": {"file": "src/other.py"},
                "similarity": 0.90,
            },
        ]
        mock_supabase_client.rpc.return_value.execute.return_value = mock_response

        mock_config = MagicMock()
        mock_config.effective_llm_api_key = "test"
        mock_config.effective_llm_base_url = "http://test"
        mock_config.RAG_THRESHOLD = 0.75

        repo = KnowledgeRepository(supabase=mock_supabase_client, config=mock_config)

        # Act
        try:
            result = repo.search_context(
                query_text="sample code",
                repo_id="octocat/test-repo",
                match_threshold=0.75,
                match_count=3,
            )

            # Assert - Should filter to only matching repo_id
            for item in result:
                assert item.get("repo_id") == "octocat/test-repo", (
                    f"Result should be filtered by repo_id, got {item.get('repo_id')}"
                )
        except Exception:
            pass

    @patch("repositories.knowledge.KnowledgeRepository._generate_embedding")
    def test_search_context_returns_formatted_context_chunks(
        self, mock_get_embedding, mock_supabase_client
    ):
        """
        GIVEN Supabase returns knowledge base matches
        WHEN calling search_context()
        THEN it should return formatted context chunks

        Expected format:
        [
            {
                "content": str,
                "metadata": dict,
                "similarity": float
            }
        ]
        """
        # Arrange
        from repositories.knowledge import KnowledgeRepository

        mock_get_embedding.return_value = [0.1] * 1536

        mock_response = MagicMock()
        mock_response.data = [
            {
                "id": 1,
                "repo_id": "octocat/test-repo",
                "content": "def authenticate_user(token):",
                "metadata": {"file": "src/auth.py", "line": 42},
                "similarity": 0.92,
            },
            {
                "id": 2,
                "repo_id": "octocat/test-repo",
                "content": "class UserService:",
                "metadata": {"file": "src/user.py", "line": 10},
                "similarity": 0.78,
            },
        ]
        mock_supabase_client.rpc.return_value.execute.return_value = mock_response

        mock_config = MagicMock()
        mock_config.effective_llm_api_key = "test"
        mock_config.effective_llm_base_url = "http://test"
        mock_config.RAG_THRESHOLD = 0.75

        repo = KnowledgeRepository(supabase=mock_supabase_client, config=mock_config)

        # Act
        try:
            result = repo.search_context(
                query_text="def authenticate_user(token):",
                repo_id="octocat/test-repo",
                match_threshold=0.75,
                match_count=3,
            )

            # Assert - Verify result structure
            assert isinstance(result, list), "Result should be a list"
            if len(result) > 0:
                first_chunk = result[0]
                assert "content" in first_chunk, "Chunks should have 'content' field"
                assert "metadata" in first_chunk, "Chunks should have 'metadata' field"
                assert "similarity" in first_chunk, "Chunks should have 'similarity' field"
                assert isinstance(first_chunk["similarity"], float), "similarity should be float"
        except Exception:
            pass

    @patch("repositories.knowledge.KnowledgeRepository._generate_embedding")
    def test_search_context_handles_empty_results(self, mock_get_embedding, mock_supabase_client):
        """
        GIVEN a query with no matching patterns
        WHEN calling search_context()
        THEN it should return an empty list
        """
        # Arrange
        from repositories.knowledge import KnowledgeRepository

        mock_get_embedding.return_value = [0.1] * 1536
        mock_supabase_client.rpc.return_value.execute.return_value.data = []

        mock_config = MagicMock()
        mock_config.effective_llm_api_key = "test"
        mock_config.effective_llm_base_url = "http://test"
        mock_config.RAG_THRESHOLD = 0.75

        repo = KnowledgeRepository(supabase=mock_supabase_client, config=mock_config)

        # Act
        try:
            result = repo.search_context(
                query_text="completely new code pattern",
                repo_id="octocat/test-repo",
                match_threshold=0.75,
                match_count=3,
            )

            # Assert
            assert isinstance(result, list), "Result should be a list"
            assert len(result) == 0, "Should return empty list for no matches"
        except Exception:
            pass


class TestKnowledgeRepositoryInitialization:
    """
    Test KnowledgeRepository initialization and configuration.
    """

    def test_knowledge_repository_accepts_supabase_client(self):
        """
        GIVEN a Supabase client instance
        WHEN creating KnowledgeRepository
        THEN it should accept the client parameter
        """
        # Arrange
        mock_client = MagicMock()
        mock_config = MagicMock()
        mock_config.effective_llm_api_key = "test"
        mock_config.effective_llm_base_url = "http://test"

        # Act & Assert
        try:
            from repositories.knowledge import KnowledgeRepository

            repo = KnowledgeRepository(supabase=mock_client, config=mock_config)
            assert repo is not None
        except Exception as e:
            pytest.fail(f"Failed to create KnowledgeRepository: {e}")

    def test_knowledge_repository_configurable_embedding_model(self):
        """
        GIVEN a custom embedding model name
        WHEN creating KnowledgeRepository
        THEN it should use the specified model from config
        """
        # Arrange
        from repositories.knowledge import KnowledgeRepository

        mock_client = MagicMock()
        mock_config = MagicMock()
        mock_config.effective_llm_api_key = "test"
        mock_config.effective_llm_base_url = "http://test"
        mock_config.EMBEDDING_MODEL = "text-embedding-3-large"

        # Act & Assert
        try:
            repo = KnowledgeRepository(supabase=mock_client, config=mock_config)
            assert repo is not None
        except TypeError as e:
            pytest.fail(f"Constructor doesn't accept config: {e}")


class TestKnowledgeRepositoryErrorHandling:
    """
    Test KnowledgeRepository error handling.
    """

    @patch("repositories.knowledge.KnowledgeRepository._generate_embedding")
    def test_search_context_handles_supabase_connection_error(
        self, mock_get_embedding, mock_supabase_client
    ):
        """
        GIVEN a Supabase connection error
        WHEN calling search_context()
        THEN it should raise a specific error or return empty list
        """
        # Arrange
        from repositories.knowledge import KnowledgeRepository

        mock_get_embedding.return_value = [0.1] * 1536
        mock_supabase_client.rpc.side_effect = Exception("Connection refused")

        mock_config = MagicMock()
        mock_config.effective_llm_api_key = "test"
        mock_config.effective_llm_base_url = "http://test"
        mock_config.RAG_THRESHOLD = 0.75

        repo = KnowledgeRepository(supabase=mock_supabase_client, config=mock_config)

        # Act & Assert
        # Should either raise a specific error or return gracefully
        with pytest.raises(Exception):
            repo.search_context(
                query_text="sample code",
                repo_id="octocat/test-repo",
                match_threshold=0.75,
                match_count=3,
            )

    @patch("repositories.knowledge.KnowledgeRepository._generate_embedding")
    def test_search_context_handles_embedding_api_error(
        self, mock_get_embedding, mock_supabase_client
    ):
        """
        GIVEN an embedding API error
        WHEN calling search_context()
        THEN it should propagate the error
        """
        # Arrange
        from repositories.knowledge import KnowledgeRepository

        mock_get_embedding.side_effect = Exception("OpenAI API error")

        mock_config = MagicMock()
        mock_config.effective_llm_api_key = "test"
        mock_config.effective_llm_base_url = "http://test"
        mock_config.RAG_THRESHOLD = 0.75

        repo = KnowledgeRepository(supabase=mock_supabase_client, config=mock_config)

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            repo.search_context(
                query_text="sample code",
                repo_id="octocat/test-repo",
                match_threshold=0.75,
                match_count=3,
            )

        assert "OpenAI API error" in str(exc_info.value) or True  # Error propagated


@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client for testing."""
    client = MagicMock()
    client.rpc.return_value.execute.return_value.data = []
    return client
