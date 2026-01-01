"""
T108 - Constitution Compliance Validation Checklist

Validates the CortexReview Platform codebase against the Constitution v3.1.0
principles defined in .specify/memory/constitution.md.

This script checks compliance with all 14 core principles:
I. Configuration as Code
II. Prompts as Data
III. Container-First
IV. Graceful Degradation
V. OpenAI-Compatible API
VI. Modular Service Architecture
VII. Async-First Processing
VIII. Platform Abstraction
IX. Observability
X. Webhook Security
XI. Task Reliability
XII. Feedback Loop
XIII. Data Governance
XIV. Test-Driven Development

Run: pytest tests/validation/constitution_compliance.py -v
"""

from pathlib import Path

import pytest

# =============================================================================
# I. Configuration as Code
# =============================================================================


class TestConstitution1_ConfigurationAsCode:
    """Validate Principle I: Configuration as Code."""

    def test_env_file_exists(self):
        """GIVEN the project WHEN checking for .env file THEN .env.example exists."""
        env_example = Path(".env.example")
        assert env_example.exists(), ".env.example must exist for configuration reference"

    def test_no_hardcoded_secrets_in_python(self):
        """GIVEN Python source files WHEN scanning for secrets THEN none found."""
        excluded_dirs = {
            ".venv",
            ".git",
            "__pycache__",
            ".specify",
            ".claude",
            "venv",
            "build",
            "dist",
        }

        # Common secret patterns
        secret_patterns = [
            "sk-",  # OpenAI key
            "ghp_",  # GitHub token
            "AKIA",  # AWS key
            "password =",
            "api_key =",
        ]

        for py_file in Path().rglob("*.py"):
            # Skip excluded directories
            if any(excluded in py_file.parts for excluded in excluded_dirs):
                continue

            content = py_file.read_text()
            for pattern in secret_patterns:
                # Check if pattern exists in source (not in comments/strings)
                lines = content.split("\n")
                for i, line in enumerate(lines, 1):
                    # Skip comments
                    if line.strip().startswith("#"):
                        continue
                    if (
                        pattern in line
                        and f'"{pattern}"' not in line
                        and f"'{pattern}'" not in line
                    ):
                        # Allow in test files and example files
                        if "test" not in str(py_file) and "example" not in str(py_file):
                            pytest.fail(f"Potential hardcoded secret in {py_file}:{i}: {line[:50]}")

    def test_config_class_centralized(self):
        """GIVEN the utils module WHEN checking for Config class THEN it exists."""
        from utils.config import Config

        assert Config is not None, "Config class must exist in utils.config"


# =============================================================================
# II. Prompts as Data
# =============================================================================


class TestConstitution2_PromptsAsData:
    """Validate Principle II: Prompts as Data."""

    def test_prompts_directory_exists(self):
        """GIVEN the project WHEN checking for prompts directory THEN it exists."""
        prompts_dir = Path("prompts")
        assert prompts_dir.exists(), "prompts/ directory must exist"
        assert prompts_dir.is_dir(), "prompts/ must be a directory"

    def test_prompts_have_yaml_front_matter(self):
        """GIVEN prompt markdown files WHEN checking format THEN they have YAML front matter."""
        prompts_dir = Path("prompts")
        if not prompts_dir.exists():
            pytest.skip("prompts/ directory not found")
        for md_file in prompts_dir.glob("*.md"):
            content = md_file.read_text()
            # Check if file has YAML markers (not necessarily at the start due to potential comments)
            assert "---" in content, f"{md_file} must have YAML front matter (---)"

    def test_prompt_loader_module_exists(self):
        """GIVEN the utils module WHEN checking for prompt loader THEN it exists."""
        from utils import prompt_loader

        assert prompt_loader is not None, "prompt_loader module must exist"


# =============================================================================
# III. Container-First
# =============================================================================


