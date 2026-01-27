"""Tests for tree-based data structures."""

from veriq._eval_engine._tree import PathNode, ScopeTree, build_scope_trees
from veriq._path import AttributePart, CalcPath, ItemPart, ModelPath, ProjectPath, VerificationPath


class TestPathNode:
    def test_is_leaf_with_no_children(self):
        path = ProjectPath(scope="Test", path=ModelPath(root="$", parts=(AttributePart("x"),)))
        node = PathNode(path=path, value=42.0)
        assert node.is_leaf is True

    def test_is_leaf_with_children(self):
        child_path = ProjectPath(scope="Test", path=ModelPath(root="$", parts=(AttributePart("x"),)))
        child = PathNode(path=child_path, value=42.0)

        parent_path = ProjectPath(scope="Test", path=ModelPath(root="$", parts=()))
        parent = PathNode(path=parent_path, value=None, children=(child,))

        assert parent.is_leaf is False
        assert child.is_leaf is True

    def test_iter_leaves_single_leaf(self):
        path = ProjectPath(scope="Test", path=ModelPath(root="$", parts=(AttributePart("x"),)))
        node = PathNode(path=path, value=42.0)

        leaves = list(node.iter_leaves())
        assert len(leaves) == 1
        assert leaves[0] is node

    def test_iter_leaves_nested(self):
        # Build a tree with 3 leaves
        leaf1_path = ProjectPath(scope="Test", path=ModelPath(root="$", parts=(AttributePart("a"),)))
        leaf1 = PathNode(path=leaf1_path, value=1.0)

        leaf2_path = ProjectPath(scope="Test", path=ModelPath(root="$", parts=(AttributePart("b"), AttributePart("x"))))
        leaf2 = PathNode(path=leaf2_path, value=2.0)

        leaf3_path = ProjectPath(scope="Test", path=ModelPath(root="$", parts=(AttributePart("b"), AttributePart("y"))))
        leaf3 = PathNode(path=leaf3_path, value=3.0)

        # Intermediate node for 'b'
        b_path = ProjectPath(scope="Test", path=ModelPath(root="$", parts=(AttributePart("b"),)))
        b_node = PathNode(path=b_path, value=None, children=(leaf2, leaf3))

        # Root node
        root_path = ProjectPath(scope="Test", path=ModelPath(root="$", parts=()))
        root = PathNode(path=root_path, value=None, children=(leaf1, b_node))

        leaves = list(root.iter_leaves())
        assert len(leaves) == 3
        assert leaves[0] is leaf1
        assert leaves[1] is leaf2
        assert leaves[2] is leaf3

    def test_get_child_found(self):
        child_path = ProjectPath(scope="Test", path=ModelPath(root="$", parts=(AttributePart("x"),)))
        child = PathNode(path=child_path, value=42.0)

        parent_path = ProjectPath(scope="Test", path=ModelPath(root="$", parts=()))
        parent = PathNode(path=parent_path, value=None, children=(child,))

        found = parent.get_child(AttributePart("x"))
        assert found is child

    def test_get_child_not_found(self):
        child_path = ProjectPath(scope="Test", path=ModelPath(root="$", parts=(AttributePart("x"),)))
        child = PathNode(path=child_path, value=42.0)

        parent_path = ProjectPath(scope="Test", path=ModelPath(root="$", parts=()))
        parent = PathNode(path=parent_path, value=None, children=(child,))

        found = parent.get_child(AttributePart("y"))
        assert found is None

    def test_get_child_with_item_part(self):
        child_path = ProjectPath(scope="Test", path=ModelPath(root="$", parts=(ItemPart("nominal"),)))
        child = PathNode(path=child_path, value=10.0)

        parent_path = ProjectPath(scope="Test", path=ModelPath(root="$", parts=()))
        parent = PathNode(path=parent_path, value=None, children=(child,))

        found = parent.get_child(ItemPart("nominal"))
        assert found is child


