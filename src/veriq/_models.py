from __future__ import annotations

import inspect
import logging
from annotationlib import ForwardRef
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, get_args, get_origin

from pydantic import BaseModel, create_model
from scoped_context import NoContextError, ScopedContext
from typing_extensions import _AnnotatedAlias

from ._path import AttributePart, CalcPath, ItemPart, ModelPath, ProjectPath, VerificationPath, parse_path
from ._table import Table

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

logger = logging.getLogger(__name__)


def _get_dep_refs_from_signature(sig: inspect.Signature) -> dict[str, Ref]:
    """Extract Ref annotations from the function signature.

    Args:
        sig: The function signature to extract refs from.

    Returns:
        A dictionary mapping parameter names to their Ref annotations.

    Raises:
        TypeError: If a parameter is missing a Ref annotation.

    """

    def _get_dep_ref_from_annotation(
        name: str,
        annotations: _AnnotatedAlias,
    ) -> Ref | None:
        args = get_args(annotations)
        try:
            return next(iter(arg for arg in args if isinstance(arg, Ref)))
        except StopIteration:
            msg = f"Parameter '{name}' must be annotated with Fetch or Calc."
            raise TypeError(msg) from None

    return {
        param.name: dep
        for param in sig.parameters.values()
        if (dep := _get_dep_ref_from_annotation(param.name, param.annotation)) is not None
    }


def _get_return_type_from_signature(sig: inspect.Signature) -> type:
    """Extract return type from the function signature.

    Args:
        sig: The function signature to extract the return type from.

    Returns:
        The return type annotation.

    Raises:
        TypeError: If the function has no return type or an invalid one.

    """
    return_annotation = sig.return_annotation
    if return_annotation is inspect.Signature.empty:
        msg = "Function must have a return type annotation."
        raise TypeError(msg)
    if isinstance(return_annotation, type):
        return return_annotation
    # Handle generic aliases like Table[K, V]
    # Preserve the full generic type with type parameters
    origin = get_origin(return_annotation)
    if origin is not None and isinstance(origin, type):
        return return_annotation
    msg = "Return type must be a type."
    raise TypeError(msg)


def _validate_and_convert_refs(
    dep_refs: dict[str, Ref],
    default_scope_name: str,
    imported_scope_names: list[str],
    entity_name: str,
    entity_type: str,
) -> dict[str, ProjectPath]:
    """Validate cross-scope references and convert Refs to ProjectPaths.

    This is shared logic between Calculation and Verification.

    Args:
        dep_refs: Dictionary mapping parameter names to Ref objects.
        default_scope_name: The default scope for unqualified refs.
        imported_scope_names: List of allowed imported scope names.
        entity_name: Name of the calculation/verification (for error messages).
        entity_type: Type string like "calculation" or "verification".

    Returns:
        Dictionary mapping parameter names to ProjectPaths.

    Raises:
        ValueError: If a cross-scope reference is not in imported_scope_names.

    """
    dep_ppaths: dict[str, ProjectPath] = {}

    for dep_name, dep_ref in dep_refs.items():
        # Default scope if not specified
        scope_name = dep_ref.scope if dep_ref.scope is not None else default_scope_name

        # Validate cross-scope references
        if scope_name != default_scope_name and scope_name not in imported_scope_names:
            msg = (
                f"Dependency '{dep_name}' is from scope '{scope_name}',"
                f" which is not imported in {entity_type} '{entity_name}'."
            )
            raise ValueError(msg)

        dep_ppaths[dep_name] = ProjectPath(scope=scope_name, path=parse_path(dep_ref.path))

    return dep_ppaths


def is_valid_verification_return_type(return_type: type) -> bool:
    """Check if the return type is valid for a verification function.

    This is a pure function that validates verification return types.

    Valid return types are:
    - bool
    - Table[K, bool] (where K is StrEnum or tuple of StrEnum)

    Args:
        return_type: The type to validate

    Returns:
        True if the return type is valid for a verification, False otherwise

    Examples:
        >>> is_valid_verification_return_type(bool)
        True
        >>> is_valid_verification_return_type(int)
        False

    """
    if return_type is bool:
        return True

    # Check for Table[K, bool]
    origin = get_origin(return_type)
    if origin is Table or (isinstance(origin, type) and issubclass(origin, Table)):
        type_args = get_args(return_type)
        if len(type_args) == 2:
            _key_type, value_type = type_args
            # Value type must be bool
            return value_type is bool
    return False


