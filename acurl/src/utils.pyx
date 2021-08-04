from collections import defaultdict


class _CaseInsensitiveDict:
    # Based on https://stackoverflow.com/a/32888599 but tweaked for python3
    @staticmethod
    def _k(key):
        return key.lower() if isinstance(key, str) else key

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._convert_keys()

    def __getitem__(self, key):
        return super().__getitem__(self._k(key))

    def __setitem__(self, key, value):
        super().__setitem__(self._k(key), value)

    def __delitem__(self, key):
        return super().__delitem__(self._k(key))

    def __contains__(self, key):
        return super().__contains__(self._k(key))

    def pop(self, key, *args, **kwargs):
        return super().pop(self._k(key), *args, **kwargs)

    def popitem(self, *args, **kwargs):
        return super().popitem(*args, **kwargs)

    def get(self, key, *args, **kwargs):
        return super().get(self._k(key), *args, **kwargs)

    def setdefault(self, key, *args, **kwargs):
        return super().setdefault(self._k(key), *args, **kwargs)

    def update(self, E=None, **F):
        super().update(self.__class__(E, **F))

    def _convert_keys(self):
        for k in list(self.keys()):
            v = super().pop(k)
            self.__setitem__(k, v)


class CaseInsensitiveDict(_CaseInsensitiveDict, dict):
    pass


class CaseInsensitiveDefaultDict(_CaseInsensitiveDict, defaultdict):
    pass
