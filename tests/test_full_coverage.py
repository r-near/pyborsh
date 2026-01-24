"""
Tests for 100% code coverage.

These tests directly call internal functions with crafted BorshFieldType objects
to cover defensive error paths that can't be triggered through normal usage.
"""

from enum import IntEnum
from typing import Annotated, Literal

import pytest
from pydantic import BaseModel

from pyborsh import (
    F32,
    F64,
    I64,
    U8,
    U32,
    Array,
    Borsh,
    BorshDeserializationError,
    BorshEnum,
    BorshSchemaError,
    BorshSerializationError,
    Bytes,
)
from pyborsh.mixin import _deserialize_value, _serialize_value
from pyborsh.reader import BorshReader
from pyborsh.schema import BorshFieldType, extract_borsh_type, get_marker_kind
from pyborsh.writer import BorshWriter

# =============================================================================
# Tests for _serialize_value with malformed BorshFieldType objects
# =============================================================================


class TestSerializeValueDefensiveChecks:
    """Test defensive error checks in _serialize_value by injecting malformed types."""

    def test_fixed_bytes_missing_length(self):
        """Test fixed_bytes without length raises error."""
        writer = BorshWriter()
        field_type = BorshFieldType(kind="fixed_bytes", length=None)
        with pytest.raises(BorshSerializationError, match="Fixed bytes must have a length"):
            _serialize_value(writer, b"test", field_type)

    def test_option_missing_element_type(self):
        """Test option with Some value but no element_type raises error."""
        writer = BorshWriter()
        field_type = BorshFieldType(kind="option", element_type=None)
        with pytest.raises(BorshSerializationError, match="Option type must have element_type"):
            _serialize_value(writer, "some_value", field_type)

    def test_vec_missing_element_type(self):
        """Test vec without element_type raises error."""
        writer = BorshWriter()
        field_type = BorshFieldType(kind="vec", element_type=None)
        with pytest.raises(BorshSerializationError, match="Vec type must have element_type"):
            _serialize_value(writer, [1, 2, 3], field_type)

    def test_hashset_missing_element_type(self):
        """Test hashset without element_type raises error."""
        writer = BorshWriter()
        field_type = BorshFieldType(kind="hashset", element_type=None)
        with pytest.raises(BorshSerializationError, match="HashSet type must have element_type"):
            _serialize_value(writer, {1, 2, 3}, field_type)

    def test_hashmap_missing_key_type(self):
        """Test hashmap without key_type raises error."""
        writer = BorshWriter()
        field_type = BorshFieldType(
            kind="hashmap", key_type=None, value_type=BorshFieldType(kind="u8")
        )
        with pytest.raises(
            BorshSerializationError, match="HashMap type must have key_type and value_type"
        ):
            _serialize_value(writer, {"a": 1}, field_type)

    def test_hashmap_missing_value_type(self):
        """Test hashmap without value_type raises error."""
        writer = BorshWriter()
        field_type = BorshFieldType(
            kind="hashmap", key_type=BorshFieldType(kind="string"), value_type=None
        )
        with pytest.raises(
            BorshSerializationError, match="HashMap type must have key_type and value_type"
        ):
            _serialize_value(writer, {"a": 1}, field_type)

    def test_fixed_array_missing_element_type(self):
        """Test fixed_array without element_type raises error."""
        writer = BorshWriter()
        field_type = BorshFieldType(kind="fixed_array", element_type=None, length=3)
        with pytest.raises(
            BorshSerializationError, match="Fixed array must have element_type and length"
        ):
            _serialize_value(writer, [1, 2, 3], field_type)

    def test_fixed_array_missing_length(self):
        """Test fixed_array without length raises error."""
        writer = BorshWriter()
        field_type = BorshFieldType(
            kind="fixed_array", element_type=BorshFieldType(kind="u8"), length=None
        )
        with pytest.raises(
            BorshSerializationError, match="Fixed array must have element_type and length"
        ):
            _serialize_value(writer, [1, 2, 3], field_type)

    def test_tuple_missing_element_types(self):
        """Test tuple without tuple_element_types raises error."""
        writer = BorshWriter()
        field_type = BorshFieldType(kind="tuple", tuple_element_types=None)
        with pytest.raises(
            BorshSerializationError, match="Tuple type must have tuple_element_types"
        ):
            _serialize_value(writer, (1, 2), field_type)

    def test_struct_missing_struct_class(self):
        """Test struct without struct_class raises error."""
        writer = BorshWriter()
        field_type = BorshFieldType(kind="struct", struct_class=None)
        with pytest.raises(BorshSerializationError, match="Struct type must have struct_class"):
            _serialize_value(writer, object(), field_type)

    def test_enum_missing_enum_class(self):
        """Test enum without enum_class raises error."""
        writer = BorshWriter()
        field_type = BorshFieldType(kind="enum", enum_class=None)
        with pytest.raises(BorshSerializationError, match="Enum type must have enum_class"):
            _serialize_value(writer, 0, field_type)

    def test_borsh_enum_missing_enum_class(self):
        """Test borsh_enum without enum_class raises error."""
        writer = BorshWriter()
        field_type = BorshFieldType(kind="borsh_enum", enum_class=None)
        with pytest.raises(BorshSerializationError, match="BorshEnum type must have enum_class"):
            _serialize_value(writer, object(), field_type)

    def test_unsupported_kind(self):
        """Test unsupported kind raises error."""
        writer = BorshWriter()
        field_type = BorshFieldType(kind="unknown_type")
        with pytest.raises(BorshSerializationError, match="Unsupported Borsh type: unknown_type"):
            _serialize_value(writer, None, field_type)


