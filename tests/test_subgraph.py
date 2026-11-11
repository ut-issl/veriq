"""Tests for the definition-level upstream subgraph API."""

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import pytest
from pydantic import BaseModel

import veriq as vq
from veriq._cli.discover import load_project_from_script
from veriq._ir import NodeKind, build_graph_spec
from veriq._path import parse_project_path


class Mode(StrEnum):
    NOMINAL = "nominal"
    SAFE = "safe"


class Battery(BaseModel):
    capacity: float
    min_capacity: float


class PowerDesign(BaseModel):
    battery: Battery
    area: float
    unused: float
    load: vq.Table[Mode, float]


class ThermalDesign(BaseModel):
    max_temp: float


class Budget(BaseModel):
    generation: float
    margin: float


def _did(s: str) -> vq.DefinitionId:
    scope, root = s.split("::")
    return vq.DefinitionId(scope=scope, root=root)


def _pp(s: str):  # noqa: ANN202
    return parse_project_path(s)


def _build_project() -> vq.Project:
    """Diamond-shaped DAG with cross-scope references, multi-leaf outputs and an assumption.

    Power::$ ──► @gen ──┐
       │                ├─► @budget ──► ?margin_ok
       └──► @heat ──────┘        ▲
    Thermal::$ ──► ?temp_ok ─(assume)┘
    """
    project = vq.Project(name="Sat")
    power = vq.Scope(name="Power")
    thermal = vq.Scope(name="Thermal")
    project.add_scope(power)
    project.add_scope(thermal)

    power.root_model(metadata={"compute_time_s": 0.0})(PowerDesign)
    thermal.root_model()(ThermalDesign)

    @thermal.verification(metadata={"compute_time_s": 1.0})
    def temp_ok(max_temp: Annotated[float, vq.Ref("$.max_temp")]) -> bool:
        return max_temp < 100

    @power.calculation(metadata={"compute_time_s": 10.0})
    def gen(
        area: Annotated[float, vq.Ref("$.area")],
        load: Annotated[vq.Table[Mode, float], vq.Ref("$.load")],
    ) -> float:
        return area * 100 - sum(load.values())

    @power.calculation(imports=["Thermal"], metadata={"compute_time_s": 20.0})
    def heat(
        battery: Annotated[Battery, vq.Ref("$.battery")],
        max_temp: Annotated[float, vq.Ref("$.max_temp", scope="Thermal")],
    ) -> float:
        return battery.capacity * max_temp

    @power.calculation(imports=["Thermal"], metadata={"compute_time_s": 5.0})
    @vq.assume(vq.Ref("?temp_ok", scope="Thermal"))
    def budget(
        generation: Annotated[float, vq.Ref("@gen")],
        heat_w: Annotated[float, vq.Ref("@heat")],
        nominal: Annotated[float, vq.Ref("$.load[nominal]")],
    ) -> Budget:
        return Budget(generation=generation, margin=generation - heat_w - nominal)

    @power.verification(metadata={"compute_time_s": 2.0})
    def margin_ok(margin: Annotated[float, vq.Ref("@budget.margin")]) -> bool:
        return margin > 0

    return project


@pytest.fixture
def project() -> vq.Project:
    return _build_project()


def test_target_forms_are_equivalent(project: vq.Project) -> None:
    by_str = vq.upstream_subgraph(project, "Power::?margin_ok")
    by_path = vq.upstream_subgraph(project, _pp("Power::?margin_ok"))
    by_id = vq.upstream_subgraph(project, _did("Power::?margin_ok"))
    by_spec = vq.upstream_subgraph(build_graph_spec(project), "Power::?margin_ok")
    by_leaf = vq.upstream_subgraph(project, "Power::@budget.margin")  # any leaf selects the definition

    assert by_str == by_path == by_id == by_spec
    assert by_leaf.target == _did("Power::@budget")


