"""Borsh type markers for use with typing.Annotated."""

from typing import Any


class _IntegerType:
    """Base class for integer type markers."""

    bits: int
    signed: bool

    def __init_subclass__(cls, bits: int, signed: bool, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls.bits = bits
        cls.signed = signed

    def __repr__(self) -> str:
        return self.__class__.__name__


# Unsigned integers
class U8(_IntegerType, bits=8, signed=False):
    """Unsigned 8-bit integer (u8)."""


class U16(_IntegerType, bits=16, signed=False):
    """Unsigned 16-bit integer (u16)."""


class U32(_IntegerType, bits=32, signed=False):
    """Unsigned 32-bit integer (u32)."""


class U64(_IntegerType, bits=64, signed=False):
    """Unsigned 64-bit integer (u64)."""


class U128(_IntegerType, bits=128, signed=False):
    """Unsigned 128-bit integer (u128)."""


# Signed integers
class I8(_IntegerType, bits=8, signed=True):
    """Signed 8-bit integer (i8)."""


class I16(_IntegerType, bits=16, signed=True):
    """Signed 16-bit integer (i16)."""


class I32(_IntegerType, bits=32, signed=True):
    """Signed 32-bit integer (i32)."""


class I64(_IntegerType, bits=64, signed=True):
    """Signed 64-bit integer (i64)."""


class I128(_IntegerType, bits=128, signed=True):
    """Signed 128-bit integer (i128)."""


# Float types
class _FloatType:
    """Base class for float type markers."""

    bits: int

    def __init_subclass__(cls, bits: int, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls.bits = bits

    def __repr__(self) -> str:
        return self.__class__.__name__


class F32(_FloatType, bits=32):
    """32-bit floating point (f32)."""


class F64(_FloatType, bits=64):
    """64-bit floating point (f64)."""


# Special types
class Bytes:
    """
    Marker for byte arrays.

    Args:
        length: If None, serializes as Vec<u8> (with u32 length prefix).
                If int, serializes as [u8; N] (fixed size, no prefix).
    """

    def __init__(self, length: int | None = None) -> None:
        self.length = length

    def __repr__(self) -> str:
        if self.length is None:
            return "Bytes()"
        return f"Bytes({self.length})"


class Array:
    """
    Marker for fixed-size arrays.

    Usage:
        coords: Annotated[list[int], Array(I32, 3)]  # [i32; 3]
    """

    def __init__(self, element_type: type, length: int) -> None:
        self.element_type = element_type
        self.length = length

    def __repr__(self) -> str:
        return f"Array({self.element_type.__name__}, {self.length})"
