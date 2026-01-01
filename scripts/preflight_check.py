#!/usr/bin/env python3
"""
Pre-flight Check Script for Supabase PostgreSQL Container

Purpose: Validate environment variables before starting PostgreSQL
- Checks required Supabase environment variables
- Validates password lengths and security requirements
- Fails fast with clear error messages if validation fails

Usage: Called from docker-entrypoint.sh before PostgreSQL starts
Exit codes: 0 (success), 1 (validation failed)
"""

import os
import sys


def check_required_env_vars() -> tuple[bool, list[str]]:
    """Check that all required environment variables are set.

    Returns:
        (success: bool, missing_vars: list[str])
    """
    required_vars = [
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
        "JWT_SECRET",
        "ANON_KEY",
        "SERVICE_ROLE_KEY",
    ]

    missing = [var for var in required_vars if not os.environ.get(var)]

    if missing:
        print("❌ ERROR: Missing required environment variables:")
        for var in missing:
            print(f"   - {var}")
        print("\nPlease set these variables in your .env file or docker-compose.yml")
        return False, missing

    print("✓ All required environment variables are set")
    return True, []


def check_password_security() -> bool:
    """Validate POSTGRES_PASSWORD meets minimum security requirements.

    Returns:
        True if password is secure enough, False otherwise
    """
    password = os.environ.get("POSTGRES_PASSWORD", "")

    if len(password) < 16:
        print(f"❌ ERROR: POSTGRES_PASSWORD must be at least 16 characters")
        print(f"   Current length: {len(password)} characters")
        print(f"   Please use a stronger password (min 16 chars)")
        return False

    print(f"✓ POSTGRES_PASSWORD meets minimum length (16+ characters)")
    return True


def check_jwt_secret() -> bool:
    """Validate JWT_SECRET meets minimum requirements.

    Returns:
        True if JWT_SECRET is long enough, False otherwise
    """
    jwt_secret = os.environ.get("JWT_SECRET", "")

    if len(jwt_secret) < 64:
        print(f"❌ ERROR: JWT_SECRET must be at least 64 characters")
        print(f"   Current length: {len(jwt_secret)} characters")
        print(f"   Generate with: openssl rand -base64 64")
        return False

    print(f"✓ JWT_SECRET meets minimum length (64+ characters)")
    return True


def check_anon_and_service_keys() -> bool:
    """Validate ANON_KEY and SERVICE_ROLE_KEY are not default values.

    Returns:
        True if keys are properly set, False otherwise
    """
    anon_key = os.environ.get("ANON_KEY", "")
    service_role_key = os.environ.get("SERVICE_ROLE_KEY", "")

    # Check for placeholder values
    placeholders = [
        "your_",
        "replace_",
        "change_",
        "example_",
    ]

    for key_name, key_value in [("ANON_KEY", anon_key), ("SERVICE_ROLE_KEY", service_role_key)]:
        if any(key_value.lower().startswith(p) for p in placeholders):
            print(f"❌ ERROR: {key_name} appears to be a placeholder value")
            print(f"   Current value: {key_value[:20]}...")
            print(f"   Please generate proper keys using Supabase CLI or JWT_SECRET")
            return False

    print(f"✓ ANON_KEY and SERVICE_ROLE_KEY are properly configured")
    return True


def check_database_name() -> bool:
    """Validate POSTGRES_DB is set to a valid database name.

    Returns:
        True if database name is valid, False otherwise
    """
    db_name = os.environ.get("POSTGRES_DB", "")

    if not db_name:
        print("❌ ERROR: POSTGRES_DB is not set")
        return False

    if db_name.lower() == "postgres":
        print("⚠️  WARNING: POSTGRES_DB is set to 'postgres'")
        print("   This is the default system database")
        print("   Consider using a different name (e.g., 'supabase')")

    print(f"✓ POSTGRES_DB is set to: {db_name}")
    return True


def main() -> int:
    """Run all pre-flight checks.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    print("=" * 60)
    print("Supabase Pre-flight Check")
    print("=" * 60)

    checks = [
        check_required_env_vars,
        check_password_security,
        check_jwt_secret,
        check_anon_and_service_keys,
        check_database_name,
    ]

    all_passed = True
    for check in checks:
        print()  # Blank line for readability
        result = check()
        if isinstance(result, tuple):
            success, _ = result
        else:
            success = result

        if not success:
            all_passed = False

    print()
    print("=" * 60)

    if all_passed:
        print("✅ All pre-flight checks passed!")
        print("=" * 60)
        return 0
    else:
        print("❌ Pre-flight checks failed!")
        print("Please fix the errors above before starting the container.")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
