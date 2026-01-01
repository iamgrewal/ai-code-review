#!/usr/bin/env python3
"""
Resource Check Script for Supabase PostgreSQL Container

Purpose: Validate system resources meet minimum requirements before starting
- Checks available RAM (minimum 4GB recommended)
- Checks available CPU cores (minimum 2 recommended)
- Checks disk space (minimum 20GB recommended)
- Issues warnings if resources are below recommended levels

Usage: Called from docker-entrypoint.sh before PostgreSQL starts
Exit codes: 0 (success), 1 (critical failure)
"""

import os
import sys
import shutil


def get_available_memory_gb() -> float:
    """Get available system memory in GB.

    Returns:
        Available memory in gigabytes
    """
    try:
        with open("/proc/meminfo", "r") as f:
            meminfo = f.read()

        # Parse MemAvailable (preferred) or MemFree
        for line in meminfo.split("\n"):
            if line.startswith("MemAvailable:"):
                kb = int(line.split()[1])
                return kb / (1024 * 1024)  # Convert to GB
            elif line.startswith("MemFree:"):
                kb = int(line.split()[1])
                return kb / (1024 * 1024)
    except Exception:
        pass

    # Fallback: use shutil if available
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / (1024**3)
    except Exception:
        return 0.0


def get_cpu_count() -> int:
    """Get number of available CPU cores.

    Returns:
        Number of CPU cores
    """
    try:
        return os.cpu_count() or 0
    except Exception:
        return 0


def get_disk_space_gb(path: str = "/var/lib/postgresql/data") -> tuple[float, float]:
    """Get available and total disk space in GB.

    Args:
        path: Filesystem path to check (default: PostgreSQL data directory)

    Returns:
        (available_gb, total_gb)
    """
    try:
        stat = shutil.disk_usage(path)
        return stat.free / (1024**3), stat.total / (1024**3)
    except Exception:
        return 0.0, 0.0


def check_memory(min_gb: float = 4.0, warn_gb: float = 6.0) -> bool:
    """Check available system memory.

    Args:
        min_gb: Minimum required memory in GB
        warn_gb: Warning threshold in GB

    Returns:
        True if memory meets minimum, False otherwise
    """
    available_gb = get_available_memory_gb()

    if available_gb == 0:
        print("⚠️  WARNING: Could not determine available memory")
        return True  # Don't fail if we can't detect

    print(f"Available memory: {available_gb:.2f} GB")

    if available_gb < min_gb:
        print(f"❌ ERROR: Insufficient memory (minimum: {min_gb} GB)")
        print(f"   Current: {available_gb:.2f} GB")
        print(f"   Please increase container memory limit")
        return False
    elif available_gb < warn_gb:
        print(f"⚠️  WARNING: Memory below recommended level (recommended: {warn_gb} GB)")
        print(f"   Current: {available_gb:.2f} GB")
        print(f"   Performance may be degraded")
    else:
        print(f"✓ Sufficient memory available")

    return True


def check_cpu(min_cores: int = 2, warn_cores: int = 4) -> bool:
    """Check available CPU cores.

    Args:
        min_cores: Minimum required cores
        warn_cores: Warning threshold

    Returns:
        True if cores meet minimum, False otherwise
    """
    cpu_count = get_cpu_count()

    if cpu_count == 0:
        print("⚠️  WARNING: Could not determine CPU count")
        return True  # Don't fail if we can't detect

    print(f"Available CPU cores: {cpu_count}")

    if cpu_count < min_cores:
        print(f"❌ ERROR: Insufficient CPU cores (minimum: {min_cores})")
        print(f"   Current: {cpu_count} core(s)")
        print(f"   Please increase container CPU limit")
        return False
    elif cpu_count < warn_cores:
        print(f"⚠️  WARNING: CPU cores below recommended (recommended: {warn_cores})")
        print(f"   Current: {cpu_count} core(s)")
        print(f"   Performance may be degraded")
    else:
        print(f"✓ Sufficient CPU cores available")

    return True


def check_disk_space(min_gb: float = 20.0, warn_gb: float = 50.0, path: str = "/var/lib/postgresql/data") -> bool:
    """Check available disk space.

    Args:
        min_gb: Minimum required disk space in GB
        warn_gb: Warning threshold in GB
        path: Filesystem path to check

    Returns:
        True if disk space meets minimum, False otherwise
    """
    available_gb, total_gb = get_disk_space_gb(path)

    if available_gb == 0:
        print("⚠️  WARNING: Could not determine available disk space")
        return True  # Don't fail if we can't detect

    print(f"Available disk space: {available_gb:.2f} GB (total: {total_gb:.2f} GB)")

    if available_gb < min_gb:
        print(f"❌ ERROR: Insufficient disk space (minimum: {min_gb} GB)")
        print(f"   Current: {available_gb:.2f} GB")
        print(f"   Please free up disk space or increase volume size")
        return False
    elif available_gb < warn_gb:
        print(f"⚠️  WARNING: Disk space below recommended (recommended: {warn_gb} GB)")
        print(f"   Current: {available_gb:.2f} GB")
        print(f"   Consider expanding volume or cleaning up old data")
    else:
        print(f"✓ Sufficient disk space available")

    return True


def main() -> int:
    """Run all resource checks.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    print("=" * 60)
    print("System Resource Check")
    print("=" * 60)

    checks = [
        ("Memory", lambda: check_memory(min_gb=4.0, warn_gb=6.0)),
        ("CPU", lambda: check_cpu(min_cores=2, warn_cores=4)),
        ("Disk Space", lambda: check_disk_space(min_gb=20.0, warn_gb=50.0)),
    ]

    all_passed = True
    for name, check in checks:
        print()  # Blank line for readability
        print(f"Checking {name}...")
        if not check():
            all_passed = False

    print()
    print("=" * 60)

    if all_passed:
        print("✅ All resource checks passed!")
        print("=" * 60)
        return 0
    else:
        print("❌ Resource checks failed!")
        print("Please address the issues above before starting the container.")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
