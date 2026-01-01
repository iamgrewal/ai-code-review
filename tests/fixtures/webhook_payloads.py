"""
Webhook payload fixtures for testing.

Provides sample webhook payloads for GitHub and Gitea platforms
for pull request and push events.
"""

from typing import Any


def github_pr_payload() -> dict[str, Any]:
    """
    Sample GitHub pull_request webhook payload.

    Represents a typical GitHub webhook when a PR is opened.
    """
    return {
        "action": "opened",
        "repository": {
            "id": 123456789,
            "node_id": "MDEwOlJlcG9zaXRvcnkxMjM0NTY3ODk=",
            "name": "test-repo",
            "full_name": "octocat/test-repo",
            "private": False,
            "owner": {
                "login": "octocat",
                "id": 1,
            },
        },
        "sender": {
            "login": "octocat",
            "id": 1,
        },
        "pull_request": {
            "id": 1,
            "number": 42,
            "state": "open",
            "title": "Add new feature",
            "user": {
                "login": "octocat",
            },
            "base": {
                "label": "octocat:main",
                "ref": "main",
                "sha": "a" * 40,
            },
            "head": {
                "label": "octocat:feature-branch",
                "ref": "feature-branch",
                "sha": "b" * 40,
            },
        },
    }


def github_push_payload() -> dict[str, Any]:
    """
    Sample GitHub push webhook payload.

    Represents a typical GitHub webhook when commits are pushed.
    """
    return {
        "ref": "refs/heads/main",
        "repository": {
            "id": 123456789,
            "name": "test-repo",
            "full_name": "octocat/test-repo",
            "owner": {
                "login": "octocat",
            },
        },
        "pusher": {
            "name": "octocat",
        },
        "before": "a" * 40,
        "after": "b" * 40,
        "commits": [
            {
                "id": "b" * 40,
                "message": "Add new feature",
            }
        ],
    }


def gitea_pr_payload() -> dict[str, Any]:
    """
    Sample Gitea pull_request webhook payload.

    Represents a typical Gitea webhook when a PR is opened.
    """
    return {
        "action": "opened",
        "repository": {
            "id": 123,
            "name": "test-repo",
            "full_name": "octocat/test-repo",
            "owner": {
                "login": "octocat",
            },
        },
        "sender": {
            "login": "octocat",
        },
        "pull_request": {
            "number": 42,
            "title": "Add new feature",
            "user": {
                "login": "octocat",
            },
            "base": {
                "ref": "main",
                "sha": "a" * 40,
            },
            "head": {
                "ref": "feature-branch",
                "sha": "b" * 40,
            },
        },
    }


def gitea_push_payload() -> dict[str, Any]:
    """
    Sample Gitea push webhook payload.

    Represents a typical Gitea webhook when commits are pushed.
    """
    return {
        "ref": "refs/heads/main",
        "repository": {
            "full_name": "octocat/test-repo",
        },
        "pusher": {
            "login": "octocat",
        },
        "before": "a" * 40,
        "after": "b" * 40,
        "commits": [
            {
                "message": "Add new feature",
            }
        ],
    }
