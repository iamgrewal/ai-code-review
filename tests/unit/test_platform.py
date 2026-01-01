"""
T030 - Unit Tests for PRMetadata Model

Tests the PRMetadata model validation with valid/invalid data,
required fields, SHA validation (40 chars), and enum validation
(platform, source).

These tests MUST FAIL because they test against the contract
defined in models/platform.py. Any failures indicate the model
does not meet the specification.
"""

import pytest
from pydantic import ValidationError

from models.platform import PRMetadata, ReviewStatus, Severity


class TestPRMetadataValidation:
    """
    Test PRMetadata model validation.

    These tests verify the model contract for webhook payload
    normalization across GitHub and Gitea platforms.
    """

    # -------------------------------------------------------------------------
    # Valid Data Tests (SHOULD PASS)
    # -------------------------------------------------------------------------

    def test_valid_pr_metadata_with_all_fields(self):
        """
        GIVEN a valid PRMetadata with all fields
        WHEN creating the model
        THEN it should validate successfully
        """
        # Arrange & Act
        metadata = PRMetadata(
            repo_id="octocat/test-repo",
            pr_number=42,
            base_sha="a" * 40,
            head_sha="b" * 40,
            author="octocat",
            platform="github",
            title="Add new feature",
            source="webhook",
            callback_url="https://example.com/callback",
        )

        # Assert
        assert metadata.repo_id == "octocat/test-repo"
        assert metadata.pr_number == 42
        assert metadata.base_sha == "a" * 40
        assert metadata.head_sha == "b" * 40
        assert metadata.author == "octocat"
        assert metadata.platform == "github"
        assert metadata.title == "Add new feature"
        assert metadata.source == "webhook"
        assert metadata.callback_url == "https://example.com/callback"

    def test_valid_pr_metadata_minimal_fields(self):
        """
        GIVEN a valid PRMetadata with only required fields
        WHEN creating the model
        THEN it should validate with default values
        """
        # Arrange & Act
        metadata = PRMetadata(
            repo_id="octocat/test-repo",
            pr_number=1,  # Minimum valid pr_number per spec (ge=1)
            base_sha="a" * 40,
            head_sha="b" * 40,
            platform="gitea",
        )

        # Assert
        assert metadata.repo_id == "octocat/test-repo"
        assert metadata.pr_number == 1
        assert metadata.author is None  # Optional field
        assert metadata.title is None  # Optional field
        assert metadata.source == "webhook"  # Default value
        assert metadata.callback_url is None  # Optional field

    def test_valid_sha_exactly_40_characters(self):
        """
        GIVEN a SHA with exactly 40 hexadecimal characters
        WHEN creating the model
        THEN it should validate successfully
        """
        # Arrange
        valid_sha = "1a2b3c4d5e6f7890abcdef1234567890abcdef12"

        # Act
        metadata = PRMetadata(
            repo_id="octocat/test-repo",
            pr_number=1,
            base_sha=valid_sha,
            head_sha=valid_sha.upper(),
            platform="github",
        )

        # Assert
        assert len(metadata.base_sha) == 40
        assert len(metadata.head_sha) == 40

    def test_valid_platform_enum_values(self):
        """
        GIVEN valid platform enum values
        WHEN creating the model
        THEN both 'github' and 'gitea' should be accepted
        """
        # Arrange & Act
        metadata_github = PRMetadata(
            repo_id="octocat/test-repo",
            pr_number=1,
            base_sha="a" * 40,
            head_sha="b" * 40,
            platform="github",
        )

        metadata_gitea = PRMetadata(
            repo_id="octocat/test-repo",
            pr_number=1,
            base_sha="a" * 40,
            head_sha="b" * 40,
            platform="gitea",
        )

        # Assert
        assert metadata_github.platform == "github"
        assert metadata_gitea.platform == "gitea"

    def test_valid_source_enum_values(self):
        """
        GIVEN valid source enum values
        WHEN creating the model
        THEN 'webhook', 'cli', and 'mcp' should all be accepted
        """
        # Arrange
        base_data = {
            "repo_id": "octocat/test-repo",
            "pr_number": 1,
            "base_sha": "a" * 40,
            "head_sha": "b" * 40,
            "platform": "github",
        }

        # Act & Assert
        for source in ["webhook", "cli", "mcp"]:
            metadata = PRMetadata(**base_data, source=source)
            assert metadata.source == source

    def test_pr_number_zero_is_rejected(self):
        """
        GIVEN a push event (not a PR)
        WHEN creating the model with pr_number=0
        THEN it should raise ValidationError (pr_number must be >= 1 per spec)
        """
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            PRMetadata(
                repo_id="octocat/test-repo",
                pr_number=0,
                base_sha="a" * 40,
                head_sha="b" * 40,
                platform="gitea",
            )

        # Assert error message mentions the constraint
        assert "greater than or equal to 1" in str(exc_info.value)

    def test_model_is_frozen_immutable(self):
        """
        GIVEN a PRMetadata instance
        WHEN attempting to modify a field
        THEN it should raise an error (frozen model)
        """
        # Arrange
        metadata = PRMetadata(
            repo_id="octocat/test-repo",
            pr_number=42,
            base_sha="a" * 40,
            head_sha="b" * 40,
            platform="github",
        )

        # Act & Assert
        with pytest.raises(Exception):  # TypeError for frozen models
            metadata.repo_id = "different/repo"

    # -------------------------------------------------------------------------
    # Invalid Data Tests (SHOULD FAIL - These verify the contract)
    # -------------------------------------------------------------------------

    def test_missing_required_field_repo_id(self):
        """
        GIVEN a PRMetadata without repo_id
        WHEN creating the model
        THEN it should raise ValidationError

        FAIL EXPECTED: Validates required field constraint
        """
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            PRMetadata(
                # repo_id missing
                pr_number=42,
                base_sha="a" * 40,
                head_sha="b" * 40,
                platform="github",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("repo_id",) for e in errors)

    def test_missing_required_field_pr_number(self):
        """
        GIVEN a PRMetadata without pr_number
        WHEN creating the model
        THEN it should raise ValidationError

        FAIL EXPECTED: Validates required field constraint
        """
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            PRMetadata(
                repo_id="octocat/test-repo",
                # pr_number missing
                base_sha="a" * 40,
                head_sha="b" * 40,
                platform="github",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("pr_number",) for e in errors)

    def test_missing_required_field_base_sha(self):
        """
        GIVEN a PRMetadata without base_sha
        WHEN creating the model
        THEN it should raise ValidationError

        FAIL EXPECTED: Validates required field constraint
        """
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            PRMetadata(
                repo_id="octocat/test-repo",
                pr_number=42,
                # base_sha missing
                head_sha="b" * 40,
                platform="github",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("base_sha",) for e in errors)

    def test_missing_required_field_head_sha(self):
        """
        GIVEN a PRMetadata without head_sha
        WHEN creating the model
        THEN it should raise ValidationError

        FAIL EXPECTED: Validates required field constraint
        """
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            PRMetadata(
                repo_id="octocat/test-repo",
                pr_number=42,
                base_sha="a" * 40,
                # head_sha missing
                platform="github",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("head_sha",) for e in errors)

    def test_missing_required_field_platform(self):
        """
        GIVEN a PRMetadata without platform
        WHEN creating the model
        THEN it should raise ValidationError

        FAIL EXPECTED: Validates required field constraint
        """
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            PRMetadata(
                repo_id="octocat/test-repo",
                pr_number=42,
                base_sha="a" * 40,
                head_sha="b" * 40,
                # platform missing
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("platform",) for e in errors)

    def test_invalid_sha_too_short(self):
        """
        GIVEN a SHA with less than 40 characters
        WHEN creating the model
        THEN it should raise ValidationError

        FAIL EXPECTED: Validates SHA length constraint (min_length=40)
        """
        # Arrange
        short_sha = "a" * 39

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            PRMetadata(
                repo_id="octocat/test-repo",
                pr_number=42,
                base_sha=short_sha,
                head_sha="b" * 40,
                platform="github",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("base_sha",) for e in errors)

    def test_invalid_sha_too_long(self):
        """
        GIVEN a SHA with more than 40 characters
        WHEN creating the model
        THEN it should raise ValidationError

        FAIL EXPECTED: Validates SHA length constraint (max_length=40)
        """
        # Arrange
        long_sha = "a" * 41

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            PRMetadata(
                repo_id="octocat/test-repo",
                pr_number=42,
                base_sha=long_sha,
                head_sha="b" * 40,
                platform="github",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("base_sha",) for e in errors)

    def test_invalid_platform_value(self):
        """
        GIVEN an invalid platform value
        WHEN creating the model
        THEN it should raise ValidationError

        FAIL EXPECTED: Validates platform enum constraint
        """
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            PRMetadata(
                repo_id="octocat/test-repo",
                pr_number=42,
                base_sha="a" * 40,
                head_sha="b" * 40,
                platform="gitlab",  # Invalid platform
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("platform",) for e in errors)

    def test_invalid_source_value(self):
        """
        GIVEN an invalid source value
        WHEN creating the model
        THEN it should raise ValidationError

        FAIL EXPECTED: Validates source enum constraint
        """
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            PRMetadata(
                repo_id="octocat/test-repo",
                pr_number=42,
                base_sha="a" * 40,
                head_sha="b" * 40,
                platform="github",
                source="api",  # Invalid source
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("source",) for e in errors)

    def test_pr_number_negative(self):
        """
        GIVEN a negative pr_number
        WHEN creating the model
        THEN it should raise ValidationError

        FAIL EXPECTED: Validates pr_number constraint (ge=1)
        """
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            PRMetadata(
                repo_id="octocat/test-repo",
                pr_number=-1,  # Negative
                base_sha="a" * 40,
                head_sha="b" * 40,
                platform="github",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("pr_number",) for e in errors)


class TestSeverityEnum:
    """Test Severity enum validation."""

    def test_all_severity_values(self):
        """
        GIVEN the Severity enum
        WHEN accessing all values
        THEN they should match the specification
        """
        # Assert
        assert Severity.NIT.value == "nit"
        assert Severity.LOW.value == "low"
        assert Severity.MEDIUM.value == "medium"
        assert Severity.HIGH.value == "high"
        assert Severity.CRITICAL.value == "critical"


class TestReviewStatusEnum:
    """Test ReviewStatus enum validation."""

    def test_all_status_values(self):
        """
        GIVEN the ReviewStatus enum
        WHEN accessing all values
        THEN they should match the specification
        """
        # Assert
        assert ReviewStatus.QUEUED.value == "queued"
        assert ReviewStatus.PROCESSING.value == "processing"
        assert ReviewStatus.COMPLETED.value == "completed"
        assert ReviewStatus.FAILED.value == "failed"
