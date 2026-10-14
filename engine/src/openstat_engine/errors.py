"""Locale-independent domain errors shared by CLI and RPC."""


class EngineError(Exception):
    def __init__(self, key: str, code: int = -32001) -> None:
        self.key = key
        self.code = code
        super().__init__(key)
