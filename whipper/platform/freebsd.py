# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

"""FreeBSD/DragonFly CD-ROM backend: camcontrol devlist/inquiry, /dev/cdN."""

import os
import re
import subprocess

from whipper.platform import base

import logging
logger = logging.getLogger(__name__)


# camcontrol inquiry: pass1: <PLEXTOR DVDR   PX-750A 1.02> ...
_CAMCONTROL_INQUIRY_RE = re.compile(
    r'<(?P<vendor>\S+)\s+(?P<model>\S.*?)\s+(?P<release>[\w.+-]+)>')

# camcontrol devlist unit list: "… (cd0,pass1)" / "… (acd0,pass2)"
_CAMCONTROL_DEVLIST_UNITS_RE = re.compile(r'\((?P<units>[^)]+)\)')
_CAMCONTROL_OPTICAL_UNIT_RE = re.compile(r'^(?:cd|acd)\d+$')

# Force a well-known driver when cdrdao's auto-detect is unreliable on CAM
# optical devices (USB/Plextor etc., issue #686).
CDRDAO_DRIVER = 'generic-mmc'


def camcontrol_cmd(device, action):
    """Build a camcontrol eject/load command for a BSD device node."""
    periph = os.path.basename(os.path.realpath(device))
    return ['camcontrol', action, periph]


def _camcontrol_devlist():
    """
    List optical device nodes via FreeBSD camcontrol devlist.

    Discovers every cdN/acdN unit, not just a hardcoded short list
    (issue #686 multi-drive). Returns [] if camcontrol is unavailable.
    """
    try:
        out = subprocess.check_output(
            ['camcontrol', 'devlist'],
            stderr=subprocess.DEVNULL).decode(errors='replace')
    except (OSError, subprocess.CalledProcessError) as e:
        logger.debug('camcontrol devlist failed: %s', e)
        return []

    paths = []
    for match in _CAMCONTROL_DEVLIST_UNITS_RE.finditer(out):
        for unit in match.group('units').split(','):
            unit = unit.strip()
            if not _CAMCONTROL_OPTICAL_UNIT_RE.match(unit):
                continue
            path = '/dev/%s' % unit
            if os.path.exists(path) and path not in paths:
                paths.append(path)
    logger.debug('camcontrol optical devices: %r', paths)
    return paths


def _camcontrol_units():
    """
    Map each optical unit name (``cd0``) to its full CAM unit group.

    ``camcontrol devlist`` lines look like ``... (cd0,pass1)``. Returns a
    mapping of optical unit -> list of all units in that group, so callers
    can find the matching ``passN`` device for a ``/dev/cdN`` node.
    """
    try:
        out = subprocess.check_output(
            ['camcontrol', 'devlist'],
            stderr=subprocess.DEVNULL).decode(errors='replace')
    except (OSError, subprocess.CalledProcessError) as e:
        logger.debug('camcontrol devlist failed: %s', e)
        return {}

    units = {}
    for match in _CAMCONTROL_DEVLIST_UNITS_RE.finditer(out):
        group = [u.strip() for u in match.group('units').split(',')]
        for unit in group:
            if _CAMCONTROL_OPTICAL_UNIT_RE.match(unit):
                units[unit] = group
    return units


def _camcontrol_inquiry(path):
    """
    Identify an optical drive via FreeBSD camcontrol inquiry.

    Returns (vendor, model, release) or None. Used when pycdio is not
    available so logs and drive list still name the drive.
    """
    periph = os.path.basename(os.path.realpath(path))
    try:
        out = subprocess.check_output(
            ['camcontrol', 'inquiry', periph],
            stderr=subprocess.DEVNULL).decode(errors='replace')
    except (OSError, subprocess.CalledProcessError) as e:
        logger.debug('camcontrol inquiry failed for %r: %s', path, e)
        return None
    m = _CAMCONTROL_INQUIRY_RE.search(out)
    if not m:
        logger.debug('camcontrol inquiry unparseable for %r: %r', path, out)
        return None
    return m.group('vendor'), m.group('model'), m.group('release')


class FreeBSDPlatform(base.Platform):

    name = 'freebsd'

    def device_paths(self):
        found = _camcontrol_devlist()
        if found:
            return found
        return base.static_device_paths()

    def identify_device(self, path):
        return _camcontrol_inquiry(path)

    def cam_pass_device(self, path):
        """The /dev/passN CAM device paired with a /dev/cdN node."""
        periph = os.path.basename(os.path.realpath(path))
        group = _camcontrol_units().get(periph, [])
        for unit in group:
            if unit.startswith('pass'):
                return '/dev/%s' % unit
        return None

    def eject(self, device):
        if base.run_tray_cmd(camcontrol_cmd(device, 'eject'),
                             'ejecting device %s via camcontrol' % device):
            return True
        return base.run_tray_cmd(['eject', device],
                                 'ejecting device %s' % device)

    def load(self, device):
        if base.run_tray_cmd(camcontrol_cmd(device, 'load'),
                             'loading device %s via camcontrol' % device):
            return True
        return base.run_tray_cmd(['eject', '-t', device],
                                 'loading (eject -t) device %s' % device)

    def is_mounted(self, device):
        # /proc/mounts does not exist; use mount(8) output (issue #686).
        try:
            mounts = subprocess.check_output(
                ['mount'], stderr=subprocess.DEVNULL).decode(errors='replace')
        except (OSError, subprocess.CalledProcessError) as e:
            logger.debug('could not read mount table via mount(8): %s', e)
            return False
        return device in mounts

    def cdrdao_driver_args(self):
        return ['--driver', CDRDAO_DRIVER]
