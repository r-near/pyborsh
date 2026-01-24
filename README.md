# PyBorsh

[![CI](https://github.com/r-near/pyborsh/actions/workflows/ci.yml/badge.svg)](https://github.com/r-near/pyborsh/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/r-near/pyborsh/branch/main/graph/badge.svg)](https://codecov.io/gh/r-near/pyborsh)
[![PyPI version](https://badge.fury.io/py/pyborsh.svg)](https://badge.fury.io/py/pyborsh)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

Pydantic-native [Borsh](https://borsh.io/) serialization for Python.

## Features

- 🎯 **Pydantic-native**: Use standard Pydantic models - all features work
- 🔒 **Type-safe**: Explicit width annotations for integers (`U8`, `U32`, `U128`, etc.)
- ⚡ **Fast**: Direct binary serialization without intermediate formats
- 🦀 **Rust-compatible**: 100% compatible with Rust's `borsh` crate

## Installation

```bash
pip install pyborsh
```

## Quick Start

```python
from pydantic import BaseModel
from typing import Annotated
from pyborsh import Borsh, U8, U16, U32, U64, U128, Bytes

class Player(Borsh, BaseModel):
    name: str
    health: Annotated[int, U8]
    balance: Annotated[int, U128]
    scores: list[Annotated[int, U16]]
    guild: str | None
    pubkey: Annotated[bytes, Bytes(32)]

# Create instance (standard Pydantic)
player = Player(
    name="Alice",
    health=100,
    balance=1_000_000_000,
    scores=[100, 95, 98],
    guild="Warriors",
    pubkey=bytes(32),
)

# Pydantic features work
player.model_dump()
player.model_dump_json()

# Borsh serialization
data = player.to_borsh()
player2 = Player.from_borsh(data)
assert player == player2
```

## Documentation

See the [documentation](https://github.com/r-near/pyborsh#readme) for full details.

## License

MIT
