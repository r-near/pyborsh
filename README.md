# PyBorsh

[![CI](https://github.com/r-near/pyborsh/actions/workflows/ci.yml/badge.svg)](https://github.com/r-near/pyborsh/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/r-near/pyborsh/branch/main/graph/badge.svg)](https://codecov.io/gh/r-near/pyborsh)
[![PyPI version](https://badge.fury.io/py/pyborsh.svg)](https://pypi.org/project/pyborsh/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Pydantic-native [Borsh](https://borsh.io/) serialization for Python.**

PyBorsh lets you define data structures using standard Pydantic models and serialize them to the Borsh binary format—the same format used by Solana, NEAR, and other blockchain ecosystems.

## Features

- 🎯 **Pydantic-native** — Use standard Pydantic models with full validation, JSON export, and all other Pydantic features
- 🔒 **Type-safe** — Explicit integer width annotations (`U8`, `U32`, `U128`, etc.) prevent overflow bugs
- ⚡ **Fast** — Direct binary serialization without intermediate representations
- 🦀 **Rust-compatible** — 100% compatible with Rust's `borsh` crate for cross-language interop

## Installation

```bash
pip install pyborsh
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv add pyborsh
```

## Quick Start

```python
from typing import Annotated
from pydantic import BaseModel
from pyborsh import Borsh, U8, U32, U128, Bytes

class Player(Borsh, BaseModel):
    name: str
    health: Annotated[int, U8]       # u8: 0-255
    score: Annotated[int, U32]       # u32: 0-4,294,967,295
    balance: Annotated[int, U128]    # u128: for large numbers
    guild: str | None                # Option<String>
    pubkey: Annotated[bytes, Bytes(32)]  # [u8; 32] fixed-size

# Create a player (standard Pydantic)
player = Player(
    name="Alice",
    health=100,
    score=50_000,
    balance=1_000_000_000_000_000_000,
    guild="Warriors",
    pubkey=bytes(32),
)

# All Pydantic features work
player.model_dump()
player.model_dump_json()
Player.model_validate({"name": "Bob", ...})

# Borsh serialization
data: bytes = player.to_borsh()
restored = Player.from_borsh(data)
assert player == restored
```

## Type Mapping

PyBorsh maps Python types to Borsh types:

| Python Type | Borsh Type | Notes |
|-------------|------------|-------|
| `Annotated[int, U8]` | `u8` | Unsigned 8-bit |
| `Annotated[int, U16]` | `u16` | Unsigned 16-bit |
| `Annotated[int, U32]` | `u32` | Unsigned 32-bit |
| `Annotated[int, U64]` | `u64` | Unsigned 64-bit |
| `Annotated[int, U128]` | `u128` | Unsigned 128-bit |
| `Annotated[int, I8]` | `i8` | Signed 8-bit |
| `Annotated[int, I16]` | `i16` | Signed 16-bit |
| `Annotated[int, I32]` | `i32` | Signed 32-bit |
| `Annotated[int, I64]` | `i64` | Signed 64-bit |
| `Annotated[int, I128]` | `i128` | Signed 128-bit |
| `Annotated[float, F32]` | `f32` | 32-bit float |
| `float` | `f64` | 64-bit float (default) |
| `bool` | `bool` | Boolean |
| `str` | `String` | UTF-8 string |
| `bytes` | `Vec<u8>` | Dynamic bytes |
| `Annotated[bytes, Bytes(N)]` | `[u8; N]` | Fixed-size bytes |
| `list[T]` | `Vec<T>` | Dynamic array |
| `Annotated[list[T], Array(T, N)]` | `[T; N]` | Fixed-size array |
| `set[T]` | `HashSet<T>` | Hash set |
| `dict[K, V]` | `HashMap<K, V>` | Hash map |
| `tuple[A, B, C]` | `(A, B, C)` | Fixed tuple |
| `T \| None` | `Option<T>` | Optional value |
| `NestedModel` | `struct` | Nested struct |
| `IntEnum` | `u8` | Simple enum |
| `BorshEnum` variants | `enum` | Rust-style tagged union |

## Examples

### Collections

```python
from typing import Annotated
from pydantic import BaseModel
from pyborsh import Borsh, U8, U16, U32, Array

class GameState(Borsh, BaseModel):
    # Vec<u16> - dynamic list
    scores: list[Annotated[int, U16]]

    # [u8; 4] - fixed array
    color: Annotated[list[int], Array(U8, 4)]

    # HashMap<String, u32>
    inventory: dict[str, Annotated[int, U32]]

    # HashSet<String>
    tags: set[str]

    # (u8, String, u32) - heterogeneous tuple
    metadata: tuple[Annotated[int, U8], str, Annotated[int, U32]]
```

### Nested Structs

```python
class Stats(Borsh, BaseModel):
    strength: Annotated[int, U8]
    agility: Annotated[int, U8]
    intelligence: Annotated[int, U8]

class Character(Borsh, BaseModel):
    name: str
    stats: Stats                    # Nested struct
    ally: Stats | None              # Optional nested struct
    party: list[Stats]              # Vec of structs
```

### Rust-Style Enums (Tagged Unions)

For Rust enums with associated data, use `BorshEnum`:

```python
from typing import Literal
from pydantic import BaseModel
from pyborsh import Borsh, BorshEnum, U32, U64

class Message(BorshEnum):
    """Equivalent to Rust:
    enum Message {
        Quit,
        Move { x: u32, y: u32 },
        Write(String),
        ChangeColor(u8, u8, u8),
    }
    """
    class Quit(Borsh, BaseModel):
        variant: Literal["Quit"] = "Quit"

    class Move(Borsh, BaseModel):
        variant: Literal["Move"] = "Move"
        x: Annotated[int, U32]
        y: Annotated[int, U32]

    class Write(Borsh, BaseModel):
        variant: Literal["Write"] = "Write"
        message: str

class Packet(Borsh, BaseModel):
    id: Annotated[int, U64]
    payload: Message.Quit | Message.Move | Message.Write

# Usage
packet = Packet(
    id=1,
    payload=Message.Move(x=10, y=20)
)
data = packet.to_borsh()
```

### Simple Enums

For simple enums without data, use `IntEnum`:

```python
from enum import IntEnum
from typing import Annotated
from pydantic import BaseModel
from pyborsh import Borsh, U32

class Status(IntEnum):
    PENDING = 0
    ACTIVE = 1
    COMPLETED = 2

class Task(Borsh, BaseModel):
    id: Annotated[int, U32]
    status: Status  # Serialized as u8
```

## Rust Interoperability

PyBorsh produces byte-for-byte identical output to Rust's `borsh` crate:

**Rust:**
```rust
use borsh::{BorshSerialize, BorshDeserialize};

#[derive(BorshSerialize, BorshDeserialize)]
struct Player {
    name: String,
    health: u8,
    balance: u128,
}

let player = Player {
    name: "Alice".to_string(),
    health: 100,
    balance: 1_000_000_000,
};
let bytes = borsh::to_vec(&player).unwrap();
```

**Python:**
```python
class Player(Borsh, BaseModel):
    name: str
    health: Annotated[int, U8]
    balance: Annotated[int, U128]

player = Player(name="Alice", health=100, balance=1_000_000_000)
data = player.to_borsh()
# `data` is identical to Rust's `bytes`
```

## Error Handling

PyBorsh provides descriptive errors:

```python
from pyborsh import BorshSchemaError, BorshSerializationError, BorshDeserializationError

# Schema errors (at definition time)
class Bad(Borsh, BaseModel):
    value: int  # Error: int requires explicit width (use U8, U32, etc.)

# Serialization errors
player = Player(health=256, ...)  # Error: 256 out of range for u8

# Deserialization errors
Player.from_borsh(b"corrupted")  # Error: Unexpected end of data
```

## Development

```bash
# Clone and install
git clone https://github.com/r-near/pyborsh.git
cd pyborsh
uv sync --all-extras

# Run tests
uv run pytest

# Run linting
uv run ruff check src/ tests/
uv run mypy src/

# Install pre-commit hooks
uv run pre-commit install
```

## License

MIT
