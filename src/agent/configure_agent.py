from src.agent import CodeIntelligenceAgent
from src.agent.embeddings import get_embedding_model
from src.agent.mcp.mcp_client import mcp_client
from src.utils.settings import settings


async def configure_agent() -> CodeIntelligenceAgent:
    system_prompt = await mcp_client.get_prompt(server_name=settings.mcp_server_name, prompt_name=settings.mcp_prompt_name)

    if system_prompt is None or len(system_prompt) == 0:
        raise ValueError(f"Prompt '{settings.mcp_prompt_name}' not found on MCP server '{settings.mcp_server_name}'")

    tools = await mcp_client.get_tools()
    agent = CodeIntelligenceAgent(
        name="Code Intelligence Agent",
        tools=tools,
        embeddings=get_embedding_model(),
        system_prompt=system_prompt[0].content,
        default_llm_model_id=settings.default_agent_model,
        temperature=settings.agent_model_temperature,
        base_memory_namespace="code_intelligence_agent_memories"
    )
    return agent