class TestScopeTree:
    def test_get_calculation_found(self):
        calc_path = ProjectPath(scope="Power", path=CalcPath(root="@total_power", parts=()))
        calc_node = PathNode(path=calc_path, value=100.0)

        tree = ScopeTree(scope_name="Power", calculations=(calc_node,))

        found = tree.get_calculation("total_power")
        assert found is calc_node

    def test_get_calculation_not_found(self):
        calc_path = ProjectPath(scope="Power", path=CalcPath(root="@total_power", parts=()))
        calc_node = PathNode(path=calc_path, value=100.0)

        tree = ScopeTree(scope_name="Power", calculations=(calc_node,))

        found = tree.get_calculation("nonexistent")
        assert found is None

    def test_get_verification_found(self):
        verif_path = ProjectPath(scope="Power", path=VerificationPath(root="?check_power", parts=()))
        verif_node = PathNode(path=verif_path, value=True)

        tree = ScopeTree(scope_name="Power", verifications=(verif_node,))

        found = tree.get_verification("check_power")
        assert found is verif_node

    def test_get_verification_not_found(self):
        tree = ScopeTree(scope_name="Power", verifications=())

        found = tree.get_verification("nonexistent")
        assert found is None

    def test_iter_all_nodes(self):
        model_path = ProjectPath(scope="Power", path=ModelPath(root="$", parts=()))
        model_node = PathNode(path=model_path, value=None)

        calc_path = ProjectPath(scope="Power", path=CalcPath(root="@calc1", parts=()))
        calc_node = PathNode(path=calc_path, value=1.0)

        verif_path = ProjectPath(scope="Power", path=VerificationPath(root="?verif1", parts=()))
        verif_node = PathNode(path=verif_path, value=True)

        tree = ScopeTree(
            scope_name="Power",
            model=model_node,
            calculations=(calc_node,),
            verifications=(verif_node,),
        )

        nodes = list(tree.iter_all_nodes())
        assert len(nodes) == 3
        assert model_node in nodes
        assert calc_node in nodes
        assert verif_node in nodes

    def test_iter_all_nodes_no_model(self):
        calc_path = ProjectPath(scope="Power", path=CalcPath(root="@calc1", parts=()))
        calc_node = PathNode(path=calc_path, value=1.0)

        tree = ScopeTree(scope_name="Power", calculations=(calc_node,))

        nodes = list(tree.iter_all_nodes())
        assert len(nodes) == 1
        assert calc_node in nodes


