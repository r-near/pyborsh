"""Property-based tests for the Borsh spec's bijective object<->bytes mapping.

Strategies are derived from pyborsh's own schema introspection (see
``tests/strategies.py``), so every Borsh model gets a value generator for
free. The properties pin the spec-level contract (borsh.io):

  P1  round-trip:      from_borsh(to_borsh(x)) == x, and re-encoding is
                       byte-stable.
  P2  determinism:     equal values -> equal bytes. HashMap/HashSet entries
                       are written sorted by key, independent of insertion
                       order and of PYTHONHASHSEED.
  P3  canonicity:      trailing bytes after a valid encoding are rejected
                       (borsh-rs try_from_slice: "Not all bytes read").
  P4  decode contract: from_borsh(any bytes) returns an instance or raises
                       BorshDeserializationError -- nothing else escapes.
  P5  encode contract: to_borsh on any pydantic-accepted model returns bytes
                       or raises BorshSerializationError -- nothing else.
  P6  resource bounds: a length prefix cannot force work beyond the input
                       size. Zero-size element types would defeat any length
                       guard, so ZST collections are rejected outright on
                       both encode and decode (borsh-rs check_zst parity).

Plus targeted probes for the NaN policy (spec: err_if_nan -- rejected on both
encode and decode; infinity stays allowed) and for duplicate-collapse on
decode (accepted, matching borsh-rs default behavior).
"""

import contextlib
import gc
import math
import os
import struct
import subprocess
import sys
import weakref
from enum import IntEnum
from typing import Annotated, Literal

import pytest
from hypothesis import example, given, strategies as st
from pydantic import BaseModel, ConfigDict, create_model

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
    BorshDeserializationError,
    BorshEnum,
    BorshSerializationError,
    Bytes,
)
from pyborsh.schema import BorshFieldType, build_model_schema, is_zero_size
from tests.strategies import models

# ---------------------------------------------------------------------------
# Model families under test -- one per structural feature of the format
# ---------------------------------------------------------------------------


class Status(IntEnum):
    """C-style enum, serialized as a u8 discriminant."""

    PENDING = 0
    ACTIVE = 1
    DONE = 2


class Primitives(Borsh, BaseModel):
    """Every integer width, both floats, bool, string, and both byte flavors."""

    u8: Annotated[int, U8]
    u16: Annotated[int, U16]
    u32: Annotated[int, U32]
    u64: Annotated[int, U64]
    u128: Annotated[int, U128]
    i8: Annotated[int, I8]
    i16: Annotated[int, I16]
    i32: Annotated[int, I32]
    i64: Annotated[int, I64]
    i128: Annotated[int, I128]
    flag: bool
    text: str
    f64_val: float
    f32_val: Annotated[float, F32]
    blob: bytes
    fixed: Annotated[bytes, Bytes(4)]


class Collections(Borsh, BaseModel):
    """Vec, HashSet, HashMap, tuple, fixed array, and Option."""

    v: list[Annotated[int, U16]]
    s: set[str]
    m: dict[str, Annotated[int, U32]]
    t: tuple[Annotated[int, U8], str, bool]
    arr: Annotated[list[int], Array(U8, 3)]
    opt: Annotated[int, U32] | None


class Inner(Borsh, BaseModel):
    """Simple struct used as a nesting building block."""

    x: Annotated[int, U32]
    label: str


class Nested(Borsh, BaseModel):
    """Structs inside options, vecs, and other structs, plus an IntEnum."""

    inner: Inner
    maybe: Inner | None
    many: list[Inner]
    status: Status


class Shape(BorshEnum):
    """Rust-style tagged union with struct, multi-field, and unit variants."""

    class Circle(Borsh, BaseModel):
        variant: Literal["Circle"] = "Circle"
        radius: Annotated[int, U32]

    class Rect(Borsh, BaseModel):
        variant: Literal["Rect"] = "Rect"
        w: Annotated[int, U32]
        h: Annotated[int, U32]

    class Unit(Borsh, BaseModel):
        variant: Literal["Unit"] = "Unit"