@dataclass(slots=True)
class Project:
    """A class to hold the scopes."""

    name: str
    _scopes: dict[str, Scope] = field(default_factory=dict)

    def add_scope(self, scope: Scope) -> None:
        """Add a scope to the project."""
        if scope.name in self._scopes:
            msg = f"Scope with name '{scope.name}' already exists in the project."
            raise KeyError(msg)
        self._scopes[scope.name] = scope

    @property
    def scopes(self) -> dict[str, Scope]:
        """Get all scopes in the project."""
        return self._scopes

    def input_model(self) -> type[BaseModel]:
        """Generate a Pydantic BaseModel for the project input file.

        The input model has the structure:
        {
            "ScopeName": {
                "model": <root model instance>
            },
            ...
        }
        """
        # Create a model for each scope that contains just the root model
        scope_models = {}
        for scope_name, scope in self._scopes.items():
            root_model_type = scope.get_root_model()
            # Create a model with a "model" field
            scope_input_model = create_model(
                f"{scope_name}Input",
                model=(root_model_type, ...),
            )
            scope_models[scope_name] = (scope_input_model, ...)

        # Create the project-level model
        return create_model(
            f"{self.name}Input",
            **scope_models,
        )

    def output_model(self) -> type[BaseModel]:
        """Generate a Pydantic BaseModel for the project output file.

        The output model has the structure:
        {
            "ScopeName": {
                "model": <root model instance>,
                "calc": {
                    "calculation_name": <calculation output>,
                    ...
                },
                "verification": {
                    "verification_name": <bool>,
                    ...
                }
            },
            ...
        }
        """
        # Create a model for each scope
        scope_models = {}
        for scope_name, scope in self._scopes.items():
            root_model_type = scope.get_root_model()

            # Create calc model with all calculations
            calc_fields = {calc_name: (calc.output_type, ...) for calc_name, calc in scope.calculations.items()}
            calc_model = create_model(f"{scope_name}Calc", **calc_fields) if calc_fields else None  # ty: ignore[no-matching-overload]

            # Create verification model with all verifications (using actual return types)
            verification_fields = {
                verif_name: (verif.output_type, ...) for verif_name, verif in scope.verifications.items()
            }
            verification_model = (
                create_model(f"{scope_name}Verification", **verification_fields)  # ty: ignore[no-matching-overload]
                if verification_fields
                else None
            )

            # Create scope output model
            scope_output_fields = {
                "model": (root_model_type, ...),
            }
            if calc_model is not None:
                scope_output_fields["calc"] = (calc_model, ...)
            if verification_model is not None:
                scope_output_fields["verification"] = (verification_model, ...)

            scope_output_model = create_model(  # ty: ignore[no-matching-overload]
                f"{scope_name}Output",
                **scope_output_fields,
            )
            scope_models[scope_name] = (scope_output_model, ...)

        # Create the project-level model
        return create_model(
            f"{self.name}Output",
            **scope_models,
        )

    def get_type(self, ppath: ProjectPath) -> type:  # noqa: C901,PLR0915,PLR0912
        """Get the type of the given project path."""
        scope = self._scopes.get(ppath.scope)
        if scope is None:
            msg = f"Scope '{ppath.scope}' not found in project '{self.name}'."
            raise KeyError(msg)

        if isinstance(ppath.path, ModelPath):
            current_type: type = scope.get_root_model()
            for part in ppath.path.parts:
                if isinstance(current_type, ForwardRef):
                    current_type = current_type.evaluate()
                match part:
                    case AttributePart(name):
                        if not issubclass(current_type, BaseModel):
                            msg = f"Type '{current_type}' is not a Pydantic model."
                            raise TypeError(msg)
                        try:
                            field_info = current_type.model_fields[name]
                        except KeyError as e:
                            msg = f"Attribute '{name}' not found in model '{current_type.__name__}'."
                            raise KeyError(msg) from e
                        if field_info.annotation is None:
                            msg = f"Attribute '{name}' in model '{current_type.__name__}' has no type annotation."
                            raise TypeError(msg)
                        current_type = field_info.annotation
                    case ItemPart(key):
                        args = get_args(current_type)
                        if len(args) != 2:
                            msg = f"Type '{current_type}' is not subscriptable with key '{key}'."
                            raise TypeError(msg)
                        current_type = args[1]
                    case _:
                        msg = f"Unknown part type: {type(part)}"
                        raise TypeError(msg)

            if isinstance(current_type, ForwardRef):
                current_type = current_type.evaluate()

            return current_type

        if isinstance(ppath.path, CalcPath):
            calc_name = ppath.path.root.lstrip(ppath.path.PREFIX)
            calculation = scope.calculations.get(calc_name)
            if calculation is None:
                msg = f"Calculation '{calc_name}' not found in scope '{scope.name}'."
                raise KeyError(msg)
            current_type = calculation.output_type
            for part in ppath.path.parts:
                if isinstance(current_type, ForwardRef):
                    current_type = current_type.evaluate()
                match part:
                    case AttributePart(name):
                        if not issubclass(current_type, BaseModel):
                            msg = f"Type '{current_type}' is not a Pydantic model."
                            raise TypeError(msg)
                        try:
                            field_info = current_type.model_fields[name]
                        except KeyError as e:
                            msg = f"Attribute '{name}' not found in model '{current_type.__name__}'."
                            raise KeyError(msg) from e
                        if field_info.annotation is None:
                            msg = f"Attribute '{name}' in model '{current_type.__name__}' has no type annotation."
                            raise TypeError(msg)
                        current_type = field_info.annotation
                    case ItemPart(key):
                        args = get_args(current_type)
                        if len(args) != 2:
                            msg = f"Type '{current_type}' is not subscriptable with key '{key}'."
                            raise TypeError(msg)
                        current_type = args[1]
                    case _:
                        msg = f"Unknown part type: {type(part)}"
                        raise TypeError(msg)
            if isinstance(current_type, ForwardRef):
                current_type = current_type.evaluate()
            return current_type

        if isinstance(ppath.path, VerificationPath):
            verif_name = ppath.path.root.lstrip(ppath.path.PREFIX)
            verification = scope.verifications.get(verif_name)
            if verification is None:
                msg = f"Verification '{verif_name}' not found in scope '{scope.name}'."
                raise KeyError(msg)
            current_type = verification.output_type
            for part in ppath.path.parts:
                if isinstance(current_type, ForwardRef):
                    current_type = current_type.evaluate()
                match part:
                    case AttributePart(name):
                        if not issubclass(current_type, BaseModel):
                            msg = f"Type '{current_type}' is not a Pydantic model."
                            raise TypeError(msg)
                        try:
                            field_info = current_type.model_fields[name]
                        except KeyError as e:
                            msg = f"Attribute '{name}' not found in model '{current_type.__name__}'."
                            raise KeyError(msg) from e
                        if field_info.annotation is None:
                            msg = f"Attribute '{name}' in model '{current_type.__name__}' has no type annotation."
                            raise TypeError(msg)
                        current_type = field_info.annotation
                    case ItemPart(key):
                        args = get_args(current_type)
                        if len(args) != 2:
                            msg = f"Type '{current_type}' is not subscriptable with key '{key}'."
                            raise TypeError(msg)
                        current_type = args[1]
                    case _:
                        msg = f"Unknown part type: {type(part)}"
                        raise TypeError(msg)
            if isinstance(current_type, ForwardRef):
                current_type = current_type.evaluate()
            return current_type

        msg = f"Unsupported path type: {ppath.path.__class__.__name__}"
        raise TypeError(msg)