class TestBuildScopeTrees:
    def test_empty_values(self):
        result = build_scope_trees({})
        assert result == {}

    def test_single_leaf_model(self):
        ppath = ProjectPath(scope="Test", path=ModelPath(root="$", parts=(AttributePart("x"),)))
        values = {ppath: 42.0}

        result = build_scope_trees(values)

        assert "Test" in result
        tree = result["Test"]
        assert tree.model is not None
        assert tree.model.is_leaf is False  # Root has child
        assert len(tree.model.children) == 1

        child = tree.model.children[0]
        assert child.is_leaf is True
        assert child.value == 42.0
        assert child.path == ppath

    def test_nested_model(self):
        path_a = ProjectPath(scope="Test", path=ModelPath(root="$", parts=(AttributePart("a"),)))
        path_b_x = ProjectPath(scope="Test", path=ModelPath(root="$", parts=(AttributePart("b"), AttributePart("x"))))
        path_b_y = ProjectPath(scope="Test", path=ModelPath(root="$", parts=(AttributePart("b"), AttributePart("y"))))

        values = {
            path_a: 1.0,
            path_b_x: 2.0,
            path_b_y: 3.0,
        }

        result = build_scope_trees(values)

        tree = result["Test"]
        assert tree.model is not None

        # Check leaves
        leaves = list(tree.model.iter_leaves())
        assert len(leaves) == 3

        leaf_values = {leaf.path: leaf.value for leaf in leaves}
        assert leaf_values[path_a] == 1.0
        assert leaf_values[path_b_x] == 2.0
        assert leaf_values[path_b_y] == 3.0

    def test_table_with_item_parts(self):
        path_nominal = ProjectPath(
            scope="Test",
            path=ModelPath(root="$", parts=(AttributePart("table"), ItemPart("nominal"))),
        )
        path_safe = ProjectPath(
            scope="Test",
            path=ModelPath(root="$", parts=(AttributePart("table"), ItemPart("safe"))),
        )

        values = {
            path_nominal: 10.0,
            path_safe: 5.0,
        }

        result = build_scope_trees(values)

        tree = result["Test"]
        assert tree.model is not None
        leaves = list(tree.model.iter_leaves())
        assert len(leaves) == 2

    def test_calculation_tree(self):
        calc_path = ProjectPath(scope="Power", path=CalcPath(root="@total_power", parts=()))

        values = {calc_path: 100.0}

        result = build_scope_trees(values)

        tree = result["Power"]
        assert tree.model is None
        assert len(tree.calculations) == 1

        calc_node = tree.get_calculation("total_power")
        assert calc_node is not None
        assert calc_node.is_leaf is True
        assert calc_node.value == 100.0

    def test_verification_tree(self):
        verif_path = ProjectPath(scope="Power", path=VerificationPath(root="?check_power", parts=()))

        values = {verif_path: True}

        result = build_scope_trees(values)

        tree = result["Power"]
        assert len(tree.verifications) == 1

        verif_node = tree.get_verification("check_power")
        assert verif_node is not None
        assert verif_node.is_leaf is True
        assert verif_node.value is True

    def test_table_verification(self):
        # Table[K, bool] verification has parts
        path_nominal = ProjectPath(
            scope="Power",
            path=VerificationPath(root="?check_power", parts=(ItemPart("nominal"),)),
        )
        path_safe = ProjectPath(
            scope="Power",
            path=VerificationPath(root="?check_power", parts=(ItemPart("safe"),)),
        )

        values = {
            path_nominal: True,
            path_safe: False,
        }

        result = build_scope_trees(values)

        tree = result["Power"]
        verif_node = tree.get_verification("check_power")
        assert verif_node is not None
        assert verif_node.is_leaf is False
        assert len(verif_node.children) == 2

        leaves = list(verif_node.iter_leaves())
        assert len(leaves) == 2

    def test_multiple_scopes(self):
        power_path = ProjectPath(scope="Power", path=ModelPath(root="$", parts=(AttributePart("x"),)))
        thermal_path = ProjectPath(scope="Thermal", path=ModelPath(root="$", parts=(AttributePart("y"),)))

        values = {
            power_path: 1.0,
            thermal_path: 2.0,
        }

        result = build_scope_trees(values)

        assert "Power" in result
        assert "Thermal" in result

        assert result["Power"].model is not None
        power_leaves = list(result["Power"].model.iter_leaves())
        assert len(power_leaves) == 1
        assert power_leaves[0].value == 1.0

        assert result["Thermal"].model is not None
        thermal_leaves = list(result["Thermal"].model.iter_leaves())
        assert len(thermal_leaves) == 1
        assert thermal_leaves[0].value == 2.0

    def test_multiple_calculations(self):
        calc1_path = ProjectPath(scope="Power", path=CalcPath(root="@calc1", parts=()))
        calc2_path = ProjectPath(scope="Power", path=CalcPath(root="@calc2", parts=()))

        values = {
            calc1_path: 10.0,
            calc2_path: 20.0,
        }

        result = build_scope_trees(values)

        tree = result["Power"]
        assert len(tree.calculations) == 2
        calc1 = tree.get_calculation("calc1")
        calc2 = tree.get_calculation("calc2")
        assert calc1 is not None
        assert calc2 is not None
        assert calc1.value == 10.0
        assert calc2.value == 20.0

    def test_calculation_with_nested_output(self):
        # Calculation that returns a complex type with nested fields
        calc_x = ProjectPath(scope="Test", path=CalcPath(root="@compute", parts=(AttributePart("x"),)))
        calc_y = ProjectPath(scope="Test", path=CalcPath(root="@compute", parts=(AttributePart("y"),)))

        values = {
            calc_x: 1.0,
            calc_y: 2.0,
        }

        result = build_scope_trees(values)

        tree = result["Test"]
        calc_node = tree.get_calculation("compute")
        assert calc_node is not None
        assert calc_node.is_leaf is False

        leaves = list(calc_node.iter_leaves())
        assert len(leaves) == 2

    def test_tuple_item_key(self):
        # Multi-dimensional table with tuple keys
        path1 = ProjectPath(
            scope="Test",
            path=ModelPath(root="$", parts=(AttributePart("matrix"), ItemPart(("launch", "nominal")))),
        )
        path2 = ProjectPath(
            scope="Test",
            path=ModelPath(root="$", parts=(AttributePart("matrix"), ItemPart(("cruise", "safe")))),
        )

        values = {
            path1: 10.0,
            path2: 20.0,
        }

        result = build_scope_trees(values)

        tree = result["Test"]
        assert tree.model is not None
        leaves = list(tree.model.iter_leaves())
        assert len(leaves) == 2
