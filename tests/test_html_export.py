"""Regression tests for HTML export."""

from __future__ import annotations

from pathlib import Path

from veriq._eval import evaluate_project
from veriq._export.html import render_html
from veriq._io import load_model_data_from_toml


def _load_dummysat() -> tuple:
    """Load the dummysat example project, model data, and evaluation result."""
    from veriq._cli.discover import load_project_from_script  # noqa: PLC0415

    script_path = Path(__file__).parent.parent / "examples" / "dummysat.py"
    project = load_project_from_script(script_path)
    input_path = Path(__file__).parent.parent / "examples" / "dummysat.in.toml"
    model_data = load_model_data_from_toml(project, input_path)
    result = evaluate_project(project, model_data)
    return project, model_data, result


def test_render_html_returns_nonempty_string():
    project, model_data, result = _load_dummysat()
    html = render_html(project, model_data, result)
    assert isinstance(html, str)
    assert len(html) > 0


def test_render_html_contains_doctype():
    project, model_data, result = _load_dummysat()
    html = render_html(project, model_data, result)
    assert "<!DOCTYPE html>" in html or "<!doctype html>" in html.lower()


def test_render_html_contains_structural_elements():
    project, model_data, result = _load_dummysat()
    html = render_html(project, model_data, result)
    for tag in ["<html", "<head", "<body", "<nav", "<main", "<table", "<style"]:
        assert tag in html, f"Missing structural element: {tag}"


def test_render_html_contains_scope_names():
    project, model_data, result = _load_dummysat()
    html = render_html(project, model_data, result)
    for scope_name in ("Power", "Thermal", "System", "AOCS", "RWA"):
        assert scope_name in html, f"Missing scope: {scope_name}"


def test_render_html_contains_requirement_ids():
    project, model_data, result = _load_dummysat()
    html = render_html(project, model_data, result)
    for req_id in ("REQ-SYS-001", "REQ-PWR-001", "REQ-TH-001"):
        assert req_id in html, f"Missing requirement: {req_id}"


def test_render_html_contains_verification_names():
    project, model_data, result = _load_dummysat()
    html = render_html(project, model_data, result)
    for verif in ("verify_battery", "verify_power_budget", "verify_power_margin"):
        assert verif in html, f"Missing verification: {verif}"


def test_render_html_contains_pass_fail_indicators():
    project, model_data, result = _load_dummysat()
    html = render_html(project, model_data, result)
    assert "PASS" in html
    assert "FAIL" in html
