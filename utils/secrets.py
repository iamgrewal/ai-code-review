"""
Secret scanning patterns for CortexReview platform.

Implements data governance requirements per Constitution XIII (Data Governance).
Scans code chunks for sensitive data before embedding generation to prevent
secrets from being stored in vector database.
"""

import re
from enum import Enum
from typing import Optional


class SecretType(str, Enum):
    """Types of secrets that can be detected."""

    API_KEY = "api_key"
    AWS_ACCESS_KEY = "aws_access_key"
    AWS_SECRET_KEY = "aws_secret_key"
    PRIVATE_KEY = "private_key"
    PASSWORD = "password"
    TOKEN = "token"
    CERTIFICATE = "certificate"
    DATABASE_URL = "database_url"
    JWT = "jwt"
    BEARER_TOKEN = "bearer_token"
    BASIC_AUTH = "basic_auth"
    GENERIC_SECRET = "generic_secret"


class SecretMatch:
    """Represents a detected secret in code."""

    def __init__(
        self,
        secret_type: SecretType,
        pattern: str,
        line_number: int,
        line_content: str,
        redacted: str,
    ):
        self.secret_type = secret_type
        self.pattern = pattern
        self.line_number = line_number
        self.line_content = line_content
        self.redacted = redacted

    def __repr__(self):
        return f"SecretMatch(type={self.secret_type}, line={self.line_number})"


# ============================================================================
# Secret Detection Patterns
# ============================================================================

# AWS Access Key ID (20 alphanumeric characters)
AWS_ACCESS_KEY_PATTERN = re.compile(
    r"(?i)(aws_access_key_id|aws_access_key)\s*=\s*['\"]?([A-Z0-9]{20})['\"]?",
)

# AWS Secret Access Key (40 characters, base64-like)
AWS_SECRET_KEY_PATTERN = re.compile(
    r"(?i)(aws_secret_access_key|aws_secret_key)\s*=\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?",
)

# Generic API Key patterns
API_KEY_PATTERNS = [
    # api_key = "..."
    re.compile(r"(?i)(api[_-]?key|apikey)\s*[:=]\s*['\"]([A-Za-z0-9_\-]{20,})['\"]"),
    # API_KEY: "..."
    re.compile(r"(?i)(api[_-]?key|apikey)\s*[:=]\s*['\"]([A-Za-z0-9_\-]{20,})['\"]"),
    # X-API-Key: ...
    re.compile(r"(?i)x-api[_-]?key\s*:\s*['\"]([A-Za-z0-9_\-]{20,})['\"]"),
]

# Private Key (RSA/EC/PGP)
PRIVATE_KEY_PATTERNS = [
    re.compile(r"-----BEGIN ([A-Z]+ )?PRIVATE KEY-----"),
    re.compile(r"-----BEGIN OPENSSH PRIVATE KEY-----"),
    re.compile(r"-----BEGIN PGP PRIVATE KEY BLOCK-----"),
]

# Password patterns
PASSWORD_PATTERNS = [
    # password = "..."
    re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]([^\s'\"]{8,})['\"]"),
    # db_password = "..."
    re.compile(r"(?i)(db[_-]?password|database[_-]?password)\s*[:=]\s*['\"]([^\s'\"]{8,})['\"]"),
]

# Token patterns (Bearer tokens, OAuth tokens, etc.)
TOKEN_PATTERNS = [
    # Authorization: Bearer <token>
    re.compile(r"(?i)authorization\s*:\s*Bearer\s+([A-Za-z0-9_\-\.]{20,})"),
    # token = "..."
    re.compile(r"(?i)(token|access_token|auth_token)\s*[:=]\s*['\"]([A-Za-z0-9_\-\.]{20,})['\"]"),
    # github: ghp_...
    re.compile(r"(?i)ghp_[A-Za-z0-9]{36}"),
    # gitea: base64 token
    re.compile(r"(?i)gitea[_-]?token\s*[:=]\s*['\"]([A-Za-z0-9_\-]{40,})['\"]"),
]