class WithEnum(Borsh, BaseModel):
    """BorshEnum union field next to an IntEnum field."""

    shape: Shape.Circle | Shape.Rect | Shape.Unit
    status: Status


class OptionCollections(Borsh, BaseModel):
    """Option-typed set elements and map keys.

    Option<T> is Ord in Rust (None < Some), so these are legal Rust Borsh
    schemas and must round-trip -- they exercise the Ord-mirroring sort key.
    """

    s: set[Annotated[int, U8] | None]
    m: dict[Annotated[int, U16] | None, Annotated[int, U8]]
    ts: set[tuple[Annotated[int, U8] | None, bool]]


ALL_MODELS = [Primitives, Collections, Nested, WithEnum, OptionCollections]


# Small single-field holders for targeted probes.


class MapHolder(Borsh, BaseModel):
    m: dict[str, Annotated[int, U32]]


class StrSetHolder(Borsh, BaseModel):
    s: set[str]


class ByteSetHolder(Borsh, BaseModel):
    s: set[Annotated[int, U8]]


class OptionSetHolder(Borsh, BaseModel):
    s: set[Annotated[int, U8] | None]


class OptionKeyMapHolder(Borsh, BaseModel):
    m: dict[Annotated[int, U8] | None, Annotated[int, U8]]


class TupleOptionSetHolder(Borsh, BaseModel):
    s: set[tuple[Annotated[int, U8] | None, Annotated[int, U8]]]


class U16MapHolder(Borsh, BaseModel):
    m: dict[Annotated[int, U16], Annotated[int, U8]]


class U16SetHolder(Borsh, BaseModel):
    s: set[Annotated[int, U16]]


class FrozenPoint(Borsh, BaseModel):
    """Hashable but unorderable -- the analog of a Rust struct without Ord."""

    model_config = ConfigDict(frozen=True)

    x: Annotated[int, U8]


class StructSetHolder(Borsh, BaseModel):
    s: set[FrozenPoint]


class StructKeyMapHolder(Borsh, BaseModel):
    m: dict[FrozenPoint, Annotated[int, U8]]


class U8Holder(Borsh, BaseModel):
    x: Annotated[int, U8]


class F32Holder(Borsh, BaseModel):
    x: Annotated[float, F32]


class F64Holder(Borsh, BaseModel):
    x: float


class VecU16Holder(Borsh, BaseModel):
    v: list[Annotated[int, U16]]


class Empty(Borsh, BaseModel):
    """Zero fields -> zero bytes on the wire."""


class EmptyVec(Borsh, BaseModel):
    items: list[Empty]


class NestedEmptyVec(Borsh, BaseModel):
    outer: list[list[Empty]]


# A known-good Collections instance, used to pin deterministic examples.
_COLLECTIONS_EXAMPLE = Collections(
    v=[1], s={"x"}, m={"k": 1}, t=(1, "y", True), arr=[1, 2, 3], opt=None
)


class TestRoundTrip:
    """P1: decode inverts encode, and encoding is byte-stable."""

    @pytest.mark.parametrize("model_cls", ALL_MODELS)
    @given(data=st.data())
    def test_roundtrip(self, model_cls, data):
        x = data.draw(models(model_cls))
        assert model_cls.from_borsh(x.to_borsh()) == x

    @pytest.mark.parametrize("model_cls", ALL_MODELS)
    @given(data=st.data())
    def test_byte_stability(self, model_cls, data):
        """to_borsh(from_borsh(to_borsh(x))) == to_borsh(x)."""
        x = data.draw(models(model_cls))
        encoded = x.to_borsh()
        assert model_cls.from_borsh(encoded).to_borsh() == encoded


