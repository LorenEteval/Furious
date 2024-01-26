from Furious.PyFramework import *

__all__ = ['QBlockSignals', 'QTranslatable']


class QProtection:
    def __init__(self, qobject):
        assert hasattr(qobject, 'setDisabled')

        self.qobject = qobject

    def __enter__(self):
        self.qobject.setDisabled(True)

    def __exit__(self, exceptionType, exceptionValue, tb):
        self.qobject.setDisabled(False)


class QBlockSignals:
    def __init__(self, qobject):
        assert hasattr(qobject, 'blockSignals')

        self.qobject = qobject

    def __enter__(self):
        self.qobject.blockSignals(True)

    def __exit__(self, exceptionType, exceptionValue, tb):
        self.qobject.blockSignals(False)


class QTranslatable(Translatable):
    def __init__(self, *args, **kwargs):
        self.useQProtection = kwargs.pop('useQProtection', True)

        super().__init__(*args, **kwargs)

    def retranslate(self):
        raise NotImplementedError

    @staticmethod
    def retranslateAll():
        for ob in QTranslatable.ObjectsPool:
            assert isinstance(ob, QTranslatable)

            if ob.translatable:
                if ob.useQProtection:
                    with QProtection(ob):
                        ob.retranslate()
                else:
                    ob.retranslate()
