"""Tests for BorshEnum (tagged unions with data)."""

from typing import Annotated, Literal

from pydantic import BaseModel

from pyborsh import U8, U32, U64, Borsh, BorshEnum


class TestBorshEnumBasic:
    """Test basic BorshEnum functionality."""

    def test_borsh_enum_variant_registration(self):
        """Test that variants are properly registered."""

        class Shape(BorshEnum):
            class Circle(BaseModel):
                variant: Literal["Circle"] = "Circle"
                radius: Annotated[int, U32]

            class Rectangle(BaseModel):
                variant: Literal["Rectangle"] = "Rectangle"
                width: Annotated[int, U32]
                height: Annotated[int, U32]

            class Point(BaseModel):
                variant: Literal["Point"] = "Point"

        # Check variants are registered in order
        assert "Circle" in Shape._variants
        assert "Rectangle" in Shape._variants
        assert "Point" in Shape._variants

        # Check indices
        assert Shape._variants["Circle"][0] == 0
        assert Shape._variants["Rectangle"][0] == 1
        assert Shape._variants["Point"][0] == 2

    def test_variant_instantiation(self):
        """Test creating variant instances."""

        class Shape(BorshEnum):
            class Circle(BaseModel):
                variant: Literal["Circle"] = "Circle"
                radius: Annotated[int, U32]

            class Rectangle(BaseModel):
                variant: Literal["Rectangle"] = "Rectangle"
                width: Annotated[int, U32]
                height: Annotated[int, U32]

        circle = Shape.Circle(radius=10)
        assert circle.radius == 10
        assert circle.variant == "Circle"

        rect = Shape.Rectangle(width=5, height=10)
        assert rect.width == 5
        assert rect.height == 10


class TestBorshEnumSerialization:
    """Test serialization of BorshEnum variants."""

    def test_serialize_variant_with_data(self):
        """Test serializing a variant with data."""

        class Message(BorshEnum):
            class Text(Borsh, BaseModel):
                variant: Literal["Text"] = "Text"
                content: str

            class Number(Borsh, BaseModel):
                variant: Literal["Number"] = "Number"
                value: Annotated[int, U64]

        msg = Message.Text(content="hello")
        # Serialize using Borsh mixin
        data = msg.to_borsh()

        # Should be: string (4 bytes len + content), no discriminant
        # For Text: 5, 0, 0, 0, h, e, l, l, o
        expected = bytes([5, 0, 0, 0, 104, 101, 108, 108, 111])
        assert data == expected

    def test_serialize_variant_in_struct(self):
        """Test serializing BorshEnum as field in a struct."""

        class Action(BorshEnum):
            class Add(Borsh, BaseModel):
                variant: Literal["Add"] = "Add"
                amount: Annotated[int, U32]

            class Remove(Borsh, BaseModel):
                variant: Literal["Remove"] = "Remove"
                amount: Annotated[int, U32]

        class Command(Borsh, BaseModel):
            id: Annotated[int, U8]
            action: Action.Add | Action.Remove

        cmd = Command(id=1, action=Action.Add(amount=100))
        data = cmd.to_borsh()

        # Should be: 1 byte id + 1 byte discriminant (0) + 4 bytes amount
        assert data[0] == 1  # id
        assert data[1] == 0  # variant discriminant (Add = 0)
        assert data[2:6] == bytes([100, 0, 0, 0])  # amount = 100

        # Test second variant
        cmd2 = Command(id=2, action=Action.Remove(amount=50))
        data2 = cmd2.to_borsh()
        assert data2[0] == 2  # id
        assert data2[1] == 1  # variant discriminant (Remove = 1)
        assert data2[2:6] == bytes([50, 0, 0, 0])  # amount = 50


class TestBorshEnumDeserialization:
    """Test deserialization of BorshEnum variants."""

    def test_deserialize_variant_in_struct(self):
        """Test deserializing BorshEnum from bytes."""

        class Action(BorshEnum):
            class Add(Borsh, BaseModel):
                variant: Literal["Add"] = "Add"
                amount: Annotated[int, U32]

            class Remove(Borsh, BaseModel):
                variant: Literal["Remove"] = "Remove"
                amount: Annotated[int, U32]

        class Command(Borsh, BaseModel):
            id: Annotated[int, U8]
            action: Action.Add | Action.Remove

        # Create test data: id=5, variant=Add(amount=42)
        test_data = bytes([5, 0, 42, 0, 0, 0])  # id, discriminant, amount

        cmd = Command.from_borsh(test_data)
        assert cmd.id == 5
        assert isinstance(cmd.action, Action.Add)
        assert cmd.action.amount == 42

        # Test second variant
        test_data2 = bytes([10, 1, 100, 0, 0, 0])  # id=10, variant=Remove, amount=100
        cmd2 = Command.from_borsh(test_data2)
        assert cmd2.id == 10
        assert isinstance(cmd2.action, Action.Remove)
        assert cmd2.action.amount == 100


class TestBorshEnumRoundtrip:
    """Test roundtrip serialization of BorshEnum."""

    def test_roundtrip_enum_in_struct(self):
        """Test roundtrip of struct containing BorshEnum."""

        class Status(BorshEnum):
            class Pending(Borsh, BaseModel):
                variant: Literal["Pending"] = "Pending"

            class Active(Borsh, BaseModel):
                variant: Literal["Active"] = "Active"
                started_at: Annotated[int, U64]

            class Completed(Borsh, BaseModel):
                variant: Literal["Completed"] = "Completed"
                result: str

        class Task(Borsh, BaseModel):
            id: Annotated[int, U32]
            status: Status.Pending | Status.Active | Status.Completed

        # Test Pending
        task1 = Task(id=1, status=Status.Pending())
        assert Task.from_borsh(task1.to_borsh()) == task1

        # Test Active
        task2 = Task(id=2, status=Status.Active(started_at=1234567890))
        task2_restored = Task.from_borsh(task2.to_borsh())
        assert task2_restored.id == 2
        assert isinstance(task2_restored.status, Status.Active)
        assert task2_restored.status.started_at == 1234567890

        # Test Completed
        task3 = Task(id=3, status=Status.Completed(result="success"))
        task3_restored = Task.from_borsh(task3.to_borsh())
        assert task3_restored.id == 3
        assert isinstance(task3_restored.status, Status.Completed)
        assert task3_restored.status.result == "success"

    def test_vec_of_enum_variants(self):
        """Test Vec of enum variants."""

        class Op(BorshEnum):
            class Push(Borsh, BaseModel):
                variant: Literal["Push"] = "Push"
                value: Annotated[int, U8]

            class Pop(Borsh, BaseModel):
                variant: Literal["Pop"] = "Pop"

        class Program(Borsh, BaseModel):
            ops: list[Op.Push | Op.Pop]

        program = Program(
            ops=[
                Op.Push(value=10),
                Op.Push(value=20),
                Op.Pop(),
                Op.Push(value=30),
            ]
        )

        data = program.to_borsh()
        restored = Program.from_borsh(data)

        assert len(restored.ops) == 4
        assert isinstance(restored.ops[0], Op.Push)
        assert restored.ops[0].value == 10
        assert isinstance(restored.ops[1], Op.Push)
        assert restored.ops[1].value == 20
        assert isinstance(restored.ops[2], Op.Pop)
        assert isinstance(restored.ops[3], Op.Push)
        assert restored.ops[3].value == 30
