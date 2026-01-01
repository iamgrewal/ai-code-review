"""
Test configuration fixtures.

Provides sample configurations for testing various components.
"""

from typing import Any


def sample_review_config() -> dict[str, Any]:
    """
    Sample ReviewConfig for testing.

    Provides a valid review configuration.
    """
    return {
        "use_rag_context": True,
        "apply_learned_suppressions": True,
        "severity_threshold": "low",
        "include_auto_fix_patches": False,
        "personas": [],
        "max_context_matches": 10,
    }


def sample_diff_content() -> str:
    """
    Sample git diff content for testing.

    Represents a typical unified diff output.
    """
    return '''diff --git a/src/main.py b/src/main.py
index 1234567..abcdefg 100644
--- a/src/main.py
+++ b/src/main.py
@@ -10,7 +10,7 @@ def process_request():
     pass

-def old_function():
+def new_function():
     """This is a new function."""
     return True
'''
