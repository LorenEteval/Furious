from Furious.Utility.Constants import *

import time

__all__ = ['PySide6LegacyEnumValueWrapper', 'PySide6LegacyEventLoopWait']


def PySide6LegacyEnumValueWrapper(enum):
    # Protect PySide6 enum wrapper behavior changes
    if PYSIDE6_VERSION < '6.2.2':
        return enum
    else:
        return enum.value


def PySide6LegacyEventLoopWait(ms):
    # Protect qWait method does not exist in some
    # old PySide6 version
    if PYSIDE6_VERSION < '6.3.1':
        for counter in range(0, ms, 10):
            time.sleep(10 / 1000)

            APP().processEvents()
    else:
        from PySide6.QtTest import QTest

        QTest.qWait(ms)

        APP().processEvents()
