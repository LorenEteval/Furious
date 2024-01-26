from Furious.QtFramework import *
from Furious.QtFramework import gettext as _
from Furious.Utility import *

from typing import Union

__all__ = ['SettingsAction']

registerAppSettings('VPNMode', isBinary=True)
registerAppSettings('StartupOnBoot', isBinary=True)
registerAppSettings('ShowProgressBarWhenConnecting', isBinary=True)
registerAppSettings('ShowTabAndSpacesInEditor', isBinary=True)


class VPNModeAction(AppQAction):
    def __init__(self, **kwargs):
        if isAdministrator():
            super().__init__(_('VPN Mode'), **kwargs)
        else:
            super().__init__(_(f'VPN Mode Disabled ({ADMINISTRATOR_NAME})'), **kwargs)

            self.setDisabled(True)

    def triggeredCallback(self, checked):
        pass


class SettingsChildAction(AppQAction):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def triggeredCallback(self, checked):
        if self.textCompare('Startup On Boot'):
            if checked:
                StartupOnBoot.on_()

                AppSettings.turnON_('StartupOnBoot')
            else:
                StartupOnBoot.off()

                AppSettings.turnOFF('StartupOnBoot')
        if self.textCompare('Show Progress Bar When Connecting'):
            if checked:
                AppSettings.turnON_('ShowProgressBarWhenConnecting')
            else:
                AppSettings.turnOFF('ShowProgressBarWhenConnecting')
        if self.textCompare('Show Tab And Spaces In Editor'):
            if checked:
                AppSettings.turnON_('ShowTabAndSpacesInEditor')
            else:
                AppSettings.turnOFF('ShowTabAndSpacesInEditor')

            # Reference
            # ServerWidget = APP().ServerWidget
            #
            # currentFocus = ServerWidget.currentFocus
            #
            # if currentFocus >= 0:
            #     ServerWidget.saveScrollBarValue(currentFocus)
            #
            # ServerWidget.showTabAndSpacesIfNecessary()
            #
            # if currentFocus >= 0:
            #     ServerWidget.restoreScrollBarValue(currentFocus)


class SettingsAction(AppQAction):
    def __init__(self):
        if PLATFORM == 'Windows' or PLATFORM == 'Darwin':
            extraActions = [
                VPNModeAction(
                    checkable=True,
                    checked=AppSettings.isStateON_('VPNMode'),
                ),
                AppQSeperator(),
            ]
        else:
            extraActions = [None]

        super().__init__(
            _('Settings'),
            icon=bootstrapIcon('gear-wide-connected.svg'),
            menu=AppQMenu(
                *extraActions,
                SettingsChildAction(
                    _('Startup On Boot'),
                    checkable=True,
                    checked=AppSettings.isStateON_('StartupOnBoot'),
                ),
                SettingsChildAction(
                    _('Show Progress Bar When Connecting'),
                    checkable=True,
                    checked=AppSettings.isStateON_('ShowProgressBarWhenConnecting'),
                ),
                SettingsChildAction(
                    _('Show Tab And Spaces In Editor'),
                    checkable=True,
                    checked=AppSettings.isStateON_('ShowTabAndSpacesInEditor'),
                ),
            ),
            useActionGroup=False,
        )

    def getVPNModeAction(self) -> Union[AppQAction, None]:
        if PLATFORM == 'Windows' or PLATFORM == 'Darwin':
            # 1st action
            return self._menu.actions()[0]
        else:
            return None
