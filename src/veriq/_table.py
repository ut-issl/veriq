from enum import StrEnum
from itertools import product
from typing import TYPE_CHECKING, Any, get_args

from pydantic_core import core_schema

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from pydantic import GetCoreSchemaHandler
    from pydantic_core import CoreSchema


class Table[K: (StrEnum, tuple[StrEnum, ...]), V](dict[K, V]):
    """Exhaustive mapping from keys of type K to values of type V."""

    _key_type: type[K]
    _expected_keys: frozenset[K]

    @property
    def key_type(self) -> type[K]:
        """The type of the keys in the table."""
        return self._key_type

    @property
    def expected_keys(self) -> frozenset[K]:
        """The set of expected keys in the table."""
        return self._expected_keys

    @staticmethod
    def _serialize_key(key: K) -> str:
        """Serialize a key to a string for JSON representation."""
        if isinstance(key, tuple):
            return ",".join(str(k.value) for k in key)  # ty: ignore[unresolved-attribute] # k is `StrEnum` but ty cannot infer it
        return str(key.value)

    def _serialize_for_pydantic(self) -> dict[str, V]:
        """Serialize the table to a dict with string keys for Pydantic."""
        return {self._serialize_key(k): v for k, v in self.items()}

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Generate Pydantic core schema for Table type."""
        # Extract type arguments K and V from the source type
        type_args = get_args(source_type)
        if len(type_args) != 2:
            msg = f"Table requires exactly 2 type arguments, got {len(type_args)}"
            raise TypeError(msg)

        key_type_arg, value_type_arg = type_args

        # Determine the actual enum type(s)
        key_type_args = get_args(key_type_arg)
        enum_types = key_type_args if key_type_args else (key_type_arg,)

        # Validate that all are StrEnum subclasses
        for enum_type in enum_types:
            if not (isinstance(enum_type, type) and issubclass(enum_type, StrEnum)):
                msg = f"All key types must be StrEnum subclasses, got {enum_type}"
                raise TypeError(msg)

        # Create a validation function that deserializes dict[str, V] -> Table[K, V]
        def validate_from_dict(value: dict[str, V]) -> Table[K, V]:
            # Deserialize the keys
            deserialized: dict[K, V] = {}
            for str_key, val in value.items():
                # Parse the key based on whether it's a tuple or single enum
                if len(enum_types) == 1:
                    # Single StrEnum key
                    enum_type = enum_types[0]
                    key = enum_type(str_key)
                else:
                    # Tuple of StrEnum keys
                    parts = str_key.split(",")
                    if len(parts) != len(enum_types):
                        msg = f"Expected {len(enum_types)} key parts, got {len(parts)} in '{str_key}'"
                        raise ValueError(msg)
                    key = tuple(enum_type(part) for enum_type, part in zip(enum_types, parts, strict=True))

                deserialized[key] = val  # ty: ignore[invalid-assignment]

            # Create the Table instance, which will validate completeness
            return cls(deserialized)

        # Create serialization function
        def serialize_table(table: Table[K, V]) -> dict[str, V]:
            return table._serialize_for_pydantic()

        # Get the schema for the value type
        value_schema = handler.generate_schema(value_type_arg)

        # Generate all valid keys from enum types
        if len(enum_types) == 1:
            # Single enum key: just use the enum values directly
            # Example: Mode.NOMINAL, Mode.SAFE -> ["nominal", "safe"]
            enum_type = enum_types[0]
            valid_keys = [member.value for member in enum_type]
        else:
            # Tuple of enum keys: generate all combinations using cartesian product
            # Example: (Phase.INITIAL, Mode.NOMINAL), (Phase.INITIAL, Mode.SAFE), ...
            # Serialized as: "initial,nominal", "initial,safe", ...
            valid_keys = [
                ",".join(member.value for member in combo)
                for combo in product(*(list(enum_type) for enum_type in enum_types))
            ]

        # Create a typed dict schema with explicit fields for each valid key
        # This ensures the JSON schema has "properties" with exact keys and "additionalProperties": false
        # instead of using a generic dict schema with "additionalProperties": <value_schema>
        fields = {
            key: core_schema.typed_dict_field(
                value_schema,
                required=True,  # All enum combinations are required in a Table
            )
            for key in valid_keys
        }

        typed_dict_schema = core_schema.typed_dict_schema(
            fields,
            extra_behavior="forbid",  # Reject any keys not in the enum - sets "additionalProperties": false
        )

        # Create a schema that accepts either a Table instance or a dict
        python_schema = core_schema.union_schema(
            [
                # Accept Table instances directly (for in-memory Python objects)
                core_schema.is_instance_schema(cls),
                # Accept dict[str, V] and convert to Table (for deserialization from JSON/TOML)
                core_schema.no_info_after_validator_function(
                    validate_from_dict,
                    typed_dict_schema,  # Use typed dict schema instead of generic dict schema
                ),
            ],
        )

        # Wrap with serialization to convert Table back to dict[str, V] when serializing
        return core_schema.no_info_after_validator_function(
            lambda x: x,  # Identity function since validation is already done
            python_schema,
            serialization=core_schema.plain_serializer_function_ser_schema(
                serialize_table,
                return_schema=typed_dict_schema,  # Use same typed dict schema for serialization
            ),
        )

    def __init__(self, mapping_or_iterable: Mapping[K, V] | Iterable[tuple[K, V]]) -> None:
        mapping: dict[K, V] = dict(mapping_or_iterable)

        if len(mapping) == 0:
            msg = "Table cannot be empty."
            raise ValueError(msg)

        # determine key types
        key_sample = next(iter(mapping.keys()))
        if isinstance(key_sample, tuple):
            key_types = tuple(type(k) for k in key_sample)
            for key_type in key_types:
                if not issubclass(key_type, StrEnum):
                    msg = f"Table key types must be StrEnum or tuple of StrEnum. Got: {key_types}"
                    raise TypeError(msg)
            expected_keys = frozenset(
                tuple(values)
                for values in product(
                    *(list(key_type) for key_type in key_types),
                )
            )
        else:
            key_type = type(key_sample)
            if not issubclass(key_type, StrEnum):
                msg = f"Table key type must be StrEnum or tuple of StrEnum. Got: {key_type}"
                raise TypeError(msg)
            expected_keys = frozenset(key_type)

        self._key_type = type(key_sample)
        self._expected_keys = expected_keys  # ty: ignore[invalid-assignment]

        missing_keys = expected_keys - set(mapping.keys())  # ty: ignore[unsupported-operator]
        if missing_keys:
            msg = f"Table is missing keys: {missing_keys}"
            raise ValueError(msg)

        disallowed_keys = set(mapping.keys()) - expected_keys  # ty: ignore[unsupported-operator]
        if disallowed_keys:
            msg = f"Table has disallowed keys: {disallowed_keys}"
            raise ValueError(msg)

        super().__init__(mapping)
