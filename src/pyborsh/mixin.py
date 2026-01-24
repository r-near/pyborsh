"""Borsh mixin for Pydantic models."""

from typing import TYPE_CHECKING, Any, Self

from pyborsh.errors import BorshDeserializationError, BorshSerializationError
from pyborsh.reader import BorshReader
from pyborsh.schema import BorshFieldType, build_model_schema
from pyborsh.writer import BorshWriter

if TYPE_CHECKING:
    from pydantic import BaseModel


class Borsh:
    """
    Mixin that adds Borsh serialization to Pydantic models.

    Usage:
        from pydantic import BaseModel
        from pyborsh import Borsh, U8

        class Player(Borsh, BaseModel):
            name: str
            health: Annotated[int, U8]

        player = Player(name="Alice", health=100)
        data = player.to_borsh()
        player2 = Player.from_borsh(data)
    """

    def to_borsh(self: "BaseModel") -> bytes:  # type: ignore[misc]
        """
        Serialize this model to Borsh binary format.

        Returns:
            bytes: The Borsh-encoded binary data.

        Raises:
            BorshSerializationError: If serialization fails.
        """
        try:
            schema = build_model_schema(type(self))
            writer = BorshWriter()
            _serialize_struct(writer, self, schema)
            return writer.get_buffer()
        except ValueError as e:
            raise BorshSerializationError(str(e)) from e

    @classmethod
    def from_borsh(cls, data: bytes) -> Self:
        """
        Deserialize a model from Borsh binary format.

        Args:
            data: The Borsh-encoded binary data.

        Returns:
            An instance of the model.

        Raises:
            BorshDeserializationError: If deserialization fails.
        """
        schema = build_model_schema(cls)
        reader = BorshReader(data)
        field_values = _deserialize_struct(reader, cls, schema)
        return cls.model_validate(field_values)  # type: ignore[attr-defined, no-any-return]


def _serialize_struct(
    writer: BorshWriter, model: "BaseModel", schema: dict[str, BorshFieldType]
) -> None:
    """Serialize a Pydantic model as a Borsh struct."""
    for field_name, field_type in schema.items():
        value = getattr(model, field_name)
        _serialize_value(writer, value, field_type)


