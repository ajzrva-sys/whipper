# -*- Mode: Python; test-case-name: whipper.test.test_common_drive -*-
# vi:si:et:sw=4:sts=4:ts=4

# Copyright (C) 2009 Thomas Vander Stichele

# This file is part of whipper.
#
# whipper is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# whipper is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with whipper.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
from fcntl import ioctl

import logging
logger = logging.getLogger(__name__)

# Linux CDROM_DRIVE_STATUS ioctl return codes
# https://www.kernel.org/doc/Documentation/ioctl/cdrom.txt
CDS_NO_INFO = 0
CDS_NO_DISC = 1
CDS_TRAY_OPEN = 2
CDS_DRIVE_NOT_READY = 3
CDS_DISC_OK = 4

# Linux CDROM_DRIVE_STATUS ioctl number (AKA 'CDROM_DRIVE_STATUS')
_CDROM_DRIVE_STATUS = 0x5326

# Static fallback device nodes when pycdio is unavailable.
_STATIC_DEVICE_CANDIDATES = (
    '/dev/cdrom',
    '/dev/cdrecorder',
    '/dev/cd0',
    '/dev/cd1',
    '/dev/acd0',
)


def _listify(listOrString):
    if isinstance(listOrString, str):
        return [listOrString, ]

    return listOrString


def getAllDevicePaths():
    try:
        # see https://savannah.gnu.org/bugs/index.php?38477
        return [str(dev) for dev in _getAllDevicePathsPyCdio()]
    except ImportError:
        logger.info('cannot import pycdio')
        return _getAllDevicePathsStatic()


def _getAllDevicePathsPyCdio():
    import pycdio
    import cdio

    # using FS_AUDIO here only makes it list the drive when an audio cd
    # is inserted
    # ticket 102: this cdio call returns a list of str, or a single str
    return _listify(cdio.get_devices_with_cap(pycdio.FS_MATCH_ALL, False))


def _getAllDevicePathsStatic():
    ret = []

    for c in _STATIC_DEVICE_CANDIDATES:
        if os.path.exists(c):
            ret.append(c)

    return ret


def getDeviceInfo(path):
    try:
        import cdio
    except ImportError:
        return None
    device = cdio.Device(path)
    _, vendor, model, release = device.get_hwinfo()

    return vendor, model, release


def get_cdrom_drive_status(drive_path):
    """
    Get the status of the disc drive.

    Drive status possibilities returned by the Linux CDROM_DRIVE_STATUS ioctl:
    - CDS_NO_INFO         = 0  (if not implemented / unsupported platform)
    - CDS_NO_DISC         = 1
    - CDS_TRAY_OPEN       = 2
    - CDS_DRIVE_NOT_READY = 3
    - CDS_DISC_OK         = 4

    Documentation here:
    - https://www.kernel.org/doc/Documentation/ioctl/cdrom.txt
    - https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/include/uapi/linux/cdrom.h  # noqa: E501

    On non-Linux platforms (FreeBSD, DragonFly, …) that ioctl does not
    exist; this returns CDS_NO_INFO so callers can proceed and leave
    emptiness detection to cdparanoia/cdrdao (issue #686).

    :param drive_path: path to the disc drive
    :type drive_path: str
    :returns: return code of the 'CDROM_DRIVE_STATUS' ioctl, or
              CDS_NO_INFO on platforms without that ioctl
    :rtype: int
    """
    if not sys.platform.startswith('linux'):
        logger.debug(
            'CDROM_DRIVE_STATUS ioctl not supported on %s, '
            'assuming disc may be present', sys.platform)
        return CDS_NO_INFO

    fd = os.open(drive_path, os.O_RDONLY | os.O_NONBLOCK)
    try:
        rc = ioctl(fd, _CDROM_DRIVE_STATUS)
    finally:
        os.close(fd)
    return rc
