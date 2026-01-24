"""Borsh binary reader for deserialization."""

import struct

from pyborsh.errors import BorshDeserializationError


class BorshReader:
    """
    Low-level binary reader for Borsh deserialization.

    All integers are read in little-endian format.
    """

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._offset = 0

    @property
    def remaining(self) -> int:
        """Number of bytes remaining to read."""
        return len(self._data) - self._offset

    def _ensure_bytes(self, count: int) -> None:
        """Ensure we have enough bytes to read."""
        if self.remaining < count:
            raise BorshDeserializationError(
                f"Unexpected end of data: need {count} bytes, have {self.remaining}"
            )

    def read_u8(self) -> int:
        """Read an unsigned 8-bit integer."""
        self._ensure_bytes(1)
        value = self._data[self._offset]
        self._offset += 1
        return value

    def read_u16(self) -> int:
        """Read an unsigned 16-bit integer (little-endian)."""
        self._ensure_bytes(2)
        value = int.from_bytes(self._data[self._offset : self._offset + 2], "little")
        self._offset += 2
        return value

    def read_u32(self) -> int:
        """Read an unsigned 32-bit integer (little-endian)."""
        self._ensure_bytes(4)
        value = int.from_bytes(self._data[self._offset : self._offset + 4], "little")
        self._offset += 4
        return value

    def read_u64(self) -> int:
        """Read an unsigned 64-bit integer (little-endian)."""
        self._ensure_bytes(8)
        value = int.from_bytes(self._data[self._offset : self._offset + 8], "little")
        self._offset += 8
        return value

    def read_u128(self) -> int:
        """Read an unsigned 128-bit integer (little-endian)."""
        self._ensure_bytes(16)
        value = int.from_bytes(self._data[self._offset : self._offset + 16], "little")
        self._offset += 16
        return value

    def read_i8(self) -> int:
        """Read a signed 8-bit integer."""
        self._ensure_bytes(1)
        value = int.from_bytes(self._data[self._offset : self._offset + 1], "little", signed=True)
        self._offset += 1
        return value

    def read_i16(self) -> int:
        """Read a signed 16-bit integer (little-endian)."""
        self._ensure_bytes(2)
        value = int.from_bytes(self._data[self._offset : self._offset + 2], "little", signed=True)
        self._offset += 2
        return value

    def read_i32(self) -> int:
        """Read a signed 32-bit integer (little-endian)."""
        self._ensure_bytes(4)
        value = int.from_bytes(self._data[self._offset : self._offset + 4], "little", signed=True)
        self._offset += 4
        return value

    def read_i64(self) -> int:
        """Read a signed 64-bit integer (little-endian)."""
        self._ensure_bytes(8)
        value = int.from_bytes(self._data[self._offset : self._offset + 8], "little", signed=True)
        self._offset += 8
        return value

    def read_i128(self) -> int:
        """Read a signed 128-bit integer (little-endian)."""
        self._ensure_bytes(16)
        value = int.from_bytes(self._data[self._offset : self._offset + 16], "little", signed=True)
        self._offset += 16
        return value

    def read_f32(self) -> float:
        """Read a 32-bit float (IEEE 754, little-endian)."""
        self._ensure_bytes(4)
        (value,) = struct.unpack("<f", self._data[self._offset : self._offset + 4])
        self._offset += 4
        return float(value)

    def read_f64(self) -> float:
        """Read a 64-bit float (IEEE 754, little-endian)."""
        self._ensure_bytes(8)
        (value,) = struct.unpack("<d", self._data[self._offset : self._offset + 8])
        self._offset += 8
        return float(value)

    def read_bool(self) -> bool:
        """Read a boolean (1 byte: 0x00 or 0x01)."""
        value = self.read_u8()
        if value == 0x00:
            return False
        if value == 0x01:
            return True
        raise BorshDeserializationError(f"Invalid boolean value: {value}")

    def read_string(self) -> str:
        """Read a UTF-8 string with u32 length prefix."""
        length = self.read_u32()
        self._ensure_bytes(length)
        try:
            value = self._data[self._offset : self._offset + length].decode("utf-8")
        except UnicodeDecodeError as e:
            raise BorshDeserializationError(f"Invalid UTF-8 string: {e}") from e
        self._offset += length
        return value

    def read_bytes(self, length: int) -> bytes:
        """Read a fixed number of bytes."""
        self._ensure_bytes(length)
        value = self._data[self._offset : self._offset + length]
        self._offset += length
        return bytes(value)

    def read_dynamic_bytes(self) -> bytes:
        """Read bytes with u32 length prefix (Vec<u8>)."""
        length = self.read_u32()
        return self.read_bytes(length)

    def read_option_discriminant(self) -> bool:
        """Read Option discriminant. Returns True if Some, False if None."""
        value = self.read_u8()
        if value == 0x00:
            return False
        if value == 0x01:
            return True
        raise BorshDeserializationError(f"Invalid Option discriminant: {value}")

    def read_enum_discriminant(self) -> int:
        """Read enum variant index (u8)."""
        return self.read_u8()