# =============================================================================
# Tests for _deserialize_value with malformed BorshFieldType objects
# =============================================================================


class TestDeserializeValueDefensiveChecks:
    """Test defensive error checks in _deserialize_value by injecting malformed types."""

    def test_fixed_bytes_missing_length(self):
        """Test fixed_bytes without length raises error."""
        reader = BorshReader(b"\x00\x00\x00\x00")
        field_type = BorshFieldType(kind="fixed_bytes", length=None)
        with pytest.raises(BorshDeserializationError, match="Fixed bytes must have a length"):
            _deserialize_value(reader, field_type)

    def test_option_missing_element_type(self):
        """Test option Some without element_type raises error."""
        reader = BorshReader(b"\x01\x00")  # Some discriminant + data
        field_type = BorshFieldType(kind="option", element_type=None)
        with pytest.raises(BorshDeserializationError, match="Option type must have element_type"):
            _deserialize_value(reader, field_type)

    def test_vec_missing_element_type(self):
        """Test vec without element_type raises error."""
        reader = BorshReader(b"\x01\x00\x00\x00")  # length=1
        field_type = BorshFieldType(kind="vec", element_type=None)
        with pytest.raises(BorshDeserializationError, match="Vec type must have element_type"):
            _deserialize_value(reader, field_type)

    def test_hashset_missing_element_type(self):
        """Test hashset without element_type raises error."""
        reader = BorshReader(b"\x01\x00\x00\x00")  # length=1
        field_type = BorshFieldType(kind="hashset", element_type=None)
        with pytest.raises(BorshDeserializationError, match="HashSet type must have element_type"):
            _deserialize_value(reader, field_type)

    def test_hashmap_missing_key_type(self):
        """Test hashmap without key_type raises error."""
        reader = BorshReader(b"\x01\x00\x00\x00")  # length=1
        field_type = BorshFieldType(
            kind="hashmap", key_type=None, value_type=BorshFieldType(kind="u8")
        )
        with pytest.raises(
            BorshDeserializationError, match="HashMap type must have key_type and value_type"
        ):
            _deserialize_value(reader, field_type)

    def test_hashmap_missing_value_type(self):
        """Test hashmap without value_type raises error."""
        reader = BorshReader(b"\x01\x00\x00\x00")  # length=1
        field_type = BorshFieldType(
            kind="hashmap", key_type=BorshFieldType(kind="string"), value_type=None
        )
        with pytest.raises(
            BorshDeserializationError, match="HashMap type must have key_type and value_type"
        ):
            _deserialize_value(reader, field_type)

    def test_fixed_array_missing_element_type(self):
        """Test fixed_array without element_type raises error."""
        reader = BorshReader(b"\x00\x00\x00\x00")
        field_type = BorshFieldType(kind="fixed_array", element_type=None, length=1)
        with pytest.raises(
            BorshDeserializationError, match="Fixed array must have element_type and length"
        ):
            _deserialize_value(reader, field_type)

    def test_fixed_array_missing_length(self):
        """Test fixed_array without length raises error."""
        reader = BorshReader(b"\x00\x00\x00\x00")
        field_type = BorshFieldType(
            kind="fixed_array", element_type=BorshFieldType(kind="u8"), length=None
        )
        with pytest.raises(
            BorshDeserializationError, match="Fixed array must have element_type and length"
        ):
            _deserialize_value(reader, field_type)

    def test_tuple_missing_element_types(self):
        """Test tuple without tuple_element_types raises error."""
        reader = BorshReader(b"\x00\x00\x00\x00")
        field_type = BorshFieldType(kind="tuple", tuple_element_types=None)
        with pytest.raises(
            BorshDeserializationError, match="Tuple type must have tuple_element_types"
        ):
            _deserialize_value(reader, field_type)

    def test_struct_missing_struct_class(self):
        """Test struct without struct_class raises error."""
        reader = BorshReader(b"\x00\x00\x00\x00")
        field_type = BorshFieldType(kind="struct", struct_class=None)
        with pytest.raises(BorshDeserializationError, match="Struct type must have struct_class"):
            _deserialize_value(reader, field_type)

    def test_enum_missing_enum_class(self):
        """Test enum without enum_class raises error."""
        reader = BorshReader(b"\x00")
        field_type = BorshFieldType(kind="enum", enum_class=None)
        with pytest.raises(BorshDeserializationError, match="Enum type must have enum_class"):
            _deserialize_value(reader, field_type)

    def test_borsh_enum_missing_enum_class(self):
        """Test borsh_enum without enum_class raises error."""
        reader = BorshReader(b"\x00")
        field_type = BorshFieldType(kind="borsh_enum", enum_class=None)
        with pytest.raises(BorshDeserializationError, match="BorshEnum type must have enum_class"):
            _deserialize_value(reader, field_type)

    def test_unsupported_kind(self):
        """Test unsupported kind raises error."""
        reader = BorshReader(b"\x00")
        field_type = BorshFieldType(kind="unknown_type")
        with pytest.raises(BorshDeserializationError, match="Unsupported Borsh type: unknown_type"):
            _deserialize_value(reader, field_type)


