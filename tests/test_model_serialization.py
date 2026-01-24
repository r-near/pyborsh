"""Tests for model-level serialization with the Borsh mixin."""

from enum import IntEnum
from typing import Annotated

import pytest
from pydantic import BaseModel

from pyborsh import (
    F32,
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
    Borsh,
    BorshSchemaError,
    BorshSerializationError,
    Bytes,
)


class TestPrimitiveModels:
    """Test models with primitive types."""

    def test_u8_field(self):
        class Model(Borsh, BaseModel):
            value: Annotated[int, U8]

        m = Model(value=42)
        data = m.to_borsh()
        assert data == bytes([42])
        assert Model.from_borsh(data) == m

    def test_u16_field(self):
        class Model(Borsh, BaseModel):
            value: Annotated[int, U16]

        m = Model(value=0x1234)
        data = m.to_borsh()
        assert data == bytes([0x34, 0x12])  # Little-endian
        assert Model.from_borsh(data) == m

    def test_u32_field(self):
        class Model(Borsh, BaseModel):
            value: Annotated[int, U32]

        m = Model(value=0x12345678)
        data = m.to_borsh()
        assert data == bytes([0x78, 0x56, 0x34, 0x12])
        assert Model.from_borsh(data) == m

    def test_u64_field(self):
        class Model(Borsh, BaseModel):
            value: Annotated[int, U64]

        m = Model(value=0x123456789ABCDEF0)
        data = m.to_borsh()
        assert Model.from_borsh(data) == m

    def test_u128_field(self):
        class Model(Borsh, BaseModel):
            value: Annotated[int, U128]

        m = Model(value=(1 << 100) + 12345)
        data = m.to_borsh()
        assert len(data) == 16
        assert Model.from_borsh(data) == m

    def test_signed_integers(self):
        class Model(Borsh, BaseModel):
            i8_val: Annotated[int, I8]
            i16_val: Annotated[int, I16]
            i32_val: Annotated[int, I32]
            i64_val: Annotated[int, I64]

        m = Model(i8_val=-100, i16_val=-1000, i32_val=-100000, i64_val=-10000000000)
        data = m.to_borsh()
        assert Model.from_borsh(data) == m

    def test_i128_field(self):
        class Model(Borsh, BaseModel):
            value: Annotated[int, I128]

        m = Model(value=-(1 << 100))
        data = m.to_borsh()
        assert Model.from_borsh(data) == m

    def test_float_fields(self):
        class Model(Borsh, BaseModel):
            f32_val: Annotated[float, F32]
            f64_val: float  # Defaults to f64

        m = Model(f32_val=3.14, f64_val=2.71828)
        data = m.to_borsh()
        m2 = Model.from_borsh(data)
        # Float comparison with tolerance due to f32 precision
        assert abs(m2.f32_val - m.f32_val) < 0.0001
        assert m2.f64_val == m.f64_val

    def test_bool_field(self):
        class Model(Borsh, BaseModel):
            flag: bool

        m_true = Model(flag=True)
        m_false = Model(flag=False)

        assert m_true.to_borsh() == bytes([0x01])
        assert m_false.to_borsh() == bytes([0x00])
        assert Model.from_borsh(bytes([0x01])) == m_true
        assert Model.from_borsh(bytes([0x00])) == m_false

    def test_string_field(self):
        class Model(Borsh, BaseModel):
            name: str

        m = Model(name="hello")
        data = m.to_borsh()
        # 4 bytes length (5) + 5 bytes content
        assert data == bytes([5, 0, 0, 0, 104, 101, 108, 108, 111])
        assert Model.from_borsh(data) == m

    def test_string_unicode(self):
        class Model(Borsh, BaseModel):
            name: str

        m = Model(name="héllo 🌍")
        data = m.to_borsh()
        assert Model.from_borsh(data) == m


