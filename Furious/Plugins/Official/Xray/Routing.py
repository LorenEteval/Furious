"""Build and load Xray-specific routing rules and profiles."""

from __future__ import annotations

from Furious.Library.Storage import Storage

__all__ = ['cleanRoutingRule', 'customRoutingObjectFromSettings']


def cleanRoutingRule(rule: dict):
    """Remove empty match fields from an Xray routing rule."""
    if not isinstance(rule, dict):
        return None

    result = {
        'type': 'field',
        'outboundTag': str(rule.get('outboundTag', 'proxy')).strip() or 'proxy',
    }

    for key in [
        'domain',
        'ip',
        'sourceIP',
        'localIP',
        'user',
        'protocol',
        'inboundTag',
        'process',
    ]:
        value = rule.get(key, [])
        if isinstance(value, list):
            value = list(str(item).strip() for item in value if str(item).strip())
            if value:
                result[key] = value

    for key in [
        'port',
        'sourcePort',
        'localPort',
        'network',
        'vlessRoute',
        'balancerTag',
        'ruleTag',
    ]:
        value = str(rule.get(key, '')).strip()
        if value:
            result[key] = value

    return result if len(result) > 2 else None


def customRoutingObjectFromSettings(routing: str):
    """Load a named custom Xray routing object from persistent settings."""
    prefix = 'Custom:'
    if not isinstance(routing, str) or not routing.startswith(prefix):
        return None

    routingProfile = Storage.UserRoutings().get(routing[len(prefix) :])
    if not isinstance(routingProfile, dict) or not routingProfile.get('enabled', True):
        return None

    domainStrategy = routingProfile.get('domainStrategy', 'AsIs')
    if domainStrategy not in ['AsIs', 'IPIfNonMatch', 'IPOnDemand']:
        domainStrategy = 'AsIs'

    rules = list(
        filter(
            lambda rule: rule is not None,
            list(cleanRoutingRule(rule) for rule in routingProfile.get('rules', [])),
        )
    )

    return {
        'domainStrategy': domainStrategy,
        'domainMatcher': 'hybrid',
        'rules': rules,
    }