def test_unknown_target_raises(project: vq.Project) -> None:
    with pytest.raises(KeyError, match="Power::\\?nope"):
        vq.upstream_subgraph(project, "Power::?nope")


def test_nodes_are_deduplicated_to_definitions(project: vq.Project) -> None:
    sub = vq.upstream_subgraph(project, "Power::?margin_ok")

    # Diamond: Power::$ is read by @gen, @heat and @budget but appears once; @budget (2 leaves) once.
    assert set(sub.nodes) == {
        _did("Power::$"),
        _did("Power::@gen"),
        _did("Power::@heat"),
        _did("Power::@budget"),
        _did("Power::?margin_ok"),
        _did("Thermal::$"),
        _did("Thermal::?temp_ok"),
    }
    assert len(sub) == 7
    assert _did("Power::@budget") in sub

    budget = sub.nodes[_did("Power::@budget")]
    assert budget.kind == NodeKind.CALCULATION
    assert budget.outputs == (_pp("Power::@budget.generation"), _pp("Power::@budget.margin"))

    model = sub.nodes[_did("Power::$")]
    assert model.kind == NodeKind.MODEL
    assert _pp("Power::$.unused") in model.outputs  # outputs are what the definition produces, not what is read
    assert _pp("Power::$.load") not in model.outputs  # whole-table node carries no value
    assert _pp("Power::$.load[safe]") in model.outputs


def test_data_edges_and_bindings(project: vq.Project) -> None:
    sub = vq.upstream_subgraph(project, "Power::?margin_ok")
    edges = {(str(e.source), str(e.target)): e for e in sub.data_edges}

    assert set(edges) == {
        ("Power::$", "Power::@gen"),
        ("Power::$", "Power::@heat"),
        ("Power::$", "Power::@budget"),
        ("Thermal::$", "Power::@heat"),
        ("Thermal::$", "Thermal::?temp_ok"),
        ("Power::@gen", "Power::@budget"),
        ("Power::@heat", "Power::@budget"),
        ("Power::@budget", "Power::?margin_ok"),
    }

    # Nested model reference expands to its leaves
    heat_from_power = edges[("Power::$", "Power::@heat")]
    assert heat_from_power.bindings == (
        vq.InputBinding(
            param="battery",
            ref=_pp("Power::$.battery"),
            leaves=frozenset({_pp("Power::$.battery.capacity"), _pp("Power::$.battery.min_capacity")}),
        ),
    )
    # Cross-scope reference keeps its scope
    heat_from_thermal = edges[("Thermal::$", "Power::@heat")]
    assert heat_from_thermal.bindings[0].param == "max_temp"
    assert heat_from_thermal.bindings[0].leaves == frozenset({_pp("Thermal::$.max_temp")})

    # Whole-table reference expands to every key (the valueless whole-table node is left out);
    # Table[key] to one leaf. The declared ref still says the whole table was referenced.
    gen_bindings = {b.param: b for b in edges[("Power::$", "Power::@gen")].bindings}
    assert gen_bindings["load"].ref == _pp("Power::$.load")
    assert gen_bindings["load"].leaves == frozenset({_pp("Power::$.load[nominal]"), _pp("Power::$.load[safe]")})
    budget_from_model = edges[("Power::$", "Power::@budget")].bindings
    assert budget_from_model == (
        vq.InputBinding(
            param="nominal",
            ref=_pp("Power::$.load[nominal]"),
            leaves=frozenset({_pp("Power::$.load[nominal]")}),
        ),
    )

    # Calculation-to-calculation: ref to a whole single-leaf output
    assert edges[("Power::@gen", "Power::@budget")].bindings[0].leaves == frozenset({_pp("Power::@gen")})
    # Leaf of a multi-leaf output
    assert edges[("Power::@budget", "Power::?margin_ok")].bindings[0].ref == _pp("Power::@budget.margin")