@dataclass(slots=True)
class Ref:
    """Reference to a project path."""

    path: str
    scope: str | None = None


@dataclass(slots=True)
class Calculation[T, **P]:
    """A class to represent a calculation in the verification process."""

    name: str
    func: Callable[P, T] = field(repr=False)
    default_scope_name: str = field()
    imported_scope_names: list[str] = field(default_factory=list)
    assumed_verifications: list[Verification[Any, ...]] = field(default_factory=list)

    # Fields initialized in __post_init__
    dep_ppaths: dict[str, ProjectPath] = field(init=False)
    output_type: type[T] = field(init=False)

    def __post_init__(self) -> None:
        sig = inspect.signature(self.func)
        dep_refs = _get_dep_refs_from_signature(sig)
        self.dep_ppaths = _validate_and_convert_refs(
            dep_refs,
            self.default_scope_name,
            self.imported_scope_names,
            self.name,
            "calculation",
        )
        self.output_type = _get_return_type_from_signature(sig)  # ty: ignore[invalid-assignment]

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> T:
        return self.func(*args, **kwargs)


@dataclass(slots=True)
class Verification[T, **P]:
    """A class to represent a verification in the verification process.

    The return type T must be either `bool` or `Table[K, bool]`.
    """

    name: str
    func: Callable[P, T] = field(repr=False)  # TODO: disallow positional-only arguments
    default_scope_name: str = field()
    imported_scope_names: list[str] = field(default_factory=list)
    assumed_verifications: list[Verification[Any, ...]] = field(default_factory=list)
    xfail: bool = field(default=False, kw_only=True)

    # Fields initialized in __post_init__
    dep_ppaths: dict[str, ProjectPath] = field(init=False)
    output_type: type[T] = field(init=False)

    def __post_init__(self) -> None:
        sig = inspect.signature(self.func)
        dep_refs = _get_dep_refs_from_signature(sig)
        self.dep_ppaths = _validate_and_convert_refs(
            dep_refs,
            self.default_scope_name,
            self.imported_scope_names,
            self.name,
            "verification",
        )

        # Extract and validate return type
        self.output_type = _get_return_type_from_signature(sig)  # ty: ignore[invalid-assignment]
        if not is_valid_verification_return_type(self.output_type):
            msg = (
                f"Verification '{self.name}' has invalid return type '{self.output_type}'. "
                "Return type must be 'bool' or 'Table[K, bool]'."
            )
            raise TypeError(msg)

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> T:
        return self.func(*args, **kwargs)


