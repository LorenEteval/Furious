# Furious

[![Build Furious](https://github.com/LorenEteval/Furious/actions/workflows/wheels.yml/badge.svg?branch=main)](https://github.com/LorenEteval/Furious/actions/workflows/wheels.yml)

Backup [0.2.x main branch](https://github.com/LorenEteval/Furious/tree/main)

Furious is now heading towards the 0.3.x milestone. Before rolling out any new features, it will remodel existing
solutions to provide a better Pythonic experience for both users and developers.

## TODO

Example: [Interface](https://github.com/LorenEteval/Furious/blob/dev/Furious/Interface), [Library](https://github.com/LorenEteval/Furious/blob/dev/Furious/Library)

Basic idea:

1. The (core) configuration needs to provide `toURI()` and `fromURI()` method for import/export usage (so that they are
   independent of each other)
2. Furious takes care of (modifying) local proxy servers exposed in the configuration in order to easily chain multiple
   proxy servers (or provide them to system proxy settings, tun2socks, etc.). The protocol details are handled by cores.
3. (TODO can update streamObject/TLSObject so that it can be updated from the popup UI)
4. More type annotations/docstrings in code
5. ...

For Python bindings repositories, a github bot is required to create binding PRs for review and automatic packaging
Release. Binding template project in the future?

## Goal

Since the go runtime issues in Python have been solved by Xray-core-python, hysteria2-python, etc., Furious together
with the corresponding Python bindings will provide a Python ecosystem against GFW.