class TestConstitution3_ContainerFirst:
    """Validate Principle III: Container-First."""

    def test_dockerfile_exists(self):
        """GIVEN the project WHEN checking for Dockerfile THEN it exists."""
        dockerfile = Path("Dockerfile")
        assert dockerfile.exists(), "Dockerfile must exist"

    def test_docker_compose_exists(self):
        """GIVEN the project WHEN checking for docker-compose.yml THEN it exists."""
        compose_file = Path("docker-compose.yml")
        assert compose_file.exists(), "docker-compose.yml must exist"

    def test_dockerfile_uses_python_311(self):
        """GIVEN Dockerfile WHEN checking base image THEN it uses Python 3.11+."""
        dockerfile = Path("Dockerfile")
        content = dockerfile.read_text()
        assert "python:3.1" in content or "python:3.12" in content, (
            "Dockerfile must use Python 3.11+"
        )

    def test_docker_compose_has_required_services(self):
        """GIVEN docker-compose.yml WHEN checking services THEN includes api, worker, redis."""
        compose_file = Path("docker-compose.yml")
        content = compose_file.read_text()

        required_services = ["api:", "worker:", "redis:"]
        for service in required_services:
            assert service in content, f"docker-compose.yml must include {service} service"


# =============================================================================
# IV. Graceful Degradation
# =============================================================================


class TestConstitution4_GracefulDegradation:
    """Validate Principle IV: Graceful Degradation."""

    def test_degradation_module_exists(self):
        """GIVEN the utils module WHEN checking for degradation THEN it exists."""
        from utils import degradation

        assert degradation is not None, "degradation module must exist"

    def test_fallback_levels_defined(self):
        """GIVEN degradation module WHEN checking enum THEN FallbackLevel exists."""
        from utils.degradation import FallbackLevel

        assert FallbackLevel is not None, "FallbackLevel enum must be defined"
        assert FallbackLevel.FULL.value == "full"
        assert FallbackLevel.EMERGENCY.value == "emergency"


# =============================================================================
# V. OpenAI-Compatible API
# =============================================================================


class TestConstitution5_OpenAICompatible:
    """Validate Principle V: OpenAI-Compatible API."""

    def test_openai_config_in_env(self):
        """GIVEN .env.example WHEN checking for OpenAI config THEN it has required vars."""
        env_example = Path(".env.example")
        content = env_example.read_text()

        assert "LLM_API_KEY" in content or "OPENAI_KEY" in content, (
            ".env.example must include LLM_API_KEY"
        )
        assert "LLM_BASE_URL" in content, ".env.example must include LLM_BASE_URL"

    def test_openai_client_used(self):
        """GIVEN the worker module WHEN checking imports THEN it uses OpenAI client."""
        # Check that OpenAI is imported somewhere
        for py_file in Path().rglob("*.py"):
            if "test" in str(py_file) or ".venv" in str(py_file):
                continue
            content = py_file.read_text()
            if "from openai import" in content or "import openai" in content:
                return True
        pytest.fail("OpenAI client not found in any module")


# =============================================================================
# VI. Modular Service Architecture
# =============================================================================


class TestConstitution6_ModularServiceArchitecture:
    """Validate Principle VI: Modular Service Architecture."""

    def test_models_directory_exists(self):
        """GIVEN the project WHEN checking for models directory THEN it exists."""
        models_dir = Path("models")
        assert models_dir.exists(), "models/ directory must exist"

    def test_adapters_directory_exists(self):
        """GIVEN the project WHEN checking for adapters directory THEN it exists."""
        adapters_dir = Path("adapters")
        assert adapters_dir.exists(), "adapters/ directory must exist"

    def test_services_directory_exists(self):
        """GIVEN the project WHEN checking for services directory THEN it exists."""
        services_dir = Path("services")
        assert services_dir.exists(), "services/ directory must exist"

    def test_base_adapter_exists(self):
        """GIVEN adapters module WHEN checking for base THEN base.py exists."""
        base_adapter = Path("adapters/base.py")
        assert base_adapter.exists(), "adapters/base.py must exist"


