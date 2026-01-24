"""BorshEnum base class for Rust-style enums with data."""

from typing import Any, ClassVar


class BorshEnumMeta(type):
    """Metaclass for BorshEnum that registers variant classes."""

    def __new__(mcs, name: str, bases: tuple[type, ...], namespace: dict[str, Any]) -> type:
        cls = super().__new__(mcs, name, bases, namespace)

        # Skip processing for the base BorshEnum class itself
        if name == "BorshEnum" and not bases:
            return cls

        # Find all nested classes that are variants
        variants: dict[str, tuple[int, type]] = {}
        variant_index = 0

        for attr_name, attr_value in namespace.items():
            if attr_name.startswith("_"):
                continue
            if isinstance(attr_value, type):
                variants[attr_name] = (variant_index, attr_value)
                # Store a reference to the parent BorshEnum on each variant
                attr_value._borsh_enum_parent = cls  # type: ignore[attr-defined]
                variant_index += 1

        cls._variants = variants  # type: ignore[attr-defined]
        return cls


class BorshEnum(metaclass=BorshEnumMeta):
    """
    Base class for Rust-style enums with associated data.

    Usage:
        class Shape(BorshEnum):
            class Circle(BaseModel):
                radius: Annotated[int, U32]

            class Rectangle(BaseModel):
                width: Annotated[int, U32]
                height: Annotated[int, U32]

            class Point(BaseModel):
                pass  # Unit variant

        # Create variants
        circle = Shape.Circle(radius=10)
        rect = Shape.Rectangle(width=5, height=10)
    """

    _variants: ClassVar[dict[str, tuple[int, type]]]
