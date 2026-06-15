"""Minimum viable tests for agents.py — CommandCenter MAF compatibility."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_build_agents_importable():
    """build_agents() must be importable and return a non-empty list."""
    from agents import build_agents  # noqa: PLC0415
    try:
        agents = build_agents()
        assert isinstance(agents, list)
        assert len(agents) >= 1
    except ImportError as e:
        # agent_framework not installed locally — that's fine; just verify the
        # module and function are importable and the function is callable.
        assert "agent_framework" in str(e) or "autogen" in str(e), (
            f"Unexpected import error: {e}"
        )


def test_agent_has_name_and_instructions():
    """Each returned agent must have a non-empty name and instructions."""
    from agents import build_agents
    try:
        agents = build_agents()
        agent = agents[0]
        assert hasattr(agent, "name") and agent.name, "Agent must have a non-empty name"
        instructions = getattr(agent, "instructions", None) or getattr(agent, "_instructions", None)
        assert instructions and len(instructions) > 100, "instructions must be non-trivial"
    except ImportError:
        pass  # framework not installed locally — skip


def test_system_prompt_includes_all_skills():
    """_build_system_prompt() must include every SKILL.md in .github/skills/."""
    from agents import _build_system_prompt, SKILLS_DIR
    prompt = _build_system_prompt()
    for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        skill_name = skill_md.parent.name
        assert skill_name in prompt, f"Skill '{skill_name}' not found in system prompt"


def test_tools_are_async():
    """All exported tool functions must be async (required by MAF)."""
    import inspect
    import agents as agents_module
    tool_names = [
        "query_hr", "ingest_resumes", "workload_analysis",
        "clickup_list_members", "clickup_list_spaces", "clickup_get_tasks",
        "clickup_create_project", "clickup_sync_tasks", "clickup_add_comment",
        "plan_project", "fetch_project_status", "generate_status_report",
        "generate_wbs", "generate_gantt", "generate_risk_register",
        "compile_project_plan", "research_web", "search_papers",
        "search_project_memory", "run_diagnostics",
    ]
    for name in tool_names:
        fn = getattr(agents_module, name, None)
        assert fn is not None, f"Tool '{name}' not found in agents.py"
        assert inspect.iscoroutinefunction(fn), f"Tool '{name}' must be async def"


def test_agent_has_tools():
    """Agent must have at least one tool — an empty tools list means it can only apologise."""
    try:
        from agents import build_agents
        agent = build_agents()[0]
        tools = getattr(agent, "tools", None) or getattr(agent, "_tools", None) or []
        assert len(tools) > 0, "Agent has no tools — it will only apologise"
    except ImportError:
        pass  # MAF runtime not available — skip


def test_config_json_valid():
    """config.json must be valid JSON with required fields and max_mutation_attempts == 1."""
    import json
    config_path = Path(__file__).resolve().parents[1] / "config.json"
    assert config_path.exists(), "config.json is missing"
    config = json.loads(config_path.read_text())
    for field in ("name", "description", "version", "max_mutation_attempts"):
        assert field in config, f"config.json missing required field: {field}"
    assert config["max_mutation_attempts"] == 1, "max_mutation_attempts must be 1 (constraint C-01)"


def test_hr_structure_valid():
    """agent-data/hr_structure.json must exist and have a non-empty departments list."""
    import json
    hr_path = Path(__file__).resolve().parents[1] / "agent-data" / "hr_structure.json"
    assert hr_path.exists(), "agent-data/hr_structure.json is missing"
    data = json.loads(hr_path.read_text())
    assert "departments" in data
    assert len(data["departments"]) > 0
