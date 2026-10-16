"""Real SDK client. Tool schemas come from tools/list, execution uses tools/call."""
from contextlib import asynccontextmanager
import json
import os

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


def unpack(result):
    data = getattr(result, "structured_content", None) or getattr(result, "structuredContent", None)
    if data is not None:
        return data
    texts = [c.text for c in result.content if getattr(c, "type", None) == "text"]
    if getattr(result, "is_error", False) or getattr(result, "isError", False):
        return {"error": " ".join(texts)[:1000]}
    return json.loads(texts[0]) if len(texts) == 1 else {"text": texts}


@asynccontextmanager
async def connect(capability=None, url=None, transport=None):
    url = url or os.environ.get("EW_MCP_INTERNAL_URL", f"http://127.0.0.1:{os.environ.get('PORT', '8000')}/mcp/")
    headers = {"x-ew-agent-capability": capability} if capability else {}
    async with httpx2.AsyncClient(headers=headers, timeout=30, trust_env=False, transport=transport) as http:
        async with streamable_http_client(url, http_client=http) as streams:
            async with ClientSession(streams[0], streams[1], read_timeout_seconds=30) as session:
                initialized = await session.initialize()
                discovery = await session.list_tools()
                tools = [{"type": "function", "function": {"name": tool.name,
                    "description": tool.description or "", "parameters": tool.model_dump(by_alias=True)["inputSchema"]}}
                    for tool in discovery.tools]
                yield session, tools, initialized.model_dump(by_alias=True)