class TestDeterminism:
    """P2: equal values -> equal bytes; unordered containers are sorted by key."""

    @given(
        d=st.dictionaries(
            st.text(max_size=4),
            st.integers(min_value=0, max_value=2**32 - 1),
            min_size=2,
            max_size=5,
        )
    )
    def test_equal_maps_serialize_identically(self, d):
        """Insertion order must not leak into the encoding."""
        fwd = MapHolder(m=dict(d.items()))
        rev = MapHolder(m=dict(reversed(list(d.items()))))
        assert fwd == rev  # same logical value...
        assert fwd.to_borsh() == rev.to_borsh()  # ...must be the same bytes

    def test_map_entries_written_in_key_order(self):
        """Golden layout: {"b": .., "a": ..} serializes "a"'s entry first."""
        m = MapHolder(m={"b": 1, "a": 2})
        expected = (
            (2).to_bytes(4, "little")  # 2 entries
            + (1).to_bytes(4, "little")
            + b"a"  # key "a"
            + (2).to_bytes(4, "little")  # value 2
            + (1).to_bytes(4, "little")
            + b"b"  # key "b"
            + (1).to_bytes(4, "little")  # value 1
        )
        assert m.to_borsh() == expected

    def test_set_elements_written_in_sorted_order(self):
        """Golden layout: {"b", "a"} serializes "a" before "b"."""
        s = StrSetHolder(s={"b", "a"})
        expected = (
            (2).to_bytes(4, "little")
            + (1).to_bytes(4, "little")
            + b"a"
            + (1).to_bytes(4, "little")
            + b"b"
        )
        assert s.to_borsh() == expected

    def test_map_int_keys_sorted_numerically_not_bytewise(self):
        """Multi-byte int keys sort by numeric value (Rust Ord), not encoding.

        256 encodes little-endian as 00 01, which sorts byte-lexicographically
        BEFORE 1's encoding 01 00; sorting the encodings instead of the values
        would wrongly write 256's entry first.
        """
        m = U16MapHolder(m={256: 9, 1: 7})
        expected = (
            (2).to_bytes(4, "little")  # 2 entries
            + (1).to_bytes(2, "little")  # key 1 first (numeric order)
            + bytes([7])
            + (256).to_bytes(2, "little")  # key 256 second
            + bytes([9])
        )
        assert m.to_borsh() == expected
        assert U16MapHolder.from_borsh(expected) == m

    def test_set_int_elements_sorted_numerically_not_bytewise(self):
        """Same property for HashSet elements: {256, 1} writes 1 first."""
        s = U16SetHolder(s={256, 1})
        expected = (
            (2).to_bytes(4, "little") + (1).to_bytes(2, "little") + (256).to_bytes(2, "little")
        )
        assert s.to_borsh() == expected
        assert U16SetHolder.from_borsh(expected) == s

    def test_option_set_elements_sort_none_first(self):
        """Option<T> is Ord in Rust: None < Some, matching bytes 0x00 < 0x01.

        This is exactly what Rust borsh emits for HashSet<Option<u8>>
        {None, Some(0)}; decoding it and re-encoding must be a fixed point
        (bijectivity), not a serialization error.
        """
        m = OptionSetHolder(s={None, 0})
        raw = (2).to_bytes(4, "little") + b"\x00" + b"\x01\x00"
        assert m.to_borsh() == raw
        assert OptionSetHolder.from_borsh(raw) == m
        assert OptionSetHolder.from_borsh(raw).to_borsh() == raw

    def test_option_map_keys_sort_none_first(self):
        """HashMap<Option<u8>, u8>: the None-keyed entry is written first."""
        m = OptionKeyMapHolder(m={0: 2, None: 1})
        raw = (
            (2).to_bytes(4, "little")
            + b"\x00"  # key None
            + b"\x01"  # value 1
            + b"\x01\x00"  # key Some(0)
            + b"\x02"  # value 2
        )
        assert m.to_borsh() == raw
        assert OptionKeyMapHolder.from_borsh(raw) == m

    def test_option_nested_in_tuple_sorts_none_first(self):
        """The Ord-mirroring sort key recurses into tuple slots."""
        m = TupleOptionSetHolder(s={(0, 5), (None, 5)})
        raw = (2).to_bytes(4, "little") + b"\x00\x05" + b"\x01\x00\x05"
        assert m.to_borsh() == raw
        assert TupleOptionSetHolder.from_borsh(raw) == m

    def test_cross_process_set_determinism(self):
        """Same value, two interpreters, randomized hash seeds -> same bytes.

        Pre-sorting, set iteration order (and thus the encoding) depended on
        each process's string hash seed.
        """
        snippet = (
            "import sys\n"
            "from pydantic import BaseModel\n"
            "from pyborsh import Borsh\n"
            "class Holder(Borsh, BaseModel):\n"
            "    tags: set[str]\n"
            'm = Holder(tags={"north", "south", "east", "west", "up", "down"})\n'
            "sys.stdout.write(m.to_borsh().hex())\n"
        )
        env = {**os.environ, "PYTHONHASHSEED": "random"}
        outputs = []
        for _ in range(2):
            result = subprocess.run(  # noqa: S603
                [sys.executable, "-c", snippet],
                capture_output=True,
                text=True,
                env=env,
                check=False,
                timeout=120,
            )
            assert result.returncode == 0, result.stderr
            outputs.append(result.stdout)
        assert outputs[0] == outputs[1], "encoding depends on the process hash seed"


