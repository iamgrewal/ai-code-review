

# Updated Product Requirement Document (PRD)
## Project: Refactor Gitea AI Code Review (External Prompts, .env Config, & Dockerization)

### 1. Overview
**Objective:** Refactor the `gitea-ai-codereview` codebase to achieve three goals:
1.  **Externalize Prompts:** Move AI instructions to `.md` files for easier editing.
2.  **Flexible Configuration:** Enable LLM provider configuration (Base URL, API Key, Model) via `.env` file.
3.  **Dockerization:** Containerize the application using `Dockerfile` and `docker-compose.yml` for easy deployment and development.

**Scope:** Python backend refactoring, environment variable handling, file I/O logic, and container orchestration setup.

---

### 2. Current Behavior Analysis
**What the code does now:**
1.  **Hardcoded Logic:** System prompts are static strings in `main.py`.
2.  **Rigid Config:** API Keys and Model names are often hardcoded or inflexibly defined. It does not support custom `BASE_URL` (needed for proxies, Azure, or local LLMs).
3.  **Manual Deployment:** No standardized containerization process defined in the project root.

---

### 3. Proposed Behavior & Requirements

#### 3.1 Externalized Prompts
*   **REQ-P-01:** The system must load prompts from `./prompts/code-review-pr.md`.
*   **REQ-P-02:** The system must support variable substitution (e.g., `${input-focus}`).
*   **REQ-P-03:** The system must strip YAML front matter from markdown files.

#### 3.2 Environment Configuration (`.env`)
*   **REQ-C-01:** The application must read configuration variables from a `.env` file in the project root.
*   **REQ-C-02:** The application must support the following LLM configuration variables:
    *   `LLM_PROVIDER` (e.g., `openai`, `anthropic`, `custom`).
    *   `LLM_API_KEY` (The secret key).
    *   `LLM_BASE_URL` (Optional: The API endpoint, allowing use of local models or proxies).
    *   `LLM_MODEL` (The specific model name, e.g., `gpt-4o`, `claude-3-opus`).
*   **REQ-C-03:** The application must default to standard OpenAI settings if variables are missing, ensuring backward compatibility.

#### 3.3 Dockerization
*   **REQ-D-01:** A `Dockerfile` must be provided to build a lightweight Python 3.10 slim image.
*   **REQ-D-02:** A `docker-compose.yml` file must orchestrate the service, mapping the `.env` file and necessary ports.
*   **REQ-D-03:** The container configuration must support mounting the `prompts/` directory locally so prompt changes do not require a container rebuild.

---

### 4. Technical Implementation Guide

#### 4.1 Dependencies (`requirements.txt`)
The coding agent must ensure the following dependencies are present/added:
```text
openai>=1.0.0  # Or specific library used
python-dotenv>=1.0.0
flask          # Or fastapi/starlette, depending on existing code
gunicorn       # If needed for production server
```

#### 4.2 Directory Structure
The agent must organize the project as follows:
```text
/project-root
  ├── main.py
  ├── .env                 # New/Updated
  ├── Dockerfile           # New
  ├── docker-compose.yml   # New
  ├── requirements.txt     # Updated
  └── prompts/
       └── code-review-pr.md
```

#### 4.3 Configuration Logic Implementation
The agent must update `main.py` to load environment variables at the top of the script using `python-dotenv`.

**Reference Implementation:**
```python
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Centralized configuration class"""
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
    LLM_API_KEY = os.getenv("LLM_API_KEY", os.getenv("OPENAI_KEY")) # Fallback for legacy support
    LLM_BASE_URL = os.getenv("LLM_BASE_URL") # Optional
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4")
    
    # Gitea Config
    GITEA_HOST = os.getenv("GITEA_HOST")
    GITEA_TOKEN = os.getenv("GITEA_TOKEN")
    
    IGNORED_SUFFIX = os.getenv("IGNORED_FILE_SUFFIX", ".json,.md,.lock")

config = Config()
```

