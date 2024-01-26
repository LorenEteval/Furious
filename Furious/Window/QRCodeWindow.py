from Furious.Interface import *
from Furious.PyFramework import *
from Furious.QtFramework import *
from Furious.QtFramework import gettext as _
from Furious.Utility import *

from PySide6 import QtCore
from PySide6.QtGui import *
from PySide6.QtWidgets import *

import io
import pyqrcode

__all__ = ['QRCodeWindow']


class QRCodeWindow(SupportImplicitReference, AppQMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_(APPLICATION_NAME))
        self.setFixedSize(640, 640)

        self.tabWidget = QTabWidget(self)
        self.tabWidget.setTabsClosable(True)
        self.tabWidget.tabCloseRequested.connect(self.handleTabCloseRequested)

        self.setCentralWidget(self.tabWidget)

    def clear(self):
        self.tabWidget.clear()

    def initTabByIndex(self, indexes):
        self.clear()

        for index in indexes:
            qrdata = io.BytesIO()

            config = AS_UserServers()[index]

            qrcode = pyqrcode.create(config.toURI())
            qrcode.png(qrdata, scale=5)

            pixmap = QPixmap()
            pixmap.loadFromData(qrdata.getvalue(), 'PNG')

            widget = QLabel(parent=self.tabWidget)
            widget.setPixmap(pixmap)

            self.tabWidget.addTab(
                widget, f'{index + 1} - ' + config.getExtras('remark')
            )

    @QtCore.Slot(int)
    def handleTabCloseRequested(self, index):
        self.tabWidget.removeTab(index)

        if self.tabWidget.count() == 0:
            self.hide()
