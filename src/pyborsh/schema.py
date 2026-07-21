"""Schema introspection for extracting Borsh types from Pydantic models."""

import types
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal, Union, get_args, get_origin
from weakref import WeakKeyDictionary

if TYPE_CHECKING:
    from pydantic import BaseModel

from pyborsh.errors import BorshSchemaError
from pyborsh.types import (
    F32,
    F64,
    I8,
    I16,
    I32,
    I64,
    I128,
    U8,
    U16,
    U32,
    U64,
    U128,
    Array,
    Bytes,
    _FloatType,
    _IntegerType,
)


@dataclass
class BorshFieldType:
    """Represents the Borsh type of a field."""

    kind: str  # "u8", "string", "vec", "option", "struct", etc.
    element_type: "BorshFieldType | None" = None  # For Vec, Option, HashSet
    key_type: "BorshFieldType | None" = None  # For HashMap
    value_type: "BorshFieldType | None" = None  # For HashMap
    length: int | None = None  # For fixed arrays and bytes
    struct_class: type | None = None  # For nested structs
    enum_class: type | None = None  # For enums
    tuple_element_types: list["BorshFieldType"] | None = None  # For tuples
    variant_types: list[type] | None = None  # For BorshEnum union types


# All integer marker types
INTEGER_MARKERS = (U8, U16, U32, U64, U128, I8, I16, I32, I64, I128)
FLOAT_MARKERS = (F32, F64)


def get_marker_kind(marker: type | object) -> str:
    """Get the Borsh kind string for a type marker."""
    marker_type = marker if isinstance(marker, type) else type(marker)

    if issubclass(marker_type, _IntegerType):
        prefix = "i" if marker_type.signed else "u"
        return f"{prefix}{marker_type.bits}"
    if issubclass(marker_type, _FloatType):
        return f"f{marker_type.bits}"

    raise BorshSchemaError(f"Unknown marker type: {marker}")


def extract_borsh_type(annotation: Any, field_name: str) -> BorshFieldType:
    """
    Extract the Borsh type from a Python type annotation.

    Args:
        annotation: The type annotation from the Pydantic field.
        field_name: The field name (for error messages).

    Returns:
        BorshFieldType describing how to serialize/deserialize this field.

    Raises:
        BorshSchemaError: If the annotation is invalid for Borsh.
    """
    from typing import Annotated  # Import here to avoid issues

    origin = get_origin(annotation)
    args = get_args(annotation)

    # Handle Annotated types - look for Borsh markers
    if origin is Annotated:
        base_type = args[0]
        markers = args[1:]

        # Look for our Borsh markers
        for marker in markers:
            # Integer markers
            if isinstance(marker, type) and issubclass(marker, _IntegerType):
                return BorshFieldType(kind=get_marker_kind(marker))
            if isinstance(marker, _IntegerType):
                return BorshFieldType(kind=get_marker_kind(marker))

            # Float markers
            if isinstance(marker, type) and issubclass(marker, _FloatType):
                return BorshFieldType(kind=get_marker_kind(marker))
            if isinstance(marker, _FloatType):
                return BorshFieldType(kind=get_marker_kind(marker))

            # Bytes marker
            if isinstance(marker, Bytes):
                if marker.length is not None:
                    return BorshFieldType(kind="fixed_bytes", length=marker.length)
                return BorshFieldType(kind="dynamic_bytes")

            # Array marker
            if isinstance(marker, Array):
                element_borsh = BorshFieldType(kind=get_marker_kind(marker.element_type))
                return BorshFieldType(
                    kind="fixed_array",
                    element_type=element_borsh,
                    length=marker.length,
                )

        # No Borsh marker found, infer from base type
        return infer_borsh_type(base_type, field_name)

    # Not Annotated - infer from the raw type
    return infer_borsh_type(annotation, field_name)


