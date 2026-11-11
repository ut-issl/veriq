# Node Metadata and Provenance

veriq's dependency graph knows *what* depends on *what*. Metadata lets you attach your own facts to the nodes of that graph, and veriq provides the primitives to ask questions that combine those facts with the graph structure, such as:

- How long will it take until this verification can run?
- Which root-model inputs does this verification ultimately read, through which parameters, and where did their values come from?

veriq stays agnostic to what the metadata means. It stores it, deduplicates it to definition granularity, and offers two aggregation primitives. Whether a key should be summed, maximised or merely listed is your decision.

The complete example lives in [`examples/compute_time.py`](https://github.com/ut-issl/veriq/blob/main/examples/compute_time.py) with its input [`compute_time.in.toml`](https://github.com/ut-issl/veriq/blob/main/examples/compute_time.in.toml).

## Three places for metadata

| Where | How | What it describes | Visible as |
|---|---|---|---|
| Root model, calculation, verification | `metadata={...}` on the decorator | The *definition*: compute time, owning team, tool used, ... | `NodeSpec.user_metadata`, `DefinitionNode.user_metadata` |
| Root-model field | `Annotated[T, vq.Meta(...)]` | The *field definition*: unit, governing document, ... | `NodeSpec.field_metadata` on MODEL leaves |
| Input value | `provenance` table in the input TOML | The *concrete value*: source, rationale, decision | `vq.load_provenance_from_toml()`, `veriq upstream -i` |

### Definition metadata

```python
@power.root_model(metadata={"owner": "eps-team"})
class PowerDesign(BaseModel): ...

@power.calculation(metadata={"compute_time_s": 120.0, "tool": "battery-model"})
def battery_sizing(...) -> BatteryBudget: ...

@power.verification(metadata={"compute_time_s": 2.0})
def margin_positive(...) -> bool: ...
```

`metadata` is a free-form `dict[str, Any]`. A shallow copy is taken at registration. It is kept apart from veriq's internal node metadata (`xfail`, output types, assumptions), so a key such as `"xfail"` in your dict never changes evaluation.

One definition may expand to several graph nodes: a calculation returning a model with three fields is three leaf nodes, and a root model is one node per field. All of them share the definition's metadata dict. Aggregating over leaf nodes would therefore count a definition once per leaf; the APIs below work at **definition granularity** instead.

### Field metadata

```python
class SolarPanel(BaseModel):
    area_m2: Annotated[float, vq.Meta(unit="m^2")]
    efficiency: Annotated[float, vq.Meta(unit="-", source_doc="SP-DS-004")]


@power.root_model()
class PowerDesign(BaseModel):
    solar_panel: Annotated[SolarPanel, vq.Meta(source_doc="SP-DS-004")]  # inherited by solar_panel.*
```

`vq.Meta` may sit on a leaf field, on a nested-model field (inherited by everything below it), or on the value type of a `Table` (applies to every key). Along the path from the root model to a leaf the dicts are shallow-merged, nearest wins.

### Value provenance

```toml
[Power.model.battery]
capacity_ah = 20.0

[Power.provenance]
"$" = { baseline = "PDR-2026-03" }            # applies to every Power input

[Power.provenance."$.battery.capacity_ah"]
source = "cell datasheet"
rationale = "two 10 Ah strings in parallel"
```

Each entry of the `provenance` table is keyed by the path of the input it describes, in the syntax of `vq.Ref`: `"$"` for the whole root model, `"$.battery"` for a nested model, `"$.power[safe]"` for a `Table` entry. The entry itself is free-form metadata (scalars, arrays or tables), so a metadata key never collides with a field name. The same inheritance rule applies. A key that is not a path of the model is an error, so a typo never silently drops provenance. `veriq calc` validates the table; `veriq schema` describes it; `veriq update` leaves it untouched.

## Two kinds of aggregation

Take the example's verification `Power::?margin_positive`. Its upstream is diamond-shaped, and `@solar_generation` additionally assumes a thermal verification:

```
Power::$ ──► @solar_generation (30 s) ──┐
   │                                     ├──► @power_margin (5 s) ──► ?margin_positive (2 s)
   └──────► @battery_sizing (120 s) ─────┘
```

```python
sub = vq.upstream_subgraph(project, "Power::?margin_positive")

sequential = sum(n.user_metadata.get("compute_time_s", 0.0) for n in sub.nodes.values())  # 203.0
parallel = sub.propagate("compute_time_s", combine=max)  # 127.0
```

**Set-style aggregation** answers questions about the *set* of upstream definitions: total compute time if everything runs one after another, the set of tools involved, the owning teams. It needs no helper. Iterate `sub.nodes` with plain Python. Every definition appears exactly once, no matter how many output leaves it has or how many paths lead to it.

**Structure-aware aggregation** answers questions about *paths*: how long until the target can run if independent nodes evaluate in parallel. That is a recurrence in topological order, `value(node) = own(node) + combine(value(p) for p in predecessors(node))`, which `propagate()` evaluates. With `combine=max` it is the critical path: `$ → @battery_sizing (120) → @power_margin (125) → ?margin_positive (127)`.

Do not use `propagate(..., combine=sum)` for a total. A dependency shared by several paths is counted once per path, so on a diamond it over-counts. Totals belong to the node set.

### Assumptions

`@vq.assume` edges are part of the upstream subgraph (`sub.assume_edges`, `follow_assumes=True` by default also pulls in the assumed verification's own upstream), which is why the sequential total above includes the thermal nodes. They are *premises*, not inputs: an assumed verification may itself read the assuming calculation's output, as `?panel_within_limit` does here. Hence they never act as ordering constraints and never take part in `propagate()`. The critical path is the same with or without them.

`@vq.assume` may be written on either side of `@scope.calculation()` / `@scope.verification()`. At evaluation time a verification that rests on a failed assumption reads `False`; the value its function actually returned stays available through `result.get_value(path, raw=True)` (and `result.raw_values`), and `result.is_valid(path)` tells the two cases apart.

## From the command line

```bash
veriq upstream "Power::?margin_positive" -p examples/compute_time.py --key compute_time_s --bindings \
    -i examples/compute_time.in.toml
```

```
Upstream of Power::?margin_positive (8 definitions, 10 data edges, 1 assume edges)

┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
┃ Kind         ┃ Definition                       ┃ Inputs ┃ compute_time_s ┃ propagated (max) ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
│ MODEL        │ Power::$                         │      0 │              0 │                0 │
│ MODEL        │ Thermal::$                       │      0 │              0 │                0 │
│ CALCULATION  │ Power::@solar_generation         │      1 │             30 │               30 │
│ CALCULATION  │ Power::@battery_sizing           │      1 │            120 │              120 │
│ CALCULATION  │ Thermal::@panel_temperature      │      2 │             45 │               75 │
│ CALCULATION  │ Power::@power_margin             │      3 │              5 │              125 │
│ VERIFICATION │ Thermal::?panel_within_limit     │      2 │              1 │               76 │
│ VERIFICATION │ Power::?margin_positive (target) │      1 │              2 │              127 │
└──────────────┴──────────────────────────────────┴────────┴────────────────┴──────────────────┘

Sequential total of compute_time_s (each definition once): 203
Propagated to target (combine=max): 127 (critical path)

Bindings (parameter <- reference):
  Power::@solar_generation
    panel <- Power::$.solar_panel (3 leaves)
    assumes Thermal::?panel_within_limit
  ...

Inputs (9 root-model leaves):
  Power::$.battery.capacity_ah
    field unit: 'Ah'
    provenance baseline: 'PDR-2026-03'
    provenance source: 'cell datasheet'
    provenance rationale: 'two 10 Ah strings in parallel'
  ...
```

`--json` emits the same information as data: nodes in topological order, data edges with their parameter bindings, assume edges, the input leaves with field metadata and provenance, and the aggregation. See the [CLI reference](cli-reference.md#veriq-upstream).

## Where this stops (for now)

- **Requirements carry no metadata.** Requirements form a decomposition tree, not part of the dependency DAG this foundation targets.
- **Nothing is measured.** `compute_time_s` is a declared value; veriq does not time calculations.
- **Metadata is untyped.** A plain `dict` is validated for nothing but shape in the `provenance` table (its keys must be model paths). Typed metadata schemas are a possible later addition.
