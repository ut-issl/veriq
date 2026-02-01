"""Tests for multi-page static site export."""

from __future__ import annotations

from pathlib import Path

import pytest

from veriq._eval import evaluate_project
from veriq._export import generate_site
from veriq._export._css import CSS
from veriq._export._urls import (
    url_for_calc,
    url_for_index,
    url_for_requirement,
    url_for_requirement_list,
    url_for_scope,
    url_for_scope_list,
    url_for_verification,
)
from veriq._io import load_model_data_from_toml


def _load_dummysat() -> tuple:
    """Load the dummysat example project, model data, and evaluation result."""
    from veriq._cli.discover import load_project_from_script

    script_path = Path(__file__).parent.parent / "examples" / "dummysat.py"
    project = load_project_from_script(script_path)
    input_path = Path(__file__).parent.parent / "examples" / "dummysat.in.toml"
    model_data = load_model_data_from_toml(project, input_path)
    result = evaluate_project(project, model_data)
    return project, model_data, result


# ---------------------------------------------------------------------------
# URL resolution tests
# ---------------------------------------------------------------------------


def test_url_for_index():
    assert url_for_index() == "/index.html"


def test_url_for_scope_list():
    assert url_for_scope_list() == "/scopes/index.html"


def test_url_for_scope():
    assert url_for_scope("Power") == "/scopes/Power/index.html"


def test_url_for_calc():
    assert (
        url_for_calc("Power", "calculate_solar_panel_heat")
        == "/scopes/Power/calculations/calculate_solar_panel_heat.html"
    )


def test_url_for_verification():
    assert url_for_verification("Power", "verify_battery") == "/scopes/Power/verifications/verify_battery.html"


def test_url_for_requirement_list():
    assert url_for_requirement_list() == "/requirements/index.html"


def test_url_for_requirement():
    assert url_for_requirement("REQ-SYS-001") == "/requirements/REQ-SYS-001.html"


# ---------------------------------------------------------------------------
# Site generation tests
# ---------------------------------------------------------------------------


