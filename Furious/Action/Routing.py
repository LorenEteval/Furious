from Furious.Gui.Action import Action
from Furious.Widget.Widget import Menu
from Furious.Utility.Utility import Switch, bootstrapIcon
from Furious.Utility.Translator import gettext as _

from PySide6.QtWidgets import QApplication

SUPPORTED_ROUTING = ('Bypass', 'Global', 'Custom')

SUPPORTED_ROUTING_DETAIL = {
    'Bypass': 'Bypass Mainland China',
    'Global': 'Global',
    'Custom': 'Custom',
}


class RoutingChildAction(Action):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def triggeredCallback(self, checked):
        for key, value in SUPPORTED_ROUTING_DETAIL.items():
            if self.textCompare(value):
                if QApplication.instance().Routing != key:
                    QApplication.instance().Routing = key

                    if QApplication.instance().tray.ConnectAction.isConnected():
                        # Connected. Re-configure connection
                        QApplication.instance().tray.ConnectAction.connectingAction(
                            showProgressBar=False,
                            showRoutingChangedMessage=True,
                        )


class RoutingAction(Action):
    def __init__(self):
        super().__init__(
            _('Routing'),
            icon=bootstrapIcon('shuffle.svg'),
            menu=Menu(
                *list(
                    RoutingChildAction(
                        _(SUPPORTED_ROUTING_DETAIL[mode]),
                        checkable=True,
                        checked=mode == QApplication.instance().Routing,
                    )
                    for mode in SUPPORTED_ROUTING
                ),
            ),
        )
