"""Basic tests for PyBorsh."""

import pytest

from pyborsh import (
    F32,
    I64,
    U8,
    Bytes,
)
from pyborsh.reader import BorshReader
from pyborsh.writer import BorshWriter


class TestBorshWriter:
    """Tests for BorshWriter."""

    def test_write_u8(self):
        writer = BorshWriter()
        writer.write_u8(42)
        assert writer.get_buffer() == bytes([42])

    def test_write_u8_max(self):
        writer = BorshWriter()
        writer.write_u8(255)
        assert writer.get_buffer() == bytes([255])

    def test_write_u8_overflow(self):
        writer = BorshWriter()
        with pytest.raises(ValueError):
            writer.write_u8(256)

    def test_write_u16(self):
        writer = BorshWriter()
        writer.write_u16(0x1234)
        assert writer.get_buffer() == bytes([0x34, 0x12])  # Little-endian

    def test_write_u32(self):
        writer = BorshWriter()
        writer.write_u32(0x12345678)
        assert writer.get_buffer() == bytes([0x78, 0x56, 0x34, 0x12])

    def test_write_u64(self):
        writer = BorshWriter()
        writer.write_u64(0x123456789ABCDEF0)
        expected = bytes([0xF0, 0xDE, 0xBC, 0x9A, 0x78, 0x56, 0x34, 0x12])
        assert writer.get_buffer() == expected

    def test_write_u128(self):
        writer = BorshWriter()
        value = (1 << 127) - 1  # Large 128-bit value
        writer.write_u128(value)
        assert len(writer.get_buffer()) == 16

    def test_write_i8_positive(self):
        writer = BorshWriter()
        writer.write_i8(42)
        assert writer.get_buffer() == bytes([42])

    def test_write_i8_negative(self):
        writer = BorshWriter()
        writer.write_i8(-1)
        assert writer.get_buffer() == bytes([0xFF])

    def test_write_bool_true(self):
        writer = BorshWriter()
        writer.write_bool(True)
        assert writer.get_buffer() == bytes([0x01])

    def test_write_bool_false(self):
        writer = BorshWriter()
        writer.write_bool(False)
        assert writer.get_buffer() == bytes([0x00])

    def test_write_string(self):
        writer = BorshWriter()
        writer.write_string("hello")
        # 4 bytes length (5) + 5 bytes content
        assert writer.get_buffer() == bytes([5, 0, 0, 0, 104, 101, 108, 108, 111])

    def test_write_string_unicode(self):
        writer = BorshWriter()
        writer.write_string("héllo")  # é is 2 bytes in UTF-8
        data = writer.get_buffer()
        length = int.from_bytes(data[:4], "little")
        assert length == 6  # h(1) + é(2) + l(1) + l(1) + o(1)


class TestBorshReader:
    """Tests for BorshReader."""

    def test_read_u8(self):
        reader = BorshReader(bytes([42]))
        assert reader.read_u8() == 42

    def test_read_u16(self):
        reader = BorshReader(bytes([0x34, 0x12]))
        assert reader.read_u16() == 0x1234

    def test_read_u32(self):
        reader = BorshReader(bytes([0x78, 0x56, 0x34, 0x12]))
        assert reader.read_u32() == 0x12345678

    def test_read_u64(self):
        data = bytes([0xF0, 0xDE, 0xBC, 0x9A, 0x78, 0x56, 0x34, 0x12])
        reader = BorshReader(data)
        assert reader.read_u64() == 0x123456789ABCDEF0

    def test_read_i8_negative(self):
        reader = BorshReader(bytes([0xFF]))
        assert reader.read_i8() == -1

    def test_read_bool_true(self):
        reader = BorshReader(bytes([0x01]))
        assert reader.read_bool() is True

    def test_read_bool_false(self):
        reader = BorshReader(bytes([0x00]))
        assert reader.read_bool() is False

    def test_read_string(self):
        data = bytes([5, 0, 0, 0, 104, 101, 108, 108, 111])
        reader = BorshReader(data)
        assert reader.read_string() == "hello"

    def test_roundtrip_u32(self):
        writer = BorshWriter()
        writer.write_u32(12345678)
        reader = BorshReader(writer.get_buffer())
        assert reader.read_u32() == 12345678

    def test_roundtrip_string(self):
        writer = BorshWriter()
        writer.write_string("hello world!")
        reader = BorshReader(writer.get_buffer())
        assert reader.read_string() == "hello world!"


class TestTypeMarkers:
    """Tests for type marker classes."""

    def test_u8_marker(self):
        assert U8.bits == 8
        assert U8.signed is False

    def test_i64_marker(self):
        assert I64.bits == 64
        assert I64.signed is True

    def test_f32_marker(self):
        assert F32.bits == 32

    def test_bytes_dynamic(self):
        b = Bytes()
        assert b.length is None

    def test_bytes_fixed(self):
        b = Bytes(32)
        assert b.length == 32
