

class _LazyModule:
    """Import a heavy module (torch, SB3) on first attribute use, so the read-only studio starts small."""

    def __init__(self, name: str):
        self._name = name

    def __getattr__(self, attr):
        import importlib
        return getattr(importlib.import_module(self._name), attr)
