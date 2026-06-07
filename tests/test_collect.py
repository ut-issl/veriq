from typing import Annotated

import pytest
from pydantic import BaseModel

import veriq as vq
from veriq._path import AttributePart, CalcPath, ProjectPath


class CollectSummary(BaseModel):
    total: float
    keys: list[str]


def test_collect_hydrates_member_values_from_all_tagged_root_fields() -> None:
    project = vq.Project("Collect Project")
    power = vq.Scope("power")
    thermal = vq.Scope("thermal")
    summary = vq.Scope("summary")
    project.add_scope(power)
    project.add_scope(thermal)
    project.add_scope(summary)

    @power.root_model()
    class PowerModel(BaseModel):
        avionics_load: Annotated[float, vq.Tag("PowerConsuming")]

    @thermal.root_model()
    class ThermalModel(BaseModel):
        heater_load: Annotated[float, vq.Tag("PowerConsuming")]

    @summary.root_model()
    class SummaryModel(BaseModel):
        pass

    @summary.calculation()
    def total_load(
        loads: Annotated[dict[str, float], vq.Collect(tag="PowerConsuming")],
    ) -> CollectSummary:
        return CollectSummary(total=sum(loads.values()), keys=list(loads))

    result = vq.evaluate_project(
        project,
        {
            "power": PowerModel(avionics_load=12.5),
            "thermal": ThermalModel(heater_load=3.25),
            "summary": SummaryModel(),
        },
    )

    assert result.get_value(ProjectPath("summary", CalcPath("@total_load", (AttributePart("total"),)))) == 15.75
    assert result.get_value(ProjectPath("summary", CalcPath("@total_load", (AttributePart("keys"),)))) == [
        "power.avionics_load",
        "thermal.heater_load",
    ]


def test_collect_does_not_require_imports_for_cross_scope_members() -> None:
    project = vq.Project("Collect Project")
    source = vq.Scope("source")
    consumer = vq.Scope("consumer")
    project.add_scope(source)
    project.add_scope(consumer)

    @source.root_model()
    class SourceModel(BaseModel):
        load: Annotated[float, vq.Tag("CrossScope")]

    @consumer.root_model()
    class ConsumerModel(BaseModel):
        pass

    @consumer.calculation()
    def consume_cross_scope(
        loads: Annotated[dict[str, float], vq.Collect(tag="CrossScope")],
    ) -> float:
        return loads["source.load"]

    result = vq.evaluate_project(
        project,
        {
            "source": SourceModel(load=4.0),
            "consumer": ConsumerModel(),
        },
    )

    assert result.get_value(ProjectPath("consumer", CalcPath("@consume_cross_scope", ()))) == 4.0


def test_collect_can_be_combined_with_regular_ref() -> None:
    project = vq.Project("Collect Project")
    power = vq.Scope("power")
    thermal = vq.Scope("thermal")
    summary = vq.Scope("summary")
    project.add_scope(power)
    project.add_scope(thermal)
    project.add_scope(summary)

    @power.root_model()
    class PowerModel(BaseModel):
        load: Annotated[float, vq.Tag("PowerConsuming")]

    @thermal.root_model()
    class ThermalModel(BaseModel):
        load: Annotated[float, vq.Tag("PowerConsuming")]

    @summary.root_model()
    class SummaryModel(BaseModel):
        margin: float

    @summary.calculation()
    def load_with_margin(
        margin: Annotated[float, vq.Ref("$.margin")],
        loads: Annotated[dict[str, float], vq.Collect(tag="PowerConsuming")],
    ) -> float:
        return sum(loads.values()) + margin

    result = vq.evaluate_project(
        project,
        {
            "power": PowerModel(load=8.0),
            "thermal": ThermalModel(load=2.0),
            "summary": SummaryModel(margin=1.5),
        },
    )

    assert result.get_value(ProjectPath("summary", CalcPath("@load_with_margin", ()))) == 11.5


def test_collect_empty_tag_set_hydrates_empty_dict() -> None:
    project = vq.Project("Collect Project")
    source = vq.Scope("source")
    summary = vq.Scope("summary")
    project.add_scope(source)
    project.add_scope(summary)

    @source.root_model()
    class SourceModel(BaseModel):
        untagged_load: float

    @summary.root_model()
    class SummaryModel(BaseModel):
        pass

    @summary.calculation()
    def count_missing_tag(
        loads: Annotated[dict[str, float], vq.Collect(tag="MissingTag")],
    ) -> CollectSummary:
        return CollectSummary(total=sum(loads.values()), keys=list(loads))

    result = vq.evaluate_project(
        project,
        {
            "source": SourceModel(untagged_load=7.0),
            "summary": SummaryModel(),
        },
    )

    assert result.get_value(ProjectPath("summary", CalcPath("@count_missing_tag", (AttributePart("total"),)))) == 0
    assert result.get_value(ProjectPath("summary", CalcPath("@count_missing_tag", (AttributePart("keys"),)))) == []


def test_collect_member_keys_are_sorted_by_scope_and_field_name() -> None:
    project = vq.Project("Collect Project")
    thermal = vq.Scope("thermal")
    power = vq.Scope("power")
    summary = vq.Scope("summary")
    project.add_scope(thermal)
    project.add_scope(power)
    project.add_scope(summary)

    @thermal.root_model()
    class ThermalModel(BaseModel):
        z_load: Annotated[float, vq.Tag("Sorted")]

    @power.root_model()
    class PowerModel(BaseModel):
        b_load: Annotated[float, vq.Tag("Sorted")]
        a_load: Annotated[float, vq.Tag("Sorted")]

    @summary.root_model()
    class SummaryModel(BaseModel):
        pass

    @summary.calculation()
    def sorted_keys(
        loads: Annotated[dict[str, float], vq.Collect(tag="Sorted")],
    ) -> CollectSummary:
        return CollectSummary(total=sum(loads.values()), keys=list(loads))

    result = vq.evaluate_project(
        project,
        {
            "thermal": ThermalModel(z_load=1.0),
            "power": PowerModel(b_load=2.0, a_load=3.0),
            "summary": SummaryModel(),
        },
    )

    assert result.get_value(ProjectPath("summary", CalcPath("@sorted_keys", (AttributePart("keys"),)))) == [
        "power.a_load",
        "power.b_load",
        "thermal.z_load",
    ]


def test_parameter_cannot_have_ref_and_collect() -> None:
    project = vq.Project("Collect Project")
    scope = vq.Scope("scope")
    project.add_scope(scope)

    @scope.root_model()
    class ScopeModel(BaseModel):
        value: Annotated[float, vq.Tag("Invalid")]

    with pytest.raises(TypeError, match="cannot be annotated with both Ref and Collect"):

        @scope.calculation()
        def invalid(
            value: Annotated[float, vq.Ref("$.value"), vq.Collect(tag="Invalid")],
        ) -> float:
            return value