**Agent Instruction for Client Initialization:**
When initializing the LLM client (e.g., OpenAI), use the `Config` class:
```python
from openai import OpenAI

client = OpenAI(
    api_key=config.LLM_API_KEY,
    base_url=config.LLM_BASE_URL if config.LLM_BASE_URL else None
)
```

#### 4.4 Prompt Loading Function
(Reiterating from previous prompt, ensuring it fits into the new structure).
*   The `load_prompt` function created in the previous step remains valid.
*   Ensure `prompts/` directory is created if it doesn't exist.

#### 4.5 Docker Implementation
**Agent Action 1: Create `Dockerfile`**
The agent must generate this file in the root directory.

```dockerfile
# Use an official lightweight Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies if any (e.g., gcc for certain python packages)
# RUN apt-get update && apt-get install -y gcc

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port defined in the environment or README (3008)
EXPOSE 3008

# Command to run the application
CMD ["python", "main.py"]
```

**Agent Action 2: Create `docker-compose.yml`**
The agent must generate this file in the root directory.
*Note: The agent should ensure the volume mounts cover both `main.py` and the `prompts/` folder for hot-reloading.*

```yaml
---
services:
  ai-codereview:
    build: .
    container_name: gitea-ai-codereview
    restart: always
    env_file: .env
    networks:
      gitea_gitea:
    ports:
      - "3008:3008"
    environment:
      # URL of your Gitea Server
      - GITEA_HOST=http://server:3000
      # Ensure these map to the .env or defaults in main.py
      - LLM_PROVIDER=${LLM_PROVIDER:-openai}
      - LLM_API_KEY=${LLM_API_KEY}
      - LLM_BASE_URL=${LLM_BASE_URL}
      - LLM_MODEL=${LLM_MODEL}
      # Gitea Specific
      - GITEA_TOKEN=${GITEA_TOKEN}
      - IGNORED_FILE_SUFFIX=${IGNORED_FILE_SUFFIX:-.json,.md,.lock,.png,.jpg,.svg,.map}
    extra_hosts:
      - "host.docker.internal:host-gateway"
    volumes:
      # Map code for hot-reloading
      - ./main.py:/app/main.py
      # Map prompts folder so you can edit them on the host without rebuilding
      - ./prompts:/app/prompts 
networks:
  gitea_gitea:
    external: true
```

**Agent Action 3: Create `.env` Template**
If `.env` does not exist, the agent should create `.env.example` to guide the user.

```bash
# LLM Configuration
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
LLM_BASE_URL=https://api.openai.com/v1 # Change to local URL if needed (e.g., http://localhost:11434/v1)
LLM_MODEL=gpt-4

# Gitea Configuration
GITEA_TOKEN=your_gitea_app_token
GITEA_HOST=http://server:3000

# Optional
IGNORED_FILE_SUFFIX=.json,.md,.lock
```

---

### 5. Testing & Validation
The coding agent must verify the following scenarios:

1.  **Config Loading:**
    *   Start the application. Ensure `config.LLM_BASE_URL` is respected if set.
    *   Test with a mock API URL to ensure traffic is routing to the `base_url` provided in `.env`.

2.  **Docker Build:**
    *   Run `docker-compose up --build`.
    *   Verify the container starts without errors and the logs show it is listening on port 3008.

3.  **Hot Reloading:**
    *   While the container is running, edit `./prompts/code-review-pr.md` on the host machine.
    *   Trigger a review. Verify the bot uses the updated prompt text immediately.

4.  **Volume Mounts:**
    *   Verify that edits to `main.py` on the host are reflected inside the container (check via `docker exec`).

---

### 6. Success Criteria
*   [ ] All hardcoded prompts removed from `main.py`.
*   [ ] `python-dotenv` implemented for `.env` loading.
*   [ ] Application successfully connects to a custom `LLM_BASE_URL` if provided.
*   [ ] `docker-compose up` runs the service successfully.
*   [ ] Changes to `prompts/` folder on the host affect the running container immediately via volume mounts.
