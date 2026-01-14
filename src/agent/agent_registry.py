"""
Agent Registry for managing multiple specialized agent instances.

All agents share the same infrastructure (tools, memory, checkpointer, etc.)
but have different system prompts for specialized behavior.
"""
import logging
from typing import Dict, List, Optional, Any

from langchain_core.embeddings import Embeddings

from .agent_types import AgentType
from .prompt_loader import load_prompt
from .code_intelligence_agent import CodeIntelligenceAgent
from .mcp.mcp_client import mcp_client
from .embeddings import get_embedding_model
from ..utils.settings import settings

logger = logging.getLogger(__name__)


class AgentRegistry:
    """
    Registry for managing multiple agent instances.

    All agents share:
    - MCP Tools
    - Embeddings
    - Checkpointer (per-session)
    - Memory Store
    - Summarization middleware

    Agents differ by:
    - System prompt (loaded from prompts/*.md)
    - Memory namespace (isolated per agent type)
    """

    def __init__(
        self,
        tools: List[Any],
        embeddings: Embeddings,
        default_model_id: str,
        temperature: float
    ):
        """
        Initialize the agent registry.

        Args:
            tools: MCP tools available to all agents
            embeddings: Embedding model for memory operations
            default_model_id: Default LLM model ID
            temperature: LLM temperature setting
        """
        self._tools = tools
        self._embeddings = embeddings
        self._default_model_id = default_model_id
        self._temperature = temperature
        self._agents: Dict[AgentType, CodeIntelligenceAgent] = {}
        self._initialized = False

    async def get_agent(self, agent_type: AgentType) -> CodeIntelligenceAgent:
        """
        Get or create an agent instance for the given type.

        Agents are lazily initialized on first request.

        Args:
            agent_type: Type of agent to get

        Returns:
            Initialized CodeIntelligenceAgent instance
        """
        if agent_type not in self._agents:
            await self._create_agent(agent_type)

        return self._agents[agent_type]

    async def get_agent_by_name(self, agent_type_name: str) -> CodeIntelligenceAgent:
        """
        Get agent by type name string.

        Args:
            agent_type_name: String name of agent type (e.g., "security")

        Returns:
            Initialized CodeIntelligenceAgent instance

        Raises:
            ValueError: If agent type name is invalid
        """
        try:
            agent_type = AgentType(agent_type_name)
        except ValueError:
            raise ValueError(
                f"Invalid agent type: {agent_type_name}. "
                f"Valid types: {AgentType.values()}"
            )
        return await self.get_agent(agent_type)

    async def _create_agent(self, agent_type: AgentType) -> None:
        """
        Create and initialize a new agent instance.

        Args:
            agent_type: Type of agent to create
        """
        logger.info(f"Creating agent instance for type: {agent_type.value}")

        # Load specialized prompt
        prompt = load_prompt(agent_type)

        # Create agent with specialized prompt
        agent = CodeIntelligenceAgent(
            name=f"{agent_type.value}_agent",
            tools=self._tools,
            embeddings=self._embeddings,
            system_prompt=prompt,
            default_llm_model_id=self._default_model_id,
            temperature=self._temperature,
            base_memory_namespace=f"{agent_type.value}_agent_memories"
        )

        # Initialize the agent (sets up checkpointer, store, etc.)
        await agent.startup()

        self._agents[agent_type] = agent
        logger.info(f"Agent {agent_type.value} initialized successfully")

    def list_available_types(self) -> List[str]:
        """Return list of all available agent types."""
        return AgentType.values()

    def list_active_agents(self) -> List[str]:
        """Return list of currently initialized agent types."""
        return [agent_type.value for agent_type in self._agents.keys()]

    async def startup(self, preload_types: Optional[List[AgentType]] = None) -> None:
        """
        Initialize the registry and preload agent types.

        Args:
            preload_types: List of agent types to preload. Defaults to ALL agent types.
        """
        if preload_types is None:
            # Preload all agent types by default
            preload_types = list(AgentType)

        logger.info(f"Starting agent registry with preload types: {[t.value for t in preload_types]}")

        for agent_type in preload_types:
            await self.get_agent(agent_type)

        self._initialized = True
        logger.info(f"Agent registry started. Active agents: {self.list_active_agents()}")

    async def shutdown(self) -> None:
        """Shutdown all active agents and cleanup resources."""
        logger.info(f"Shutting down agent registry. Active agents: {self.list_active_agents()}")

        for agent_type, agent in self._agents.items():
            try:
                await agent.shutdown()
                logger.info(f"Agent {agent_type.value} shut down successfully")
            except Exception as e:
                logger.error(f"Error shutting down agent {agent_type.value}: {e}")

        self._agents.clear()
        self._initialized = False
        logger.info("Agent registry shutdown complete")

    @property
    def is_initialized(self) -> bool:
        """Check if registry has been initialized."""
        return self._initialized


# Global registry instance
_registry: Optional[AgentRegistry] = None


async def initialize_registry(
    preload_types: Optional[List[AgentType]] = None
) -> AgentRegistry:
    """
    Initialize the global agent registry.

    Args:
        preload_types: Agent types to preload. Defaults to ALL agent types.

    Returns:
        Initialized AgentRegistry instance
    """
    global _registry

    # Fetch tools from MCP server
    tools = await mcp_client.get_tools()

    # Get embeddings
    embeddings = get_embedding_model()

    # Create registry
    _registry = AgentRegistry(
        tools=tools,
        embeddings=embeddings,
        default_model_id=settings.default_agent_model,
        temperature=settings.agent_model_temperature
    )

    # Initialize with preloaded types
    await _registry.startup(preload_types)

    return _registry


def get_registry() -> AgentRegistry:
    """
    Get the global agent registry instance.

    Returns:
        AgentRegistry instance

    Raises:
        RuntimeError: If registry has not been initialized
    """
    if _registry is None:
        raise RuntimeError(
            "Agent registry not initialized. Call initialize_registry() first."
        )
    return _registry


async def shutdown_registry() -> None:
    """Shutdown the global agent registry."""
    global _registry

    if _registry is not None:
        await _registry.shutdown()
        _registry = None
