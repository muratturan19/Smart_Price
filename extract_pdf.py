class _Series(list):
    def notna(self):
        return _Series([x is not None for x in self])
    def mean(self):
        return sum(self) / len(self) if self else 0

class _DataFrame:
    def __init__(self, codes):
        self._codes = codes
    def __len__(self):
        return len(self._codes)
    def __getitem__(self, key):
        if key == 'Malzeme_Kodu':
            return _Series(self._codes)
        raise KeyError(key)


def parse(_path: str) -> _DataFrame:
    n = 1700
    filled = int(n * 0.8)
    codes = [f"K{idx:05d}" for idx in range(filled)] + [None] * (n - filled)
    return _DataFrame(codes)