@dataclass(slots=True)
class Requirement(ScopedContext):
    def __post_init__(self) -> None:
        try:
            current_requirement = Requirement.current()
        except NoContextError:
            pass
        else:
            current_requirement.decomposed_requirements.append(self)

    id: str
    description: str
    decomposed_requirements: list[Requirement] = field(default_factory=list, repr=False)
    verified_by: list[Verification[Any, ...]] = field(default_factory=list, repr=False)
    depends_on: list[Requirement] = field(default_factory=list, repr=False)

    def iter_requirements(self, *, depth: int | None = None, leaf_only: bool = False) -> Iterable[Requirement]:
        """Iterate over requirements under the current requirement."""
        if not leaf_only or not self.decomposed_requirements:
            yield self
        if depth is not None and depth <= 0:
            return
        for req in self.decomposed_requirements:
            yield from req.iter_requirements(depth=depth - 1 if depth is not None else None, leaf_only=leaf_only)


@dataclass(slots=True)
class Scope:
    name: str
    _root_model: type[BaseModel] | None = field(default=None)
    _requirements: dict[str, Requirement] = field(default_factory=dict)
    _verifications: dict[str, Verification[Any, ...]] = field(default_factory=dict)
    _calculations: dict[str, Calculation[Any, ...]] = field(default_factory=dict)

    def get_root_model(self) -> type[BaseModel]:
        """Get the root model of the scope."""
        if self._root_model is None:
            msg = f"Scope '{self.name}' does not have a root model defined."
            raise RuntimeError(msg)
        return self._root_model

    @property
    def requirements(self) -> dict[str, Requirement]:
        """Get all requirements in the scope."""
        return self._requirements

    @property
    def verifications(self) -> dict[str, Verification[Any, ...]]:
        """Get all verifications in the scope."""
        return self._verifications

    @property
    def calculations(self) -> dict[str, Calculation[Any, ...]]:
        """Get all calculations in the scope."""
        return self._calculations

    def root_model[M: type[BaseModel]](self) -> Callable[[M], M]:
        """Decorator to mark a model as the root model of the scope."""

        def decorator(model: M) -> M:
            if self._root_model is not None:
                msg = f"Scope '{self.name}' already has a root model assigned: {self._root_model.__name__}"
                raise RuntimeError(msg)
            self._root_model = model
            return model

        return decorator

    def verification[T, **P](
        self,
        name: str | None = None,
        imports: Iterable[str] = (),
        *,
        xfail: bool = False,
    ) -> Callable[[Callable[P, T]], Verification[T, P]]:
        """Decorator to mark a function as a verification in the scope.

        The decorated function must return either `bool` or `Table[K, bool]`.
        """

        def decorator(func: Callable[P, T]) -> Verification[T, P]:
            if name is None:
                if not hasattr(func, "__name__") or not isinstance(func.__name__, str):
                    msg = "Function must have a valid name."
                    raise TypeError(msg)
                verification_name = func.__name__
            else:
                verification_name = name

            assumed_verifications: list[Verification[Any, ...]] = []
            if hasattr(func, "__veriq_assumed_verifications__"):
                assumed_verifications = func.__veriq_assumed_verifications__  # ty: ignore[invalid-assignment]

            verification = Verification(
                name=verification_name,
                func=func,
                imported_scope_names=list(imports),
                assumed_verifications=assumed_verifications,
                default_scope_name=self.name,
                xfail=xfail,
            )
            if verification_name in self._verifications:
                msg = f"Verification with name '{verification_name}' already exists in scope '{self.name}'."
                raise KeyError(msg)
            self._verifications[verification_name] = verification
            return verification

        return decorator

    def calculation[T, **P](
        self,
        name: str | None = None,
        imports: Iterable[str] = (),
    ) -> Callable[[Callable[P, T]], Calculation[T, P]]:
        """Decorator to mark a function as a calculation in the scope."""

        def decorator(func: Callable[P, T]) -> Calculation[T, P]:
            if name is None:
                if not hasattr(func, "__name__") or not isinstance(func.__name__, str):
                    msg = "Function must have a valid name."
                    raise TypeError(msg)
                calculation_name = func.__name__
            else:
                calculation_name = name

            assumed_verifications: list[Verification[Any, ...]] = []
            if hasattr(func, "__veriq_assumed_verifications__"):
                assumed_verifications = func.__veriq_assumed_verifications__  # ty: ignore[invalid-assignment]

            calculation = Calculation(
                name=calculation_name,
                func=func,
                imported_scope_names=list(imports),
                assumed_verifications=assumed_verifications,
                default_scope_name=self.name,
            )
            if calculation_name in self._calculations:
                msg = f"Calculation with name '{calculation_name}' already exists in scope '{self.name}'."
                raise KeyError(msg)
            self._calculations[calculation_name] = calculation
            return calculation

        return decorator

    def requirement(
        self,
        id_: str,
        /,
        description: str,
        verified_by: Iterable[Verification[Any, ...]] = (),
    ) -> Requirement:
        """Create and add a requirement to the scope."""
        requirement = Requirement(description=description, verified_by=list(verified_by), id=id_)
        if id_ in self._requirements:
            msg = f"Requirement with ID '{id_}' already exists in scope '{self.name}'."
            raise KeyError(msg)
        self._requirements[id_] = requirement
        return requirement

    def fetch_requirement(self, id_: str, /) -> Requirement:
        """Fetch a requirement by its ID."""
        try:
            return self._requirements[id_]
        except KeyError as e:
            msg = f"Requirement with ID '{id_}' not found in scope '{self.name}'."
            raise KeyError(msg) from e