def test_inputs_of_predecessors_successors(project: vq.Project) -> None:
    sub = vq.upstream_subgraph(project, "Power::?margin_ok")
    budget = _did("Power::@budget")

    assert {b.param for b in sub.inputs_of(budget)} == {"generation", "heat_w", "nominal"}
    assert sub.predecessors(budget) == {_did("Power::$"), _did("Power::@gen"), _did("Power::@heat")}
    assert sub.successors(_did("Power::$")) == {_did("Power::@gen"), _did("Power::@heat"), budget}
    assert sub.predecessors(_did("Power::$")) == frozenset()
    assert sub.inputs_of(_did("Power::$")) == ()


def test_input_leaves_are_root_model_leaves_only(project: vq.Project) -> None:
    sub = vq.upstream_subgraph(project, "Power::?margin_ok")

    assert sub.input_leaves() == {
        _pp("Power::$.area"),
        _pp("Power::$.load[nominal]"),
        _pp("Power::$.load[safe]"),
        _pp("Power::$.battery.capacity"),
        _pp("Power::$.battery.min_capacity"),
        _pp("Thermal::$.max_temp"),
    }
    assert _pp("Power::$.unused") not in sub.input_leaves()


def test_assume_edges_followed_by_default(project: vq.Project) -> None:
    sub = vq.upstream_subgraph(project, "Power::?margin_ok")

    assert sub.assume_edges == (vq.AssumeEdge(source=_did("Thermal::?temp_ok"), target=_did("Power::@budget")),)
    assert sub.assumptions_of(_did("Power::@budget")) == {_did("Thermal::?temp_ok")}
    # Closure: the assumed verification's own upstream is included
    assert ("Thermal::$", "Thermal::?temp_ok") in {(str(e.source), str(e.target)) for e in sub.data_edges}


def test_assume_edges_not_followed(project: vq.Project) -> None:
    sub = vq.upstream_subgraph(project, "Power::@budget", follow_assumes=False)

    assert sub.assume_edges == (vq.AssumeEdge(source=_did("Thermal::?temp_ok"), target=_did("Power::@budget")),)
    assert _did("Thermal::?temp_ok") in sub  # the assumed node itself is present...
    assert sub.predecessors(_did("Thermal::?temp_ok")) == frozenset()  # ...but not traversed past
    # Thermal::$ is still present because @heat reads it directly
    assert _did("Thermal::$") in sub


def test_upstream_of_model_is_itself(project: vq.Project) -> None:
    sub = vq.upstream_subgraph(project, "Power::$")
    assert set(sub.nodes) == {_did("Power::$")}
    assert sub.data_edges == ()
    assert sub.input_leaves() == frozenset()


def test_user_metadata_and_set_style_aggregation(project: vq.Project) -> None:
    sub = vq.upstream_subgraph(project, "Power::?margin_ok")

    assert sub.nodes[_did("Power::@heat")].user_metadata == {"compute_time_s": 20.0}
    assert sub.nodes[_did("Thermal::$")].user_metadata == {}

    # Sequential total: each definition counted once despite the diamond and multi-leaf outputs
    total = sum(n.user_metadata.get("compute_time_s", 0.0) for n in sub.nodes.values())
    assert total == 0.0 + 10.0 + 20.0 + 5.0 + 2.0 + 1.0


def test_topological_order_respects_data_edges(project: vq.Project) -> None:
    sub = vq.upstream_subgraph(project, "Power::?margin_ok")
    order = sub.topological_order()
    pos = {node_id: i for i, node_id in enumerate(order)}

    assert set(order) == set(sub.nodes)
    for edge in sub.data_edges:
        assert pos[edge.source] < pos[edge.target]


