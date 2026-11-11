from typing import TYPE_CHECKING, ParamSpec, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

    from ._models import Ref

T = TypeVar("T")
P = ParamSpec("P")


def assume(ref: Ref) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator to mark that a calculation assumes a verification.

    Args:
        ref: Reference to the assumed verification, e.g., vq.Ref("?verify_temp", scope="Thermal").
             The path must start with "?" (verification symbol).

    The decorator may be applied either inside or outside of `@scope.calculation()` /
    `@scope.verification()`; both orders register the same assumption.

    Example:
        @power.calculation()
        @vq.assume(vq.Ref("?solar_panel_max_temperature"))
        def calculate_solar_panel_heat(...):
            ...

    """
    # Validate that the ref points to a verification
    if not ref.path.startswith("?"):
        msg = f"assume() requires a verification reference (path starting with '?'), got: {ref.path}"
        raise ValueError(msg)

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        # Applied outside @scope.calculation() / @scope.verification(): the decorated
        # object is already registered, so record the assumption on it directly.
        from ._models import Calculation, Verification  # noqa: PLC0415

        if isinstance(func, (Calculation, Verification)):
            func.assumed_refs.append(ref)
            return func

        # HACK: We should avoid modifying the function object directly,
        # but this is a simple way to attach metadata.
        # In the future, we might implement a builder class for calculations/verifications.
        attr = "__veriq_assumed_refs__"
        if not hasattr(func, attr):
            setattr(func, attr, [])
        getattr(func, attr).append(ref)
        return func

    return decorator
