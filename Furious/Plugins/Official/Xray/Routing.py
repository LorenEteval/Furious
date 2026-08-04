# Copyright (C) 2024–present  Loren Eteval & contributors <loren.eteval@proton.me>
#
# This file is part of Furious.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Build and load Xray-specific routing rules and profiles."""

from __future__ import annotations

from Furious.Library import *

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
