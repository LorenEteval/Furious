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

"""Attempt-local host preparation and recovery for the native auto-route engine."""

from __future__ import annotations

from Furious.Frozenlib import (
    PLATFORM,
    SystemRuntime,
    runExternalCommand,
    SystemRoutingTable,
)
from Furious.Models.SingTUN import (
    SingTUNHostSettingsCallers,
    addSingTUNExclusions,
    prepareSingTUNSettings,
)

import copy
import ipaddress
import json
import os
import secrets
import shutil
import socket
import subprocess
import threading
import base64


def _command(arguments):
    """Run a checked, bounded argument vector without shell interpolation."""
    try:
        return (
            runExternalCommand(
                arguments,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=5,
            )
            .stdout.decode('utf-8', 'replace')
            .strip()
        )
    except (OSError, subprocess.SubprocessError):
        # Command output may contain host configuration; keep the UI diagnostic
        # useful without forwarding it or profile credentials to logs.
        raise RuntimeError('sing-tun host operation failed: ' + arguments[0]) from None


def _powershell(script):
    script = (
        '[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; '
        '$OutputEncoding=[Console]::OutputEncoding; ' + script
    )

    return _command(
        [
            'powershell',
            '-NoProfile',
            '-NonInteractive',
            '-EncodedCommand',
            base64.b64encode(script.encode('utf-16le')).decode(),
        ]
    )


def _darwinRoutes(text, family):
    """Normalize netstat's abbreviated destinations, never matching substrings."""
    result = []

    for line in text.splitlines():
        fields = line.split()

        if len(fields) < 4:
            continue

        destination = fields[0]

        try:
            if destination == 'default':
                destination = '0.0.0.0/0' if family == 4 else '::/0'
            elif family == 4:
                address, separator, mask = destination.partition('/')
                octets = address.split('.')
                destination = (
                    '.'.join(octets + ['0'] * (4 - len(octets)))
                    + '/'
                    + (mask if separator else str(8 * len(octets)))
                )

            network = ipaddress.ip_network(destination, strict=False)
        except ValueError:
            continue

        if network.version == family:
            result.append((network, fields[1], fields[3]))

    return result


def _routeRanges(tun):
    """Mirror the pinned Darwin BuildAutoRouteRanges for exact conflict checks."""
    result = []

    for family in (4, 6):
        addresses = tun['Inet' + str(family) + 'Address']

        if not addresses:
            continue

        routes = tun.get('Inet' + str(family) + 'RouteAddress', [])

        if routes:
            ranges = [ipaddress.ip_network(value, strict=False) for value in routes]
            ranges.extend(
                ipaddress.ip_interface(value).network
                for value in addresses
                if ipaddress.ip_interface(value).network.prefixlen < 32
            )
        else:
            bits = 32 if family == 4 else 128
            ranges = [
                ipaddress.ip_network(
                    (ipaddress.ip_address(1 << (bits - length)), length)
                )
                for length in range(8, 0, -1)
            ]

        for value in tun.get('Inet' + str(family) + 'RouteExcludeAddress', []):
            exclusion = ipaddress.ip_network(value, strict=False)
            remaining = []

            for network in ranges:
                if network.subnet_of(exclusion):
                    continue

                remaining.extend(
                    network.address_exclude(exclusion)
                    if exclusion.subnet_of(network)
                    else [network]
                )

            ranges = remaining

        result.extend(ipaddress.collapse_addresses(ranges))

    return result