def test_assume_cycle_with_data_edges_is_allowed() -> None:
    """Assume edges are premises, not ordering: a verification may assume-depend circularly on a calc."""
    project = vq.Project(name="P")
    scope = vq.Scope(name="S")
    project.add_scope(scope)
    scope.root_model()(ThermalDesign)

    def heat(max_temp: Annotated[float, vq.Ref("$.max_temp")]) -> float:
        return max_temp

    scope.calculation()(vq.assume(vq.Ref("?temp_ok"))(heat))

    @scope.verification()
    def temp_ok(h: Annotated[float, vq.Ref("@heat")]) -> bool:
        return h < 100

    sub = vq.upstream_subgraph(project, "S::?temp_ok")
    assert set(sub.nodes) == {_did("S::$"), _did("S::@heat"), _did("S::?temp_ok")}
    assert sub.assume_edges == (vq.AssumeEdge(source=_did("S::?temp_ok"), target=_did("S::@heat")),)
    assert sub.topological_order() == [_did("S::$"), _did("S::@heat"), _did("S::?temp_ok")]


def test_result_is_deterministic(project: vq.Project) -> None:
    a = vq.upstream_subgraph(project, "Power::?margin_ok")
    b = vq.upstream_subgraph(_build_project(), "Power::?margin_ok")
    assert list(a.nodes) == list(b.nodes)
    assert a.data_edges == b.data_edges
    assert a.assume_edges == b.assume_edges


def test_definition_id_str_and_from_path() -> None:
    did = vq.DefinitionId.from_path(_pp("Power::@budget.margin"))
    assert did == _did("Power::@budget")
    assert str(did) == "Power::@budget"


def test_table_outputs_exclude_whole_table_node() -> None:
    project = vq.Project(name="P")
    scope = vq.Scope(name="S")
    project.add_scope(scope)
    scope.root_model()(PowerDesign)

    @scope.calculation()
    def doubled(load: Annotated[vq.Table[Mode, float], vq.Ref("$.load")]) -> vq.Table[Mode, float]:
        return vq.Table({k: v * 2 for k, v in load.items()})

    @scope.verification()
    def ok(d: Annotated[vq.Table[Mode, float], vq.Ref("@doubled")]) -> bool:
        return all(v > 0 for v in d.values())

    sub = vq.upstream_subgraph(project, "S::?ok")
    assert sub.nodes[_did("S::@doubled")].outputs == (_pp("S::@doubled[nominal]"), _pp("S::@doubled[safe]"))
    (edge,) = [e for e in sub.data_edges if e.source == _did("S::@doubled")]
    assert edge.bindings[0].ref == _pp("S::@doubled")
    assert edge.bindings[0].leaves == frozenset({_pp("S::@doubled[nominal]"), _pp("S::@doubled[safe]")})


# --- definitions without leaves ---


class Empty(BaseModel): ...


class Design(BaseModel):
    x: float


def _build_project_with_leafless_definitions() -> vq.Project:
    """A::$ (empty) ──────────────┐
    B::$ ──► @nothing (empty) ──► ?ok        @nothing assumes ?pre, which reads B::$.
    """
    project = vq.Project(name="P")
    a = vq.Scope(name="A")
    b = vq.Scope(name="B")
    project.add_scope(a)
    project.add_scope(b)
    a.root_model(metadata={"owner": "a"})(Empty)
    b.root_model()(Design)

    @b.verification(metadata={"t": 1.0})
    def pre(x: Annotated[float, vq.Ref("$.x")]) -> bool:
        return x > 0

    @b.calculation(metadata={"t": 2.0})
    @vq.assume(vq.Ref("?pre"))
    def nothing(x: Annotated[float, vq.Ref("$.x")]) -> Empty:  # noqa: ARG001
        return Empty()

    @b.verification(imports=["A"], metadata={"t": 3.0})
    def ok(
        e: Annotated[Empty, vq.Ref("@nothing")],  # noqa: ARG001
        m: Annotated[Empty, vq.Ref("$", scope="A")],  # noqa: ARG001
    ) -> bool:
        return True

    return project


