# Gitea AI Code Reviewer

A lightweight, self-hosted AI bot that automatically reviews Pull Requests in Gitea. It listens for webhook events, analyzes code changes using LLMs (OpenAI, Custom Local LLMs, or Copilot), and posts intelligent review comments directly to your PRs.

## 🚀 Features

* **Automated Reviews:** Automatically analyzes new Pull Requests and updates.
* **External Prompt Management:** Customize the AI's behavior and persona by editing Markdown files without changing the code.
* **Flexible LLM Configuration:** Support for custom Base URLs, API Keys, and Models via `.env` (compatible with OpenAI, Azure, LocalAI, Ollama, etc.).
* **Self-Hosted:** Runs entirely on your own infrastructure (Docker or Metal).
* **Webhook Based:** No complex Gitea Actions runners required; works as a standalone service.
* **Hot Reload (Docker):** Edit prompts or code locally and see changes immediately without rebuilding the image.

## 🛠 Prerequisites

* **Gitea Instance:** Version 1.19+ recommended.
* **Docker & Docker Compose** (Recommended for deployment).
* **API Key:** An API key for your preferred LLM provider.

## 📦 Installation & Deployment

### Option 1: Docker Compose (Recommended)

This setup includes volume mounts for **hot-reloading** prompts and code.

1.  Create a folder structure on your host:
    ```text
    /gitea-ai-codereview
      ├── docker-compose.yml
      ├── .env
      ├── main.py       (Optional: If you want to modify source)
      └── prompts/      (Required: Place your custom prompts here)
           └── code-review-pr.md
    ```

2.  Create a `docker-compose.yml` file with the following configuration:

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
          # URL of your Gitea Server (Internal Docker URL if in same network, or Host IP)
          - GITEA_HOST=http://server:3000
          # Token you will generate in Step 4
          - GITEA_TOKEN=${GITEA_TOKEN}
          # LLM Configuration (Loaded from .env)
          - LLM_PROVIDER=${LLM_PROVIDER}
          - LLM_API_KEY=${LLM_API_KEY}
          - LLM_BASE_URL=${LLM_BASE_URL}
          - LLM_MODEL=${LLM_MODEL}
          # Optional Configs
          - IGNORED_FILE_SUFFIX=${IGNORED_FILE_SUFFIX:-.json,.md,.lock,.png,.jpg,.svg,.map}
        extra_hosts:
          - "host.docker.internal:host-gateway" # Helps access host services if needed
        volumes:
          # Map source for hot-reloading code changes
          - ./main.py:/app/main.py
          # Map prompts folder so you can edit them on the host without rebuilding
          - ./prompts:/app/prompts
    networks:
      gitea_gitea:
        external: true
    ```

3.  Create a `.env` file in the same directory to configure your keys:

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

4.  Start the service:
    ```bash
    docker-compose up -d --build
    ```

### Option 2: Local Python Setup

1.  Clone the repository:
    ```bash
    git clone https://github.com/bestK/gitea-ai-codereview.git
    cd gitea-ai-codereview
    ```

2.  Create a virtual environment and install dependencies:
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    ```

3.  Configure environment variables (create a `.env` file):
    ```ini
    LLM_PROVIDER=openai
    LLM_API_KEY=sk-xyz...
    LLM_BASE_URL=https://api.openai.com/v1
    LLM_MODEL=gpt-4
    GITEA_HOST=http://localhost:3000
    GITEA_TOKEN=your_token_here
    ```

4.  Ensure you have created the `./prompts/` directory and added your `code-review-pr.md` file.

5.  Run the application:
    ```bash
    python main.py
    ```

## ⚙️ Configuration

The application is configured primarily via the `.env` file and the Prompt files.

### Environment Variables

