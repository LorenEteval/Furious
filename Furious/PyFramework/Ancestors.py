__all__ = [
    'Translatable',
    'SupportConnectedCallback',
    'SupportThemeChangedCallback',
    'SupportExitCleanup',
    'SupportImplicitReference',
]


class Translatable:
    ObjectsPool = list()

    def __init__(self, *args, **kwargs):
        self.translatable = kwargs.pop('translatable', True)

        super().__init__(*args, **kwargs)

        Translatable.ObjectsPool.append(self)

    def retranslate(self):
        raise NotImplementedError

    @staticmethod
    def retranslateAll():
        for ob in Translatable.ObjectsPool:
            assert isinstance(ob, Translatable)

            if ob.translatable:
                ob.retranslate()


class SupportConnectedCallback:
    ObjectsPool = list()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        SupportConnectedCallback.ObjectsPool.append(self)

    def disconnectedCallback(self):
        raise NotImplementedError

    def connectedCallback(self):
        raise NotImplementedError

    @staticmethod
    def callConnectedCallback():
        for ob in SupportConnectedCallback.ObjectsPool:
            assert isinstance(ob, SupportConnectedCallback)

            ob.connectedCallback()

    @staticmethod
    def callDisconnectedCallback():
        for ob in SupportConnectedCallback.ObjectsPool:
            assert isinstance(ob, SupportConnectedCallback)

            ob.disconnectedCallback()


class SupportThemeChangedCallback:
    ObjectsPool = list()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        SupportThemeChangedCallback.ObjectsPool.append(self)

    def themeChangedCallback(self, theme):
        raise NotImplementedError

    @staticmethod
    def callThemeChangedCallback(theme):
        for ob in SupportThemeChangedCallback.ObjectsPool:
            assert isinstance(ob, SupportThemeChangedCallback)

            ob.themeChangedCallback(theme)


class SupportExitCleanup:
    ObjectsPool = list()
    VisitedType = dict()

    def __init__(self, *args, **kwargs):
        self.uniqueCleanup = kwargs.pop('uniqueCleanup', True)

        super().__init__(*args, **kwargs)

        SupportExitCleanup.ObjectsPool.append(self)

    def cleanup(self):
        raise NotImplementedError

    @staticmethod
    def cleanupAll():
        for ob in SupportExitCleanup.ObjectsPool:
            assert isinstance(ob, SupportExitCleanup)

            if ob.uniqueCleanup:
                obtype = str(type(ob))

                if not SupportExitCleanup.VisitedType.get(obtype, False):
                    ob.cleanup()

                    SupportExitCleanup.VisitedType[obtype] = True
                else:
                    pass
            else:
                ob.cleanup()


class SupportImplicitReference:
    ObjectsPool = list()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        SupportImplicitReference.ObjectsPool.append(self)
