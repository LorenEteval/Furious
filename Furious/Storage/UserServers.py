from __future__ import annotations

from Furious.Interface import *
from Furious.PyFramework import *
from Furious.Utility import *
from Furious.Library import *

__all__ = ['UserServers']

registerAppSettings('Configuration')


class UserServers(SupportExitCleanup, StorageFactory):
    # remark, config, subsId. (subsId corresponds to unique in user subscription)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        def restore():
            try:
                return UJSONEncoder.decode(
                    PyBase64Encoder.decode(AppSettings.get('Configuration'))
                )
            except Exception:
                # Any non-exit exceptions

                return {'model': []}

        self._data = restore()
        self._list = list(
            constructFromAny(model.pop('config', ''), **model)
            for model in self._data['model']
        )

    def sync(self):
        AppSettings.set(
            'Configuration',
            PyBase64Encoder.encode(
                UJSONEncoder.encode(
                    {'model': list(factory.toStorageObject() for factory in self._list)}
                ).encode()
            ),
        )

    def data(self) -> list[ConfigurationFactory]:
        # Shallow copy
        return self._list

    def cleanup(self):
        self.sync()