class TestTrailingBytes:
    """P3: canonicity -- accepted bytes must be exactly one valid encoding."""

    @pytest.mark.parametrize("model_cls", ALL_MODELS)
    @given(data=st.data())
    def test_trailing_junk_rejected(self, model_cls, data):
        x = data.draw(models(model_cls))
        junk = data.draw(st.binary(min_size=1, max_size=8))
        with pytest.raises(BorshDeserializationError):
            model_cls.from_borsh(x.to_borsh() + junk)

    @given(x=models(Collections), junk=st.binary(min_size=1, max_size=8))
    @example(x=_COLLECTIONS_EXAMPLE, junk=b"\x00")
    def test_trailing_junk_rejected_pinned(self, x, junk):
        """Pinned: even a single trailing zero byte is an error."""
        with pytest.raises(BorshDeserializationError):
            Collections.from_borsh(x.to_borsh() + junk)


class TestDecodeContract:
    """P4: from_borsh(bytes) -> instance | BorshDeserializationError, nothing else.

    Any other exception (ValueError, ValidationError, struct.error,
    OverflowError, RecursionError...) is a leak in the API contract.
    """

    @pytest.mark.parametrize("model_cls", ALL_MODELS)
    @given(data=st.binary(max_size=64))
    @example(data=b"\x02\x03")  # WithEnum: valid Unit variant + invalid Status
    def test_raw_bytes(self, model_cls, data):
        """Arbitrary bytes never escape the documented exception type.

        The pinned example decodes shape=Shape.Unit then hits discriminant 3
        for Status -- the path that used to leak a bare ValueError.
        """
        with contextlib.suppress(BorshDeserializationError):
            model_cls.from_borsh(data)

    def test_pydantic_validation_failure_wrapped(self):
        """Valid Borsh bytes violating a model constraint still raise the wrapper.

        pydantic's ValidationError subclasses ValueError, so from_borsh's
        catch-all must convert it -- P4 holds even when decoding succeeds
        byte-wise but the resulting value fails model validation.
        """
        from pydantic import Field

        class Constrained(Borsh, BaseModel):
            x: Annotated[int, U8, Field(gt=10)]

        with pytest.raises(BorshDeserializationError):
            Constrained.from_borsh(bytes([5]))

    @pytest.mark.parametrize("model_cls", ALL_MODELS)
    @given(data=st.data())
    def test_mutated_valid_encodings(self, model_cls, data):
        """Corrupt real encodings (flip up to 3 bytes, maybe truncate).

        Mutations get past the length prefixes and exercise deep decode
        paths that uniformly-random bytes rarely reach.
        """
        x = data.draw(models(model_cls))
        buf = bytearray(x.to_borsh())
        if not buf:
            return
        n_flips = data.draw(st.integers(min_value=1, max_value=3))
        for _ in range(n_flips):
            pos = data.draw(st.integers(min_value=0, max_value=len(buf) - 1))
            buf[pos] = data.draw(st.integers(min_value=0, max_value=255))
        trunc = data.draw(st.integers(min_value=0, max_value=len(buf)))
        with contextlib.suppress(BorshDeserializationError):
            model_cls.from_borsh(bytes(buf[:trunc]))


