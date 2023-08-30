from Furious.Gui.Action import Action, Seperator
from Furious.Widget.Widget import Menu
from Furious.Utility.Constants import APP
from Furious.Utility.Utility import bootstrapIcon, Switch
from Furious.Utility.Translator import gettext as _
from Furious.Utility.StartupOnBoot import StartupOnBoot


class SettingsChildAction(Action):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def triggeredCallback(self, checked):
        if self.textCompare('Startup On Boot'):
            if checked:
                StartupOnBoot.on_()

                APP().StartupOnBoot = Switch.ON_
            else:
                StartupOnBoot.off()

                APP().StartupOnBoot = Switch.OFF
        if self.textCompare('Show Progress Bar When Connecting'):
            if checked:
                APP().ShowProgressBarWhenConnecting = Switch.ON_
            else:
                APP().ShowProgressBarWhenConnecting = Switch.OFF
        if self.textCompare('Show Tab And Spaces In Editor'):
            if checked:
                APP().ShowTabAndSpacesInEditor = Switch.ON_
            else:
                APP().ShowTabAndSpacesInEditor = Switch.OFF

            APP().ServerWidget.showTabAndSpacesIfNecessary()


class RoutingChildAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Routing Settings...'), **kwargs)

    def triggeredCallback(self, checked):
        APP().RoutesWidget.show()


class TorRelaySettingsChildAction(Action):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def triggeredCallback(self, checked):
        APP().torRelaySettingsWidget.open()


class SettingsAction(Action):
    def __init__(self):
        super().__init__(
            _('Settings'),
            icon=bootstrapIcon('gear-wide-connected.svg'),
            menu=Menu(
                SettingsChildAction(
                    _('Startup On Boot'),
                    checkable=True,
                    checked=APP().StartupOnBoot == Switch.ON_,
                ),
                SettingsChildAction(
                    _('Show Progress Bar When Connecting'),
                    checkable=True,
                    checked=APP().ShowProgressBarWhenConnecting == Switch.ON_,
                ),
                SettingsChildAction(
                    _('Show Tab And Spaces In Editor'),
                    checkable=True,
                    checked=APP().ShowTabAndSpacesInEditor == Switch.ON_,
                ),
                Seperator(),
                RoutingChildAction(),
                Seperator(),
                TorRelaySettingsChildAction(_('Tor Relay Settings...')),
            ),
            useActionGroup=False,
        )