# JWT tokens
JWT_PATTERN = re.compile(
    r"eyJ[A-Za-z0-9_\-]*\.[A-Za-z0-9_\-]*\.[A-Za-z0-9_\-]*"
)

# Certificate patterns
CERTIFICATE_PATTERNS = [
    re.compile(r"-----BEGIN CERTIFICATE-----"),
    re.compile(r"-----BEGIN TRUSTED CERTIFICATE-----"),
]

# Database URL patterns
DATABASE_URL_PATTERNS = [
    # postgresql://user:password@host:port/db
    re.compile(
        r"(?i)(postgres|mysql|mongodb|redis)://[A-Za-z0-9_\-]+:[^\s@']{8,}@[^/\s']+"
    ),
    # DATABASE_URL = "postgresql://..."
    re.compile(
        r"(?i)(database[_-]?url|db_url|db[_-]?connection)\s*[:=]\s*[\"']([^\"']+@[^\s'\"]+)[\"']"
    ),
]

# Basic Auth in URLs
BASIC_AUTH_PATTERN = re.compile(
    r"(?i)https?://[A-Za-z0-9_\-]+:[^\s@]{8,}@[^\s/]+"
)

# Generic secret patterns (heuristic)
GENERIC_SECRET_PATTERNS = [
    # secret = "..." with at least 16 characters
    re.compile(r"(?i)(secret|private_key|access_key)\s*[:=]\s*['\"]([A-Za-z0-9_\-]{16,})['\"]"),
]


# ============================================================================
# Secret Scanning Functions
# ============================================================================

def scan_for_secrets(code: str, filename: str = "") -> list[SecretMatch]:
    """
    Scan code chunk for potential secrets.

    Args:
        code: Code content to scan
        filename: Optional filename for context (e.g., to skip config files)

    Returns:
        List of SecretMatch objects representing detected secrets
    """
    matches = []

    # Skip scanning for certain file types that often contain false positives
    if _should_skip_file(filename):
        return matches

    lines = code.split("\n")

    for line_number, line in enumerate(lines, start=1):
        # Check AWS keys
        aws_access_match = AWS_ACCESS_KEY_PATTERN.search(line)
        if aws_access_match:
            matches.append(
                SecretMatch(
                    secret_type=SecretType.AWS_ACCESS_KEY,
                    pattern="AWS_ACCESS_KEY_ID",
                    line_number=line_number,
                    line_content=line.strip(),
                    redacted=_redact_line(line, aws_access_match.group(2)),
                )
            )

        aws_secret_match = AWS_SECRET_KEY_PATTERN.search(line)
        if aws_secret_match:
            matches.append(
                SecretMatch(
                    secret_type=SecretType.AWS_SECRET_KEY,
                    pattern="AWS_SECRET_ACCESS_KEY",
                    line_number=line_number,
                    line_content=line.strip(),
                    redacted=_redact_line(line, aws_secret_match.group(2)),
                )
            )

        # Check API keys
        for pattern in API_KEY_PATTERNS:
            match = pattern.search(line)
            if match:
                matches.append(
                    SecretMatch(
                        secret_type=SecretType.API_KEY,
                        pattern="API_KEY",
                        line_number=line_number,
                        line_content=line.strip(),
                        redacted=_redact_line(line, match.group(2)),
                    )
                )

        # Check private keys
        for pattern in PRIVATE_KEY_PATTERNS:
            match = pattern.search(line)
            if match:
                matches.append(
                    SecretMatch(
                        secret_type=SecretType.PRIVATE_KEY,
                        pattern="PRIVATE_KEY",
                        line_number=line_number,
                        line_content=line.strip(),
                        redacted=_redact_line(line, match.group(0)),
                    )
                )

        # Check passwords
        for pattern in PASSWORD_PATTERNS:
            match = pattern.search(line)
            if match:
                matches.append(
                    SecretMatch(
                        secret_type=SecretType.PASSWORD,
                        pattern="PASSWORD",
                        line_number=line_number,
                        line_content=line.strip(),
                        redacted=_redact_line(line, match.group(2)),
                    )
                )

        # Check tokens
        for pattern in TOKEN_PATTERNS:
            match = pattern.search(line)
            if match:
                matches.append(
                    SecretMatch(
                        secret_type=SecretType.TOKEN,
                        pattern="TOKEN",
                        line_number=line_number,
                        line_content=line.strip(),
                        redacted=_redact_line(line, match.group(1) if match.lastindex else match.group(0)),
                    )
                )

        # Check JWT
        jwt_match = JWT_PATTERN.search(line)
        if jwt_match:
            matches.append(
                SecretMatch(
                    secret_type=SecretType.JWT,
                    pattern="JWT",
                    line_number=line_number,
                    line_content=line.strip(),
                    redacted=_redact_line(line, jwt_match.group(0)[:20] + "..."),
                )
            )

        # Check certificates
        for pattern in CERTIFICATE_PATTERNS:
            match = pattern.search(line)
            if match:
                matches.append(
                    SecretMatch(
                        secret_type=SecretType.CERTIFICATE,
                        pattern="CERTIFICATE",
                        line_number=line_number,
                        line_content=line.strip(),
                        redacted=_redact_line(line, match.group(0)),
                    )
                )

        # Check database URLs
        for pattern in DATABASE_URL_PATTERNS:
            match = pattern.search(line)
            if match:
                matches.append(
                    SecretMatch(
                        secret_type=SecretType.DATABASE_URL,
                        pattern="DATABASE_URL",
                        line_number=line_number,
                        line_content=line.strip(),
                        redacted=_redact_line(line, match.group(0)),
                    )
                )

        # Check basic auth
        basic_auth_match = BASIC_AUTH_PATTERN.search(line)
        if basic_auth_match:
            matches.append(
                SecretMatch(
                    secret_type=SecretType.BASIC_AUTH,
                    pattern="BASIC_AUTH",
                    line_number=line_number,
                    line_content=line.strip(),
                    redacted=_redact_line(line, basic_auth_match.group(0)),
                )
            )

        # Check generic secrets
        for pattern in GENERIC_SECRET_PATTERNS:
            match = pattern.search(line)
            if match:
                matches.append(
                    SecretMatch(
                        secret_type=SecretType.GENERIC_SECRET,
                        pattern="GENERIC_SECRET",
                        line_number=line_number,
                        line_content=line.strip(),
                        redacted=_redact_line(line, match.group(2)),
                    )
                )

    return matches