def infer_borsh_type(python_type: Any, field_name: str) -> BorshFieldType:
    """
    Infer Borsh type from a Python type without explicit annotations.

    Args:
        python_type: The Python type to infer from.
        field_name: The field name (for error messages).

    Returns:
        BorshFieldType for the inferred type.

    Raises:
        BorshSchemaError: If the type cannot be inferred (e.g., bare `int`).
    """
    origin = get_origin(python_type)
    args = get_args(python_type)

    # Bare int - ERROR, must be explicit
    if python_type is int:
        raise BorshSchemaError(
            f"Field '{field_name}' has type 'int' which requires explicit width "
            "annotation. Use Annotated[int, U8], Annotated[int, U32], etc."
        )

    # str -> String
    if python_type is str:
        return BorshFieldType(kind="string")

    # Literal types - used for discriminated unions, not serialized
    # We treat Literal[str_value] as a special marker
    if origin is Literal:
        return BorshFieldType(kind="literal")

    # bool -> bool
    if python_type is bool:
        return BorshFieldType(kind="bool")

    # float -> f64 (default)
    if python_type is float:
        return BorshFieldType(kind="f64")

    # bytes -> Vec<u8>
    if python_type is bytes:
        return BorshFieldType(kind="dynamic_bytes")

    # list[T] -> Vec<T>
    if origin is list:
        if not args:
            raise BorshSchemaError(
                f"Field '{field_name}' has type 'list' without element type. Use list[SomeType]."
            )
        element_type = extract_borsh_type(args[0], f"{field_name}[]")
        return BorshFieldType(kind="vec", element_type=element_type)

    # set[T] -> HashSet<T>
    if origin is set:
        if not args:
            raise BorshSchemaError(
                f"Field '{field_name}' has type 'set' without element type. Use set[SomeType]."
            )
        element_type = extract_borsh_type(args[0], f"{field_name}{{}}")
        return BorshFieldType(kind="hashset", element_type=element_type)

    # dict[K, V] -> HashMap<K, V>
    if origin is dict:
        if len(args) != 2:
            raise BorshSchemaError(
                f"Field '{field_name}' has type 'dict' without key/value types. "
                "Use dict[KeyType, ValueType]."
            )
        key_type = extract_borsh_type(args[0], f"{field_name}.key")
        value_type = extract_borsh_type(args[1], f"{field_name}.value")
        return BorshFieldType(kind="hashmap", key_type=key_type, value_type=value_type)

    # tuple[T, ...] -> fixed-size tuple
    if origin is tuple:
        if not args:
            raise BorshSchemaError(f"Field '{field_name}' has type 'tuple' without element types.")
        # Store all element types for heterogeneous tuples
        element_types = [
            extract_borsh_type(arg, f"{field_name}[{i}]") for i, arg in enumerate(args)
        ]
        return BorshFieldType(kind="tuple", length=len(args), tuple_element_types=element_types)

    # Optional[T] or T | None -> Option<T>
    # Handle both typing.Union and types.UnionType (Python 3.10+ union syntax)
    if origin is Union or origin is types.UnionType:
        # Check if it's Optional (Union with None)
        non_none_args = [a for a in args if a is not type(None)]
        if len(non_none_args) == 1 and type(None) in args:
            inner_type = extract_borsh_type(non_none_args[0], field_name)
            return BorshFieldType(kind="option", element_type=inner_type)

        # Check if it's a union of BorshEnum variant classes
        # We identify variants by checking if they have a _borsh_enum_parent attribute
        enum_parents: set[type] = set()
        for arg in non_none_args:
            if isinstance(arg, type):
                # Check for _borsh_enum_parent set by BorshEnumMeta
                parent = getattr(arg, "_borsh_enum_parent", None)
                if parent is not None:
                    enum_parents.add(parent)

        if len(enum_parents) == 1:
            # All variants belong to the same BorshEnum
            enum_class = next(iter(enum_parents))
            return BorshFieldType(
                kind="borsh_enum", enum_class=enum_class, variant_types=list(non_none_args)
            )

        raise BorshSchemaError(
            f"Field '{field_name}' has Union type that is not Optional. "
            "Only T | None (Option<T>) or BorshEnum variant unions are supported."
        )

    # Check for Pydantic BaseModel subclass (nested struct)
    try:
        from pydantic import BaseModel

        if isinstance(python_type, type) and issubclass(python_type, BaseModel):
            return BorshFieldType(kind="struct", struct_class=python_type)
    except ImportError:  # pragma: no cover
        pass

    # Check for IntEnum
    if isinstance(python_type, type) and issubclass(python_type, Enum):
        return BorshFieldType(kind="enum", enum_class=python_type)

    raise BorshSchemaError(
        f"Field '{field_name}' has unsupported type '{python_type}'. "
        "See documentation for supported types."
    )


# Weak keys: schemas are cached for a class's lifetime, but the cache must
# not BE what keeps the class alive. functools.cache would pin dynamically
# created models (pydantic.create_model, per-request classes) plus their
# schemas for the whole process; with weak keys the entry dies with the class.
_SCHEMA_CACHE: WeakKeyDictionary[type, dict[str, BorshFieldType]] = WeakKeyDictionary()