def test_empty_root_model_is_a_node_without_outputs() -> None:
    project = _build_project_with_leafless_definitions()
    sub = vq.upstream_subgraph(project, "B::?ok")

    node = sub.nodes[_did("A::$")]
    assert node.kind == NodeKind.MODEL
    assert node.outputs == ()
    assert node.user_metadata == {"owner": "a"}

    edge = next(e for e in sub.data_edges if e.source == _did("A::$"))
    assert edge.target == _did("B::?ok")
    assert [(b.param, b.ref, b.leaves) for b in edge.bindings] == [("m", _pp("A::$"), frozenset())]
    assert sub.input_leaves() == {_pp("B::$.x")}


def test_empty_root_model_can_be_the_target() -> None:
    project = _build_project_with_leafless_definitions()
    for source in (project, build_graph_spec(project)):
        sub = vq.upstream_subgraph(source, "A::$")
        assert set(sub.nodes) == {_did("A::$")}
        assert sub.data_edges == ()


def test_leafless_calculation_keeps_its_upstream_and_assumptions() -> None:
    project = _build_project_with_leafless_definitions()
    sub = vq.upstream_subgraph(project, "B::?ok")

    assert set(sub.nodes) == {_did(s) for s in ("A::$", "B::$", "B::@nothing", "B::?pre", "B::?ok")}
    nothing = sub.nodes[_did("B::@nothing")]
    assert nothing.kind == NodeKind.CALCULATION
    assert nothing.outputs == ()
    assert nothing.user_metadata == {"t": 2.0}
    assert sub.predecessors(_did("B::@nothing")) == {_did("B::$")}
    assert sub.assumptions_of(_did("B::@nothing")) == {_did("B::?pre")}

    by_target = vq.upstream_subgraph(project, "B::@nothing")
    assert set(by_target.nodes) == {_did("B::$"), _did("B::@nothing"), _did("B::?pre")}


def test_propagate_passes_through_a_leafless_calculation() -> None:
    project = _build_project_with_leafless_definitions()
    sub = vq.upstream_subgraph(project, "B::?ok")

    # B::?ok (t=3) reads B::@nothing (t=2); the assumed B::?pre is a premise and does not feed in
    assert sub.propagate("t", combine=max) == 5.0


def test_leafless_definitions_from_bare_graph_spec() -> None:
    # The IR has no node for a definition without leaves: it is still shown, with the kind
    # taken from the path symbol, but its metadata and its own inputs are unknown.
    project = _build_project_with_leafless_definitions()
    sub = vq.upstream_subgraph(build_graph_spec(project), "B::?ok")

    assert set(sub.nodes) == {_did("A::$"), _did("B::@nothing"), _did("B::?ok")}
    assert sub.nodes[_did("A::$")].kind == NodeKind.MODEL
    assert sub.nodes[_did("A::$")].user_metadata == {}
    assert sub.nodes[_did("B::@nothing")].kind == NodeKind.CALCULATION


def test_unknown_root_model_scope_raises() -> None:
    project = _build_project_with_leafless_definitions()
    with pytest.raises(vq.DefinitionNotFoundError, match="Nope::\\$"):
        vq.upstream_subgraph(project, "Nope::$")


def test_every_definition_of_dummysat_has_an_upstream() -> None:
    # dummysat's Thermal root model has no fields and is read as a whole by a System verification
    project = load_project_from_script(Path(__file__).resolve().parent.parent / "examples" / "dummysat.py")

    targets = [f"{scope_name}::$" for scope_name in project.scopes]
    for scope_name, scope in project.scopes.items():
        targets += [f"{scope_name}::@{name}" for name in scope.calculations]
        targets += [f"{scope_name}::?{name}" for name in scope.verifications]

    for target in targets:
        sub = vq.upstream_subgraph(project, target)
        assert sub.target in sub.nodes
        assert set(sub.topological_order()) == set(sub.nodes)

    sub = vq.upstream_subgraph(project, "System::?power_thermal_compatibility")
    assert _did("Thermal::$") in sub.nodes
    assert sub.nodes[_did("Thermal::$")].outputs == ()