# =============================================================================
# Tests for schema.py extract_borsh_type edge cases
# =============================================================================


class TestExtractBorshTypeEdgeCases:
    """Test extract_borsh_type for all code paths."""

    def test_annotated_integer_instance(self):
        """Test Annotated with integer marker instance."""
        result = extract_borsh_type(Annotated[int, U8()], "field")
        assert result.kind == "u8"

    def test_annotated_integer_class(self):
        """Test Annotated with integer marker class."""
        result = extract_borsh_type(Annotated[int, U8], "field")
        assert result.kind == "u8"

    def test_annotated_float_instance(self):
        """Test Annotated with float marker instance."""
        result = extract_borsh_type(Annotated[float, F32()], "field")
        assert result.kind == "f32"

    def test_annotated_float_class(self):
        """Test Annotated with float marker class."""
        result = extract_borsh_type(Annotated[float, F64], "field")
        assert result.kind == "f64"

    def test_annotated_bytes_fixed(self):
        """Test Annotated with fixed Bytes marker."""
        result = extract_borsh_type(Annotated[bytes, Bytes(32)], "field")
        assert result.kind == "fixed_bytes"
        assert result.length == 32

    def test_annotated_bytes_dynamic(self):
        """Test Annotated with dynamic Bytes marker."""
        result = extract_borsh_type(Annotated[bytes, Bytes()], "field")
        assert result.kind == "dynamic_bytes"

    def test_annotated_array(self):
        """Test Annotated with Array marker."""
        result = extract_borsh_type(Annotated[list[int], Array(U32, 5)], "field")
        assert result.kind == "fixed_array"
        assert result.length == 5

    def test_infer_list(self):
        """Test inference of list type."""
        result = extract_borsh_type(list[str], "field")
        assert result.kind == "vec"

    def test_infer_set(self):
        """Test inference of set type."""
        result = extract_borsh_type(set[str], "field")
        assert result.kind == "hashset"

    def test_infer_dict(self):
        """Test inference of dict type."""
        result = extract_borsh_type(dict[str, Annotated[int, U32]], "field")
        assert result.kind == "hashmap"

    def test_infer_tuple(self):
        """Test inference of tuple type."""
        result = extract_borsh_type(tuple[str, Annotated[int, U8]], "field")
        assert result.kind == "tuple"
        assert result.length == 2

    def test_infer_nested_model(self):
        """Test inference of nested Pydantic model."""

        class Inner(Borsh, BaseModel):
            value: Annotated[int, U8]

        result = extract_borsh_type(Inner, "field")
        assert result.kind == "struct"
        assert result.struct_class is Inner

    def test_infer_int_enum(self):
        """Test inference of IntEnum."""

        class Status(IntEnum):
            A = 0
            B = 1

        result = extract_borsh_type(Status, "field")
        assert result.kind == "enum"
        assert result.enum_class is Status