def has_secrets(code: str, filename: str = "") -> bool:
    """
    Check if code chunk contains any secrets.

    Args:
        code: Code content to check
        filename: Optional filename for context

    Returns:
        True if secrets detected, False otherwise
    """
    return len(scan_for_secrets(code, filename)) > 0


def _should_skip_file(filename: str) -> bool:
    """
    Determine if file should be skipped from secret scanning.

    Some file types are known to contain false positives (e.g., example configs,
    test files with dummy credentials, migration files, etc.).

    Args:
        filename: File path/name

    Returns:
        True if scanning should be skipped
    """
    skip_patterns = [
        "example",
        "sample",
        "test",
        "spec",
        "fixture",
        "migration",
        "seed",
        ".env.example",
        ".env.sample",
        ".env.test",
        "docker-compose.yml",
        "docker-compose.yaml",
    ]

    filename_lower = filename.lower()
    for pattern in skip_patterns:
        if pattern in filename_lower:
            return True

    return False


def _redact_line(line: str, secret: str) -> str:
    """
    Redact secret from line for logging.

    Args:
        line: Original line content
        secret: Secret value to redact

    Returns:
        Line with secret replaced by asterisks
    """
    return line.replace(secret, "*" * len(secret))


# ============================================================================
# Redaction Functions
# ============================================================================

def redact_secrets(code: str, filename: str = "") -> tuple[str, list[SecretMatch]]:
    """
    Redact secrets from code chunk before embedding.

    Args:
        code: Code content to redact
        filename: Optional filename for context

    Returns:
        Tuple of (redacted_code, list_of_secrets_found)
    """
    matches = scan_for_secrets(code, filename)
    redacted_code = code

    for match in matches:
        redacted_code = redacted_code.replace(match.line_content, match.redacted)

    return redacted_code, matches
