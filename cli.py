#!/usr/bin/env python3
"""
CLI for testing the Code Intelligence Agent locally.

Usage:
    python cli.py

Requirements:
    pip install rich

This CLI provides an interactive interface to:
- Create chat sessions with different agent types
- Stream chat responses with markdown rendering
- View conversation history
"""

import os

# Force CPU mode for embeddings to avoid CUDA issues in CLI
os.environ["CUDA_VISIBLE_DEVICES"] = ""

# Suppress debug logs
os.environ["LOG_LEVEL"] = "WARNING"

import logging
# Suppress noisy loggers
for logger_name in [
    "httpx", "httpcore", "urllib3", "mcp",
    "sentence_transformers", "transformers", "torch",
    "root", "src", "src.agent", "src.agent.code_intelligence_agent",
    "src.services", "markdown_it",
    "openai", "openai._base_client", "anthropic", "google", "google.ai",
]:
    logging.getLogger(logger_name).setLevel(logging.WARNING)

import asyncio
import sys
from uuid import UUID, uuid4
from typing import Optional

# Rich imports for TUI
try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.table import Table
    from rich.live import Live
    from rich.text import Text
    from rich.rule import Rule
    from rich.style import Style
except ImportError:
    print("Error: 'rich' library is required. Install it with: pip install rich")
    sys.exit(1)

# Initialize Rich console
console = Console()

# Styles
USER_STYLE = Style(color="cyan", bold=True)
AI_STYLE = Style(color="green")
TOOL_STYLE = Style(color="yellow", dim=True)
ERROR_STYLE = Style(color="red", bold=True)
INFO_STYLE = Style(color="blue")

# Current model ID (can be changed during chat)
current_model_id: Optional[str] = None


async def initialize_app():
    """Initialize the application (database, agent registry, etc.)"""
    console.print("\n[bold blue]Initializing Code Intelligence Agent CLI...[/bold blue]\n")

    # Suppress all loggers during initialization
    logging.disable(logging.WARNING)

    # Import and initialize components
    from src.db.context import DbContext
    from src.agent.agent_registry import initialize_registry

    try:
        # Initialize database
        console.print("  [dim]→ Initializing database connection...[/dim]")
        DbContext.initialize()
        console.print("  [green]✓[/green] Database initialized")

        # Initialize agent registry (this will preload all agents)
        console.print("  [dim]→ Initializing agent registry (this may take a moment)...[/dim]")
        await initialize_registry()
        console.print("  [green]✓[/green] Agent registry initialized")

        console.print("\n[bold green]Ready![/bold green]\n")

        # Re-enable logging but keep it quiet
        logging.disable(logging.NOTSET)
        # Re-apply log level suppression after enabling
        logging.getLogger("src").setLevel(logging.WARNING)
        logging.getLogger("src.agent").setLevel(logging.WARNING)
        logging.getLogger("src.agent.code_intelligence_agent").setLevel(logging.WARNING)
        logging.getLogger("src.services").setLevel(logging.WARNING)
        return True

    except Exception as e:
        console.print(f"\n[bold red]Initialization failed:[/bold red] {e}")
        console.print("\n[dim]Make sure your .env.local file is configured correctly.[/dim]")
        return False


async def shutdown_app():
    """Cleanup resources"""
    from src.agent.agent_registry import shutdown_registry
    from src.db.context import DbContext

    try:
        await shutdown_registry()
        await DbContext.dispose_engine()
    except Exception:
        pass


def get_agent_types() -> list[str]:
    """Get list of available agent types"""
    from src.agent.agent_types import AgentType
    return AgentType.values()


def display_agent_types():
    """Display available agent types in a table"""
    table = Table(title="Available Agent Types", show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=3)
    table.add_column("Agent Type", style="cyan")
    table.add_column("Description", style="dim")

    descriptions = {
        "general": "General code understanding and navigation",
        "security": "Security vulnerabilities and OWASP analysis",
        "database": "Database patterns and query optimization",
        "api": "REST API design and best practices",
        "performance": "Performance bottlenecks and optimization",
        "architecture": "Code structure and design patterns",
        "testing": "Test coverage and quality analysis",
        "code_quality": "Code smells and maintainability",
    }

    for i, agent_type in enumerate(get_agent_types(), 1):
        table.add_row(str(i), agent_type, descriptions.get(agent_type, ""))

    console.print(table)