class TestBytesModels:
    """Test models with bytes fields."""

    def test_dynamic_bytes(self):
        class Model(Borsh, BaseModel):
            data: bytes

        m = Model(data=b"\x01\x02\x03")
        serialized = m.to_borsh()
        # 4 bytes length + 3 bytes data
        assert serialized == bytes([3, 0, 0, 0, 1, 2, 3])
        assert Model.from_borsh(serialized) == m

    def test_dynamic_bytes_annotated(self):
        class Model(Borsh, BaseModel):
            data: Annotated[bytes, Bytes()]

        m = Model(data=b"\x01\x02\x03")
        serialized = m.to_borsh()
        assert Model.from_borsh(serialized) == m

    def test_fixed_bytes(self):
        class Model(Borsh, BaseModel):
            pubkey: Annotated[bytes, Bytes(32)]

        m = Model(pubkey=bytes(range(32)))
        serialized = m.to_borsh()
        # No length prefix, just 32 bytes
        assert len(serialized) == 32
        assert serialized == bytes(range(32))
        assert Model.from_borsh(serialized) == m

    def test_fixed_bytes_wrong_length(self):
        class Model(Borsh, BaseModel):
            pubkey: Annotated[bytes, Bytes(32)]

        m = Model(pubkey=bytes(16))  # Too short
        with pytest.raises(BorshSerializationError):
            m.to_borsh()


class TestOptionModels:
    """Test models with Option<T> fields."""

    def test_option_none(self):
        class Model(Borsh, BaseModel):
            value: Annotated[int, U32] | None

        m = Model(value=None)
        data = m.to_borsh()
        assert data == bytes([0x00])  # None discriminant
        assert Model.from_borsh(data) == m

    def test_option_some(self):
        class Model(Borsh, BaseModel):
            value: Annotated[int, U32] | None

        m = Model(value=42)
        data = m.to_borsh()
        # 0x01 (Some) + 4 bytes u32
        assert data == bytes([0x01, 42, 0, 0, 0])
        assert Model.from_borsh(data) == m

    def test_option_string(self):
        class Model(Borsh, BaseModel):
            name: str | None

        m_some = Model(name="Alice")
        m_none = Model(name=None)

        assert Model.from_borsh(m_some.to_borsh()) == m_some
        assert Model.from_borsh(m_none.to_borsh()) == m_none


class TestCollectionModels:
    """Test models with collection fields."""

    def test_vec_u16(self):
        class Model(Borsh, BaseModel):
            values: list[Annotated[int, U16]]

        m = Model(values=[1, 2, 3])
        data = m.to_borsh()
        # 4 bytes length (3) + 3 * 2 bytes
        assert len(data) == 4 + 6
        assert Model.from_borsh(data) == m

    def test_vec_string(self):
        class Model(Borsh, BaseModel):
            tags: list[str]

        m = Model(tags=["foo", "bar", "baz"])
        data = m.to_borsh()
        assert Model.from_borsh(data) == m

    def test_empty_vec(self):
        class Model(Borsh, BaseModel):
            values: list[Annotated[int, U32]]

        m = Model(values=[])
        data = m.to_borsh()
        assert data == bytes([0, 0, 0, 0])  # Just length 0
        assert Model.from_borsh(data) == m

    def test_hashset_string(self):
        class Model(Borsh, BaseModel):
            unique_tags: set[str]

        m = Model(unique_tags={"foo", "bar"})
        data = m.to_borsh()
        m2 = Model.from_borsh(data)
        assert m2.unique_tags == m.unique_tags

    def test_hashmap_string_u32(self):
        class Model(Borsh, BaseModel):
            counts: dict[str, Annotated[int, U32]]

        m = Model(counts={"a": 1, "b": 2})
        data = m.to_borsh()
        m2 = Model.from_borsh(data)
        assert m2.counts == m.counts


class TestTupleModels:
    """Test models with tuple fields."""

    def test_tuple_homogeneous(self):
        class Model(Borsh, BaseModel):
            coords: tuple[Annotated[int, I32], Annotated[int, I32]]

        m = Model(coords=(10, 20))
        data = m.to_borsh()
        # 2 * 4 bytes, no length prefix
        assert len(data) == 8
        assert Model.from_borsh(data) == m

    def test_tuple_heterogeneous(self):
        class Model(Borsh, BaseModel):
            data: tuple[Annotated[int, U8], str, bool]

        m = Model(data=(42, "hi", True))
        data = m.to_borsh()
        assert Model.from_borsh(data) == m


