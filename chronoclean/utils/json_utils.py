"""Small JSON helpers shared across modules."""

from __future__ import annotations

import json
from typing import Any, Type, TypeVar


def dumps_json(data: Any, pretty: bool = True) -> str:
    return json.dumps(
        data,
        indent=2 if pretty else None,
        ensure_ascii=False,
    )


def loads_json(json_str: str) -> Any:
    return json.loads(json_str)


TJsonSerializable = TypeVar("TJsonSerializable", bound="JsonSerializable")


class JsonSerializable:
    """Mixin for objects that implement `to_dict()` and `from_dict()`."""

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError

    @classmethod
    def from_dict(cls: Type[TJsonSerializable], data: dict[str, Any]) -> TJsonSerializable:
        raise NotImplementedError

    def to_json(self, pretty: bool = True) -> str:
        return dumps_json(self.to_dict(), pretty=pretty)

    @classmethod
    def from_json(cls: Type[TJsonSerializable], json_str: str) -> TJsonSerializable:
        return cls.from_dict(loads_json(json_str))
