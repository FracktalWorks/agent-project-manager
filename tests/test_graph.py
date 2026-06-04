"""Minimum viable tests for agent-hr-manager."""
import sys
from pathlib import Path

# Ensure repo root is on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_build_graph_importable():
    from graph import build_graph
    from langgraph.graph import StateGraph
    assert isinstance(build_graph(), StateGraph)


def test_graph_has_chat_node():
    from graph import build_graph
    graph = build_graph()
    assert "chat" in graph.nodes


def test_hr_structure_valid():
    import json
    hr_path = Path(__file__).resolve().parents[1] / "data" / "hr_structure.json"
    assert hr_path.exists(), "data/hr_structure.json is missing"
    data = json.loads(hr_path.read_text())
    assert "departments" in data
    assert len(data["departments"]) > 0


def test_project_priorities_valid():
    import json
    pp_path = Path(__file__).resolve().parents[1] / "data" / "project_priorities.json"
    assert pp_path.exists(), "data/project_priorities.json is missing"
    data = json.loads(pp_path.read_text())
    assert "projects" in data


def test_slugify():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from project_data_manager import slugify
    assert slugify("Website Redesign 2026") == "website-redesign-2026"
    assert slugify("  Hello World! ") == "hello-world"