class TestFixedArrayModels:
    """Test models with fixed-size array fields."""

    def test_fixed_array(self):
        class Model(Borsh, BaseModel):
            rgba: Annotated[list[int], Array(U8, 4)]

        m = Model(rgba=[255, 128, 64, 255])
        data = m.to_borsh()
        # 4 bytes, no length prefix
        assert data == bytes([255, 128, 64, 255])
        assert Model.from_borsh(data) == m

    def test_fixed_array_wrong_length(self):
        class Model(Borsh, BaseModel):
            rgba: Annotated[list[int], Array(U8, 4)]

        m = Model(rgba=[1, 2, 3])  # Too short
        with pytest.raises(BorshSerializationError):
            m.to_borsh()


class TestNestedModels:
    """Test nested struct serialization."""

    def test_nested_struct(self):
        class Address(Borsh, BaseModel):
            street: str
            zip_code: Annotated[int, U32]

        class Person(Borsh, BaseModel):
            name: str
            address: Address

        addr = Address(street="123 Main St", zip_code=12345)
        person = Person(name="Alice", address=addr)

        data = person.to_borsh()
        person2 = Person.from_borsh(data)
        assert person2 == person
        assert person2.address.street == "123 Main St"
        assert person2.address.zip_code == 12345

    def test_optional_nested_struct(self):
        class Address(Borsh, BaseModel):
            city: str

        class Person(Borsh, BaseModel):
            name: str
            address: Address | None

        p_with = Person(name="Alice", address=Address(city="NYC"))
        p_without = Person(name="Bob", address=None)

        assert Person.from_borsh(p_with.to_borsh()) == p_with
        assert Person.from_borsh(p_without.to_borsh()) == p_without

    def test_vec_of_structs(self):
        class Item(Borsh, BaseModel):
            id: Annotated[int, U32]
            name: str

        class Inventory(Borsh, BaseModel):
            items: list[Item]

        inv = Inventory(
            items=[
                Item(id=1, name="Sword"),
                Item(id=2, name="Shield"),
            ]
        )
        data = inv.to_borsh()
        inv2 = Inventory.from_borsh(data)
        assert len(inv2.items) == 2
        assert inv2.items[0].name == "Sword"
        assert inv2.items[1].id == 2


class TestIntEnumModels:
    """Test models with IntEnum fields."""

    def test_int_enum(self):
        class Status(IntEnum):
            Pending = 0
            Active = 1
            Completed = 2

        class Task(Borsh, BaseModel):
            id: Annotated[int, U32]
            status: Status

        task = Task(id=123, status=Status.Active)
        data = task.to_borsh()
        # 4 bytes id + 1 byte enum
        assert len(data) == 5
        task2 = Task.from_borsh(data)
        assert task2 == task
        assert task2.status == Status.Active


class TestSchemaErrors:
    """Test schema validation errors."""

    def test_bare_int_error(self):
        with pytest.raises(BorshSchemaError, match="requires explicit width"):

            class BadModel(Borsh, BaseModel):
                age: int

            BadModel(age=25).to_borsh()

    def test_bare_list_error(self):
        with pytest.raises(BorshSchemaError, match="unsupported type"):

            class BadModel(Borsh, BaseModel):
                items: list  # type: ignore

            BadModel(items=[]).to_borsh()


class TestMultipleFields:
    """Test models with multiple fields of different types."""

    def test_complex_model(self):
        class Player(Borsh, BaseModel):
            name: str
            health: Annotated[int, U8]
            balance: Annotated[int, U128]
            scores: list[Annotated[int, U16]]
            guild: str | None
            active: bool

        player = Player(
            name="Alice",
            health=100,
            balance=1_000_000_000,
            scores=[100, 95, 98],
            guild="Warriors",
            active=True,
        )

        data = player.to_borsh()
        player2 = Player.from_borsh(data)
        assert player2 == player

    def test_rust_compatibility(self):
        """Test against known Rust borsh output."""

        class TestStruct(Borsh, BaseModel):
            name: str
            value: Annotated[int, U32]

        # Known output from Rust: TestStruct { name: "hello", value: 42 }
        # String: 5, 0, 0, 0, h, e, l, l, o
        # u32: 42, 0, 0, 0
        rust_bytes = bytes([5, 0, 0, 0, 104, 101, 108, 108, 111, 42, 0, 0, 0])

        model = TestStruct(name="hello", value=42)
        assert model.to_borsh() == rust_bytes
        assert TestStruct.from_borsh(rust_bytes) == model