class TestEncodeContract:
    """P5: to_borsh -> bytes | BorshSerializationError, nothing else.

    Pydantic does not enforce U8/F32 ranges (the markers are opaque
    metadata), so range errors legitimately surface at to_borsh time -- but
    they must be wrapped.
    """

    @given(x=st.integers())
    def test_u8_out_of_range(self, x):
        m = U8Holder(x=x)
        if 0 <= x <= 255:
            assert U8Holder.from_borsh(m.to_borsh()) == m
        else:
            with pytest.raises(BorshSerializationError):
                m.to_borsh()

    @given(x=st.floats())
    @example(x=3.4028235677973366e38)  # smallest double that overflows f32
    def test_f32_any_float(self, x):
        """Any float pydantic accepts either encodes or raises the wrapper.

        The pinned example used to leak struct.pack's OverflowError; NaN
        (generated by default here) must also surface as the wrapper.
        """
        m = F32Holder(x=x)
        with contextlib.suppress(BorshSerializationError):
            m.to_borsh()

    def test_f32_overflow_raises(self):
        """Doubles beyond f32 range must raise, not silently encode."""
        with pytest.raises(BorshSerializationError):
            F32Holder(x=3.4028235677973366e38).to_borsh()

    def test_f32_nan_rejected(self):
        """Spec err_if_nan: NaN is not a valid Borsh value (f32)."""
        with pytest.raises(BorshSerializationError):
            F32Holder(x=math.nan).to_borsh()

    def test_f64_nan_rejected(self):
        """Spec err_if_nan: NaN is not a valid Borsh value (f64)."""
        with pytest.raises(BorshSerializationError):
            F64Holder(x=math.nan).to_borsh()

    def test_f64_infinity_allowed(self):
        """The spec bans only NaN -- infinities round-trip fine."""
        m = F64Holder(x=math.inf)
        assert F64Holder.from_borsh(m.to_borsh()) == m

    def test_unorderable_set_elements_rejected(self):
        """Sets whose elements have no defined order have no canonical encoding.

        A struct set element is the analog of a Rust HashSet<T> where T lacks
        Ord -- which Rust's borsh derive requires -- so serialization must
        fail with the wrapper, not a bare TypeError. (Option<u8> is NOT such
        a case: Option is Ord in Rust, None < Some, so optional elements are
        sorted rather than rejected -- see TestDeterminism.)
        """
        m = StructSetHolder(s={FrozenPoint(x=1), FrozenPoint(x=2)})
        with pytest.raises(BorshSerializationError):
            m.to_borsh()

    def test_unorderable_map_keys_rejected(self):
        """Same contract for HashMap keys without a defined order."""
        m = StructKeyMapHolder(m={FrozenPoint(x=1): 1, FrozenPoint(x=2): 2})
        with pytest.raises(BorshSerializationError):
            m.to_borsh()


