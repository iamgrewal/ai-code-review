"""
Gitea AI Code Reviewer - FastAPI Application

This module provides a webhook service that integrates with Gitea to perform
AI-powered code reviews on push events.
"""

import json
from time import sleep
from typing import Dict

import requests
from codereview.copilot import Copilot
from gitea.client import GiteaClient
from utils.config import Config
from utils.logger import logger, setup_logging
from fastapi import FastAPI

from utils.utils import create_comment, extract_info_from_request

app = FastAPI()

# Load configuration
config = Config()

# Initialize clients
gitea_client = GiteaClient(config.GITEA_HOST, config.GITEA_TOKEN)
copilot = Copilot(config)


@app.post("/codereview")
async def analyze_code(request_body: Dict):
    """
    Webhook endpoint for Gitea push events.

    Triggers AI code review for pushed commits.
    """
    owner, repo, sha, ref, pusher, full_name, title, commit_url = (
        extract_info_from_request(request_body)
    )

    if "[skip codereview]" in title:
        return {"message": "Skip codereview"}

    diff_blocks = gitea_client.get_diff_blocks(owner, repo, sha)
    if diff_blocks is None:
        return {"message": "Failed to get diff content"}

    current_issue_id = None

    ignored_file_suffix = config.IGNORED_FILE_SUFFIX.split(",")

    for i, diff_content in enumerate(diff_blocks, start=1):
        file_path = diff_content.split(" ")[0].split("/")
        file_name = file_path[-1]

        # Ignore the file if it's in the ignored list
        if ignored_file_suffix:
            for suffix in ignored_file_suffix:
                if file_name.endswith(suffix):
                    logger.warning(f"File {file_name} is ignored")
                    continue

        # Send the diff to AI for code analysis
        response = copilot.code_review(diff_content)

        comment = create_comment(file_name, diff_content, response)
        if i == 1:
            issue_res = gitea_client.create_issue(
                owner,
                repo,
                f"Code Review {title}",
                f"本次提交：{commit_url} \n\r 提交人：{pusher} \n\r {comment}",
                ref,
                pusher,
            )
            issue_url = issue_res["html_url"]
            current_issue_id = issue_res["number"]

            logger.success(f"The code review: {issue_url}")

            # Send a notification to the webhook
            if config.webhook and config.webhook.is_init:
                headers = {}
                if config.webhook.header_name and config.webhook.header_value:
                    headers = {config.webhook.header_name: config.webhook.header_value}

                content = (
                    f"Code Review: {title}\n{commit_url}\n\n审查结果: \n{issue_url}"
                )
                request_body_str = config.webhook.request_body.format(
                    content=content,
                    mention=full_name,
                )
                request_body = json.loads(request_body_str, strict=False)
                requests.post(
                    config.webhook.url,
                    headers=headers,
                    json=request_body,
                )

        else:
            gitea_client.add_issue_comment(
                owner,
                repo,
                current_issue_id,
                comment,
            )

        logger.info("Sleep for 1.5 seconds...")
        sleep(1.5)

    # Add banner to the issue
    gitea_client.add_issue_comment(
        owner,
        repo,
        current_issue_id,
        copilot.banner,
    )

    return {"message": response}


@app.post("/test")
def test(request_body: str):
    """
    Manual testing endpoint for code review.

    Accepts raw code text and returns AI review.
    """
    logger.success("Test")
    return {"message": copilot.code_review(request_body)}


if __name__ == "__main__":
    import uvicorn

    serv_config = uvicorn.Config(
        "main:app",
        host="0.0.0.0",
        port=3008,
        access_log=True,
        workers=1,
        reload=True,
    )
    server = uvicorn.Server(serv_config)

    setup_logging()
    server.run()