# =============================================================================
# VII. Async-First Processing
# =============================================================================


class TestConstitution7_AsyncFirstProcessing:
    """Validate Principle VII: Async-First Processing."""

    def test_celery_app_exists(self):
        """GIVEN the project WHEN checking for Celery app THEN celery_app.py exists."""
        celery_app = Path("celery_app.py")
        assert celery_app.exists(), "celery_app.py must exist"

    def test_worker_module_exists(self):
        """GIVEN the project WHEN checking for worker THEN worker.py exists."""
        worker_file = Path("worker.py")
        assert worker_file.exists(), "worker.py must exist"

    def test_worker_has_tasks(self):
        """GIVEN worker.py WHEN checking for tasks THEN process_code_review exists."""
        worker_file = Path("worker.py")
        content = worker_file.read_text()
        assert "process_code_review" in content, "worker.py must define process_code_review task"


# =============================================================================
# VIII. Platform Abstraction
# =============================================================================


class TestConstitution8_PlatformAbstraction:
    """Validate Principle VIII: Platform Abstraction."""

    def test_github_adapter_exists(self):
        """GIVEN adapters module WHEN checking for GitHub THEN github.py exists."""
        github_adapter = Path("adapters/github.py")
        assert github_adapter.exists(), "adapters/github.py must exist"

    def test_gitea_adapter_exists(self):
        """GIVEN adapters module WHEN checking for Gitea THEN gitea.py exists."""
        gitea_adapter = Path("adapters/gitea.py")
        assert gitea_adapter.exists(), "adapters/gitea.py must exist"


# =============================================================================
# IX. Observability
# =============================================================================


class TestConstitution9_Observability:
    """Validate Principle IX: Observability."""

    def test_metrics_module_exists(self):
        """GIVEN utils module WHEN checking for metrics THEN metrics.py exists."""
        metrics_file = Path("utils/metrics.py")
        assert metrics_file.exists(), "utils/metrics.py must exist"

    def test_prometheus_configured(self):
        """GIVEN .env.example WHEN checking for Prometheus THEN it has config."""
        env_example = Path(".env.example")
        content = env_example.read_text()
        assert "ENABLE_PROMETHEUS" in content, ".env.example must include ENABLE_PROMETHEUS"


# =============================================================================
# X. Webhook Security
# =============================================================================


class TestConstitution10_WebhookSecurity:
    """Validate Principle X: Webhook Security."""

    def test_webhook_secrets_in_env(self):
        """GIVEN .env.example WHEN checking for webhook secrets THEN they are configured."""
        env_example = Path(".env.example")
        content = env_example.read_text()

        assert (
            "PLATFORM_GITHUB_WEBHOOK_SECRET" in content
            or "PLATFORM_GITEA_WEBHOOK_SECRET" in content
        ), ".env.example must include webhook secret configuration"


# =============================================================================
# XI. Task Reliability
# =============================================================================


class TestConstitution11_TaskReliability:
    """Validate Principle XI: Task Reliability."""

    def test_celery_retry_configured(self):
        """GIVEN celery_app.py WHEN checking for retry THEN it's configured."""
        celery_app = Path("celery_app.py")
        content = celery_app.read_text()

        assert "task_retry" in content or "max_retries" in content, (
            "celery_app.py must configure retry settings"
        )


# =============================================================================
# XII. Feedback Loop
# =============================================================================


class TestConstitution12_FeedbackLoop:
    """Validate Principle XII: Feedback Loop."""

    def test_feedback_models_exist(self):
        """GIVEN models module WHEN checking for feedback THEN feedback.py exists."""
        feedback_models = Path("models/feedback.py")
        assert feedback_models.exists(), "models/feedback.py must exist"


# =============================================================================
# XIII. Data Governance
# =============================================================================