class TestResourceBounds:
    """P6: a length prefix cannot demand more work than the input can back.

    Two mechanisms cooperate. Collections whose element type occupies zero
    bytes are rejected outright, on encode and decode alike (borsh-rs
    check_zst parity): no byte-count guard can bound elements that consume
    nothing, and nesting such collections amplifies work quadratically. For
    everything else, each element consumes at least one input byte, so a
    declared length beyond the remaining input is malformed -- which bounds
    total decode work linearly in the input size, nested containers included.
    """

    def test_zero_size_element_bomb(self):
        """A 4-byte payload must not force ~4.3 billion iterations.

        Empty structs occupy zero bytes each, so no length-vs-remaining
        guard can bound the work; the collection type itself is rejected,
        exactly as borsh-rs refuses ZST collections.
        """
        with pytest.raises(BorshDeserializationError, match="zero-sized"):
            EmptyVec.from_borsh(b"\xff\xff\xff\xff")

    def test_nested_zero_size_element_bomb(self):
        """Nested ZST vecs (quadratic amplification) are rejected too.

        Each inner vec could declare length == remaining and slip past a
        naive per-container guard while consuming zero bytes, turning an
        N-byte input into O(N^2) allocations.
        """
        payload = (1).to_bytes(4, "little") + (2**32 - 1).to_bytes(4, "little")
        with pytest.raises(BorshDeserializationError, match="zero-sized"):
            NestedEmptyVec.from_borsh(payload)

    def test_zero_size_collections_rejected_on_encode_too(self):
        """Rejection is symmetric so encode never emits undecodable bytes.

        Without this, EmptyVec(items=[...]).to_borsh() would produce a
        4-byte encoding that from_borsh refuses -- a round-trip hole.
        """
        with pytest.raises(BorshSerializationError, match="zero-sized"):
            EmptyVec(items=[Empty(), Empty()]).to_borsh()
        with pytest.raises(BorshSerializationError, match="zero-sized"):
            EmptyVec(items=[]).to_borsh()

    def test_zero_size_model_alone_still_round_trips(self):
        """Only ZST *collections* are rejected: an empty struct on its own
        (or nested as a plain field) still encodes to zero bytes, as in Rust.
        """
        assert Empty().to_borsh() == b""
        assert Empty.from_borsh(b"") == Empty()

    def test_zero_size_set_elements_and_map_keys_rejected(self):
        """HashSet elements and HashMap keys get the same ZST treatment."""

        class FrozenEmpty(Borsh, BaseModel):
            model_config = ConfigDict(frozen=True)

        class EmptySet(Borsh, BaseModel):
            s: set[FrozenEmpty]

        class EmptyKeyMap(Borsh, BaseModel):
            m: dict[FrozenEmpty, Annotated[int, U8]]

        with pytest.raises(BorshSerializationError, match="zero-sized"):
            EmptySet(s={FrozenEmpty()}).to_borsh()
        with pytest.raises(BorshSerializationError, match="zero-sized"):
            EmptyKeyMap(m={FrozenEmpty(): 1}).to_borsh()
        with pytest.raises(BorshDeserializationError, match="zero-sized"):
            EmptySet.from_borsh(b"\xff\xff\xff\xff")
        with pytest.raises(BorshDeserializationError, match="zero-sized"):
            EmptyKeyMap.from_borsh(b"\xff\xff\xff\xff")

    def test_literal_only_struct_collections_rejected(self):
        """A marker type whose only field is a Literal occupies zero bytes."""

        class Tag(Borsh, BaseModel):
            kind: Literal["tag"] = "tag"

        class TagVec(Borsh, BaseModel):
            tags: list[Tag]

        with pytest.raises(BorshSerializationError, match="zero-sized"):
            TagVec(tags=[Tag()]).to_borsh()

    def test_zero_size_detection_covers_composite_kinds(self):
        """Unit checks for the schema-level ZST detector."""
        u8 = BorshFieldType(kind="u8")
        assert is_zero_size(BorshFieldType(kind="literal"))
        assert not is_zero_size(u8)
        assert is_zero_size(BorshFieldType(kind="fixed_bytes", length=0))
        assert not is_zero_size(BorshFieldType(kind="fixed_bytes", length=4))
        assert is_zero_size(BorshFieldType(kind="fixed_array", length=0, element_type=u8))
        assert not is_zero_size(BorshFieldType(kind="fixed_array", length=3, element_type=u8))
        assert is_zero_size(
            BorshFieldType(kind="tuple", tuple_element_types=[BorshFieldType(kind="literal")])
        )
        assert not is_zero_size(BorshFieldType(kind="tuple", tuple_element_types=[u8]))
        assert is_zero_size(BorshFieldType(kind="struct", struct_class=Empty))
        assert not is_zero_size(BorshFieldType(kind="struct", struct_class=Inner))
        # Malformed struct node without a class: treated as non-zero (total check)
        assert not is_zero_size(BorshFieldType(kind="struct", struct_class=None))
        # Options/enums always write their tag byte
        assert not is_zero_size(BorshFieldType(kind="option", element_type=u8))

    def test_vec_length_exceeding_remaining_rejected(self):
        """A vec claiming more elements than remaining bytes is rejected."""
        payload = (1000).to_bytes(4, "little") + b"\x00\x00"
        with pytest.raises(BorshDeserializationError, match="exceeds remaining"):
            VecU16Holder.from_borsh(payload)

    def test_hashset_length_exceeding_remaining_rejected(self):
        """The HashSet guard fires, not the slower end-of-data fallback."""
        payload = (1000).to_bytes(4, "little") + b"\x00"
        with pytest.raises(BorshDeserializationError, match="exceeds remaining"):
            StrSetHolder.from_borsh(payload)

    def test_hashmap_length_exceeding_remaining_rejected(self):
        """The HashMap guard fires, not the slower end-of-data fallback."""
        payload = (1000).to_bytes(4, "little") + b"\x00\x00"
        with pytest.raises(BorshDeserializationError, match="exceeds remaining"):
            MapHolder.from_borsh(payload)


