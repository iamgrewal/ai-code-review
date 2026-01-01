# /test Endpoint Configuration Guide

## Issue Analysis

The `/test` endpoint in [`main.py:469-480`](main.py:469-480) has a parameter definition issue. The current code:

```python
@app.post("/test")
async def test_code_review(request_body: str):
```

This treats `request_body` as a **query parameter** by default, not a request body. To fix this, the endpoint needs to be modified to use `Body()` or accept raw request body.

## Root Cause

FastAPI interprets simple type parameters (like `str`) as query parameters unless explicitly marked as body parameters using `Body()` or by using `Request` object directly.

## Fix Required

The endpoint needs to be modified. See "Required Code Changes" section below.

## Required Code Changes

The `/test` endpoint needs to be modified in [`main.py:469-480`](main.py:469-480):

### Option 1: Use Body() to accept JSON

```python
from fastapi import Body

@app.post("/test")
async def test_code_review(request_body: str = Body(..., embed=True)):
    from codereview.copilot import Copilot
    copilot = Copilot(config)
    logger.success("Test endpoint called")
    return {"message": copilot.code_review(request_body)}
```

With this change, use this curl command:
```bash
curl -X POST http://localhost:3008/test \
  -H "Content-Type: application/json" \
  -d '{"request_body": "a = 2\nb = 5\na + b = 5"}'
```

### Option 2: Use Request to accept raw text

```python
from fastapi import Request

@app.post("/test")
async def test_code_review(request: Request):
    from codereview.copilot import Copilot
    copilot = Copilot(config)
    request_body = await request.body()
    request_body = request_body.decode("utf-8")
    logger.success("Test endpoint called")
    return {"message": copilot.code_review(request_body)}
```

With this change, use this curl command:
```bash
curl -X POST http://localhost:3008/test \
  -H "Content-Type: text/plain" \
  -d "a = 2
b = 5
a + b = 5"
```

### Option 3: Accept both JSON and raw text

```python
from fastapi import Request, Body
from typing import Optional

@app.post("/test")
async def test_code_review(
    request: Request,
    request_body: Optional[str] = Body(None, embed=True)
):
    from codereview.copilot import Copilot
    copilot = Copilot(config)
    
    if request_body is not None:
        # JSON body received
        body = request_body
    else:
        # Raw text body received
        raw_body = await request.body()
        body = raw_body.decode("utf-8")
    
    logger.success("Test endpoint called")
    return {"message": copilot.code_review(body)}
```

With this change, both curl commands work:
```bash
# JSON format
curl -X POST http://localhost:3008/test \
  -H "Content-Type: application/json" \
  -d '{"request_body": "a = 2\nb = 5\na + b = 5"}'

# Raw text format
curl -X POST http://localhost:3008/test \
  -H "Content-Type: text/plain" \
  -d "a = 2
b = 5
a + b = 5"
```

## Required Environment Variables

Before testing, ensure your `.env` file has these required variables:

```bash
# Required for Gitea
GITEA_TOKEN=your_gitea_token_here
GITEA_HOST=http://server:3000

# Required for LLM (choose one method)
LLM_API_KEY=your_api_key_here
# OR
OPENAI_KEY=your_openai_key_here
# OR  
COPILOT_TOKEN=your_copilot_token_here

# Optional LLM configuration
LLM_BASE_URL=https://api.openai.com/v1  # or your custom endpoint
LLM_MODEL=gpt-4
LLM_LOCALE=en_us
```

## Correct curl Commands

### Option 1: Send as JSON (Recommended)

```bash
curl -X POST http://localhost:3008/test \
  -H "Content-Type: application/json" \
  -d '{
    "request_body": "a = 2\nb = 5\na + b = 5"
  }'
```

### Option 2: Send as raw text/plain

```bash
curl -X POST http://localhost:3008/test \
  -H "Content-Type: text/plain" \
  -d "a = 2
b = 5
a + b = 5"
```

### Option 3: Send code diff format (more realistic)

```bash
curl -X POST http://localhost:3008/test \
  -H "Content-Type: text/plain" \
  -d 'diff --git a/src/main.py b/src/main.py
index 1234567..abcdef 100644
--- a/src/main.py
+++ b/src/main.py
@@ -1,5 +1,5 @@
 def calculate():
-    a = 2
+    a = 5
     b = 5
-    return a + b  # Returns 7
+    return a + b  # Returns 10'
```

## Python Code Examples

### Using requests library

```python
import requests

# Option 1: JSON format
response = requests.post(
    "http://localhost:3008/test",
    json={
        "request_body": "a = 2\nb = 5\na + b = 5"
    }
)
print(response.json())

# Option 2: Raw text format
response = requests.post(
    "http://localhost:3008/test",
    data="a = 2\nb = 5\na + b = 5",
    headers={"Content-Type": "text/plain"}
)
print(response.json())
```

### Using httpx (async)

```python
import httpx

async def test_code_review():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:3008/test",
            content="a = 2\nb = 5\na + b = 5",
            headers={"Content-Type": "text/plain"}
        )
        return response.json()
```

## Expected Response

```json
{
  "message": "AI code review response here..."
}
```

## Troubleshooting

### Error: "LLM_API_KEY is required"

- Make sure you have set `LLM_API_KEY`, `OPENAI_KEY`, or `COPILOT_TOKEN` in your `.env` file
- Restart the server after updating `.env`

### Error: "GITEA_TOKEN is required"

- Set `GITEA_TOKEN` in your `.env` file
- This is required even for the `/test` endpoint

### Error: 422 Unprocessable Entity

- This means the request body format is incorrect
- Use one of the correct curl commands above
- Ensure Content-Type header is set correctly

### Connection Refused

- Make sure the server is running on port 3008
- Start the server with: `python main.py` or `uvicorn main:app --host 0.0.0.0 --port 3008`

## Endpoint Details

| Property | Value |
|----------|-------|
| URL | `http://localhost:3008/test` |
| Method | POST |
| Content-Type | `application/json` or `text/plain` (after fix) |
| Body | String containing code or diff |
| Status | DEPRECATED (use `/v1/webhook/{platform}` for production) |
| Issue | Currently broken - requires code fix |
