"""
Hybrid domain router for the orchestrator agent.

First pass: embedding similarity with lexical keyword boosts (~50ms).
If confidence is high, returns immediately. If confidence is low,
escalates to an LLM classification call for accurate routing (~200-500ms).

Decisions:
- Always picks the single highest-scoring domain (D2)
- Falls back to 'general' when top score < min_threshold (D3)
- Uses the existing HuggingFace embedding model (D1)
- Hybrid escalation to LLM for low-confidence results (D9)
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

from .agent_types import AgentType

logger = logging.getLogger(__name__)

# Domain exemplars: short representative queries per domain.
# Each exemplar is embedded at startup. At classify-time, the user message
# is compared against ALL exemplars and the domain with the highest
# single-exemplar match wins. Short query-like phrases work best because
# the user's input is also a short query — matching like-to-like.
#
# Includes domain-specific anchor terms (alembic, OWASP, OpenAPI, etc.)
# to sharpen separation between overlapping domains.
DOMAIN_EXEMPLARS: dict[str, list[str]] = {
    AgentType.SECURITY.value: [
        "find security vulnerabilities in this code",
        "are there any SQL injection or XSS issues",
        "check for hardcoded credentials and secrets",
        "is the authentication and authorization secure",
        "OWASP top 10 vulnerability scan",
        "are there any insecure deserialization or CSRF risks",
        "check for exposed secrets and sensitive data in code",
        "scan for CWE CVE SSRF RCE security weaknesses",
        "is user input sanitized to prevent injection attacks",
    ],
    AgentType.DATABASE.value: [
        "show me the database schema and tables",
        "are there any N+1 query problems",
        "check for missing database indexes",
        "how are database migrations managed",
        "review the database queries for optimization",
        "are there connection pooling or transaction issues",
        "check the ORM usage and data modeling",
        "review alembic prisma typeorm migration files",
        "check foreign key constraints and ERD relationships",
    ],
    AgentType.API.value: [
        "what REST API endpoints are available",
        "is there proper input validation on the API",
        "are API responses paginated correctly",
        "check the endpoint design and HTTP methods",
        "is rate limiting implemented on the API",
        "review CORS configuration and API security",
        "check the route definitions and middleware",
        "review OpenAPI swagger API documentation and contracts",
        "check auth headers and API versioning strategy",
    ],
    AgentType.PERFORMANCE.value: [
        "find performance bottlenecks in this code",
        "are there any memory leaks",
        "check for blocking I/O in async code",
        "find slow code paths and optimize them",
        "how can we improve speed and latency",
        "check for caching opportunities",
        "review algorithmic complexity and efficiency",
        "profile CPU usage and hot path optimization",
        "check for O(n²) nested loops and inefficient algorithms",
    ],
    AgentType.ARCHITECTURE.value: [
        "what is the architecture of this project",
        "how is this codebase structured and organized",
        "are there any circular dependencies",
        "what design patterns are used here",
        "review the module organization and layers",
        "check for SOLID principle violations",
        "explain the project structure and component layout",
        "review service boundaries and dependency graph",
        "check the separation between layers and modules",
    ],
    AgentType.TESTING.value: [
        "what is the test coverage",
        "are there any untested functions or code paths",
        "show me the test files",
        "are there any flaky or broken tests",
        "how are mocks and fixtures used in tests",
        "review the unit test and integration test quality",
        "check for missing test assertions",
        "review pytest conftest fixtures and parameterized tests",
        "check test isolation and arrange act assert pattern",
    ],
    AgentType.CODE_QUALITY.value: [
        "are there any code smells",
        "find duplicate or copy-pasted code",
        "check for magic numbers and hardcoded values",
        "which functions or classes are too long",
        "review naming conventions and code readability",
        "check for dead code and unused imports",
        "are there refactoring opportunities",
        "check for deep nesting and complex conditionals",
        "review type hints annotations and docstring coverage",
    ],
    AgentType.GENERAL.value: [
        "what does this function do",
        "explain this code to me",
        "where is the main entry point",
        "what calls this method or function",
        "how does the request flow work end to end",
        "help me understand this codebase",
        "find where something is defined in the code",
        "walk me through this code step by step",
        "what is this project about",
    ],
}

# Lexical keyword boosts: high-precision trigger words that strongly
# indicate a specific domain. Applied as a score boost BEFORE the
# embedding-based ranking to catch obvious signals that embeddings
# might miss. Each keyword maps to (domain, boost_amount).
LEXICAL_BOOSTS: dict[str, tuple[str, float]] = {
    # Security triggers
    "owasp": (AgentType.SECURITY.value, 0.15),
    "cve": (AgentType.SECURITY.value, 0.15),
    "cwe": (AgentType.SECURITY.value, 0.15),
    "xss": (AgentType.SECURITY.value, 0.15),
    "csrf": (AgentType.SECURITY.value, 0.15),
    "ssrf": (AgentType.SECURITY.value, 0.15),
    "sqli": (AgentType.SECURITY.value, 0.15),
    "vulnerability": (AgentType.SECURITY.value, 0.10),
    "injection": (AgentType.SECURITY.value, 0.10),
    "credential": (AgentType.SECURITY.value, 0.10),
    "credentials": (AgentType.SECURITY.value, 0.10),
    "secret": (AgentType.SECURITY.value, 0.10),
    "secrets": (AgentType.SECURITY.value, 0.10),
    # Database triggers
    "schema": (AgentType.DATABASE.value, 0.10),
    "migration": (AgentType.DATABASE.value, 0.10),
    "migrations": (AgentType.DATABASE.value, 0.10),
    "alembic": (AgentType.DATABASE.value, 0.15),
    "prisma": (AgentType.DATABASE.value, 0.15),
    "typeorm": (AgentType.DATABASE.value, 0.15),
    "foreign key": (AgentType.DATABASE.value, 0.10),
    "n+1": (AgentType.DATABASE.value, 0.15),
    "index": (AgentType.DATABASE.value, 0.08),
    "indexes": (AgentType.DATABASE.value, 0.10),
    # API triggers
    "endpoint": (AgentType.API.value, 0.10),
    "endpoints": (AgentType.API.value, 0.10),
    "openapi": (AgentType.API.value, 0.15),
    "swagger": (AgentType.API.value, 0.15),
    "rest api": (AgentType.API.value, 0.10),
    "rate limit": (AgentType.API.value, 0.10),
    "rate limiting": (AgentType.API.value, 0.10),
    "cors": (AgentType.API.value, 0.10),
    "middleware": (AgentType.API.value, 0.08),
    # Performance triggers
    "bottleneck": (AgentType.PERFORMANCE.value, 0.10),
    "bottlenecks": (AgentType.PERFORMANCE.value, 0.10),
    "memory leak": (AgentType.PERFORMANCE.value, 0.10),
    "latency": (AgentType.PERFORMANCE.value, 0.10),
    "profiling": (AgentType.PERFORMANCE.value, 0.10),
    "blocking i/o": (AgentType.PERFORMANCE.value, 0.10),
    # Architecture triggers
    "architecture": (AgentType.ARCHITECTURE.value, 0.10),
    "circular dependency": (AgentType.ARCHITECTURE.value, 0.10),
    "circular dependencies": (AgentType.ARCHITECTURE.value, 0.10),
    "design pattern": (AgentType.ARCHITECTURE.value, 0.10),
    "design patterns": (AgentType.ARCHITECTURE.value, 0.10),
    "solid principles": (AgentType.ARCHITECTURE.value, 0.10),
    # Testing triggers
    "test coverage": (AgentType.TESTING.value, 0.10),
    "unit test": (AgentType.TESTING.value, 0.10),
    "unit tests": (AgentType.TESTING.value, 0.10),
    "flaky test": (AgentType.TESTING.value, 0.10),
    "flaky tests": (AgentType.TESTING.value, 0.10),
    "pytest": (AgentType.TESTING.value, 0.15),
    "conftest": (AgentType.TESTING.value, 0.15),
    # Code quality triggers
    "code smell": (AgentType.CODE_QUALITY.value, 0.10),
    "code smells": (AgentType.CODE_QUALITY.value, 0.10),
    "naming convention": (AgentType.CODE_QUALITY.value, 0.10),
    "naming conventions": (AgentType.CODE_QUALITY.value, 0.10),
    "magic number": (AgentType.CODE_QUALITY.value, 0.10),
    "magic numbers": (AgentType.CODE_QUALITY.value, 0.10),
    "dead code": (AgentType.CODE_QUALITY.value, 0.10),
    "duplicate code": (AgentType.CODE_QUALITY.value, 0.10),
    "refactor": (AgentType.CODE_QUALITY.value, 0.08),
}

# Default minimum similarity threshold.
# Below this, fall back to 'general' (Decision D3).
DEFAULT_MIN_THRESHOLD = 0.30

# LLM escalation thresholds (Decision D9).
# When the embedding top score is at or below this, escalate to LLM.
LLM_ESCALATION_THRESHOLD = 0.70

# When the gap between top and runner-up is at or below this, escalate to LLM.
# A narrow gap means the embedding model isn't confident which domain is correct.
LLM_ESCALATION_GAP = 0.10

# Mid-range confidence: if the gap between top and runner-up exceeds this,
# trust the embedding result even when the absolute score is below
# LLM_ESCALATION_THRESHOLD. A large gap means the relative ranking is
# unambiguous — the LLM call would just add latency without changing the outcome.
MID_RANGE_CONFIDENCE_GAP = 0.20

# Maximum total lexical boost that can be applied to a single domain.
# Prevents multiple keyword hits from artificially inflating a domain's score
# past the high-confidence threshold.
MAX_LEXICAL_BOOST_PER_DOMAIN = 0.20

# Tiebreaker priority order.
# If two domains have the exact same cosine similarity score,
# the domain earlier in this list wins. Specialized domains take
# priority over 'general' since 'general' is the catch-all fallback.
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

# Valid domain names for LLM response validation.
VALID_DOMAINS: set[str] = set(DOMAIN_EXEMPLARS)

# System prompt for LLM classification fallback.
CLASSIFICATION_SYSTEM_PROMPT = (
    "You are a domain classifier for a code intelligence system. "
    "Given a user message about code, classify it into exactly ONE domain.\n\n"
    "Available domains:\n"
    "- security: Security vulnerabilities, authentication, authorization, injection attacks, secrets, "
    "cryptographic issues. Includes: login safety, session handling, protecting user data, "
    "attacker scenarios, access control, safe handling of sensitive information.\n"
    "- database: Database schema, queries, ORM, migrations, indexing, transactions, data modeling. "
    "Includes: where or how data is stored, saved, written, or persisted; data flow after "
    "form submissions; user information storage; anything about tables, records, or data persistence.\n"
    "- api: REST API design, endpoints, validation, pagination, rate limiting, CORS, middleware. "
    "Includes: how clients or external systems communicate with the backend; what data the "
    "server accepts or returns; integration points; request/response contracts.\n"
    "- performance: Performance bottlenecks, memory leaks, caching, latency, algorithmic complexity. "
    "Includes: slow pages or responses, long-running operations, speed optimization, "
    "why something takes too long, user complaints about waiting.\n"
    "- architecture: Software architecture, design patterns, dependencies, SOLID principles, module structure. "
    "Includes: codebase layout and organization, how services interact, overall project structure, "
    "where things are located in the codebase.\n"
    "- testing: Test coverage, unit tests, integration tests, mocking, fixtures, test quality. "
    "Includes: verifying correctness, catching bugs or regressions, confidence that code works, "
    "whether breakages would be detected, quality assurance.\n"
    "- code_quality: Code smells, refactoring, naming conventions, dead code, duplication, readability. "
    "Includes: maintainability, understandability for new developers, code cleanliness, "
    "repeated logic, overall code quality assessment.\n"
    "- general: General code questions, navigation, understanding code flow, debugging, explanations. "
    "Use ONLY when the message does not fit any specialized domain above.\n\n"
    "Classification approach:\n"
    "1. First, check if the message clearly matches a specialized domain from the descriptions above.\n"
    "2. If no clear match, use your own judgment — consider what the user is ultimately trying "
    "to achieve. Indirect or conversational phrasing often maps to a specialized domain "
    "(e.g., 'where does user info end up' is about data persistence → database).\n"
    "3. Choose 'general' ONLY as a last resort, when the message is genuinely about code "
    "navigation, explanation, or debugging with no underlying specialized intent.\n\n"
    "Do NOT misclassify just to avoid 'general' — if you are not confident that a specialized "
    "domain fits, 'general' is the correct choice.\n\n"
    "Respond with ONLY the domain name. No explanation, no punctuation, just the domain."
)


@dataclass
class RouteResult:
    """Result of domain classification."""
    domain: str
    score: float
    routing_method: str = "embedding"  # "embedding" or "llm"


class EmbeddingRouter:
    """
    Hybrid router: embedding similarity + LLM classification fallback.

    At startup, embeds all domain exemplars and caches the normalized vectors.
    On each message:
    1. Embeds the message and computes dot-product similarity against all
       cached exemplar vectors (vectors are pre-normalized, so dot product
       equals cosine similarity).
    2. Applies lexical keyword boosts for high-precision trigger words.
    3. Checks confidence (score threshold + gap to runner-up).
    4. High confidence → returns embedding result immediately.
    5. Low confidence → escalates to LLM classification call (Decision D9).
    """

    def __init__(
        self,
        embeddings: Embeddings,
        classification_llm: Optional[BaseChatModel] = None,
        domain_exemplars: Optional[dict[str, list[str]]] = None,
        min_threshold: float = DEFAULT_MIN_THRESHOLD,
    ):
        self._embeddings = embeddings
        self._classification_llm = classification_llm
        self._min_threshold = min_threshold
        self._exemplars = domain_exemplars or DOMAIN_EXEMPLARS
        # Maps domain -> list of exemplar vectors (normalized)
        self._domain_vectors: dict[str, list[np.ndarray]] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """
        Precompute and cache domain exemplar embeddings.
        Must be called once at startup before classify() is used.
        """
        logger.info("Initializing embedding router - computing exemplar vectors...")

        loop = asyncio.get_running_loop()
        total_exemplars = 0
        for domain, exemplars in self._exemplars.items():
            vectors = []
            for exemplar in exemplars:
                raw_vector = await loop.run_in_executor(
                    None, self._embeddings.embed_query, exemplar
                )
                vec = np.array(raw_vector, dtype=np.float32)
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec = vec / norm
                vectors.append(vec)
            self._domain_vectors[domain] = vectors
            total_exemplars += len(vectors)

        self._initialized = True
        llm_status = "enabled" if self._classification_llm else "disabled (embedding-only)"
        logger.info(
            f"Embedding router initialized with {len(self._domain_vectors)} domains, "
            f"{total_exemplars} total exemplars. LLM fallback: {llm_status}"
        )

    async def classify(self, message: str) -> RouteResult:
        """
        Classify a user message into a domain.

        Runs embedding similarity first. If confidence is high (score above
        threshold with clear gap to runner-up), returns immediately. If
        confidence is low, escalates to an LLM classification call.

        Args:
            message: The user's message text

        Returns:
            RouteResult with domain, score, and routing_method.
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
        # Normalize for dot-product similarity
        msg_norm = np.linalg.norm(message_vector)
        if msg_norm > 0:
            message_vector = message_vector / msg_norm

        # Compute best-exemplar similarity for each domain (dot product = cosine for unit vectors)
        scores: dict[str, float] = {}
        for domain, exemplar_vectors in self._domain_vectors.items():
            best_score = max(
                float(np.dot(message_vector, ev))
                for ev in exemplar_vectors
            )
            scores[domain] = best_score

        # Apply lexical keyword boosts
        scores = self._apply_lexical_boosts(message, scores)

        # Sort domains by score (descending), with priority tiebreaker
        sorted_domains = sorted(
            scores.keys(),
            key=lambda d: (
                scores[d],
                -DOMAIN_PRIORITY.index(d) if d in DOMAIN_PRIORITY else -len(DOMAIN_PRIORITY),
            ),
            reverse=True,
        )

        top_domain = sorted_domains[0]
        top_score = scores[top_domain]
        runner_up_domain = sorted_domains[1] if len(sorted_domains) > 1 else None
        runner_up_score = scores[runner_up_domain] if runner_up_domain else 0.0

        # Below minimum threshold — try LLM before falling back to general (Decision D3)
        if top_score < self._min_threshold:
            if self._classification_llm:
                llm_domain = await self._llm_classify(message)
                if llm_domain:
                    logger.info(
                        f"Router: embedding score {top_score:.3f} ({top_domain}) below threshold "
                        f"{self._min_threshold}, but LLM classified as '{llm_domain}'. Method: llm"
                    )
                    return RouteResult(domain=llm_domain, score=top_score, routing_method="llm")
            logger.info(
                f"Router: top score {top_score:.3f} ({top_domain}) below threshold "
                f"{self._min_threshold}. Falling back to 'general'."
            )
            return RouteResult(domain=AgentType.GENERAL.value, score=top_score)

        # Check confidence for LLM escalation (Decision D9)
        gap = top_score - runner_up_score
        is_high_confidence = (
            (top_score > LLM_ESCALATION_THRESHOLD and gap > LLM_ESCALATION_GAP)
            or gap > MID_RANGE_CONFIDENCE_GAP  # clear relative winner, even at moderate absolute scores
        )

        if is_high_confidence:
            runner_up_str = f"'{runner_up_domain}' ({runner_up_score:.3f})" if runner_up_domain else "none"
            logger.info(
                f"Router: classified as '{top_domain}' (score: {top_score:.3f}, "
                f"gap: {gap:.3f}). Runner-up: {runner_up_str}. Method: embedding"
            )
            return RouteResult(domain=top_domain, score=top_score, routing_method="embedding")

        # Low confidence — escalate to LLM if available
        if self._classification_llm:
            llm_domain = await self._llm_classify(message)
            if llm_domain:
                logger.info(
                    f"Router: LLM classified as '{llm_domain}' (embedding was '{top_domain}' "
                    f"at {top_score:.3f}, gap: {gap:.3f}). Method: llm"
                )
                return RouteResult(domain=llm_domain, score=top_score, routing_method="llm")
            # LLM call failed — fall through to embedding result
            logger.warning("Router: LLM classification failed, using embedding result as fallback")

        # No LLM available or LLM failed — use embedding result
        runner_up_str = f"'{runner_up_domain}' ({runner_up_score:.3f})" if runner_up_domain else "none"
        logger.info(
            f"Router: classified as '{top_domain}' (score: {top_score:.3f}, "
            f"gap: {gap:.3f}). Runner-up: {runner_up_str}. Method: embedding (no LLM)"
        )
        return RouteResult(domain=top_domain, score=top_score, routing_method="embedding")

    async def _llm_classify(self, message: str) -> Optional[str]:
        """
        Classify a message using an LLM call.
        Used as fallback when embedding confidence is low.

        Returns:
            Domain name string, or None if the call fails.
        """
        try:
            response = await self._classification_llm.ainvoke([
                SystemMessage(content=CLASSIFICATION_SYSTEM_PROMPT),
                HumanMessage(content=message),
            ])
            domain = response.content.strip().lower().replace('"', '').replace("'", "")
            if domain in VALID_DOMAINS:
                return domain
            logger.warning(f"LLM returned unknown domain '{domain}', falling back to embedding result")
            return None
        except Exception:
            logger.exception("LLM classification call failed")
            return None

    @staticmethod
    def _apply_lexical_boosts(message: str, scores: dict[str, float]) -> dict[str, float]:
        """
        Apply keyword-based score boosts for high-precision domain triggers.

        Scans the lowercased message for known trigger words/phrases and
        adds a boost to the corresponding domain's embedding score.
        Multiple keywords for the same domain stack, but each keyword
        is only counted once.
        """
        message_lower = message.lower()
        boosted = dict(scores)

        # Accumulate boosts per domain, then cap each at MAX_LEXICAL_BOOST_PER_DOMAIN
        domain_boosts: dict[str, float] = {}
        for keyword, (domain, boost) in LEXICAL_BOOSTS.items():
            if keyword in message_lower:
                domain_boosts[domain] = domain_boosts.get(domain, 0.0) + boost

        for domain, total_boost in domain_boosts.items():
            boosted[domain] = boosted.get(domain, 0.0) + min(total_boost, MAX_LEXICAL_BOOST_PER_DOMAIN)

        return boosted

    @property
    def is_initialized(self) -> bool:
        return self._initialized
