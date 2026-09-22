# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

"""
Pick the platform backend once at import time.

Importing ``whipper.platform.platform`` gives the active backend. Tests swap
the backend (or its methods) instead of patching ``sys.platform``.
"""

import sys


def _make_platform():
    if sys.platform.startswith('linux'):
        from whipper.platform import linux
        return linux.LinuxPlatform()

    # Every non-Linux platform keeps the historical BSD behaviour
    # (camcontrol-first device discovery/identity and tray control).
    from whipper.platform import freebsd
    return freebsd.FreeBSDPlatform()


platform = _make_platform()

__all__ = ['platform']
