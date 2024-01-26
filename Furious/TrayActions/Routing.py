from Furious.QtFramework import *
from Furious.QtFramework import gettext as _
from Furious.Utility import *

__all__ = ['RoutingAction']

BUILTIN_ROUTING = ['Bypass Mainland China', 'Bypass Iran', 'Global', 'Custom']

registerAppSettings('Routing', validRange=BUILTIN_ROUTING)


class RoutingChildAction(AppQAction):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def triggeredCallback(self, checked):
        pass


class RoutingAction(AppQAction):
    def __init__(self):
        if AppSettings.get('Routing') == 'Bypass':
            # Update value for backward compatibility
            AppSettings.set('Routing', 'Bypass Mainland China')

        super().__init__(
            _('Routing'),
            icon=bootstrapIcon('shuffle.svg'),
            menu=AppQMenu(
                *list(
                    RoutingChildAction(
                        _(routing),
                        checkable=True,
                        checked=AppSettings.get('Routing') == routing,
                    )
                    for routing in BUILTIN_ROUTING
                ),
            ),
        )