# =============================================================================
# Tests for enum.py branch coverage
# =============================================================================


class TestBorshEnumBranchCoverage:
    """Test BorshEnum for branch coverage."""

    def test_enum_with_no_nested_classes(self):
        """Test BorshEnum with no variant classes."""

        class EmptyEnum(BorshEnum):
            some_value = 42  # Not a class, won't be registered

        assert EmptyEnum._variants == {}

    def test_enum_skips_private_attributes(self):
        """Test that private attributes are skipped."""

        class MyEnum(BorshEnum):
            _private = "ignored"

            class Public(Borsh, BaseModel):
                variant: Literal["Public"] = "Public"

        assert "_private" not in MyEnum._variants
        assert "Public" in MyEnum._variants


# =============================================================================
# Tests for writer.py overflow errors
# =============================================================================


class TestWriterOverflowErrors:
    """Test overflow error paths in writer."""

    def test_u8_negative(self):
        writer = BorshWriter()
        with pytest.raises(ValueError, match="out of range for u8"):
            writer.write_u8(-1)

    def test_u16_overflow(self):
        writer = BorshWriter()
        with pytest.raises(ValueError, match="out of range for u16"):
            writer.write_u16(0x10000)

    def test_u32_overflow(self):
        writer = BorshWriter()
        with pytest.raises(ValueError, match="out of range for u32"):
            writer.write_u32(0x100000000)

    def test_u64_overflow(self):
        writer = BorshWriter()
        with pytest.raises(ValueError, match="out of range for u64"):
            writer.write_u64(0x10000000000000000)

    def test_u128_overflow(self):
        writer = BorshWriter()
        with pytest.raises(ValueError, match="out of range for u128"):
            writer.write_u128(1 << 128)

    def test_i8_overflow(self):
        writer = BorshWriter()
        with pytest.raises(ValueError, match="out of range for i8"):
            writer.write_i8(128)

    def test_i8_underflow(self):
        writer = BorshWriter()
        with pytest.raises(ValueError, match="out of range for i8"):
            writer.write_i8(-129)

    def test_i16_overflow(self):
        writer = BorshWriter()
        with pytest.raises(ValueError, match="out of range for i16"):
            writer.write_i16(32768)

    def test_i32_overflow(self):
        writer = BorshWriter()
        with pytest.raises(ValueError, match="out of range for i32"):
            writer.write_i32(2**31)

    def test_i64_overflow(self):
        writer = BorshWriter()
        with pytest.raises(ValueError, match="out of range for i64"):
            writer.write_i64(2**63)

    def test_i128_overflow(self):
        writer = BorshWriter()
        with pytest.raises(ValueError, match="out of range for i128"):
            writer.write_i128(2**127)

    def test_write_raw_bytes(self):
        """Test write_bytes for raw bytes (no length prefix)."""
        writer = BorshWriter()
        writer.write_bytes(b"\x01\x02\x03")
        assert writer.get_buffer() == bytes([1, 2, 3])


# =============================================================================
# Tests for reader.py error paths
# =============================================================================


class TestReaderErrors:
    """Test reader error paths."""

    def test_unexpected_end_of_data(self):
        reader = BorshReader(b"")
        with pytest.raises(BorshDeserializationError, match="Unexpected end of data"):
            reader.read_u32()

    def test_invalid_bool(self):
        reader = BorshReader(bytes([0x02]))
        with pytest.raises(BorshDeserializationError, match="Invalid boolean value"):
            reader.read_bool()

    def test_invalid_utf8(self):
        reader = BorshReader(bytes([2, 0, 0, 0, 0xFF, 0xFE]))
        with pytest.raises(BorshDeserializationError, match="Invalid UTF-8"):
            reader.read_string()

    def test_invalid_option_discriminant(self):
        reader = BorshReader(bytes([0x02]))
        with pytest.raises(BorshDeserializationError, match="Invalid Option discriminant"):
            reader.read_option_discriminant()


# =============================================================================
# Tests for types.py repr methods
# =============================================================================