def select_agent_type() -> str:
    """Interactive agent type selection"""
    display_agent_types()
    console.print()

    agent_types = get_agent_types()
    while True:
        choice = Prompt.ask(
            "Select agent type",
            default="1"
        )

        # Check if it's a number
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(agent_types):
                return agent_types[idx]
        # Check if it's a type name
        elif choice in agent_types:
            return choice

        console.print("[red]Invalid selection. Please try again.[/red]")


async def create_new_session() -> Optional[dict]:
    """Create a new chat session - asks for all required info"""
    from src.services.agent_session_service import agent_session_service

    console.print(Rule("Create New Session"))
    console.print()

    # Get user ID
    user_id_str = Prompt.ask(
        "Enter User ID (UUID)",
        default=str(uuid4())
    )
    try:
        user_id = UUID(user_id_str)
    except ValueError:
        console.print("[red]Invalid UUID format. Generating new one.[/red]")
        user_id = uuid4()
        console.print(f"[dim]Using: {user_id}[/dim]")

    # Get task ID (required)
    task_id_str = Prompt.ask(
        "Enter Task ID (UUID) [bold red]*required*[/bold red]"
    )
    while not task_id_str.strip():
        console.print("[red]Task ID is required![/red]")
        task_id_str = Prompt.ask(
            "Enter Task ID (UUID) [bold red]*required*[/bold red]"
        )

    try:
        UUID(task_id_str)  # Validate
        task_id = task_id_str
    except ValueError:
        console.print("[red]Invalid UUID format.[/red]")
        return None

    # Get repo namespace (required)
    repo_namespace = Prompt.ask(
        "Enter Repository Namespace [bold red]*required*[/bold red]"
    )
    while not repo_namespace.strip():
        console.print("[red]Repository namespace is required![/red]")
        repo_namespace = Prompt.ask(
            "Enter Repository Namespace [bold red]*required*[/bold red]"
        )

    console.print()

    # Select agent type
    agent_type = select_agent_type()
    console.print(f"\n[green]Selected:[/green] {agent_type}\n")

    # Get optional title
    title = Prompt.ask("Session title (optional)", default="")
    if not title:
        title = None

    try:
        session = await agent_session_service.create_session(
            user_id=user_id,
            task_id=UUID(task_id),
            repo_namespace=repo_namespace,
            title=title,
            agent_type=agent_type
        )

        console.print(f"\n[green]✓[/green] Session created: [cyan]{session.id}[/cyan]")
        return {
            "id": str(session.id),
            "agent_type": session.agent_type,
            "task_id": task_id,
            "repo_namespace": repo_namespace,
            "user_id": str(user_id)
        }

    except Exception as e:
        console.print(f"\n[red]Error creating session:[/red] {e}")
        return None


async def list_user_sessions(user_id: UUID) -> list[dict]:
    """List existing sessions for a user"""
    from src.services.agent_session_service import agent_session_service

    sessions = await agent_session_service.list_sessions(
        user_id=user_id,
        limit=20
    )

    return [
        {
            "id": str(s.id),
            "title": s.title,
            "agent_type": s.agent_type,
            "task_id": str(s.task_id),
            "repo_namespace": s.repo_namespace,
            "status": s.status,
            "created": s.created_on.strftime("%Y-%m-%d %H:%M") if s.created_on else "N/A",
            "user_id": str(s.user_id)
        }
        for s in sessions
    ]


