"""agent-project-manager — MAF Agent definitions.

CommandCenter entry point. Called by the Dynamic Agent Loader at runtime.
VS Code Copilot Chat continues to use .github/agents/ + .github/skills/*/SKILL.md
unchanged — both modes share the same .github/prompts/system.md +
.github/skills/*/SKILL.md source of truth.

Architecture (DOE v2):
  Layer 1 (Skills)        — .github/skills/*/SKILL.md + .github/skills/*/scripts/
  Layer 2 (Orchestration) — THIS FILE (GitHubCopilotAgent via MAF)
  Layer 3 (Execution)     — scripts/ shared utilities + skill scripts
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
AGENT_DIR   = Path(__file__).parent.resolve()
PROMPTS_DIR = AGENT_DIR / ".github" / "prompts"
SKILLS_DIR  = AGENT_DIR / ".github" / "skills"
SCRIPTS_DIR = AGENT_DIR / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


# ── System prompt builder ─────────────────────────────────────────────────────

# Skills are loaded in priority order: high-frequency ops first, reference last.
# This ensures critical rules appear early in the context window for all model tiers.
_SKILL_LOAD_ORDER = [
    "clickup-ops",           # most-used: task creation, assignment, API rules
    "hr-structure",          # always needed: user IDs, delegation
    "task-capture",          # frequently used: quick task capture
    "project-planning",      # frequently used: new projects, planning
    "project-tracking",      # frequently used: status checks
    "project-breakdown",     # periodic: WBS, Gantt, risks
    "project-memory",        # periodic: decisions, risks, follow-ups
    "agent-memory",          # periodic: session memory
    "clickup-docs",          # occasional: documentation
    "external-integrations", # occasional: GitHub, Notion links
    "self-annealing",        # diagnostic: error recovery
    "technical-planning",    # heavy: research, WBS generation
]


def _build_system_prompt() -> str:
    parts: list[str] = []
    system_md = PROMPTS_DIR / "system.md"
    if system_md.exists():
        parts.append(system_md.read_text(encoding="utf-8"))
    if SKILLS_DIR.exists():
        parts.append("\n\n---\n\n## Skill Reference Library\n")
        # Load in priority order first, then any unlisted skills alphabetically
        loaded: set[str] = set()
        for skill_name in _SKILL_LOAD_ORDER:
            skill_md = SKILLS_DIR / skill_name / "SKILL.md"
            if skill_md.exists():
                parts.append(
                    f"\n### Skill: {skill_name}\n\n"
                    f"{skill_md.read_text(encoding='utf-8')}"
                )
                loaded.add(skill_name)
        for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
            if skill_md.parent.name not in loaded:
                parts.append(
                    f"\n### Skill: {skill_md.parent.name}\n\n"
                    f"{skill_md.read_text(encoding='utf-8')}"
                )
    return "\n".join(parts)


# ── Shared subprocess helper ──────────────────────────────────────────────────

async def _run(cmd: list[str]) -> str:
    result = await asyncio.to_thread(
        subprocess.run, cmd, capture_output=True, text=True, cwd=str(AGENT_DIR)
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr[:1000] or f"Script exited {result.returncode}")
    return result.stdout or "(no output)"


# ═══════════════════════════════════════════════════════════════════════════════
# HR STRUCTURE
# ═══════════════════════════════════════════════════════════════════════════════

async def query_hr(role_or_skill: str) -> str:
    """Query the HR org chart by role, skill, or name to find available team members.

    Use this tool when the user asks who should handle a task, wants to see team
    capacity, or needs to delegate work to a specific person or skill set.
    """
    return await _run([
        sys.executable,
        str(SKILLS_DIR / "hr-structure/scripts/query_hr.py"),
        "--query", role_or_skill,
    ])


async def ingest_resumes(dry_run: bool = False) -> str:
    """Parse PDF resumes from data/Resumes/ and update hr_structure.json with extracted skills.

    Use this tool when new resumes have been added, or when the user wants to
    refresh the skills data from uploaded resumes.
    """
    cmd = [sys.executable, str(SCRIPTS_DIR / "ingest_resumes.py"), "--no-llm"]
    if dry_run:
        cmd.append("--dry-run")
    return await _run(cmd)


async def workload_analysis(person: str = "", suggest_skills: str = "", effort_hours: float = 4.0, update_hr: bool = False) -> str:
    """Fetch live ClickUp task data to compute each person's workload and identify who is free.

    Use this tool when the user asks about current team workload, wants to know
    who is available for new work, or needs to find the best person for a task
    based on skills and capacity.

    person: optional name filter (partial match)
    suggest_skills: space-separated skill keywords to find best assignee for a task
    effort_hours: estimated hours for the task (used with suggest_skills)
    update_hr: if True, writes computed load back to hr_structure.json
    """
    cmd = [sys.executable, str(SCRIPTS_DIR / "workload_analysis.py")]
    if person:
        cmd += ["--person", person]
    if suggest_skills:
        cmd += ["--suggest"] + suggest_skills.split()
        cmd += ["--effort", str(effort_hours)]
    if update_hr:
        cmd.append("--update-hr")
    return await _run(cmd)


# ═══════════════════════════════════════════════════════════════════════════════
# CLICKUP OPS
# ═══════════════════════════════════════════════════════════════════════════════

async def clickup_list_members() -> str:
    """List all members currently in the ClickUp workspace with their IDs and emails.

    Use this tool when the user asks who is on ClickUp, wants to verify mappings,
    or needs a ClickUp user ID for task assignment.
    """
    return await _run([
        sys.executable,
        str(SKILLS_DIR / "clickup-ops/scripts/clickup_client.py"),
        "--list-members",
    ])


async def clickup_list_spaces() -> str:
    """List all ClickUp Spaces in the workspace.

    Use this tool to see the current ClickUp hierarchy before creating or
    updating tasks, or when the user asks about project spaces.
    """
    return await _run([
        sys.executable,
        str(SKILLS_DIR / "clickup-ops/scripts/clickup_client.py"),
        "--list-spaces",
    ])


async def clickup_get_tasks(list_id: str) -> str:
    """Get all open tasks in a ClickUp list by its list ID.

    Use this tool when the user asks about tasks in a specific list, wants a
    status report, or needs to see current assignments and due dates.
    """
    return await _run([
        sys.executable,
        str(SKILLS_DIR / "clickup-ops/scripts/clickup_client.py"),
        "--list-tasks", list_id,
    ])


async def clickup_create_project(plan_file: str) -> str:
    """Create a full ClickUp Space + Folder + Lists from a confirmed project plan JSON.

    Use this tool ONLY after the user has explicitly confirmed the plan structure.
    plan_file: path to the step_1_project_plan.json file (e.g. outputs/my-project/step_1_project_plan.json)
    """
    return await _run([
        sys.executable,
        str(SKILLS_DIR / "clickup-ops/scripts/create_project.py"),
        "--plan", plan_file,
    ])


async def clickup_sync_tasks(plan_file: str) -> str:
    """Create or update ClickUp tasks with assignees and due dates from a plan file.

    Use this tool after clickup_create_project to populate the lists with tasks.
    plan_file: path to the project plan JSON.
    """
    return await _run([
        sys.executable,
        str(SKILLS_DIR / "clickup-ops/scripts/sync_tasks.py"),
        "--plan", plan_file,
    ])


async def clickup_add_comment(task_id: str, comment: str) -> str:
    """Post a follow-up comment on a ClickUp task.

    Use this tool ONLY after the user has confirmed the comment text.
    task_id: the ClickUp task ID.
    comment: the comment text to post.
    """
    return await _run([
        sys.executable,
        str(SKILLS_DIR / "clickup-ops/scripts/add_comment.py"),
        "--task-id", task_id,
        "--comment", comment,
    ])


# ═══════════════════════════════════════════════════════════════════════════════
# TASK CAPTURE
# ═══════════════════════════════════════════════════════════════════════════════

async def capture_task(task_description: str, project: str = "", due_date: str = "tomorrow", assignee: str = "") -> str:
    """Quickly add a task to the right project/list/subtask hierarchy in ClickUp.

    The agent intelligently determines where the task belongs based on:
    - Active projects and their lists
    - Keyword matching to suggest the right list
    - Optional project hint to narrow choices
    - Asks clarifying questions if project or assignee is ambiguous

    The skill is assignee-agnostic: if no assignee is provided, the script will
    ask who to assign the task to. Always resolve the assignee before calling
    this tool when possible.

    Use this tool when the user wants to add any task for any team member without
    manually navigating ClickUp hierarchy.

    task_description: what needs to be done (e.g. "Review vendor quotations")
    project: optional project name hint (e.g. "Photo Booth")
    due_date: when it's due — "today", "tomorrow", "next week", or YYYY-MM-DD
    assignee: who it's assigned to — first name, last name, or full name (e.g. "Ayush")
    """
    cmd = [
        sys.executable,
        str(SKILLS_DIR / "task-capture/scripts/capture_task.py"),
        task_description,
    ]
    if project:
        cmd += ["--project", project]
    if due_date and due_date != "tomorrow":
        cmd += ["--due", due_date]
    if assignee:
        cmd += ["--assignee", assignee]
    return await _run(cmd)


# ═══════════════════════════════════════════════════════════════════════════════
# PROJECT PLANNING
# ═══════════════════════════════════════════════════════════════════════════════

async def plan_project(project_name: str, description: str, output_slug: str = "") -> str:
    """Create a prioritised project plan with tasks, owners, and timeline estimates.

    Use this tool when the user wants to plan a new project, sprint, or initiative.
    project_name: the project title.
    description: high-level description of goals and constraints.
    output_slug: optional folder slug under outputs/ (defaults to slugified name).
    """
    cmd = [
        sys.executable,
        str(SKILLS_DIR / "project-planning/scripts/plan_project.py"),
        "--name", project_name,
        "--description", description,
    ]
    if output_slug:
        cmd += ["--slug", output_slug]
    return await _run(cmd)


# ═══════════════════════════════════════════════════════════════════════════════
# PROJECT TRACKING
# ═══════════════════════════════════════════════════════════════════════════════

async def fetch_project_status(project_slug: str = "") -> str:
    """Fetch the current status of all tasks in a project from ClickUp.

    Use this tool when the user asks for a status report, wants to see what is
    on track vs at risk, or needs a weekly review summary.
    project_slug: optional project slug to filter (leave empty for all projects).
    """
    cmd = [sys.executable, str(SKILLS_DIR / "project-tracking/scripts/fetch_status.py")]
    if project_slug:
        cmd += ["--slug", project_slug]
    return await _run(cmd)


async def generate_status_report(project_slug: str = "") -> str:
    """Generate a formatted status report for a project or the full portfolio.

    Use this tool when the user asks for a written progress report, executive
    summary, or wants to see ✅ on track / ⚠️ at risk / ❌ blocked breakdown.
    project_slug: optional slug to filter (leave empty for full portfolio report).
    """
    cmd = [sys.executable, str(SKILLS_DIR / "project-tracking/scripts/generate_report.py")]
    if project_slug:
        cmd += ["--slug", project_slug]
    return await _run(cmd)


# ═══════════════════════════════════════════════════════════════════════════════
# TECHNICAL PLANNING
# ═══════════════════════════════════════════════════════════════════════════════

async def generate_wbs(project_name: str, output_slug: str, requirements_file: str = "") -> str:
    """Generate a V-model Work Breakdown Structure for a hardware-software engineering project.

    Use this tool when the user needs a WBS, wants to decompose a technical project
    into phases and work packages, or needs PERT effort estimates.
    project_name: project title.
    output_slug: folder slug under outputs/ where deliverables will be saved.
    requirements_file: optional path to parsed requirements JSON.
    """
    cmd = [
        sys.executable,
        str(SKILLS_DIR / "technical-planning/scripts/generate_project_plan.py"),
        "--mode", "wbs",
        "--project-name", project_name,
        "--output", f"outputs/{output_slug}/wbs.md",
    ]
    if requirements_file:
        cmd += ["--requirements", requirements_file]
    return await _run(cmd)


async def generate_gantt(project_name: str, output_slug: str, start_date: str = "") -> str:
    """Generate a Mermaid Gantt chart with milestones, dependencies, and critical path.

    Use this tool when the user needs a project schedule, timeline visualisation,
    or wants to identify the critical path of a technical project.
    project_name: project title.
    output_slug: folder slug under outputs/ where deliverables will be saved.
    start_date: project start date in YYYY-MM-DD format (defaults to today).
    """
    cmd = [
        sys.executable,
        str(SKILLS_DIR / "technical-planning/scripts/generate_project_plan.py"),
        "--mode", "gantt",
        "--project-name", project_name,
        "--output", f"outputs/{output_slug}/gantt_chart.md",
    ]
    if start_date:
        cmd += ["--start-date", start_date]
    else:
        from datetime import date
        cmd += ["--start-date", date.today().isoformat()]
    return await _run(cmd)


async def generate_risk_register(project_name: str, output_slug: str, domain: str = "") -> str:
    """Generate a risk register with probability/impact scoring and mitigation strategies.

    Use this tool when the user needs a risk assessment, wants to identify project
    risks proactively, or needs a risk register for a technical project.
    project_name: project title.
    output_slug: folder slug under outputs/.
    domain: technical domain (e.g. 'embedded systems', 'IoT', 'robotics').
    """
    cmd = [
        sys.executable,
        str(SKILLS_DIR / "technical-planning/scripts/generate_project_plan.py"),
        "--mode", "risks",
        "--project-name", project_name,
        "--output", f"outputs/{output_slug}/risk_register.md",
    ]
    if domain:
        cmd += ["--domain", domain]
    return await _run(cmd)


async def compile_project_plan(project_name: str, output_slug: str) -> str:
    """Compile all deliverables (WBS, Gantt, risk register, research) into a master project plan.

    Use this tool as the final step after WBS, Gantt, and risk register have been
    generated, to produce a single master project_plan.md document.
    project_name: project title.
    output_slug: folder slug under outputs/ containing all deliverable files.
    """
    return await _run([
        sys.executable,
        str(SKILLS_DIR / "technical-planning/scripts/generate_project_plan.py"),
        "--mode", "compile",
        "--project-name", project_name,
        "--project-dir", f"outputs/{output_slug}/",
        "--output", f"outputs/{output_slug}/project_plan.md",
    ])


async def research_web(query: str, mode: str = "search", output_slug: str = "", num_results: int = 15) -> str:
    """Search the web for industry practices, prior art, standards, and technology comparisons.

    Use this tool during technical project planning to research best practices,
    find reference architectures, or compare technology options.
    query: the search query.
    mode: one of 'search', 'prior-art', 'standards', 'news', 'tech-compare'.
    output_slug: folder slug under .tmp/ for saving results.
    num_results: number of results to fetch (default 15).
    """
    output_path = f".tmp/{output_slug}/web_{mode}.json" if output_slug else f".tmp/web_{mode}.json"
    return await _run([
        sys.executable,
        str(SKILLS_DIR / "technical-planning/scripts/web_research.py"),
        "--mode", mode,
        "--query", query,
        "--num-results", str(num_results),
        "--output", output_path,
    ])


async def search_papers(topic: str, output_slug: str = "", limit: int = 20) -> str:
    """Search academic databases (Semantic Scholar, arXiv, CrossRef) for research papers.

    Use this tool to find academic references, prior art, or technical background
    for a specific engineering challenge during technical project planning.
    topic: the research topic or technical challenge to search for.
    output_slug: folder slug under .tmp/ for saving results.
    limit: max number of papers to return (default 20).
    """
    output_path = f".tmp/{output_slug}/papers.json" if output_slug else ".tmp/papers.json"
    return await _run([
        sys.executable,
        str(SKILLS_DIR / "technical-planning/scripts/search_papers.py"),
        "--topic", topic,
        "--source", "all",
        "--limit", str(limit),
        "--output", output_path,
    ])


# ═══════════════════════════════════════════════════════════════════════════════
# MEMORY & DIAGNOSTICS
# ═══════════════════════════════════════════════════════════════════════════════

async def search_project_memory(query: str) -> str:
    """Full-text search across all project history, decisions, risks, and follow-ups.

    Use this tool when the user asks about past decisions, wants to find previous
    project context, or needs to check if a similar problem was solved before.
    query: keywords to search for in project memory.
    """
    return await _run([
        sys.executable,
        str(SCRIPTS_DIR / "memory_search.py"),
        "--query", query,
    ])


async def run_diagnostics() -> str:
    """Run self-annealing health checks on scripts, APIs, and data files.

    Use this tool when something is not working, after a script fails, or at the
    start of a new session to verify the agent environment is healthy.
    """
    return await _run([
        sys.executable,
        str(SCRIPTS_DIR / "self_anneal_diagnostics.py"),
        "--check", "all",
    ])


# ═══════════════════════════════════════════════════════════════════════════════
# Agent factory
# ═══════════════════════════════════════════════════════════════════════════════

def build_agents():
    """Return MAF agents for agent-project-manager.

    Called by the Dynamic Agent Loader at runtime. Synchronous, zero-argument, pure.
    """
    try:
        from agent_framework import Agent
        from agent_framework.openai import OpenAIChatCompletionClient
        client = OpenAIChatCompletionClient(
            base_url=os.environ.get("LITELLM_BASE_URL", "http://litellm:4000") + "/v1",
            api_key=os.environ.get("LITELLM_API_KEY", ""),
            model="tier2-sonnet",
        )
        AgentClass = Agent
    except ImportError:
        # Fallback for local VS Code dev — agent_framework not installed
        try:
            from autogen_agentchat.agents import AssistantAgent as AgentClass  # type: ignore
            from autogen_ext.models.openai import OpenAIChatCompletionClient    # type: ignore
            client = OpenAIChatCompletionClient(
                base_url=os.environ.get("LITELLM_BASE_URL", "http://litellm:4000") + "/v1",
                api_key=os.environ.get("LITELLM_API_KEY", "sk-local"),
                model="gpt-4o",
            )
        except ImportError:
            raise ImportError(
                "Neither agent_framework nor autogen_agentchat is installed. "
                "Install agent_framework for CommandCenter or autogen_agentchat for local dev."
            )

    return [AgentClass(
        name="agent-project-manager",
        instructions=_build_system_prompt(),
        tools=[
            # HR Structure
            query_hr,
            ingest_resumes,
            workload_analysis,
            # ClickUp Ops
            clickup_list_members,
            clickup_list_spaces,
            clickup_get_tasks,
            clickup_create_project,
            clickup_sync_tasks,
            clickup_add_comment,
            # Project Planning
            plan_project,
            # Project Tracking
            fetch_project_status,
            generate_status_report,
            # Technical Planning
            generate_wbs,
            generate_gantt,
            generate_risk_register,
            compile_project_plan,
            research_web,
            search_papers,
            # Memory & Diagnostics
            search_project_memory,
            run_diagnostics,
        ],
        model_client=client,
    )]


# ── Smoke test (python agents.py) ────────────────────────────────────────────
if __name__ == "__main__":
    print("System prompt length:", len(_build_system_prompt()), "chars")
    print("Skills loaded:", [p.parent.name for p in sorted(SKILLS_DIR.glob("*/SKILL.md"))])
    print("Tools count: will be wired at build_agents() call")
    print("\nagents.py is valid. Run build_agents() inside CommandCenter to instantiate.")