class TestTypeReprs:
    """Test __repr__ methods of type markers."""

    def test_integer_repr(self):
        assert repr(U8()) == "U8"
        assert repr(I64()) == "I64"

    def test_float_repr(self):
        assert repr(F32()) == "F32"
        assert repr(F64()) == "F64"

    def test_bytes_repr(self):
        assert repr(Bytes()) == "Bytes()"
        assert repr(Bytes(32)) == "Bytes(32)"

    def test_array_repr(self):
        assert repr(Array(U8, 4)) == "Array(U8, 4)"


# =============================================================================
# Tests for schema.py error paths
# =============================================================================


class TestSchemaErrors:
    """Test schema error paths."""

    def test_bare_int_error(self):
        with pytest.raises(BorshSchemaError, match="requires explicit width"):

            class BadModel(Borsh, BaseModel):
                value: int

            BadModel(value=1).to_borsh()

    def test_unknown_marker_kind(self):
        class UnknownMarker:
            pass

        with pytest.raises(BorshSchemaError, match="Unknown marker type"):
            get_marker_kind(UnknownMarker)

    def test_non_basemodel_error(self):
        from pyborsh.schema import build_model_schema

        with pytest.raises(BorshSchemaError, match="is not a Pydantic BaseModel"):
            build_model_schema(str)  # type: ignore

    def test_non_optional_union_error(self):
        """Non-optional union that isn't a BorshEnum."""
        with pytest.raises(BorshSchemaError, match="Union type that is not Optional"):

            class BadModel(Borsh, BaseModel):
                value: str | int

            BadModel(value="test").to_borsh()

    def test_field_without_annotation(self):
        """Test that field without annotation raises error."""
        from pyborsh.schema import build_model_schema

        class BadModel(BaseModel):
            pass

        # Manually add a field without annotation
        BadModel.model_fields["bad_field"] = type(
            "MockFieldInfo", (), {"annotation": None, "metadata": []}
        )()

        with pytest.raises(BorshSchemaError, match="has no type annotation"):
            build_model_schema(BadModel)


# =============================================================================
# Tests for BorshEnum serialization error paths
# =============================================================================


class TestBorshEnumErrors:
    """Test BorshEnum error paths."""

    def test_invalid_variant_value(self):
        """Test serializing a value that's not a registered variant."""
        from pyborsh.mixin import _serialize_borsh_enum

        class MyEnum(BorshEnum):
            class A(Borsh, BaseModel):
                variant: Literal["A"] = "A"

        class NotAVariant(BaseModel):
            pass

        writer = BorshWriter()
        with pytest.raises(BorshSerializationError, match="not a valid variant"):
            _serialize_borsh_enum(writer, NotAVariant(), MyEnum)

    def test_invalid_variant_index_deserialize(self):
        """Test deserializing with invalid variant index."""

        class Action(BorshEnum):
            class Add(Borsh, BaseModel):
                variant: Literal["Add"] = "Add"

            class Remove(Borsh, BaseModel):
                variant: Literal["Remove"] = "Remove"

        class Command(Borsh, BaseModel):
            action: Action.Add | Action.Remove

        # Variant index 99 doesn't exist
        data = bytes([99])
        with pytest.raises(BorshDeserializationError, match="Invalid variant index"):
            Command.from_borsh(data)


# =============================================================================
# Tests for remaining edge cases
# =============================================================================


class TestTupleLengthMismatch:
    """Test tuple length mismatch error via public API."""

    def test_tuple_wrong_length_serialization(self):
        """Test that tuple with wrong length raises error during serialization."""

        # We need to trick the system by modifying the value after model creation
        class Model(Borsh, BaseModel):
            data: tuple[Annotated[int, U8], Annotated[int, U8]]

            class Config:
                arbitrary_types_allowed = True

        m = Model(data=(1, 2))
        # Now modify the internal data to have wrong length
        object.__setattr__(m, "data", (1, 2, 3))

        with pytest.raises(BorshSerializationError, match="Tuple expected 2 elements, got 3"):
            m.to_borsh()


