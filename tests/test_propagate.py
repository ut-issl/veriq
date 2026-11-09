"""Tests for UpstreamSubgraph.propagate / propagate_all (structure-aware metadata aggregation)."""

from typing import TYPE_CHECKING, Annotated

import pytest
from pydantic import BaseModel

import veriq as vq

if TYPE_CHECKING:
    from collections.abc import Callable


class Design(BaseModel):
    x: float
    t: float


def _did(s: str) -> vq.DefinitionId:
    scope, root = s.split("::")
    return vq.DefinitionId(scope=scope, root=root)


def _diamond(*, assume_time: float | None = None) -> vq.Project:
    """$ (0) -> a (10), b (3) -> c (5) -> ?ok (2); optional ?pre assumed by c.

    Sequential total: 0 + 10 + 3 + 5 + 2 (+ assume_time).
    Critical path:    0 -> a (10) -> c (15) -> ?ok (17).
    """
    project = vq.Project(name="P")
    scope = vq.Scope(name="S")
    project.add_scope(scope)
    scope.root_model()(Design)  # no compute_time_s: uses default

    @scope.calculation(metadata={"compute_time_s": 10.0})
    def a(x: Annotated[float, vq.Ref("$.x")]) -> float:
        return x

    @scope.calculation(metadata={"compute_time_s": 3.0})
    def b(x: Annotated[float, vq.Ref("$.x")]) -> float:
        return x

    def c(a: Annotated[float, vq.Ref("@a")], b: Annotated[float, vq.Ref("@b")]) -> float:
        return a + b

    calc_fn: Callable[..., float] = c
    if assume_time is not None:

        @scope.verification(metadata={"compute_time_s": assume_time})
        def pre(t: Annotated[float, vq.Ref("$.t")]) -> bool:
            return t > 0

        calc_fn = vq.assume(vq.Ref("?pre"))(calc_fn)

    scope.calculation(metadata={"compute_time_s": 5.0})(calc_fn)

    @scope.verification(metadata={"compute_time_s": 2.0})
    def ok(c: Annotated[float, vq.Ref("@c")]) -> bool:
        return c > 0

    return project


def test_critical_path_is_less_than_sequential_total() -> None:
    sub = vq.upstream_subgraph(_diamond(), "S::?ok")

    sequential = sum(n.user_metadata.get("compute_time_s", 0.0) for n in sub.nodes.values())
    parallel = sub.propagate("compute_time_s", combine=max)

    assert sequential == 20.0
    assert parallel == 17.0
    assert parallel < sequential


def test_combine_sum_double_counts_shared_dependency() -> None:
    sub = vq.upstream_subgraph(_diamond(), "S::?ok")
    # Paths through a and b both include $ and c: $->a->c->ok (17) + $->b->c->ok ... sum recurrence:
    # a = 10, b = 3, c = 5 + (10 + 3) = 18, ok = 2 + 18 = 20 (equal to the total only by coincidence of $ = 0)
    assert sub.propagate("compute_time_s", combine=sum) == 20.0

    # Give the shared input a cost: the sequential total grows by 1, the sum recurrence by 2 (once per path)
    project = _diamond()
    project.scopes["S"]._root_model_metadata["compute_time_s"] = 1.0
    sub = vq.upstream_subgraph(project, "S::?ok")
    assert sum(n.user_metadata.get("compute_time_s", 0.0) for n in sub.nodes.values()) == 21.0
    assert sub.propagate("compute_time_s", combine=sum) == 22.0


def test_propagate_all_matches_recurrence_and_target() -> None:
    sub = vq.upstream_subgraph(_diamond(), "S::?ok")
    values = sub.propagate_all("compute_time_s", combine=max)

    assert values == {
        _did("S::$"): 0.0,
        _did("S::@a"): 10.0,
        _did("S::@b"): 3.0,
        _did("S::@c"): 15.0,
        _did("S::?ok"): 17.0,
    }
    assert values[sub.target] == sub.propagate("compute_time_s", combine=max)


def test_missing_key_uses_default() -> None:
    sub = vq.upstream_subgraph(_diamond(), "S::?ok")
    assert sub.propagate_all("compute_time_s", combine=max, default=100.0)[_did("S::$")] == 100.0
    assert sub.propagate("compute_time_s", combine=max, default=100.0) == 117.0
    # A key nobody defines: every node gets the default, critical path = default * path length
    assert sub.propagate("nope", combine=max, default=1.0) == 4.0


def test_non_numeric_value_raises() -> None:
    project = _diamond()
    project.scopes["S"].calculations["a"].metadata["compute_time_s"] = "slow"
    sub = vq.upstream_subgraph(project, "S::?ok")
    with pytest.raises(TypeError, match=r"compute_time_s.*S::@a.*str"):
        sub.propagate("compute_time_s", combine=max)

    project.scopes["S"].calculations["a"].metadata["compute_time_s"] = True
    sub = vq.upstream_subgraph(project, "S::?ok")
    with pytest.raises(TypeError, match="bool"):
        sub.propagate("compute_time_s", combine=max)


def test_include_assumes_toggle() -> None:
    sub = vq.upstream_subgraph(_diamond(assume_time=30.0), "S::?ok")
    assert sub.assume_edges == (vq.AssumeEdge(source=_did("S::?pre"), target=_did("S::@c")),)

    # ?pre (30) must finish before c: critical path becomes $ -> ?pre -> c -> ok = 30 + 5 + 2
    assert sub.propagate("compute_time_s", combine=max) == 37.0
    assert sub.propagate("compute_time_s", combine=max, include_assumes=False) == 17.0

    # The assumed verification is still a node either way (set-style totals include it)
    assert _did("S::?pre") in sub
    assert sub.propagate_all("compute_time_s", combine=max, include_assumes=False)[_did("S::?pre")] == 30.0


def test_propagate_on_model_target_is_own_value() -> None:
    sub = vq.upstream_subgraph(_diamond(), "S::$")
    assert sub.propagate("compute_time_s", combine=max, default=7.0) == 7.0


def test_results_are_deterministic() -> None:
    first = vq.upstream_subgraph(_diamond(assume_time=1.0), "S::?ok").propagate_all("compute_time_s", combine=max)
    for _ in range(5):
        again = vq.upstream_subgraph(_diamond(assume_time=1.0), "S::?ok").propagate_all("compute_time_s", combine=max)
        assert again == first
        assert list(again) == list(first)