def _serialize_value(writer: BorshWriter, value: Any, field_type: BorshFieldType) -> None:
    """Serialize a single value according to its Borsh type."""
    kind = field_type.kind

    # Integer types
    if kind == "u8":
        writer.write_u8(value)
    elif kind == "u16":
        writer.write_u16(value)
    elif kind == "u32":
        writer.write_u32(value)
    elif kind == "u64":
        writer.write_u64(value)
    elif kind == "u128":
        writer.write_u128(value)
    elif kind == "i8":
        writer.write_i8(value)
    elif kind == "i16":
        writer.write_i16(value)
    elif kind == "i32":
        writer.write_i32(value)
    elif kind == "i64":
        writer.write_i64(value)
    elif kind == "i128":
        writer.write_i128(value)

    # Float types
    elif kind == "f32":
        writer.write_f32(value)
    elif kind == "f64":
        writer.write_f64(value)

    # Boolean
    elif kind == "bool":
        writer.write_bool(value)

    # String
    elif kind == "string":
        writer.write_string(value)

    # Bytes
    elif kind == "dynamic_bytes":
        writer.write_dynamic_bytes(value)
    elif kind == "fixed_bytes":
        if field_type.length is None:
            raise BorshSerializationError("Fixed bytes must have a length")
        writer.write_fixed_bytes(value, field_type.length)

    # Option<T>
    elif kind == "option":
        if value is None:
            writer.write_option_discriminant(False)
        else:
            writer.write_option_discriminant(True)
            if field_type.element_type is None:
                raise BorshSerializationError("Option type must have element_type")
            _serialize_value(writer, value, field_type.element_type)

    # Vec<T>
    elif kind == "vec":
        if field_type.element_type is None:
            raise BorshSerializationError("Vec type must have element_type")
        writer.write_u32(len(value))
        for item in value:
            _serialize_value(writer, item, field_type.element_type)

    # HashSet<T>
    elif kind == "hashset":
        if field_type.element_type is None:
            raise BorshSerializationError("HashSet type must have element_type")
        writer.write_u32(len(value))
        for item in value:
            _serialize_value(writer, item, field_type.element_type)

    # HashMap<K, V>
    elif kind == "hashmap":
        if field_type.key_type is None or field_type.value_type is None:
            raise BorshSerializationError("HashMap type must have key_type and value_type")
        writer.write_u32(len(value))
        for k, v in value.items():
            _serialize_value(writer, k, field_type.key_type)
            _serialize_value(writer, v, field_type.value_type)

    # Fixed array [T; N]
    elif kind == "fixed_array":
        if field_type.element_type is None or field_type.length is None:
            raise BorshSerializationError("Fixed array must have element_type and length")
        if len(value) != field_type.length:
            raise BorshSerializationError(
                f"Fixed array expected {field_type.length} elements, got {len(value)}"
            )
        for item in value:
            _serialize_value(writer, item, field_type.element_type)

    # Tuple
    elif kind == "tuple":
        if field_type.tuple_element_types is None:
            raise BorshSerializationError("Tuple type must have tuple_element_types")
        if len(value) != len(field_type.tuple_element_types):
            raise BorshSerializationError(
                f"Tuple expected {len(field_type.tuple_element_types)} elements, got {len(value)}"
            )
        for item, elem_type in zip(value, field_type.tuple_element_types, strict=True):
            _serialize_value(writer, item, elem_type)

    # Nested struct
    elif kind == "struct":
        if field_type.struct_class is None:
            raise BorshSerializationError("Struct type must have struct_class")
        nested_schema = build_model_schema(field_type.struct_class)
        _serialize_struct(writer, value, nested_schema)

    # IntEnum
    elif kind == "enum":
        if field_type.enum_class is None:
            raise BorshSerializationError("Enum type must have enum_class")
        writer.write_enum_discriminant(int(value))

    # Literal - skip serialization (used for discriminated unions)
    elif kind == "literal":
        pass  # Literals are not serialized

    # BorshEnum (tagged union)
    elif kind == "borsh_enum":
        if field_type.enum_class is None:
            raise BorshSerializationError("BorshEnum type must have enum_class")
        _serialize_borsh_enum(writer, value, field_type.enum_class)

    else:
        raise BorshSerializationError(f"Unsupported Borsh type: {kind}")


def _serialize_borsh_enum(writer: BorshWriter, value: Any, enum_class: type) -> None:
    """Serialize a BorshEnum variant."""
    from pydantic import BaseModel

    # Find which variant this value is
    value_type = type(value)
    variants = getattr(enum_class, "_variants", {})

    for _variant_name, (variant_index, variant_cls) in variants.items():
        if value_type is variant_cls:
            # Write variant discriminant
            writer.write_enum_discriminant(variant_index)
            # Serialize variant data (struct fields)
            if isinstance(value, BaseModel):
                variant_schema = build_model_schema(variant_cls)
                # Filter out the 'variant' discriminator field
                for field_name, field_type in variant_schema.items():
                    if field_name != "variant":
                        field_value = getattr(value, field_name)
                        _serialize_value(writer, field_value, field_type)
            return

    raise BorshSerializationError(f"Value {value} is not a valid variant of {enum_class.__name__}")


def _deserialize_struct(
    reader: BorshReader, model_class: type, schema: dict[str, BorshFieldType]
) -> dict[str, Any]:
    """Deserialize a Borsh struct into a dict of field values."""
    field_values: dict[str, Any] = {}
    for field_name, field_type in schema.items():
        value = _deserialize_value(reader, field_type)
        # Skip literal fields - they have defaults in the model
        if field_type.kind != "literal":
            field_values[field_name] = value
    return field_values


