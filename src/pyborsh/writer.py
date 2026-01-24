"""Borsh binary writer for serialization."""

import struct


class BorshWriter:
    """
    Low-level binary writer for Borsh serialization.

    All integers are written in little-endian format.
    """

    def __init__(self) -> None:
        self._buffer = bytearray()

    def write_u8(self, value: int) -> None:
        """Write an unsigned 8-bit integer."""
        if not (0 <= value <= 0xFF):
            raise ValueError(f"Value {value} out of range for u8 (0-255)")
        self._buffer.append(value)

    def write_u16(self, value: int) -> None:
        """Write an unsigned 16-bit integer (little-endian)."""
        if not (0 <= value <= 0xFFFF):
            raise ValueError(f"Value {value} out of range for u16 (0-65535)")
        self._buffer.extend(value.to_bytes(2, "little"))

    def write_u32(self, value: int) -> None:
        """Write an unsigned 32-bit integer (little-endian)."""
        if not (0 <= value <= 0xFFFFFFFF):
            raise ValueError(f"Value {value} out of range for u32")
        self._buffer.extend(value.to_bytes(4, "little"))

    def write_u64(self, value: int) -> None:
        """Write an unsigned 64-bit integer (little-endian)."""
        if not (0 <= value <= 0xFFFFFFFFFFFFFFFF):
            raise ValueError(f"Value {value} out of range for u64")
        self._buffer.extend(value.to_bytes(8, "little"))

    def write_u128(self, value: int) -> None:
        """Write an unsigned 128-bit integer (little-endian)."""
        if not (0 <= value <= (1 << 128) - 1):
            raise ValueError(f"Value {value} out of range for u128")
        self._buffer.extend(value.to_bytes(16, "little"))

    def write_i8(self, value: int) -> None:
        """Write a signed 8-bit integer."""
        if not (-128 <= value <= 127):
            raise ValueError(f"Value {value} out of range for i8 (-128 to 127)")
        self._buffer.extend(value.to_bytes(1, "little", signed=True))

    def write_i16(self, value: int) -> None:
        """Write a signed 16-bit integer (little-endian)."""
        if not (-32768 <= value <= 32767):
            raise ValueError(f"Value {value} out of range for i16")
        self._buffer.extend(value.to_bytes(2, "little", signed=True))

    def write_i32(self, value: int) -> None:
        """Write a signed 32-bit integer (little-endian)."""
        if not (-(1 << 31) <= value <= (1 << 31) - 1):
            raise ValueError(f"Value {value} out of range for i32")
        self._buffer.extend(value.to_bytes(4, "little", signed=True))

    def write_i64(self, value: int) -> None:
        """Write a signed 64-bit integer (little-endian)."""
        if not (-(1 << 63) <= value <= (1 << 63) - 1):
            raise ValueError(f"Value {value} out of range for i64")
        self._buffer.extend(value.to_bytes(8, "little", signed=True))

    def write_i128(self, value: int) -> None:
        """Write a signed 128-bit integer (little-endian)."""
        if not (-(1 << 127) <= value <= (1 << 127) - 1):
            raise ValueError(f"Value {value} out of range for i128")
        self._buffer.extend(value.to_bytes(16, "little", signed=True))

    def write_f32(self, value: float) -> None:
        """Write a 32-bit float (IEEE 754, little-endian)."""
        self._buffer.extend(struct.pack("<f", value))

    def write_f64(self, value: float) -> None:
        """Write a 64-bit float (IEEE 754, little-endian)."""
        self._buffer.extend(struct.pack("<d", value))

    def write_bool(self, value: bool) -> None:
        """Write a boolean (1 byte: 0x00 or 0x01)."""
        self._buffer.append(0x01 if value else 0x00)

    def write_string(self, value: str) -> None:
        """Write a UTF-8 string with u32 length prefix."""
        encoded = value.encode("utf-8")
        self.write_u32(len(encoded))
        self._buffer.extend(encoded)

    def write_bytes(self, value: bytes) -> None:
        """Write raw bytes (no length prefix)."""
        self._buffer.extend(value)

    def write_dynamic_bytes(self, value: bytes) -> None:
        """Write bytes with u32 length prefix (Vec<u8>)."""
        self.write_u32(len(value))
        self._buffer.extend(value)

    def write_fixed_bytes(self, value: bytes, length: int) -> None:
        """Write fixed-size bytes ([u8; N])."""
        if len(value) != length:
            raise ValueError(f"Expected {length} bytes, got {len(value)}")
        self._buffer.extend(value)

    def write_option_discriminant(self, is_some: bool) -> None:
        """Write Option discriminant (0x00 for None, 0x01 for Some)."""
        self._buffer.append(0x01 if is_some else 0x00)

    def write_enum_discriminant(self, variant_index: int) -> None:
        """Write enum variant index (u8)."""
        self.write_u8(variant_index)

    def get_buffer(self) -> bytes:
        """Get the serialized bytes."""
        return bytes(self._buffer)