def _linuxRuleDelete(flag, rule, table, start, device):
    """Match a pinned native rule's selectors, never delete a priority wildcard."""
    allowed = {
        'priority',
        'src',
        'dst',
        'table',
        'not',
        'iif',
        'oif',
        'goto',
        'suppress_prefixlength',
        'dport',
        'action',
        'protocol',
    }
    priority = int(rule['priority'])
    target = str(rule.get('table', ''))

    if set(rule) - allowed or target not in ('', str(table), 'main', '254'):
        raise RuntimeError('Conflicting Linux policy rule; refusing sing-tun recovery')

    if rule.get('iif') not in (None, 'lo', device) or rule.get('oif') is not None:
        raise RuntimeError(
            'Conflicting Linux interface rule; refusing sing-tun recovery'
        )

    if 'goto' in rule and rule['goto'] != start + 10:
        raise RuntimeError('Conflicting Linux goto rule; refusing sing-tun recovery')

    if priority == start + 10 and rule.get('action') != 'nop':
        raise RuntimeError(
            'Conflicting Linux terminal rule; refusing sing-tun recovery'
        )

    if rule.get('protocol') not in (None, 0, 'unspec'):
        raise RuntimeError(
            'Conflicting Linux rule protocol; refusing sing-tun recovery'
        )

    args = ['ip', flag, 'rule', 'del', 'priority', str(priority)]

    if rule.get('not'):
        args.append('not')

    for key, parameter in (('src', 'from'), ('dst', 'to'), ('iif', 'iif')):
        if key in rule:
            value = str(rule[key])

            if key != 'iif' and value != 'all':
                ipaddress.ip_network(value, strict=False)

            args.extend([parameter, value])

    if 'suppress_prefixlength' in rule:
        if rule['suppress_prefixlength'] != 0:
            raise RuntimeError('Conflicting Linux suppression rule')

        args.extend(['suppress_prefixlength', '0'])

    if 'dport' in rule:
        if str(rule['dport']) not in ('53', '53-53'):
            raise RuntimeError('Conflicting Linux DNS rule')

        args.extend(['dport', '53'])

    if target:
        args.extend(['table', target])

    if 'goto' in rule:
        args.extend(['goto', str(rule['goto'])])
    elif rule.get('action') == 'nop':
        args.append('nop')
    elif not target:
        raise RuntimeError('Unrecognized Linux rule; cleanup ownership retained')

    return args


