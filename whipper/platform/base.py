# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

"""
OS abstraction for CD-ROM devices and the tooling whipper drives.

``whipper.platform`` is the single seam for everything that used to fork on
``sys.platform``. A backend is picked once at import time (``__init__.py``);
callers talk to ``whipper.platform.platform`` and never check ``sys.platform``
themselves.
"""

import os
import shutil
import subprocess

import logging
logger = logging.getLogger(__name__)


# Linux CDROM_DRIVE_STATUS ioctl return codes (shared vocabulary; the ioctl
# itself is Linux-only and lives in linux.py).
CDS_NO_INFO = 0
CDS_NO_DISC = 1
CDS_TRAY_OPEN = 2
CDS_DRIVE_NOT_READY = 3
CDS_DISC_OK = 4

# Static fallback device nodes when no backend-native discovery works.
STATIC_DEVICE_CANDIDATES = (
    '/dev/cdrom',
    '/dev/cdrecorder',
    '/dev/cd0',
    '/dev/cd1',
    '/dev/cd2',
    '/dev/cd3',
    '/dev/acd0',
    '/dev/acd1',
)


def _listify(listOrString):
    if isinstance(listOrString, str):
        return [listOrString, ]

    return listOrString


def static_device_paths():
    """Existing device nodes from :data:`STATIC_DEVICE_CANDIDATES`."""
    ret = []

    for c in STATIC_DEVICE_CANDIDATES:
        if os.path.exists(c):
            ret.append(c)

    return ret


def run_tray_cmd(cmd, description):
    """
    Run a tray open/close helper.

    Soft-fails when the binary is missing or exits non-zero so a missing
    `eject` package cannot abort a rip. Returns True on success.
    """
    logger.debug("%s: %s", description, ' '.join(cmd))
    try:
        subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        return True
    except FileNotFoundError:
        logger.warning(
            "command '%s' not found; %s skipped "
            "(Linux: util-linux eject; FreeBSD: pkg install eject "
            "or use camcontrol)",
            cmd[0], description)
        return False
    except subprocess.CalledProcessError as e:
        logger.warning("command '%s' returned with exit code '%d' (%s)",
                       ' '.join(e.cmd), e.returncode, e.output.rstrip())
        return False


def find_binary(name):
    """Absolute path of ``name`` on PATH, or None."""
    return shutil.which(name)


class Platform:
    """
    Base CD-ROM backend.

    Subclasses override the ``*`` methods that differ per OS. The public
    entry points (``get_all_device_paths``, ``get_device_info``) are shared:
    they prefer pycdio and only fall back to backend-native discovery when
    pycdio is unavailable.
    """

    name = 'base'

    # -- device list ------------------------------------------------------

    def get_all_device_paths(self):
        """Optical device nodes, pycdio-first then backend-native."""
        try:
            # see https://savannah.gnu.org/bugs/index.php?38477
            import pycdio
            import cdio

            # FS_MATCH_ALL so the drive is listed even without a disc
            return [str(dev) for dev in _listify(
                cdio.get_devices_with_cap(pycdio.FS_MATCH_ALL, False))]
        except ImportError:
            logger.info('cannot import pycdio')

        return self.device_paths()

    def device_paths(self):
        """Backend-native device nodes (no pycdio)."""
        return static_device_paths()

    # -- identity ---------------------------------------------------------

    def get_device_info(self, path):
        """(vendor, model, release) for ``path``, or None (pycdio-first)."""
        try:
            import cdio
        except ImportError:
            cdio = None

        if cdio is not None:
            try:
                device = cdio.Device(path)
                _, vendor, model, release = device.get_hwinfo()
                return vendor, model, release
            except Exception as e:  # noqa: BLE001 - identity is best-effort
                logger.debug('pycdio hwinfo failed for %r: %s', path, e)

        return self.identify_device(path)

    def identify_device(self, path):
        """Backend-native identity (no pycdio); None when unsupported."""
        return None

    # -- disc presence ----------------------------------------------------

    def disc_status(self, path):
        """
        CDS_* status of the drive at ``path``.

        Returns CDS_NO_INFO when the platform has no such ioctl so callers
        can proceed and leave emptiness detection to cdparanoia/cdrdao.
        """
        logger.debug('disc status not supported on %s, '
                     'assuming disc may be present', self.name)
        return CDS_NO_INFO

    # -- tray -------------------------------------------------------------

    def eject(self, device):
        """Eject ``device``. Returns True on success."""
        return run_tray_cmd(['eject', device],
                            'ejecting device %s' % device)

    def load(self, device):
        """Close the tray of ``device``. Returns True on success."""
        return run_tray_cmd(['eject', '-t', device],
                            'loading (eject -t) device %s' % device)

    # -- mount ------------------------------------------------------------

    def is_mounted(self, device):
        """Whether ``device`` appears in the system mount table."""
        return False

    def unmount(self, device):
        """Unmount ``device`` if it is mounted (soft-fails)."""
        device = os.path.realpath(device)
        logger.debug('possibly unmount real path %r', device)
        if not self.is_mounted(device):
            return
        print('Device %s is mounted, unmounting' % device)
        try:
            subprocess.check_output(['umount', device],
                                    stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            logger.warning("command '%s' returned with exit code '%d' (%s)",
                           ' '.join(e.cmd), e.returncode, e.output.rstrip())

    # -- tooling ----------------------------------------------------------

    def cdrdao_driver_args(self):
        """Extra cdrdao argv (e.g. a forced driver) for this platform."""
        return []

    def find_binary(self, name):
        """Absolute path of ``name`` on PATH, or None."""
        return find_binary(name)
