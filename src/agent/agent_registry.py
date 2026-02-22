"""
Agent Registry for managing multiple specialized agent instances.

All agents share the same infrastructure (tools, memory, checkpointer, etc.)
but have different system prompts for specialized behavior.

The registry manages both:
- Per-agent instances (old flow): one CodeIntelligenceAgent per AgentType with static prompts
- Orchestrator instance (new flow): single agent with dynamic prompt injection + embedding router

Decision D8: Both flows coexist. Orchestrator is the new default, old per-agent flow stays functional.
"""
import logging
from typing import Dict, List, Optional, Any

from langchain_core.embeddings import Embeddings

from .agent_types import AgentType
from .prompt_loader import load_prompt
from .code_intelligence_agent import CodeIntelligenceAgent
from .router import EmbeddingRouter
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
        self._agents: Dict[AgentType, CodeIntelligenceAgent] = {}  # Per-type agents (old flow)
        self._orchestrator_agent: Optional[CodeIntelligenceAgent] = None  # Orchestrator (new flow)
        self._router: Optional[EmbeddingRouter] = None  # Embedding router (new flow)
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
        Initialize the registry: preload per-agent instances, then create
        the orchestrator agent and embedding router.

        Args:
            preload_types: List of agent types to preload for the old per-agent flow.
                          Defaults to all types except ORCHESTRATOR (which gets special init).
        """
        if preload_types is None:
            # Preload all agent types EXCEPT orchestrator (it gets special initialization below)
            preload_types = [t for t in AgentType if t != AgentType.ORCHESTRATOR]

        # Filter out ORCHESTRATOR even if explicitly passed — it's handled separately
        per_agent_types = [t for t in preload_types if t != AgentType.ORCHESTRATOR]

        logger.info(f"Starting agent registry with preload types: {[t.value for t in per_agent_types]}")

        # --- Per-agent preloading (existing flow) ---
        for agent_type in per_agent_types:
            await self.get_agent(agent_type)

        # --- Initialize the hybrid router (Decision D9) ---
        from langchain.chat_models import init_chat_model
        classification_llm = init_chat_model(self._default_model_id, temperature=0.0)

        self._router = EmbeddingRouter(
            embeddings=self._embeddings,
            classification_llm=classification_llm,
        )
        await self._router.initialize()

        # --- Create orchestrator agent with auto-routed memory tools ---
        from .memory_tools import (
            create_auto_routed_manage_memory_tool,
            create_auto_routed_search_memory_tool
        )

        orchestrator_prompt = load_prompt(AgentType.ORCHESTRATOR)

        self._orchestrator_agent = CodeIntelligenceAgent(
            name="orchestrator_agent",
            tools=self._tools,
            embeddings=self._embeddings,
            system_prompt=orchestrator_prompt,
            default_llm_model_id=self._default_model_id,
            temperature=self._temperature,
            base_memory_namespace="orchestrator_agent_memories",
            # Defensive fallback namespace — not expected to be used in practice
            # because the router always classifies a domain (routed_domain is always set).
            # Memory routing is handled by the auto-routed tools and
            # domain-based middleware. Kept as a safety net for edge cases.
            memory_tools=[
                create_auto_routed_manage_memory_tool(),
                create_auto_routed_search_memory_tool()
            ],
        )
        await self._orchestrator_agent.startup()

        self._initialized = True
        logger.info(
            f"Agent registry started: {len(per_agent_types)} per-agent instances + "
            f"orchestrator agent + embedding router"
        )

    def get_orchestrator_agent(self) -> CodeIntelligenceAgent:
        """Get the orchestrator agent instance."""
        if self._orchestrator_agent is None:
            raise RuntimeError("Agent registry not initialized or orchestrator not created.")
        return self._orchestrator_agent

    def get_router(self) -> EmbeddingRouter:
        """Get the embedding router instance."""
        if self._router is None:
            raise RuntimeError("Agent registry not initialized or router not created.")
        return self._router

    async def shutdown(self) -> None:
        """Shutdown all active agents (per-type + orchestrator) and cleanup resources."""
        logger.info(f"Shutting down agent registry. Active agents: {self.list_active_agents()}")

        # Shutdown per-agent instances
        for agent_type, agent in self._agents.items():
            try:
                await agent.shutdown()
                logger.info(f"Agent {agent_type.value} shut down successfully")
            except Exception as e:
                logger.error(f"Error shutting down agent {agent_type.value}: {e}")

        # Shutdown orchestrator agent
        if self._orchestrator_agent:
            try:
                await self._orchestrator_agent.shutdown()
                logger.info("Orchestrator agent shut down successfully")
            except Exception as e:
                logger.error(f"Error shutting down orchestrator agent: {e}")
            self._orchestrator_agent = None

        self._router = None
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
