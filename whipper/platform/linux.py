# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

"""Linux CD-ROM backend: /dev/sr*, CDROM_DRIVE_STATUS ioctl, eject(1)."""

import os
from fcntl import ioctl

from whipper.platform import base

import logging
logger = logging.getLogger(__name__)


# Linux CDROM_DRIVE_STATUS ioctl number (AKA 'CDROM_DRIVE_STATUS')
CDROM_DRIVE_STATUS = 0x5326


class LinuxPlatform(base.Platform):

    name = 'linux'

    def device_paths(self):
        # Linux has no camcontrol equivalent; rely on the static candidates
        # (and /dev/sr* is covered via symlinks like /dev/cdrom).
        return base.static_device_paths()

    def identify_device(self, path):
        # Without pycdio there is no kernel/command way to name the drive.
        return None

    def disc_status(self, path):
        """
        CDS_* status via the Linux CDROM_DRIVE_STATUS ioctl.

        See https://www.kernel.org/doc/Documentation/ioctl/cdrom.txt
        """
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        try:
            rc = ioctl(fd, CDROM_DRIVE_STATUS)
        finally:
            os.close(fd)
        return rc

    def eject(self, device):
        return base.run_tray_cmd(['eject', device],
                                 'ejecting device %s' % device)

    def load(self, device):
        return base.run_tray_cmd(['eject', '-t', device],
                                 'loading (eject -t) device %s' % device)

    def is_mounted(self, device):
        try:
            with open('/proc/mounts') as handle:
                return device in handle.read()
        except OSError as e:
            logger.debug('could not read /proc/mounts: %s', e)
            return False