def test_generate_site_creates_output_directory(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    assert output_dir.is_dir()


def test_generate_site_creates_index_html(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    assert (output_dir / "index.html").is_file()


def test_generate_site_creates_styles_css(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    css_file = output_dir / "styles.css"
    assert css_file.is_file()
    assert css_file.read_text() == CSS


def test_generate_site_creates_nojekyll(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    nojekyll = output_dir / ".nojekyll"
    assert nojekyll.is_file()
    assert nojekyll.read_text() == ""


def test_generate_site_index_contains_doctype(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "index.html").read_text()
    assert "<!DOCTYPE html>" in html


def test_generate_site_index_links_external_css(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "index.html").read_text()
    assert 'href="/styles.css"' in html
    assert "<style>" not in html


def test_generate_site_index_contains_project_name(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "index.html").read_text()
    assert project.name in html


def test_generate_site_index_contains_scope_names(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "index.html").read_text()
    for scope_name in ("Power", "Thermal", "System", "AOCS", "RWA"):
        assert scope_name in html, f"Missing scope: {scope_name}"


def test_generate_site_index_contains_requirement_ids(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "index.html").read_text()
    for req_id in ("REQ-SYS-001", "REQ-PWR-001", "REQ-TH-001"):
        assert req_id in html, f"Missing requirement: {req_id}"


def test_generate_site_index_contains_navigation(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "index.html").read_text()
    assert "<nav" in html
    assert "Navigation" in html
    assert "/scopes/" in html
    assert "/requirements/" in html


def test_generate_site_index_contains_summary_stats(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "index.html").read_text()
    assert "Total:" in html
    assert "Verified:" in html
    assert "Failed:" in html


@pytest.mark.parametrize(
    "scope_name",
    ["Power", "Thermal", "System", "AOCS", "RWA"],
)
def test_generate_site_index_links_to_scopes(tmp_path: Path, scope_name: str):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "index.html").read_text()
    expected_href = url_for_scope(scope_name)
    assert expected_href in html, f"Missing link to scope: {expected_href}"


# ---------------------------------------------------------------------------
# Scope page tests
# ---------------------------------------------------------------------------


def test_generate_site_creates_scope_listing(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    assert (output_dir / "scopes" / "index.html").is_file()


@pytest.mark.parametrize(
    "scope_name",
    ["Power", "Thermal", "System", "AOCS", "RWA"],
)
def test_generate_site_creates_scope_detail_pages(tmp_path: Path, scope_name: str):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    assert (output_dir / "scopes" / scope_name / "index.html").is_file()


def test_scope_listing_contains_all_scope_names(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "scopes" / "index.html").read_text()
    for scope_name in ("Power", "Thermal", "System", "AOCS", "RWA"):
        assert scope_name in html, f"Missing scope in listing: {scope_name}"


def test_scope_listing_links_to_detail_pages(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "scopes" / "index.html").read_text()
    for scope_name in ("Power", "Thermal"):
        assert url_for_scope(scope_name) in html


def test_scope_listing_has_breadcrumbs(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "scopes" / "index.html").read_text()
    assert "Home" in html
    assert url_for_index() in html


def test_scope_detail_contains_scope_name(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "scopes" / "Power" / "index.html").read_text()
    assert "Power" in html


def test_scope_detail_contains_model_data(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "scopes" / "Power" / "index.html").read_text()
    assert "Model" in html
    assert "<table" in html


def test_scope_detail_links_to_calculations(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "scopes" / "Power" / "index.html").read_text()
    assert "Calculations" in html
    assert url_for_calc("Power", "calculate_solar_panel_heat") in html


def test_scope_detail_shows_verifications(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "scopes" / "Power" / "index.html").read_text()
    assert "Verifications" in html
    assert "PASS" in html or "FAIL" in html


def test_scope_detail_has_breadcrumbs(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "scopes" / "Power" / "index.html").read_text()
    assert "Home" in html
    assert "Scopes" in html
    assert url_for_scope_list() in html


def test_scope_detail_links_external_css(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "scopes" / "Power" / "index.html").read_text()
    assert 'href="/styles.css"' in html
    assert "<style>" not in html


# ---------------------------------------------------------------------------
# Calculation page tests (nested under scopes)
# ---------------------------------------------------------------------------


def test_generate_site_creates_calc_detail_pages(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    assert (output_dir / "scopes" / "Power" / "calculations" / "calculate_solar_panel_heat.html").is_file()
    assert (output_dir / "scopes" / "Thermal" / "calculations" / "calculate_temperature.html").is_file()


def test_calc_detail_contains_scope_link(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "scopes" / "Thermal" / "calculations" / "calculate_temperature.html").read_text()
    assert "Thermal" in html
    assert url_for_scope("Thermal") in html


def test_calc_detail_shows_inputs(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "scopes" / "Thermal" / "calculations" / "calculate_temperature.html").read_text()
    assert "Inputs" in html


def test_calc_detail_inputs_are_linked(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "scopes" / "Thermal" / "calculations" / "calculate_temperature.html").read_text()
    # Input references should be hyperlinks to their source pages
    assert "<a " in html
    assert url_for_scope("Thermal") in html


def test_calc_detail_shows_outputs(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "scopes" / "Thermal" / "calculations" / "calculate_temperature.html").read_text()
    assert "Outputs" in html
    assert "<table" in html


def test_calc_detail_has_breadcrumbs(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "scopes" / "Thermal" / "calculations" / "calculate_temperature.html").read_text()
    assert "Home" in html
    assert "Scopes" in html
    assert "Thermal" in html
    assert url_for_scope("Thermal") in html


# ---------------------------------------------------------------------------
# Verification page tests (nested under scopes)
# ---------------------------------------------------------------------------


def test_generate_site_creates_verif_detail_pages(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    assert (output_dir / "scopes" / "Power" / "verifications" / "verify_battery.html").is_file()
    assert (output_dir / "scopes" / "Power" / "verifications" / "verify_power_budget.html").is_file()
    assert (output_dir / "scopes" / "RWA" / "verifications" / "verify_power_margin.html").is_file()
    assert (output_dir / "scopes" / "System" / "verifications" / "power_thermal_compatibility.html").is_file()


def test_verif_detail_contains_scope_link(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "scopes" / "Power" / "verifications" / "verify_battery.html").read_text()
    assert "Power" in html
    assert url_for_scope("Power") in html


def test_verif_detail_shows_result(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "scopes" / "Power" / "verifications" / "verify_battery.html").read_text()
    assert "Result" in html
    assert "PASS" in html or "FAIL" in html


def test_verif_detail_shows_inputs(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "scopes" / "Power" / "verifications" / "verify_battery.html").read_text()
    assert "Inputs" in html


def test_verif_detail_inputs_are_linked(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "scopes" / "Power" / "verifications" / "verify_battery.html").read_text()
    # Input references should be hyperlinks to their source pages
    assert "<a " in html
    assert url_for_scope("Power") in html


def test_verif_detail_has_breadcrumbs(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "scopes" / "Power" / "verifications" / "verify_battery.html").read_text()
    assert "Home" in html
    assert "Scopes" in html
    assert "Power" in html
    assert url_for_scope("Power") in html


def test_verif_detail_links_requirements(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "scopes" / "Power" / "verifications" / "verify_battery.html").read_text()
    assert "Satisfies Requirements" in html
    assert "/requirements/" in html


# ---------------------------------------------------------------------------
# Requirement page tests
# ---------------------------------------------------------------------------


def test_generate_site_creates_requirement_listing(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    assert (output_dir / "requirements" / "index.html").is_file()


@pytest.mark.parametrize(
    "req_id",
    ["REQ-SYS-001", "REQ-SYS-002", "REQ-SYS-003", "REQ-SYS-004", "REQ-PWR-001", "REQ-TH-001"],
)
def test_generate_site_creates_requirement_detail_pages(tmp_path: Path, req_id: str):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    assert (output_dir / "requirements" / f"{req_id}.html").is_file()


def test_requirement_listing_contains_all_requirement_ids(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "requirements" / "index.html").read_text()
    for req_id in ("REQ-SYS-001", "REQ-SYS-002", "REQ-SYS-003", "REQ-SYS-004", "REQ-PWR-001", "REQ-TH-001"):
        assert req_id in html, f"Missing requirement in listing: {req_id}"


def test_requirement_listing_links_to_detail_pages(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "requirements" / "index.html").read_text()
    for req_id in ("REQ-SYS-001", "REQ-PWR-001"):
        assert url_for_requirement(req_id) in html


def test_requirement_listing_contains_summary_stats(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "requirements" / "index.html").read_text()
    assert "Total:" in html
    assert "Verified:" in html
    assert "Failed:" in html
    assert "Not Verified:" in html


def test_requirement_listing_has_breadcrumbs(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "requirements" / "index.html").read_text()
    assert "Home" in html
    assert url_for_index() in html
    assert "Requirements" in html


def test_requirement_listing_shows_scope_names(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "requirements" / "index.html").read_text()
    assert "Power" in html
    assert "System" in html


def test_requirement_detail_contains_requirement_id(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "requirements" / "REQ-SYS-001.html").read_text()
    assert "REQ-SYS-001" in html


def test_requirement_detail_shows_status(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "requirements" / "REQ-SYS-001.html").read_text()
    assert "Status:" in html


def test_requirement_detail_shows_description(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "requirements" / "REQ-SYS-001.html").read_text()
    assert "System-level requirement" in html


def test_requirement_detail_links_to_scope(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "requirements" / "REQ-SYS-001.html").read_text()
    assert url_for_scope("System") in html


def test_requirement_detail_shows_child_requirements(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "requirements" / "REQ-SYS-001.html").read_text()
    assert "Child Requirements" in html
    assert url_for_requirement("REQ-SYS-002") in html
    assert url_for_requirement("REQ-SYS-003") in html
    assert url_for_requirement("REQ-SYS-004") in html


def test_requirement_detail_shows_parent_requirement(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "requirements" / "REQ-SYS-002.html").read_text()
    assert "Parent Requirement" in html
    assert url_for_requirement("REQ-SYS-001") in html


def test_requirement_detail_shows_verification_results(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "requirements" / "REQ-PWR-001.html").read_text()
    assert "Verification Results" in html
    assert "PASS" in html or "FAIL" in html
    assert "verify_battery" in html
    assert "verify_power_budget" in html


def test_requirement_detail_links_to_verifications(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "requirements" / "REQ-PWR-001.html").read_text()
    assert url_for_verification("Power", "verify_battery") in html
    assert url_for_verification("Power", "verify_power_budget") in html


def test_requirement_detail_has_breadcrumbs(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "requirements" / "REQ-SYS-001.html").read_text()
    assert "Home" in html
    assert "Requirements" in html
    assert url_for_requirement_list() in html


def test_requirement_detail_leaf_has_no_children_section(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "requirements" / "REQ-SYS-004.html").read_text()
    assert "Child Requirements" not in html


def test_requirement_detail_links_external_css(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    html = (output_dir / "requirements" / "REQ-SYS-001.html").read_text()
    assert 'href="/styles.css"' in html
    assert "<style>" not in html


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_generate_site_is_idempotent(tmp_path: Path):
    project, model_data, result = _load_dummysat()
    output_dir = tmp_path / "site"
    generate_site(project, model_data, result, output_dir)
    first_index = (output_dir / "index.html").read_text()
    first_css = (output_dir / "styles.css").read_text()

    # Run again over same directory
    generate_site(project, model_data, result, output_dir)
    second_index = (output_dir / "index.html").read_text()
    second_css = (output_dir / "styles.css").read_text()

    assert first_index == second_index
    assert first_css == second_css