async def select_existing_session() -> Optional[dict]:
    """Select an existing session - only asks for user_id to list sessions"""
    console.print(Rule("Continue Existing Session"))
    console.print()

    # Get user ID to list their sessions
    user_id_str = Prompt.ask(
        "Enter your User ID (UUID)"
    )
    while not user_id_str.strip():
        console.print("[red]User ID is required to list your sessions![/red]")
        user_id_str = Prompt.ask(
            "Enter your User ID (UUID)"
        )

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        console.print("[red]Invalid UUID format.[/red]")
        return None

    sessions = await list_user_sessions(user_id)

    if not sessions:
        console.print("[yellow]No existing sessions found for this user.[/yellow]")
        return None

    table = Table(title="Your Sessions", show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=3)
    table.add_column("Title", style="cyan", max_width=30)
    table.add_column("Agent", style="green")
    table.add_column("Task ID", style="dim", max_width=20)
    table.add_column("Repo", style="dim", max_width=25)
    table.add_column("Created", style="dim")

    for i, session in enumerate(sessions, 1):
        task_short = session["task_id"][:8] + "..." if session["task_id"] else "N/A"
        repo_short = session["repo_namespace"][:22] + "..." if len(session["repo_namespace"]) > 25 else session["repo_namespace"]
        table.add_row(
            str(i),
            session["title"][:30] if session["title"] else "Untitled",
            session["agent_type"],
            task_short,
            repo_short,
            session["created"]
        )

    console.print(table)
    console.print()

    while True:
        choice = Prompt.ask("Select session number (or 'b' to go back)", default="1")

        if choice.lower() == 'b':
            return None

        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(sessions):
                return sessions[idx]

        console.print("[red]Invalid selection. Please try again.[/red]")


def display_message(role: str, content: str):
    """Display a chat message with appropriate styling"""
    if role == "USER":
        console.print(Panel(
            Text(content, style=USER_STYLE),
            title="[bold cyan]You[/bold cyan]",
            border_style="cyan",
            padding=(0, 1)
        ))
    else:
        # Render AI response as markdown
        console.print(Panel(
            Markdown(content),
            title="[bold green]Agent[/bold green]",
            border_style="green",
            padding=(0, 1)
        ))


async def stream_chat_response(
    user_id: UUID,
    session_id: UUID,
    message: str,
    task_id: str,
    repo_namespace: str,
    agent_type: str,
    model_id: Optional[str] = None
):
    """Stream and display chat response"""
    from src.services.agent_chat_service import agent_chat_service
    from rich.status import Status

    # Display user message
    display_message("USER", message)
    console.print()

    # Accumulate streamed content
    full_content = ""
    tool_calls_shown = set()
    current_status = "Thinking..."

    with Status(current_status, console=console, spinner="dots") as status:
        try:
            async for chunk in agent_chat_service.stream_message(
                user_id=user_id,
                session_id=session_id,
                message=message,
                model_id=model_id,
                task_id=task_id,
                repo_namespace=repo_namespace,
                agent_type=agent_type
            ):
                chunk_type = chunk.get("type")
                data = chunk.get("data", {})

                if chunk_type == "update":
                    # Handle AI content (accumulate silently)
                    if "ai_content" in data and data["ai_content"]:
                        full_content += data["ai_content"]
                        status.update("Generating response...")

                    # Handle tool calls (update status)
                    if "tool_call_chunks" in data:
                        for tc in data["tool_call_chunks"]:
                            if tc.get("name") and tc["name"] not in tool_calls_shown:
                                tool_calls_shown.add(tc["name"])
                                status.update(f"Using tool: {tc['name']}")

                    # Handle tool results (update status)
                    if "tool_results" in data:
                        for tr in data["tool_results"]:
                            name = tr.get("name", "tool")
                            status.update(f"{name} completed")

                elif chunk_type == "error":
                    console.print(f"\n[red]Error: {data.get('error', 'Unknown error')}[/red]")
                    return

        except Exception as e:
            console.print(f"\n[red]Stream error: {e}[/red]")
            return

    # Display final formatted response (only the boxed version)
    if full_content:
        display_message("ASSISTANT", full_content)


async def load_chat_history(session_id: UUID):
    """Load and display chat history"""
    from src.services.agent_chat_service import agent_chat_service

    messages = await agent_chat_service.get_messages(
        session_id=session_id,
        limit=50
    )

    if messages:
        console.print(Rule("Chat History"))
        for msg in messages:
            role = msg.get("role", "UNKNOWN")
            content = msg.get("message", {}).get("content", "")
            if content:
                display_message(role, content)
                console.print()
        console.print(Rule())

    return len(messages)


