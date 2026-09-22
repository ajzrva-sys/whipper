# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

"""Tray and mount helpers, delegated to :mod:`whipper.platform`."""

from whipper.platform import platform as _platform

import logging
logger = logging.getLogger(__name__)


def eject_device(device):
    """Eject the given device."""
    _platform.eject(device)


def load_device(device):
    """Load the given device (close the tray)."""
    _platform.load(device)


def unmount_device(device):
    """
    Unmount the given device if it is mounted.

    This usually happens with automounted data tracks.

    If the given device is a symlink, the target will be checked.
    """
    _platform.unmount(device)
