"""
Embedding-based domain router for the orchestrator agent.

Classifies user messages into specialized domains (security, database, etc.)
using cosine similarity between the message embedding and precomputed
domain description embeddings.

Decisions:
- Always picks the single highest-scoring domain (D2)
- Falls back to 'general' when top score < min_threshold (D3)
- Uses the existing HuggingFace embedding model (D1)
"""

import asyncio
import logging
from typing import Optional

import numpy as np
from langchain_core.embeddings import Embeddings

from .agent_types import AgentType

logger = logging.getLogger(__name__)

# Domain descriptions for embedding-based classification.
# These are embedded at startup and compared against user messages.
# Keep descriptions focused on the vocabulary/terms a user would use
# when asking questions in that domain.
DOMAIN_DESCRIPTIONS: dict[str, str] = {
    AgentType.SECURITY.value: (
        "Security vulnerabilities and attack vectors including OWASP top 10, SQL injection, "
        "NoSQL injection, OS command injection, LDAP injection, XSS, CSRF, SSRF, "
        "and insecure deserialization via pickle.load or yaml.load. Authentication and "
        "authorization weaknesses such as hardcoded credentials, weak passwords, missing "
        "login protection, session token issues, and broken access control. Cryptographic "
        "problems like use of MD5, SHA1, DES, ECB mode, weak random number generation "
        "instead of bcrypt or argon2. Dangerous patterns like shell=True, os.system, "
        "subprocess with user input, sensitive data in logs, verbose error messages, "
        "and secrets exposed in API responses or source code."
    ),
    AgentType.DATABASE.value: (
        "Database schema design, query optimization, and data modeling including foreign keys, "
        "joins, indexes, and constraints. N+1 query problems, lazy loading vs eager loading "
        "with joinedload, selectinload, or prefetch_related. ORM anti-patterns like detached "
        "entities, raw SQL with string formatting, missing migrations, and schema drift. "
        "Connection management issues such as connection pooling, connection leaks, pool "
        "exhaustion, and missing transaction boundaries with commit and rollback. Query "
        "performance problems like SELECT *, unbounded queries without LIMIT, full table "
        "scans, Cartesian products, and missing indexes. Repository pattern, DAO classes, "
        "alembic migrations, cascade deletes, and race conditions in concurrent writes."
    ),
    AgentType.API.value: (
        "REST API design and endpoint structure including resource naming, HTTP methods, "
        "status codes, versioning, and idempotency. Request validation with Pydantic models, "
        "serializers, or schema validators. Response design problems like over-fetching, "
        "under-fetching, inconsistent error formats, and missing pagination on list endpoints "
        "with limit, offset, or cursor-based pagination. API security including missing "
        "authentication decorators, unprotected endpoints, missing rate limiting, overly "
        "permissive CORS configuration, and input injection via request parameters. "
        "OpenAPI documentation, route decorators like @get, @post, @put, @patch, @delete, "
        "middleware chains, content negotiation, GraphQL schema design, and API contracts."
    ),
    AgentType.PERFORMANCE.value: (
        "Performance bottlenecks and algorithmic complexity including O(n²) nested loops, "
        "O(n³) operations, linear searches with 'in' checks on lists, and sorting inside "
        "iterations. Memory issues like memory leaks, GC pressure, unbounded caches, large "
        "object allocation, and string concatenation with += in loops instead of join or "
        "StringBuilder. I/O performance problems such as synchronous blocking I/O in async "
        "code, sequential HTTP requests instead of parallel with Promise.all or asyncio.gather, "
        "missing connection pooling, readFileSync, and loading entire files into memory instead "
        "of streaming or chunking. Caching strategies with @lru_cache, TTL expiry, and cache "
        "invalidation. Concurrency issues like thread contention, deadlocks, race conditions, "
        "and over-threading. Profiling, latency, throughput, CPU usage, and hot path optimization."
    ),
    AgentType.ARCHITECTURE.value: (
        "Software architecture and design patterns including Clean Architecture, Hexagonal "
        "Architecture, MVC, and layered architecture. Dependency management problems like "
        "circular dependencies, circular imports, package cycles, wrong dependency direction, "
        "and tight coupling between modules. Layer violations where controllers access "
        "repositories directly bypassing service layers. SOLID principle violations especially "
        "dependency inversion and single responsibility. Structural anti-patterns like God "
        "classes with too many responsibilities, spaghetti code, feature envy, and shotgun "
        "surgery. Code organization issues including poor cohesion, missing abstractions, "
        "concrete dependencies instead of interfaces, hub classes, orphan classes, "
        "inheritance hierarchy problems, and inconsistent module structure."
    ),
    AgentType.TESTING.value: (
        "Test coverage gaps, untested functions, untested code paths, and missing tests for "
        "critical or complex code. Unit tests, integration tests, and end-to-end test strategy. "
        "Test quality issues like tests without assertions, flaky tests with intermittent "
        "failures, slow tests, brittle tests coupled to implementation, and dead or duplicate "
        "tests. Test design patterns including AAA pattern (Arrange Act Assert), test isolation, "
        "fixtures and conftest setup, mocking with mock, patch, stub, fake, and spy. "
        "Over-mocking that hides real bugs, missing error path testing with raises or throws, "
        "missing edge case coverage, and TDD workflow. Test frameworks, parameterized tests, "
        "test organization, and test-to-code ratio per module."
    ),
    AgentType.CODE_QUALITY.value: (
        "Code smells and clean code issues including long methods over 30 lines, large classes "
        "over 300 lines or 10+ methods, long parameter lists, and duplicate or copy-pasted "
        "code. Naming and readability problems like unclear variable names, misleading names, "
        "inconsistent naming conventions, magic numbers and unexplained hardcoded literals, "
        "and complex boolean expressions that are hard to read. Structural issues such as "
        "deep nesting over 4 levels that needs guard clauses, complex conditionals, flag "
        "arguments with boolean parameters, and primitive obsession. Refactoring opportunities "
        "like extract method, extract class, and feature envy. Documentation gaps including "
        "missing docstrings, outdated comments, TODO and FIXME accumulation as technical debt, "
        "missing type hints and annotations, and dead or unreachable code."
    ),
    AgentType.GENERAL.value: (
        "General code questions, navigation, and understanding how code works. Finding where "
        "something is defined, what calls a function, where a class is used, and tracing "
        "execution flow through call chains. Dependency mapping to understand what depends on "
        "a component and what breaks if it changes. Impact analysis for breaking changes and "
        "downstream effects. Debugging support to locate issues, trace data flow, and find "
        "entry points. Explaining what a function, class, or module does. Semantic code search "
        "to discover related code by concept. General programming questions and code walkthroughs."
    ),
}

