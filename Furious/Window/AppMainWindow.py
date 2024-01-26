from Furious.Interface import *
from Furious.QtFramework import *
from Furious.QtFramework import gettext as _
from Furious.Library import *
from Furious.Utility import *
from Furious.Widget.UserServersQTableWidget import *
from Furious.Window.UserSubsWindow import *
from Furious.Window.LogViewerWindow import *

from PySide6 import QtWidgets
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from PySide6.QtNetwork import *

__all__ = ['AppMainWindow']

registerAppSettings('ServerWidgetWindowSize')


class AppMainWindow(AppQMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_(APPLICATION_NAME))

        self.userServersQTableWidget = UserServersQTableWidget()
        self.userSubsWindow = UserSubsWindow(
            deleteUniqueCallback=lambda unique: self.userServersQTableWidget.deleteItemByIndex(
                list(
                    index
                    for index, server in enumerate(AS_UserServers())
                    if server.getExtras('subsId') == unique
                )
            )
        )

        self.mainTab = AppQTabWidget()
        self.mainTab.addTab(self.userServersQTableWidget, _('Server'))

        self.toolbar = AppQToolBar(
            _('My Tool Bar'),
            AppQAction(
                _('File'),
                icon=bootstrapIcon('folder2-open.svg'),
                useActionGroup=False,
                checkable=True,
                # TODO
                statusTip=_('This is your button'),
            ),
            AppQSeperator(),
            AppQAction(
                _('Subscription'),
                icon=bootstrapIcon('star.svg'),
                menu=AppQMenu(
                    AppQAction(
                        _('Update Subscription (Use Current Proxy)'),
                        parent=self,
                        callback=lambda: self.userServersQTableWidget.updateSubs(
                            # TODO
                            '127.0.0.1:10809'
                        ),
                    ),
                    AppQAction(
                        _('Update Subscription (Force Proxy)'),
                        parent=self,
                        callback=lambda: self.userServersQTableWidget.updateSubs(
                            '127.0.0.1:10809'
                        ),
                    ),
                    AppQAction(
                        _('Update Subscription (No Proxy)'),
                        parent=self,
                        callback=lambda: self.userServersQTableWidget.updateSubs(None),
                    ),
                    AppQSeperator(),
                    AppQAction(
                        _('Edit Subscription...'),
                        parent=self,
                        callback=lambda: self.userSubsWindow.show(),
                    ),
                ),
                useActionGroup=False,
                checkable=False,
                # TODO
                statusTip=_('This is your button'),
            ),
            AppQSeperator(),
            AppQAction(
                _('Log'),
                icon=bootstrapIcon('layout-text-sidebar-reverse.svg'),
                menu=AppQMenu(
                    AppQAction(
                        _('Show Log'),
                        parent=self,
                        callback=lambda: APP().appLogViewerWindow.showMaximized(),
                    ),
                ),
                useActionGroup=False,
                checkable=False,
                # TODO
                statusTip=_('This is your button'),
            ),
        )
        self.toolbar.setIconSize(QtCore.QSize(64, 32))
        self.toolbar.setToolButtonStyle(
            QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon
        )
        self.addToolBar(self.toolbar)

        self.setStatusBar(QStatusBar(self))

        # TODO
        self.lineColumnLabel = AppQLabel('1:1 0', translatable=False)
        self.statusBar().addPermanentWidget(self.lineColumnLabel)

        self._widget = QWidget()
        self._layout = QVBoxLayout(self._widget)
        self._layout.addWidget(self.mainTab)

        self.setCentralWidget(self._widget)

    def appendNewItemByFactory(self, factory: ConfigurationFactory):
        self.userServersQTableWidget.appendNewItemByFactory(factory)

    def setWidthAndHeight(self):
        try:
            windowSize = AppSettings.get('ServerWidgetWindowSize').split(',')

            self.setGeometry(100, 100, *list(int(size) for size in windowSize))
        except Exception:
            # Any non-exit exceptions

            self.setGeometry(100, 100, 1800, 960)

    def cleanup(self):
        AppSettings.set(
            'ServerWidgetWindowSize',
            f'{self.geometry().width()},{self.geometry().height()}',
        )