async def chat_loop(session_info: dict):
    """Main chat loop for a session"""
    global current_model_id

    session_id = UUID(session_info["id"])
    user_id = UUID(session_info["user_id"])
    agent_type = session_info["agent_type"]
    task_id = session_info["task_id"]
    repo_namespace = session_info.get("repo_namespace", "")

    console.print(Rule(f"[bold]Chat Session - {agent_type} Agent[/bold]"))
    console.print(f"[dim]Session ID: {session_id}[/dim]")
    console.print(f"[dim]Task ID: {task_id}[/dim]")
    console.print(f"[dim]Repo: {repo_namespace}[/dim]")
    if current_model_id:
        console.print(f"[dim]Model: {current_model_id}[/dim]")
    else:
        console.print("[dim]Model: default[/dim]")
    console.print()
    console.print("[dim]Commands: /quit, /history, /clear, /model <id>, /help[/dim]")
    console.print()

    # Load existing history
    await load_chat_history(session_id)

    while True:
        try:
            # Get user input
            user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]")

            if not user_input.strip():
                continue

            # Handle commands
            if user_input.startswith("/"):
                cmd_parts = user_input.strip().split(maxsplit=1)
                cmd = cmd_parts[0].lower()
                cmd_arg = cmd_parts[1] if len(cmd_parts) > 1 else None

                if cmd in ["/quit", "/exit", "/q"]:
                    console.print("[dim]Ending chat session...[/dim]")
                    break

                elif cmd == "/history":
                    await load_chat_history(session_id)
                    continue

                elif cmd == "/clear":
                    console.clear()
                    console.print(Rule(f"[bold]Chat Session - {agent_type} Agent[/bold]"))
                    continue

                elif cmd == "/model":
                    if cmd_arg:
                        current_model_id = cmd_arg
                        console.print(f"[green]Model set to:[/green] [cyan]{current_model_id}[/cyan]")
                    else:
                        console.print(f"[dim]Current model: {current_model_id or 'default'}[/dim]")
                        console.print("[dim]Usage: /model <model_id>[/dim]")
                        console.print("[dim]Examples:[/dim]")
                        console.print("[dim]  /model openai:gpt-4[/dim]")
                        console.print("[dim]  /model anthropic:claude-3-5-sonnet[/dim]")
                        console.print("[dim]  /model google:gemini-2.0-flash[/dim]")
                    continue

                elif cmd == "/help":
                    console.print(Panel(
                        "[cyan]/quit[/cyan] - Exit chat\n"
                        "[cyan]/history[/cyan] - Show chat history\n"
                        "[cyan]/clear[/cyan] - Clear screen\n"
                        "[cyan]/model <id>[/cyan] - Set model (e.g., openai:gpt-4)\n"
                        "[cyan]/help[/cyan] - Show this help",
                        title="Commands",
                        border_style="dim"
                    ))
                    continue

                else:
                    console.print(f"[yellow]Unknown command: {cmd}[/yellow]")
                    continue

            # Send message and stream response
            console.print()
            await stream_chat_response(
                user_id=user_id,
                session_id=session_id,
                message=user_input,
                task_id=task_id,
                repo_namespace=repo_namespace,
                agent_type=agent_type,
                model_id=current_model_id
            )

        except KeyboardInterrupt:
            console.print("\n[dim]Use /quit to exit[/dim]")
            continue
        except EOFError:
            break


async def main_menu():
    """Main menu - first asks what user wants to do"""
    while True:
        console.print(Rule("[bold]Code Intelligence Agent CLI[/bold]"))
        console.print()

        table = Table(show_header=False, box=None)
        table.add_column(style="bold cyan", width=3)
        table.add_column()
        table.add_row("1", "Create new session")
        table.add_row("2", "Continue existing session")
        table.add_row("3", "Exit")
        console.print(table)
        console.print()

        choice = Prompt.ask("Select option", default="1")

        if choice == "1":
            session = await create_new_session()
            if session:
                await chat_loop(session)

        elif choice == "2":
            session = await select_existing_session()
            if session:
                await chat_loop(session)

        elif choice == "3":
            console.print("\n[dim]Goodbye![/dim]\n")
            return

        else:
            console.print("[red]Invalid option[/red]")


async def main():
    """Main entry point"""
    console.print(Panel.fit(
        "[bold blue]Code Intelligence Agent CLI[/bold blue]\n"
        "[dim]Interactive testing tool for the AI Agent Service[/dim]",
        border_style="blue"
    ))

    # Initialize the application
    if not await initialize_app():
        return

    try:
        await main_menu()

    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted. Shutting down...[/dim]")

    finally:
        await shutdown_app()


if __name__ == "__main__":
    asyncio.run(main())
