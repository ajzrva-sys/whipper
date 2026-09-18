import os
import platform
import subprocess

import logging
logger = logging.getLogger(__name__)


def eject_device(device):
    """Eject the given device."""
    logger.debug("ejecting device %s", device)
    try:
        # `eject device` prints nothing to stdout
        subprocess.check_output(['eject', device], stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        logger.warning("command '%s' returned with exit code '%d' (%s)",
                       ' '.join(e.cmd), e.returncode, e.output.rstrip())


def load_device(device):
    """Load the given device."""
    logger.debug("loading (eject -t) device %s", device)
    try:
        # `eject -t device` prints nothing to stdout
        subprocess.check_output(['eject', '-t', device],
                                stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        logger.warning("command '%s' returned with exit code '%d' (%s)",
                       ' '.join(e.cmd), e.returncode, e.output.rstrip())


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
