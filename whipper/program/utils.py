import os
import platform
import subprocess

import logging
logger = logging.getLogger(__name__)


def _run_tray_cmd(cmd, description):
    """
    Run a tray open/close helper.

    Soft-fails when the binary is missing or exits non-zero so a missing
    `eject` package cannot abort a rip (issue #686 FreeBSD follow-up).
    Returns True on success.
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


def _camcontrol_cmd(device, action):
    """Build a camcontrol eject/load command for a BSD device node."""
    periph = os.path.basename(os.path.realpath(device))
    return ['camcontrol', action, periph]


def eject_device(device):
    """Eject the given device."""
    if platform.system() != 'Linux':
        # FreeBSD / DragonFly: base-system camcontrol, then eject(1)
        if _run_tray_cmd(_camcontrol_cmd(device, 'eject'),
                         'ejecting device %s via camcontrol' % device):
            return
    _run_tray_cmd(['eject', device],
                  'ejecting device %s' % device)


def load_device(device):
    """Load the given device (close the tray)."""
    if platform.system() != 'Linux':
        if _run_tray_cmd(_camcontrol_cmd(device, 'load'),
                         'loading device %s via camcontrol' % device):
            return
    _run_tray_cmd(['eject', '-t', device],
                  'loading (eject -t) device %s' % device)


def _device_is_mounted(device):
    """Return True if ``device`` appears in the system mount table."""
    if platform.system() == 'Linux':
        try:
            with open('/proc/mounts') as handle:
                return device in handle.read()
        except OSError as e:
            logger.debug('could not read /proc/mounts: %s', e)
            return False

    # FreeBSD / DragonFly / other BSDs: /proc/mounts does not exist.
    # Use mount(8) output instead (issue #686).
    try:
        mounts = subprocess.check_output(
            ['mount'], stderr=subprocess.DEVNULL).decode(errors='replace')
    except (OSError, subprocess.CalledProcessError) as e:
        logger.debug('could not read mount table via mount(8): %s', e)
        return False
    return device in mounts


def unmount_device(device):
    """
    Unmount the given device if it is mounted.

    This usually happens with automounted data tracks.

    If the given device is a symlink, the target will be checked.
    """
    device = os.path.realpath(device)
    logger.debug('possibly unmount real path %r', device)
    if not _device_is_mounted(device):
        return
    print('Device %s is mounted, unmounting' % device)
    try:
        subprocess.check_output(['umount', device],
                                stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        logger.warning("command '%s' returned with exit code '%d' (%s)",
                       ' '.join(e.cmd), e.returncode, e.output.rstrip())
