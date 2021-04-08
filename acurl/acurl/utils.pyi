from collections import defaultdict
from typing import MutableMapping, TypeVar

_K = TypeVar("_K")
_V = TypeVar("_V")

class _CaseInsensitiveDict(MutableMapping[_K, _V]):
    @staticmethod
    def _k(key: _K) -> _K: ...
    def _convert_keys(self) -> None: ...

class CaseInsensitiveDict(_CaseInsensitiveDict[_K, _V], dict[_K, _V]):
    ...

class CaseInsensitiveDefaultDict(_CaseInsensitiveDict[_K, _V], defaultdict[_K, _V]):
    ...
