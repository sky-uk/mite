from __future__ import annotations

from abc import ABCMeta
from collections import defaultdict
from typing import DefaultDict, Dict, MutableMapping, TypeVar

_K = TypeVar("_K")
_V = TypeVar("_V")

class _CaseInsensitiveDict(MutableMapping[_K, _V], metaclass=ABCMeta):
    @staticmethod
    def _k(key: _K) -> _K: ...
    def _convert_keys(self) -> None: ...

class CaseInsensitiveDict(_CaseInsensitiveDict[_K, _V], Dict[_K, _V]):
    ...

class CaseInsensitiveDefaultDict(_CaseInsensitiveDict[_K, _V], Defaultdict[_K, _V]):
    ...