| Variable | Description | Required | Default |
| --- | --- | --- | --- |
| **LLM Configuration** |
| `LLM_PROVIDER` | The provider identifier (e.g., `openai`, `anthropic`, `custom`). | ✅ | `openai` |
| `LLM_API_KEY` | API Key for your LLM provider. | ✅ | None |
| `LLM_BASE_URL` | Base URL for the LLM API (Crucial for Local LLMs, Azure, or Proxies). | ❌ | OpenAI Default |
| `LLM_MODEL` | The model name to use (e.g., `gpt-4o`, `claude-3-opus`, `llama3`). | ✅ | `gpt-4` |
| **Gitea Configuration** |
| `GITEA_HOST` | Your Gitea server URL (e.g., `http://192.168.1.50:3000`). | ✅ | None |
| `GITEA_TOKEN` | Gitea Access Token (Settings -> Applications). | ✅ | None |
| **Optional** |
| `IGNORED_FILE_SUFFIX` | Comma-separated list of extensions to skip (e.g., `.json,.md`). | ❌ | None |
| `COPILOT_TOKEN` | Legacy support: Use this *instead* of `LLM_API_KEY` if using GitHub Copilot. | ❌ | None |

### Customizing the AI Prompt

You can control exactly how the AI reviews your code by editing `./prompts/code-review-pr.md`.

**Features of the Prompt System:**

*   **Markdown Support:** Write instructions using clean Markdown.
*   **YAML Front Matter:** You can add metadata at the top of the file (surrounded by `---`). The bot will strip this before sending it to the AI.
    ```yaml
    ---
    mode: 'agent'
    description: 'Strict Security Reviewer'
    ---
    ```
*   **Variable Substitution:** Inject dynamic values into your prompt using `${variable}` syntax.
    *   Example in `code-review-pr.md`: `Focus on: ${input-focus}`
    *   The bot automatically replaces this with the default context defined in the code (e.g., "security, performance, and code quality") or specific context if configured in the future.

## 🔗 Connecting to Gitea

Once the bot is running, you need to tell Gitea to send events to it.

1.  Navigate to your **Repository Settings** (or Organization Settings).
2.  Click on **Webhooks** > **Add Webhook** > **Gitea**.
3.  **Target URL:**
    *   If using Docker Network: `http://gitea-ai-codereview:3008/hook`
    *   If using distinct servers: `http://YOUR_BOT_IP:3008/hook`
    *   *(Note: Check `http://localhost:3008/docs` to verify the exact endpoint path if `/hook` fails).*
4.  **Trigger On:**
    *   [x] **Pull Request**
    *   [x] **Pull Request Synchronize** (if available, ensures updates are reviewed)
5.  Click **Add Webhook**.

## 📝 Usage

1.  Create a new Branch and push some code.
2.  Open a **Pull Request** in Gitea.
3.  The bot will receive the webhook, load the prompt from `./prompts/code-review-pr.md`, fetch the diff, send it to the AI, and post a review comment on the PR timeline automatically.

## ❓ Troubleshooting

*   **Bot doesn't reply:** Check the Docker logs (`docker logs gitea-ai-codereview`). If you see "Connection refused", ensure `GITEA_HOST` is reachable from inside the bot container (use `host.docker.internal` or the actual LAN IP, not `localhost`).
*   **Prompt not updating:** Ensure you have mounted the volume `- ./prompts:/app/prompts` in your `docker-compose.yml`. If running locally (no Docker), ensure you are editing the file in the project root.
*   **404 on Webhook:** Ensure the Target URL ends with the correct endpoint (usually `/hook` or `/webhook`).
*   **LLM Connection Errors:** If using a local LLM (like Ollama), verify `LLM_BASE_URL` is accessible by the container. Ensure the URL includes the version suffix (e.g., `/v1`).

### Relevant Video Resource

[Better Code Reviews with AI? GitHub Copilot and Qodo Merge Tested](https://www.youtube.com/watch?v=wmmMYFVNxA0)
This video compares different AI code review strategies and tools, helping you understand the type of feedback you can expect when integrating LLMs into your PR workflow.

