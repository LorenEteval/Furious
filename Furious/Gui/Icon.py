from PySide6.QtGui import QIcon


class Icon(QIcon):
    def __init__(self, iconFileName):
        super().__init__(iconFileName)

        self.iconFileName = iconFileName
