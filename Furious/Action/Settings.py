from Furious.Gui.Action import Action
from Furious.Widget.Widget import Menu
from Furious.Utility.Utility import bootstrapIcon, Switch
from Furious.Utility.Translator import gettext as _
from Furious.Utility.StartupOnBoot import StartupOnBoot

from PySide6.QtWidgets import QApplication


class SettingsChildAction(Action):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def triggeredCallback(self, checked):
        if self.textCompare('Startup On Boot'):
            if checked:
                StartupOnBoot.on_()

                QApplication.instance().StartupOnBoot = Switch.ON_
            else:
                StartupOnBoot.off()

                QApplication.instance().StartupOnBoot = Switch.OFF
        if self.textCompare('Show Progress Bar When Connecting'):
            if checked:
                QApplication.instance().ShowProgressBarWhenConnecting = Switch.ON_
            else:
                QApplication.instance().ShowProgressBarWhenConnecting = Switch.OFF
        if self.textCompare('Show Tab And Spaces In Editor'):
            if checked:
                QApplication.instance().ShowTabAndSpacesInEditor = Switch.ON_
            else:
                QApplication.instance().ShowTabAndSpacesInEditor = Switch.OFF

            QApplication.instance().MainWidget.showTabAndSpacesIfNecessary()


class SettingsAction(Action):
    def __init__(self):
        super().__init__(
            _('Settings'),
            icon=bootstrapIcon('gear-wide-connected.svg'),
            menu=Menu(
                SettingsChildAction(
                    _('Startup On Boot'),
                    checkable=True,
                    checked=QApplication.instance().StartupOnBoot == Switch.ON_,
                ),
                SettingsChildAction(
                    _('Show Progress Bar When Connecting'),
                    checkable=True,
                    checked=QApplication.instance().ShowProgressBarWhenConnecting
                    == Switch.ON_,
                ),
                SettingsChildAction(
                    _('Show Tab And Spaces In Editor'),
                    checkable=True,
                    checked=QApplication.instance().ShowTabAndSpacesInEditor
                    == Switch.ON_,
                ),
            ),
            useActionGroup=False,
        )