class TestSchemaInferenceErrors:
    """Test schema inference error paths through extract_borsh_type."""

    def test_list_without_element_type(self):
        """Test list without element type raises descriptive error."""
        from typing import List

        with pytest.raises(BorshSchemaError, match="without element type"):
            extract_borsh_type(List, "field")  # type: ignore[type-arg]

    def test_set_without_element_type(self):
        """Test set without element type raises descriptive error."""
        from typing import Set

        with pytest.raises(BorshSchemaError, match="without element type"):
            extract_borsh_type(Set, "field")  # type: ignore[type-arg]

    def test_dict_without_types(self):
        """Test dict without key/value types raises descriptive error."""
        from typing import Dict

        with pytest.raises(BorshSchemaError, match="without key/value types"):
            extract_borsh_type(Dict, "field")  # type: ignore[type-arg]

    def test_tuple_without_element_types(self):
        """Test tuple without element types raises descriptive error."""
        from typing import Tuple

        with pytest.raises(BorshSchemaError, match="without element types"):
            extract_borsh_type(Tuple, "field")  # type: ignore[type-arg]


class TestBranchCoverageEdgeCases:
    """Tests for remaining branch coverage edge cases."""

    def test_union_with_non_type_args(self):
        """Test union where some args aren't types (covers 219->218 branch).

        When checking if a Union is a BorshEnum, we iterate through args and check
        isinstance(arg, type). If an arg is NOT a type (like a Literal), we
        skip it and continue the loop - this is the 219->218 branch.
        """
        from typing import Literal, get_args

        # Literal types are NOT types - they're special forms
        # Union[str, Literal["a"]] has args where Literal["a"] is not isinstance(..., type)
        union_type = str | Literal["a"]

        # Verify our assumption - Literal["a"] should not be a type
        args = get_args(union_type)
        non_none = [a for a in args if a is not type(None)]
        assert any(not isinstance(a, type) for a in non_none), "Need at least one non-type arg"

        # This should raise because it's not a valid Optional or BorshEnum
        with pytest.raises(BorshSchemaError, match="Union type that is not Optional"):
            extract_borsh_type(union_type, "field")

    def test_annotated_with_multiple_non_borsh_markers(self):
        """Test Annotated with multiple non-Borsh markers to cover the loop continuation."""
        from typing import Annotated

        class Marker1:
            pass

        class Marker2:
            pass

        # This should continue past Marker1 and Marker2, then infer from str
        result = extract_borsh_type(Annotated[str, Marker1(), Marker2()], "field")
        assert result.kind == "string"

    def test_metadata_loop_with_non_matching_markers(self):
        """Test extract_borsh_type_with_metadata iterates through non-matching markers (318->298).

        When metadata contains markers that don't match any Borsh type, the loop
        continues to the next marker. This tests that branch.
        """
        from pyborsh.schema import extract_borsh_type_with_metadata

        class NotABorshMarker:
            pass

        class AnotherNonMarker:
            pass

        # Pass multiple non-Borsh markers - loop should iterate through all,
        # then fall through to extract_borsh_type for the base annotation
        result = extract_borsh_type_with_metadata(
            str, [NotABorshMarker(), AnotherNonMarker()], "field"
        )
        assert result.kind == "string"

    def test_extract_borsh_type_with_metadata_array(self):
        """Test extract_borsh_type_with_metadata with Array marker."""
        from pyborsh.schema import extract_borsh_type_with_metadata

        # Test that Array in metadata is handled
        result = extract_borsh_type_with_metadata(list, [Array(U8, 4)], "field")
        assert result.kind == "fixed_array"
        assert result.length == 4

    def test_extract_borsh_type_with_metadata_integer_instance(self):
        """Test extract_borsh_type_with_metadata with integer instance marker (line 303)."""
        from pyborsh.schema import extract_borsh_type_with_metadata

        # Test with U32() instance (not the class)
        result = extract_borsh_type_with_metadata(int, [U32()], "field")
        assert result.kind == "u32"

    def test_extract_borsh_type_with_metadata_float_instance(self):
        """Test extract_borsh_type_with_metadata with float instance marker (line 309)."""
        from pyborsh.schema import extract_borsh_type_with_metadata

        # Test with F32() instance (not the class)
        result = extract_borsh_type_with_metadata(float, [F32()], "field")
        assert result.kind == "f32"

    def test_borsh_enum_non_basemodel_variant(self):
        """Test BorshEnum with a variant that is NOT a BaseModel (unit variant)."""
        from pyborsh.mixin import _serialize_borsh_enum

        class UnitEnum(BorshEnum):
            class Unit:  # Not a BaseModel - a pure unit variant
                pass

        writer = BorshWriter()
        # Create instance and serialize
        unit = UnitEnum.Unit()
        _serialize_borsh_enum(writer, unit, UnitEnum)

        # Should just write the discriminant (0) and nothing else
        assert writer.get_buffer() == bytes([0])
