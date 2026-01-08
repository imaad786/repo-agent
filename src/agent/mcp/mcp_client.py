from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import MCPToolCallRequest

from src.utils.settings import settings


async def inject_dynamic_headers(request: MCPToolCallRequest, call_next):
    if request.headers is None:
        request.headers = {}
    # X-Task-Id is REQUIRED for data isolation in the MCP server
    request.headers["X-Task-Id"] = request.runtime.context.task_id
    # X-Repo-Namespace is optional for additional filtering/metadata
    request.headers["X-Repo-Namespace"] = request.runtime.context.repo_namespace or ""
    response = await call_next(request)
    return response


mcp_client = MultiServerMCPClient(
    {
        "Taazaa AI MCP Server": {
            "transport": "http",
            "url": settings.mcp_server_url
        }
    },
    tool_interceptors=[inject_dynamic_headers]
)