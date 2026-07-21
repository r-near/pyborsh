"""Hypothesis strategies derived from pyborsh's own schema introspection.

The core idea: ``build_model_schema`` already describes any Borsh-serializable
Pydantic model as a tree of ``BorshFieldType`` nodes. ``strategy_for`` walks
that tree and maps each node to a hypothesis strategy for valid Python values
of that field, so ``models(SomeModel)`` generates valid instances of *any*
Borsh model for free -- no per-model strategy code. Adding a field (or a whole
new model) automatically extends the generated test space.

Collections are kept small (``MAX_COLLECTION_SIZE``): the properties under
test are structural (framing, ordering, error contracts), not about bulk data.
"""

from typing import Any

from hypothesis import strategies as st

from pyborsh.schema import BorshFieldType, build_model_schema

# Keep collections small; the interesting behavior is structural, not bulk.
MAX_COLLECTION_SIZE = 4


def strategy_for(ft: BorshFieldType) -> st.SearchStrategy[Any]:  # noqa: C901, PLR0911, PLR0912
    """Map a ``BorshFieldType`` node to a strategy for valid field values."""
    kind = ft.kind
    if kind[0] == "u" and kind[1:].isdigit():
        bits = int(kind[1:])
        return st.integers(min_value=0, max_value=2**bits - 1)
    if kind[0] == "i" and kind[1:].isdigit():
        bits = int(kind[1:])
        return st.integers(min_value=-(2 ** (bits - 1)), max_value=2 ** (bits - 1) - 1)
    if kind == "f32":
        # width=32 -> exactly representable as f32, so round-trips are lossless.
        # NaN is excluded: the Borsh spec forbids it (err_if_nan); the NaN
        # error paths are probed by dedicated tests instead.
        return st.floats(width=32, allow_nan=False)
    if kind == "f64":
        return st.floats(allow_nan=False)
    if kind == "bool":
        return st.booleans()
    if kind == "string":
        return st.text(max_size=8)
    if kind == "dynamic_bytes":
        return st.binary(max_size=8)
    if kind == "fixed_bytes":
        assert ft.length is not None
        return st.binary(min_size=ft.length, max_size=ft.length)
    if kind == "option":
        assert ft.element_type is not None
        return st.none() | strategy_for(ft.element_type)
    if kind == "vec":
        assert ft.element_type is not None
        return st.lists(strategy_for(ft.element_type), max_size=MAX_COLLECTION_SIZE)
    if kind == "hashset":
        assert ft.element_type is not None
        return st.frozensets(strategy_for(ft.element_type), max_size=MAX_COLLECTION_SIZE)
    if kind == "hashmap":
        assert ft.key_type is not None
        assert ft.value_type is not None
        return st.dictionaries(
            strategy_for(ft.key_type),
            strategy_for(ft.value_type),
            max_size=MAX_COLLECTION_SIZE,
        )
    if kind == "fixed_array":
        assert ft.element_type is not None
        assert ft.length is not None
        return st.lists(strategy_for(ft.element_type), min_size=ft.length, max_size=ft.length)
    if kind == "tuple":
        assert ft.tuple_element_types is not None
        return st.tuples(*(strategy_for(t) for t in ft.tuple_element_types))
    if kind == "struct":
        assert ft.struct_class is not None
        return models(ft.struct_class)
    if kind == "enum":
        assert ft.enum_class is not None
        return st.sampled_from(list(ft.enum_class))  # type: ignore[call-overload]
    if kind == "borsh_enum":
        assert ft.variant_types is not None
        return st.one_of(*(models(v) for v in ft.variant_types))
    raise NotImplementedError(kind)


def models(model_cls: type) -> st.SearchStrategy[Any]:
    """Strategy generating valid instances of any ``Borsh + BaseModel`` class.

    ``literal`` fields (BorshEnum variant discriminators) are skipped: they
    carry model defaults and are never serialized.
    """
    schema = build_model_schema(model_cls)
    return st.builds(
        model_cls,
        **{name: strategy_for(ft) for name, ft in schema.items() if ft.kind != "literal"},
    )