# Default minimum similarity threshold.
# Below this, fall back to 'general' (Decision D3).
DEFAULT_MIN_THRESHOLD = 0.3

# Tiebreaker priority order.
# If two domains have the exact same cosine similarity score,
# the domain earlier in this list wins. Specialized domains take
# priority over 'general' since 'general' is the catch-all fallback.
# Exact float ties are extremely unlikely in practice, but this
# ensures deterministic behavior.
DOMAIN_PRIORITY: list[str] = [
    AgentType.SECURITY.value,
    AgentType.DATABASE.value,
    AgentType.API.value,
    AgentType.PERFORMANCE.value,
    AgentType.ARCHITECTURE.value,
    AgentType.TESTING.value,
    AgentType.CODE_QUALITY.value,
    AgentType.GENERAL.value,  # Always last — it's the fallback
]


class EmbeddingRouter:
    """
    Routes user messages to the appropriate domain using embedding similarity.

    At startup, embeds all domain descriptions and caches the vectors.
    On each message, embeds the message and computes cosine similarity
    against all cached domain vectors. Returns the top-scoring domain.

    Tiebreaker: On exact score ties (extremely unlikely with float cosine
    similarity), DOMAIN_PRIORITY order is used — specialized domains win
    over 'general'.
    """

    def __init__(
        self,
        embeddings: Embeddings,
        domain_descriptions: Optional[dict[str, str]] = None,
        min_threshold: float = DEFAULT_MIN_THRESHOLD,
    ):
        self._embeddings = embeddings
        self._min_threshold = min_threshold
        self._descriptions = domain_descriptions or DOMAIN_DESCRIPTIONS
        self._domain_vectors: dict[str, np.ndarray] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """
        Precompute and cache domain description embeddings.
        Must be called once at startup before classify() is used.
        """
        logger.info("Initializing embedding router - computing domain vectors...")

        loop = asyncio.get_running_loop()
        for domain, description in self._descriptions.items():
            raw_vector = await loop.run_in_executor(
                None, self._embeddings.embed_query, description
            )
            self._domain_vectors[domain] = np.array(raw_vector, dtype=np.float32)

        self._initialized = True
        logger.info(
            f"Embedding router initialized with {len(self._domain_vectors)} domains: "
            f"{list(self._domain_vectors.keys())}"
        )

    async def classify(self, message: str) -> tuple[str, float]:
        """
        Classify a user message into a domain.

        Runs the embedding call in a thread executor to avoid blocking
        the async event loop (~50ms for HuggingFace model).

        Args:
            message: The user's message text

        Returns:
            Tuple of (domain_name, similarity_score).
            Falls back to 'general' if top score < min_threshold.

        Raises:
            RuntimeError: If initialize() has not been called.
        """
        if not self._initialized:
            raise RuntimeError(
                "EmbeddingRouter not initialized. Call initialize() first."
            )

        # Embed the user message in a thread executor to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        raw_vector = await loop.run_in_executor(
            None, self._embeddings.embed_query, message
        )
        message_vector = np.array(raw_vector, dtype=np.float32)

        # Compute cosine similarity against all domain vectors
        scores: dict[str, float] = {}
        for domain, domain_vector in self._domain_vectors.items():
            scores[domain] = self._cosine_similarity(message_vector, domain_vector)

        # Pick the highest-scoring domain (Decision D2: always top score).
        # On exact ties, use DOMAIN_PRIORITY order as tiebreaker
        # (specialized domains win over general).
        top_domain = max(
            scores,
            key=lambda d: (
                scores[d],
                -DOMAIN_PRIORITY.index(d) if d in DOMAIN_PRIORITY else -len(DOMAIN_PRIORITY),
            ),
        )
        top_score = scores[top_domain]

        # Fall back to general if below threshold (Decision D3)
        if top_score < self._min_threshold:
            logger.info(
                f"Router: top score {top_score:.3f} ({top_domain}) below threshold "
                f"{self._min_threshold}. Falling back to 'general'."
            )
            return AgentType.GENERAL.value, top_score

        runner_up = self._get_runner_up(scores, top_domain)
        logger.info(
            f"Router: classified as '{top_domain}' (score: {top_score:.3f}). "
            f"Runner-up: {runner_up}"
        )
        return top_domain, top_score

    @staticmethod
    def _cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        dot_product = np.dot(vec_a, vec_b)
        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot_product / (norm_a * norm_b))

    @staticmethod
    def _get_runner_up(scores: dict[str, float], top_domain: str) -> str:
        """Get the runner-up domain for logging."""
        remaining = {k: v for k, v in scores.items() if k != top_domain}
        if not remaining:
            return "none"
        runner_up = max(remaining, key=remaining.get)
        return f"'{runner_up}' ({remaining[runner_up]:.3f})"

    @property
    def is_initialized(self) -> bool:
        return self._initialized
