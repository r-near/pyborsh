"""Custom exceptions for PyBorsh."""


class BorshError(Exception):
    """Base exception for all Borsh errors."""


class BorshSchemaError(BorshError):
    """
    Raised when a model has an invalid Borsh schema.

    Examples:
        - Field with bare `int` type without width annotation
        - Unsupported type in schema
        - Invalid enum definition
    """


class BorshSerializationError(BorshError):
    """
    Raised during serialization failures.

    Examples:
        - Value out of range for type (e.g., 256 for U8)
        - Fixed-size bytes with wrong length
    """


class BorshDeserializationError(BorshError):
    """
    Raised during deserialization failures.

    Examples:
        - Unexpected end of data
        - Invalid UTF-8 in string
        - Invalid enum variant index
    """
