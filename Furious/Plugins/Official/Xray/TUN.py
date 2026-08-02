"""Store and apply Xray-core native TUN settings."""

from __future__ import annotations

from Furious.Frozenlib import *

import copy
import json

__all__ = [
    'DEFAULT_XRAY_TUN_SETTINGS',
    'buildXrayTUNInbound',
    'getXrayTUNSettings',
    'hasXrayTUNInbound',
    'isXrayTUNEnabled',
    'saveXrayTUNSettings',
    'setXrayTUNEnabled',
]


DEFAULT_XRAY_TUN_SETTINGS = {
    'name': '',
    'desc': '',
    'mtu': 1500,
    'gateway': ['10.0.0.1/16', 'fc00::1/64'],
    'dns': ['1.1.1.1', '8.8.8.8'],
    'userLevel': 0,
    'autoSystemRoutingTable': ['0.0.0.0/0', '::/0'],
    'autoOutboundsInterface': 'auto',
}

registerAppSettings('useXrayTUN', isBinary=True)
registerAppSettings('XrayTUNSettings')


def isXrayTUNEnabled() -> bool:
    """Return whether Xray-core should provide TUN mode."""
    return AppSettings.isStateON_('useXrayTUN')


def setXrayTUNEnabled(enabled: bool):
    """Persist whether Xray-core should provide TUN mode."""
    AppSettings.set(
        'useXrayTUN',
        AppBinarySettings.ON_ if enabled else AppBinarySettings.OFF,
    )


def _normalizedXrayTUNSettings(settings) -> dict:
    """Return validated Xray TUN settings with defaults for invalid fields."""
    result = copy.deepcopy(DEFAULT_XRAY_TUN_SETTINGS)
    if not isinstance(settings, dict):
        return result

    for key in ('name', 'desc', 'autoOutboundsInterface'):
        value = settings.get(key)
        if isinstance(value, str):
            result[key] = value.strip()

    for key in ('gateway', 'dns', 'autoSystemRoutingTable'):
        value = settings.get(key)
        if isinstance(value, (list, tuple)):
            result[key] = [
                item.strip() for item in value if isinstance(item, str) and item.strip()
            ]

    mtu = settings.get('mtu')
    if isinstance(mtu, int) and not isinstance(mtu, bool) and mtu > 0:
        result['mtu'] = mtu

    userLevel = settings.get('userLevel')
    if (
        isinstance(userLevel, int)
        and not isinstance(userLevel, bool)
        and userLevel >= 0
    ):
        result['userLevel'] = userLevel

    return result


def getXrayTUNSettings() -> dict:
    """Return a validated copy of the persisted Xray TUN settings."""
    try:
        settings = json.loads(AppSettings.get('XrayTUNSettings'))
    except Exception:
        settings = None

    return _normalizedXrayTUNSettings(settings)


def saveXrayTUNSettings(settings: dict):
    """Validate and persist Xray TUN settings."""
    AppSettings.set(
        'XrayTUNSettings',
        json.dumps(_normalizedXrayTUNSettings(settings), ensure_ascii=False),
    )


def buildXrayTUNInbound(settings=None) -> dict:
    """Build an Xray TUN inbound from persisted or supplied settings."""
    settings = _normalizedXrayTUNSettings(
        getXrayTUNSettings() if settings is None else settings
    )
    settings = {
        key: value for key, value in settings.items() if value != '' and value != []
    }

    return {
        'tag': 'tun',
        'protocol': 'tun',
        'settings': settings,
        'sniffing': {
            'enabled': True,
            'destOverride': ['http', 'tls', 'quic'],
        },
    }


def hasXrayTUNInbound(config) -> bool:
    """Return whether an Xray configuration contains a TUN inbound."""
    inbounds = config.get('inbounds', [])
    if not isinstance(inbounds, list):
        return False

    return any(
        isinstance(inbound, dict)
        and str(inbound.get('protocol', '')).casefold() == 'tun'
        for inbound in inbounds
    )