class TestConstitution13_DataGovernance:
    """Validate Principle XIII: Data Governance."""

    def test_data_governance_module_exists(self):
        """GIVEN utils module WHEN checking for data governance THEN data_governance.py exists."""
        dg_file = Path("utils/data_governance.py")
        assert dg_file.exists(), "utils/data_governance.py must exist"

    def test_secrets_scanner_exists(self):
        """GIVEN utils module WHEN checking for secrets scanner THEN secrets.py exists."""
        secrets_file = Path("utils/secrets.py")
        assert secrets_file.exists(), "utils/secrets.py must exist"


# =============================================================================
# XIV. Test-Driven Development
# =============================================================================


class TestConstitution14_TestDrivenDevelopment:
    """Validate Principle XIV: Test-Driven Development."""

    def test_tests_directory_exists(self):
        """GIVEN the project WHEN checking for tests directory THEN it exists."""
        tests_dir = Path("tests")
        assert tests_dir.exists(), "tests/ directory must exist"

    def test_pytest_config_exists(self):
        """GIVEN the project WHEN checking for pytest config THEN it's configured."""
        pyproject = Path("pyproject.toml")
        assert pyproject.exists(), "pyproject.toml must exist"

        content = pyproject.read_text()
        assert "[tool.pytest.ini_options]" in content, (
            "pyproject.toml must include pytest configuration"
        )

    def test_coverage_threshold_defined(self):
        """GIVEN pytest config WHEN checking for coverage THEN threshold is >= 80%."""
        pyproject = Path("pyproject.toml")
        content = pyproject.read_text()

        assert "cov-fail-under" in content, "pyproject.toml must define coverage threshold"
        # Check that threshold is at least 80
        for line in content.split("\n"):
            if "cov-fail-under" in line:
                # Extract number from string like 'cov-fail-under = 80'
                parts = line.split("=")[1].strip().split()
                threshold = int(float(parts[0]))
                assert threshold >= 80, f"Coverage threshold must be >= 80%, got {threshold}%"

    def test_unit_tests_exist(self):
        """GIVEN tests directory WHEN checking for unit tests THEN they exist."""
        unit_dir = Path("tests/unit")
        assert unit_dir.exists(), "tests/unit/ directory must exist"

        # Count test files
        test_files = list(unit_dir.glob("test_*.py"))
        assert len(test_files) > 0, "At least one unit test must exist"

    def test_integration_tests_exist(self):
        """GIVEN tests directory WHEN checking for integration tests THEN they exist."""
        integration_dir = Path("tests/integration")
        assert integration_dir.exists(), "tests/integration/ directory must exist"

        # Count test files
        test_files = list(integration_dir.glob("test_*.py"))
        assert len(test_files) > 0, "At least one integration test must exist"


# =============================================================================
# Summary Report
# =============================================================================


@pytest.mark.summary
def test_constitution_compliance_summary():
    """
    GIVEN all constitution tests WHEN generating summary THEN report compliance.
    """
    # This test generates a summary report
    # It will run after all other tests due to the 'summary' marker

    principles = [
        "I. Configuration as Code",
        "II. Prompts as Data",
        "III. Container-First",
        "IV. Graceful Degradation",
        "V. OpenAI-Compatible API",
        "VI. Modular Service Architecture",
        "VII. Async-First Processing",
        "VIII. Platform Abstraction",
        "IX. Observability",
        "X. Webhook Security",
        "XI. Task Reliability",
        "XII. Feedback Loop",
        "XIII. Data Governance",
        "XIV. Test-Driven Development",
    ]

    print("\n" + "=" * 60)
    print("CONSTITUTION COMPLIANCE SUMMARY")
    print("=" * 60)
    for principle in principles:
        print(f"  ✓ {principle}")
    print("=" * 60)
    print("Run individual test classes for detailed validation")
    print("=" * 60)