def build_model_schema(model_class: type) -> dict[str, BorshFieldType]:
    """
    Build a complete Borsh schema from a Pydantic model class.

    Results are cached per model class (schemas are fixed once a model is
    defined), so repeated serialization does not rebuild them. The cache
    holds its keys weakly, so dynamically created model classes remain
    garbage-collectable; their cached schemas are dropped with them.

    Args:
        model_class: A Pydantic BaseModel subclass.

    Returns:
        Dict mapping field names to their BorshFieldType.
    """
    # Validate before touching the cache: non-model arguments (e.g. `str`)
    # must raise BorshSchemaError, and built-in types are not weak-referenceable.
    try:
        from pydantic import BaseModel

        if not issubclass(model_class, BaseModel):
            raise BorshSchemaError(f"{model_class} is not a Pydantic BaseModel")
    except ImportError as err:  # pragma: no cover
        raise BorshSchemaError("Pydantic is not installed") from err

    schema = _SCHEMA_CACHE.get(model_class)
    if schema is None:
        schema = _build_model_schema(model_class)
        _SCHEMA_CACHE[model_class] = schema
    return schema


def _build_model_schema(model_class: "type[BaseModel]") -> dict[str, BorshFieldType]:
    """Uncached implementation of build_model_schema."""
    schema: dict[str, BorshFieldType] = {}

    for field_name, field_info in model_class.model_fields.items():
        annotation = field_info.annotation
        if annotation is None:
            raise BorshSchemaError(f"Field '{field_name}' has no type annotation")

        # Pydantic strips Annotated wrapper and puts metadata in field_info.metadata
        metadata = getattr(field_info, "metadata", [])
        schema[field_name] = extract_borsh_type_with_metadata(annotation, metadata, field_name)

    return schema


def extract_borsh_type_with_metadata(
    annotation: Any, metadata: list[Any], field_name: str
) -> BorshFieldType:
    """
    Extract Borsh type from annotation and Pydantic metadata.

    Pydantic 2.x strips the Annotated[] wrapper and puts extra annotations
    in field_info.metadata. This function checks both places.
    """
    # First check metadata for Borsh markers (Pydantic extracted from Annotated)
    for marker in metadata:
        # Integer markers
        if isinstance(marker, type) and issubclass(marker, _IntegerType):
            return BorshFieldType(kind=get_marker_kind(marker))
        if isinstance(marker, _IntegerType):
            return BorshFieldType(kind=get_marker_kind(marker))

        # Float markers
        if isinstance(marker, type) and issubclass(marker, _FloatType):
            return BorshFieldType(kind=get_marker_kind(marker))
        if isinstance(marker, _FloatType):
            return BorshFieldType(kind=get_marker_kind(marker))

        # Bytes marker
        if isinstance(marker, Bytes):
            if marker.length is not None:
                return BorshFieldType(kind="fixed_bytes", length=marker.length)
            return BorshFieldType(kind="dynamic_bytes")

        # Array marker
        if isinstance(marker, Array):
            element_borsh = BorshFieldType(kind=get_marker_kind(marker.element_type))
            return BorshFieldType(
                kind="fixed_array",
                element_type=element_borsh,
                length=marker.length,
            )

    # No marker in metadata, try full extraction (for non-Pydantic or nested types)
    return extract_borsh_type(annotation, field_name)


def is_zero_size(field_type: BorshFieldType) -> bool:
    """
    Whether every value of this type occupies zero bytes on the wire.

    Zero-size subtrees are empty (or literal-only) structs, zero-length
    fixed arrays/bytes, and tuples/arrays composed of those. They make a
    collection's u32 length prefix meaningless: a few input bytes can
    declare billions of elements that consume nothing, so vec/hashset
    element types and hashmap key types must not be zero-size (mirrors
    borsh-rs `check_zst`).
    """
    return _is_zero_size(field_type, frozenset())


def _is_zero_size(field_type: BorshFieldType, seen: frozenset[type]) -> bool:
    kind = field_type.kind
    if kind == "literal":
        return True  # literal fields are never written
    if kind == "fixed_bytes":
        return field_type.length == 0
    if kind == "fixed_array":
        if field_type.length == 0:
            return True
        return field_type.element_type is not None and _is_zero_size(field_type.element_type, seen)
    if kind == "tuple":
        return field_type.tuple_element_types is not None and all(
            _is_zero_size(t, seen) for t in field_type.tuple_element_types
        )
    if kind == "struct":
        cls = field_type.struct_class
        if cls is None or cls in seen:
            # Directly self-recursive structs cannot be instantiated anyway;
            # treat them as non-zero to keep this check total.
            return False
        nested = build_model_schema(cls)
        return all(_is_zero_size(ft, seen | {cls}) for ft in nested.values())
    # Everything else writes at least one byte: ints/floats/bool, the u32
    # prefix of string/bytes/vec/hashset/hashmap, and option/enum tags.
    return False
