from __future__ import annotations

__all__ = ['ApplicationFactory']


class ApplicationFactory:
    class ExitCode:
        ExitSuccess = 0
        UnknownException = 1
        PlatformNotSupported = 2
        AssertionError = 3

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run(self):
        raise NotImplementedError