def _deserialize_value(reader: BorshReader, field_type: BorshFieldType) -> Any:
    """Deserialize a single value according to its Borsh type."""
    kind = field_type.kind

    # Integer types
    if kind == "u8":
        return reader.read_u8()
    if kind == "u16":
        return reader.read_u16()
    if kind == "u32":
        return reader.read_u32()
    if kind == "u64":
        return reader.read_u64()
    if kind == "u128":
        return reader.read_u128()
    if kind == "i8":
        return reader.read_i8()
    if kind == "i16":
        return reader.read_i16()
    if kind == "i32":
        return reader.read_i32()
    if kind == "i64":
        return reader.read_i64()
    if kind == "i128":
        return reader.read_i128()

    # Float types
    if kind == "f32":
        return reader.read_f32()
    if kind == "f64":
        return reader.read_f64()

    # Boolean
    if kind == "bool":
        return reader.read_bool()

    # String
    if kind == "string":
        return reader.read_string()

    # Bytes
    if kind == "dynamic_bytes":
        return reader.read_dynamic_bytes()
    if kind == "fixed_bytes":
        if field_type.length is None:
            raise BorshDeserializationError("Fixed bytes must have a length")
        return reader.read_bytes(field_type.length)

    # Option<T>
    if kind == "option":
        is_some = reader.read_option_discriminant()
        if not is_some:
            return None
        if field_type.element_type is None:
            raise BorshDeserializationError("Option type must have element_type")
        return _deserialize_value(reader, field_type.element_type)

    # Vec<T>
    if kind == "vec":
        if field_type.element_type is None:
            raise BorshDeserializationError("Vec type must have element_type")
        length = reader.read_u32()
        return [_deserialize_value(reader, field_type.element_type) for _ in range(length)]

    # HashSet<T>
    if kind == "hashset":
        if field_type.element_type is None:
            raise BorshDeserializationError("HashSet type must have element_type")
        length = reader.read_u32()
        return {_deserialize_value(reader, field_type.element_type) for _ in range(length)}

    # HashMap<K, V>
    if kind == "hashmap":
        if field_type.key_type is None or field_type.value_type is None:
            raise BorshDeserializationError("HashMap type must have key_type and value_type")
        length = reader.read_u32()
        result = {}
        for _ in range(length):
            k = _deserialize_value(reader, field_type.key_type)
            v = _deserialize_value(reader, field_type.value_type)
            result[k] = v
        return result

    # Fixed array [T; N]
    if kind == "fixed_array":
        if field_type.element_type is None or field_type.length is None:
            raise BorshDeserializationError("Fixed array must have element_type and length")
        return [
            _deserialize_value(reader, field_type.element_type) for _ in range(field_type.length)
        ]

    # Tuple
    if kind == "tuple":
        if field_type.tuple_element_types is None:
            raise BorshDeserializationError("Tuple type must have tuple_element_types")
        return tuple(
            _deserialize_value(reader, elem_type) for elem_type in field_type.tuple_element_types
        )

    # Nested struct
    if kind == "struct":
        if field_type.struct_class is None:
            raise BorshDeserializationError("Struct type must have struct_class")
        nested_schema = build_model_schema(field_type.struct_class)
        field_values = _deserialize_struct(reader, field_type.struct_class, nested_schema)
        return field_type.struct_class.model_validate(field_values)  # type: ignore[attr-defined]

    # IntEnum
    if kind == "enum":
        if field_type.enum_class is None:
            raise BorshDeserializationError("Enum type must have enum_class")
        variant_index = reader.read_enum_discriminant()
        return field_type.enum_class(variant_index)

    # Literal - not deserialized, return None (will be provided by Pydantic model default)
    if kind == "literal":
        return None  # Literal fields have defaults in model

    # BorshEnum (tagged union)
    if kind == "borsh_enum":
        if field_type.enum_class is None:
            raise BorshDeserializationError("BorshEnum type must have enum_class")
        return _deserialize_borsh_enum(reader, field_type.enum_class)

    raise BorshDeserializationError(f"Unsupported Borsh type: {kind}")


def _deserialize_borsh_enum(reader: BorshReader, enum_class: type) -> Any:
    """Deserialize a BorshEnum variant."""
    variant_index = reader.read_enum_discriminant()
    variants = getattr(enum_class, "_variants", {})

    for variant_name, (idx, variant_cls) in variants.items():
        if idx == variant_index:
            # Deserialize variant data
            variant_schema = build_model_schema(variant_cls)
            field_values: dict[str, Any] = {"variant": variant_name}
            for field_name, field_type in variant_schema.items():
                if field_name != "variant":
                    field_values[field_name] = _deserialize_value(reader, field_type)
            return variant_cls.model_validate(field_values)

    raise BorshDeserializationError(
        f"Invalid variant index {variant_index} for {enum_class.__name__}"
    )
