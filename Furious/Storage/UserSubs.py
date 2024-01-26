from __future__ import annotations

from Furious.Interface import *
from Furious.PyFramework import *
from Furious.Utility import *
from Furious.Library import *

__all__ = ['UserSubs']

registerAppSettings('CustomSubscription')


class UserSubs(SupportExitCleanup, StorageFactory):
    # unique: remark, webURL
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        def restore():
            try:
                return UJSONEncoder.decode(
                    PyBase64Encoder.decode(AppSettings.get('CustomSubscription'))
                )
            except Exception:
                # Any non-exit exceptions

                return {}

        self._data = restore()

    def sync(self):
        AppSettings.set(
            'CustomSubscription',
            PyBase64Encoder.encode(
                UJSONEncoder.encode(self._data).encode(),
            ),
        )

    def data(self) -> dict[str, dict]:
        # Shallow copy
        return self._data

    def cleanup(self):
        self.sync()