class TestNaNDecode:
    """Spec err_if_nan applies on the read side too."""

    def test_f64_nan_bytes_rejected(self):
        payload = struct.pack("<d", math.nan)
        with pytest.raises(BorshDeserializationError):
            F64Holder.from_borsh(payload)

    def test_f32_nan_bytes_rejected(self):
        payload = struct.pack("<f", math.nan)
        with pytest.raises(BorshDeserializationError):
            F32Holder.from_borsh(payload)


class TestDuplicateCollapse:
    """Duplicate map keys / set elements on decode are accepted and collapse.

    This matches borsh-rs default behavior (strict read-side ordering would
    be a future opt-in). Documented here as a regression pin, not an
    endorsement: the re-encoding is canonical.
    """

    def test_duplicate_set_elements_collapse(self):
        raw = (3).to_bytes(4, "little") + bytes([1, 1, 1])
        m = ByteSetHolder.from_borsh(raw)
        assert m.s == {1}
        # Re-encoding collapses to the canonical single-element form.
        assert m.to_borsh() == (1).to_bytes(4, "little") + bytes([1])


class TestSchemaCache:
    """Schemas are cached per class -- without pinning classes forever."""

    def test_schema_cached_per_class(self):
        assert build_model_schema(Collections) is build_model_schema(Collections)

    def test_dynamic_model_classes_remain_collectable(self):
        """The cache must hold model classes weakly.

        Dynamically created models (pydantic.create_model, per-request
        classes) would otherwise be pinned -- classes plus cached schemas --
        for the process lifetime after a single to_borsh() call.
        """
        model_cls = create_model(
            "Ephemeral", __base__=(Borsh, BaseModel), x=(Annotated[int, U8], ...)
        )
        assert model_cls(x=1).to_borsh() == b"\x01"
        ref = weakref.ref(model_cls)
        del model_cls
        for _ in range(3):
            gc.collect()
        assert ref() is None, "schema cache is pinning dynamically created model classes"