class SingTUNHostPlan:
    """Owned by one SingTUN runtime, including any unfinished host worker."""

    def __init__(self, configuration, *, platform=PLATFORM):
        copied = copy.deepcopy(configuration)
        proxy = copied.pop('proxy', None)

        self.configuration = prepareSingTUNSettings(copied, platform=platform)
        self.hostSettings = self.configuration.pop('host_options')
        self.hostSettingsCallers = SingTUNHostSettingsCallers(self.hostSettings)

        if proxy is not None:
            self.configuration['proxy'] = proxy

        self.platform = platform
        self.deviceName = ''
        self._worker = None
        self._done = threading.Event()
        self._cancel = threading.Event()
        self.error = ''
        self._dnsRestore = []
        self._table = None
        self._ruleStart = None
        self._activated = False
        self._ranges = []
        self._cleanupComplete = False
        self.egressIP = ''

    def begin(self, method, *args):
        """Schedule bounded host work; the Qt owner polls completion."""
        if self._worker is not None and self._worker.is_alive():
            raise RuntimeError('sing-tun host worker is already active')

        self._done.clear()
        self.error = ''

        def run():
            try:
                if not self._cancel.is_set():
                    getattr(self, method)(*args)
            except Exception as ex:
                self.error = str(ex)
            finally:
                self._done.set()

        self._worker = threading.Thread(target=run, name='sing-tun-host')
        self._worker.start()

    @property
    def workDone(self):
        return self._done.is_set()

    def workCompleted(self):
        return self.workDone

    def drain(self):
        """Retain a worker on timeout; no late DNS mutation can escape cleanup."""
        self._cancel.set()

        if self._worker is not None:
            self._worker.join(6)

            if self._worker.is_alive():
                raise RuntimeError('sing-tun host preparation is still stopping')

            self._worker = None

    def prepare(self, addresses):
        if SystemRuntime.flatpakID():
            raise RuntimeError('sing-tun application TUN is unavailable in Flatpak')

        if self.platform == 'Linux':
            # The legacy pkexec script does not elevate this spawned Go child.
            if os.geteuid() != 0:
                raise RuntimeError(
                    'sing-tun auto-routing requires root on Linux; '
                    'select tun2socks to use the existing privileged helper'
                )

            if not shutil.which('resolvectl'):
                raise RuntimeError(
                    'sing-tun DNS management requires systemd-resolved on Linux; select tun2socks on other resolver configurations'
                )

            try:
                _command(['resolvectl', 'status'])
            except RuntimeError:
                raise RuntimeError(
                    'sing-tun requires an active systemd-resolved service on Linux'
                ) from None
        elif not SystemRuntime.isAdmin():
            raise RuntimeError('sing-tun requires networking administrator privileges')

        self.configuration = addSingTUNExclusions(self.configuration, addresses)

        self.captureEgress()

        tun = self.configuration['tun_options']
        names = self._interfaceNames()
        name = tun['Name']

        if name and name in names:
            raise RuntimeError('The requested sing-tun interface already exists')

        if not name:
            candidates = ['utun' + str(number) for number in range(10, 1025)]
            candidates = [value for value in candidates if value not in names]

            if not candidates:
                raise RuntimeError('No unused sing-tun interface name is available')

            name = secrets.choice(candidates)

        if self.platform == 'Linux' and len(name) > 15:
            raise ValueError('Linux TUN names must be at most 15 characters')

        if self.platform == 'Darwin' and (
            not name.startswith('utun') or not name[4:].isdigit()
        ):
            raise ValueError('macOS requires a utun device name followed by a number')

        tun['Name'] = self.deviceName = name

        if self.platform == 'Linux':
            rules = sum(
                (
                    json.loads(_command(['ip', flag, '-j', 'rule', 'show']))
                    for flag in ('-4', '-6')
                ),
                [],
            )
            routes = sum(
                (
                    json.loads(
                        _command(['ip', flag, '-j', 'route', 'show', 'table', 'all'])
                    )
                    for flag in ('-4', '-6')
                ),
                [],
            )
            tables = {str(item.get('table')) for item in rules + routes}
            priorities = {int(item['priority']) for item in rules}

            for _ in range(100):
                table = secrets.randbelow(1000000000) + 100000
                start = secrets.randbelow(1800) * 11 + 1000

                if str(table) not in tables and not any(
                    start <= value <= start + 10 for value in priorities
                ):
                    self._table, self._ruleStart = table, start

                    break
            else:
                raise RuntimeError(
                    'No isolated sing-tun routing identifiers are available'
                )

            tun['IPRoute2TableIndex'], tun['IPRoute2RuleIndex'] = (
                self._table,
                self._ruleStart,
            )
        elif self.platform == 'Darwin':
            self._ranges = _routeRanges(tun)

            # Upstream replaces EEXIST destinations. Refuse a conflict before
            # activation rather than replacing another owner's exact route.
            existing = self._darwinRouteSnapshot()

            if any(network in {row[0] for row in existing} for network in self._ranges):
                raise RuntimeError(
                    'sing-tun route ranges conflict with existing macOS routes'
                )

    def markActivated(self):
        # Install before process.start: partial native initialization also needs recovery.
        self._activated = True

    def applyDNS(self, actualName):
        if actualName != self.deviceName:
            raise RuntimeError('sing-tun reported an unexpected interface name')

        tun = self.configuration['tun_options']
        dns = self.hostSettingsCallers.userTunAdapterInterfaceDNS() or (
            '1.1.1.1' if tun['Inet4Address'] else '2606:4700:4700::1111'
        )
        address = ipaddress.ip_address(dns)

        if not tun['Inet' + str(address.version) + 'Address']:
            raise ValueError(
                'The configured TUN DNS address requires that address family on the interface'
            )

        if self._cancel.is_set():
            return

        if self.platform == 'Windows':
            primaryName = self.hostSettingsCallers.userPrimaryAdapterInterfaceName()
            primaryIP = self.hostSettingsCallers.userPrimaryAdapterInterfaceIP()

            snapshot = json.loads(
                _powershell(
                    '$ErrorActionPreference="Stop"; '
                    '$items=@(Get-WmiObject Win32_NetworkAdapterConfiguration | Where-Object {$_.IPEnabled}); '
                    '@($items | ForEach-Object { $c=$_; '
                    '$a=Get-WmiObject Win32_NetworkAdapter -Filter ("Index="+$c.Index); '
                    '$p=Get-ItemProperty ("HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces\\"+$c.SettingID); '
                    'New-Object PSObject -Property @{Name=$a.NetConnectionID; IP=$c.IPAddress; '
                    'Static=$p.NameServer; DNS=$c.DNSServerSearchOrder}}) | ConvertTo-Json -Depth 4'
                )
            )

            if isinstance(snapshot, dict):
                snapshot = [snapshot]

            physical = [
                item
                for item in snapshot
                if item['Name'] != actualName
                and (
                    (primaryName and item['Name'] == primaryName)
                    or (primaryIP and primaryIP in (item['IP'] or []))
                )
            ]

            if not primaryName and not primaryIP:
                # The physical default route was captured before native startup.
                physical = [
                    item for item in snapshot if self.egressIP in (item['IP'] or [])
                ]

            if self.hostSettingsCallers.userDisablePrimaryAdapterInterfaceDNS():
                if len(physical) != 1:
                    raise RuntimeError(
                        'Unable to identify the physical adapter for DNS restoration'
                    )

                item = physical[0]

                if not isinstance(item.get('Name'), str) or not item['Name']:
                    raise RuntimeError(
                        'Unable to snapshot the physical adapter DNS identity'
                    )

                item['DNS'] = [
                    server
                    for server in item.get('DNS') or []
                    if ipaddress.ip_address(server).version == 4
                ]

                # Register restoration before the first host write.
                self._dnsRestore.append(('Windows', item))
                self._windowsDNS(item['Name'], ['127.0.0.1'])

            self._windowsDNS(actualName, [str(address)])

            _command(['ipconfig', '/flushdns'])
        elif self.platform == 'Darwin':
            listing = _command(
                ['networksetup', '-listallnetworkservices']
            ).splitlines()[1:]

            for service in listing:
                if not service or service.startswith('*') or self._cancel.is_set():
                    continue

                original = _command(
                    ['networksetup', '-getdnsservers', service]
                ).splitlines()

                servers = []

                for value in original:
                    try:
                        servers.append(str(ipaddress.ip_address(value)))
                    except ValueError:
                        if "aren't any DNS Servers" not in value:
                            raise RuntimeError(
                                'Cannot snapshot macOS DNS configuration'
                            ) from None

                self._dnsRestore.append(('Darwin', (service, servers)))

                _command(['networksetup', '-setdnsservers', service, str(address)])
        elif self.platform == 'Linux':
            # Only the new, ephemeral interface is touched; never /etc/resolv.conf.
            _command(['resolvectl', 'dns', actualName, str(address)])
            _command(['resolvectl', 'domain', actualName, '~.'])

    def captureEgress(self):
        if self.platform == 'Windows':
            gateways = SystemRoutingTable.DEFAULT_GATEWAY_WIN32.findall(
                _command(['route', 'print', '0.0.0.0'])
            )

            if len(gateways) != 1:
                raise RuntimeError('Unable to identify the physical default gateway')

            self.egressIP = (
                self.hostSettingsCallers.userPrimaryAdapterInterfaceIP()
                or gateways[0][1]
            )

    @staticmethod
    def _windowsDNS(name, servers):
        family = (
            'ipv4'
            if not servers or ipaddress.ip_address(servers[0]).version == 4
            else 'ipv6'
        )

        if not servers:
            _command(
                [
                    'netsh',
                    'interface',
                    family,
                    'set',
                    'dnsservers',
                    'name=' + name,
                    'source=dhcp',
                ]
            )

            return

        _command(
            [
                'netsh',
                'interface',
                family,
                'set',
                'dnsservers',
                'name=' + name,
                'source=static',
                'address=' + servers[0],
                'validate=no',
            ]
        )

        for index, server in enumerate(servers[1:], 2):
            _command(
                [
                    'netsh',
                    'interface',
                    family,
                    'add',
                    'dnsservers',
                    'name=' + name,
                    'address=' + server,
                    'index=' + str(index),
                    'validate=no',
                ]
            )

    def _interfaceNames(self):
        if self.platform == 'Windows':
            names = json.loads(
                _powershell(
                    '@([System.Net.NetworkInformation.NetworkInterface]::GetAllNetworkInterfaces() | ForEach-Object {$_.Name}) | ConvertTo-Json'
                )
            )

            return set(names if isinstance(names, list) else [names] if names else [])

        return {name for _, name in socket.if_nameindex()}

    def _darwinRouteSnapshot(self):
        result = []

        for family, name in ((4, 'inet'), (6, 'inet6')):
            result.extend(
                _darwinRoutes(_command(['netstat', '-rn', '-f', name]), family)
            )

        return result

    def restoreDNS(self):
        """Restore only recorded host DNS, independently of native release."""
        errors = []

        for platform, snapshot in reversed(self._dnsRestore[:]):
            try:
                if platform == 'Windows':
                    self._windowsDNS(
                        snapshot['Name'], snapshot['DNS'] if snapshot['Static'] else []
                    )
                else:
                    service, servers = snapshot

                    _command(
                        [
                            'networksetup',
                            '-setdnsservers',
                            service,
                            *(servers or ['Empty']),
                        ]
                    )

                self._dnsRestore.remove((platform, snapshot))
            except Exception as ex:
                errors.append(str(ex))

        if errors:
            raise RuntimeError('; '.join(errors))

    def cleanup(self, cleanExit):
        """Restore independent DNS even if exact native recovery refuses cleanup."""
        errors = []

        try:
            self.restoreDNS()
        except Exception as ex:
            errors.append(str(ex))

        if self._activated:
            try:
                self._recoverNative()
            except Exception as ex:
                errors.append(str(ex))

        if errors:
            raise RuntimeError('; '.join(errors))

        self._activated = False
        self._cleanupComplete = True

    def finishCleanup(self, cleanExit):
        """Run host restoration outside Qt; retain the worker on a bounded drain."""
        if self._cleanupComplete:
            return

        self._finishCleanupWork('cleanup', cleanExit)

    def finishDNSCleanup(self):
        """Restore DNS even when the child cannot be reaped; retain native ownership."""
        if self._dnsRestore:
            self._finishCleanupWork('restoreDNS')

    def _finishCleanupWork(self, method, *args):
        if self._worker is None:
            # drain() cancelled preparation; restoration must still execute.
            self._cancel.clear()
            self.begin(method, *args)

        self._worker.join(6)

        if self._worker.is_alive():
            raise RuntimeError('sing-tun host restoration is still running')

        self._worker = None

        if self.error:
            raise RuntimeError(self.error)

    def _recoverNative(self):
        names = self._interfaceNames()

        if self.deviceName in names:
            # Closing the exact child should remove its ephemeral TUN. Do not
            # destroy a same-named interface whose identity we cannot prove.
            raise RuntimeError(
                'sing-tun interface remains after child exit; cleanup ownership retained'
            )

        if self.platform == 'Linux' and self._table is not None:
            for flag in ('-4', '-6'):
                rules = json.loads(_command(['ip', flag, '-j', 'rule', 'show']))

                for rule in rules:
                    priority = int(rule['priority'])

                    if not self._ruleStart <= priority <= self._ruleStart + 10:
                        continue

                    _command(
                        _linuxRuleDelete(
                            flag, rule, self._table, self._ruleStart, self.deviceName
                        )
                    )

                remaining = json.loads(_command(['ip', flag, '-j', 'rule', 'show']))

                if any(
                    self._ruleStart <= int(rule['priority']) <= self._ruleStart + 10
                    for rule in remaining
                ):
                    raise RuntimeError(
                        'sing-tun Linux rules remain; cleanup ownership retained'
                    )

                routes = json.loads(
                    _command(
                        ['ip', flag, '-j', 'route', 'show', 'table', str(self._table)]
                    )
                )

                if routes:
                    # Routes referring to the now-closed ephemeral interface
                    # should disappear in the kernel; never flush an unrelated table.
                    raise RuntimeError(
                        'sing-tun routing table remains; cleanup ownership retained'
                    )
        elif self.platform == 'Darwin':
            # Routes may survive a partial native start before routeSet is set.
            # Delete only an exact planned destination AND its attempt gateway.
            table = self._darwinRouteSnapshot()

            for network in self._ranges:
                family = '4' if network.version == 4 else '6'
                gateway = str(
                    ipaddress.ip_interface(
                        self.configuration['tun_options']['Inet' + family + 'Address'][
                            0
                        ]
                    ).ip
                )

                if any(
                    row[0] == network
                    and row[1].split('%', 1)[0] == gateway
                    and row[2] == self.deviceName
                    for row in table
                ):
                    _command(
                        [
                            'route',
                            '-n',
                            'delete',
                            '-inet' + ('6' if family == '6' else ''),
                            str(network),
                            gateway,
                        ]
                    )

            remaining = self._darwinRouteSnapshot()

            if any(
                row[0] in self._ranges and row[2] == self.deviceName
                for row in remaining
            ):
                raise RuntimeError(
                    'sing-tun macOS routes remain; cleanup ownership retained'
                )
