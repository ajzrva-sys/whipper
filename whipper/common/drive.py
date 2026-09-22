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

"""
CD-ROM drive helpers.

Thin wrapper over :mod:`whipper.platform`: the actual Linux/FreeBSD logic
lives there so the rest of the tree never checks ``sys.platform``.
"""

from whipper.platform import base, platform

import logging
logger = logging.getLogger(__name__)

# Re-export the CDS_* status vocabulary for callers and tests.
CDS_NO_INFO = base.CDS_NO_INFO
CDS_NO_DISC = base.CDS_NO_DISC
CDS_TRAY_OPEN = base.CDS_TRAY_OPEN
CDS_DRIVE_NOT_READY = base.CDS_DRIVE_NOT_READY
CDS_DISC_OK = base.CDS_DISC_OK


def getAllDevicePaths():
    return platform.get_all_device_paths()


def getDeviceInfo(path):
    """
    Return (vendor, model, release) for an optical drive path.

    Prefers pycdio; falls back to the platform backend (camcontrol on
    FreeBSD) when pycdio is missing or fails.
    """
    return platform.get_device_info(path)


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

    On non-Linux platforms (FreeBSD, DragonFly, …) that ioctl does not
    exist; this returns CDS_NO_INFO so callers can proceed and leave
    emptiness detection to cdparanoia/cdrdao (issue #686).

    :param drive_path: path to the disc drive
    :type drive_path: str
    :returns: return code of the 'CDROM_DRIVE_STATUS' ioctl, or
              CDS_NO_INFO on platforms without that ioctl
    :rtype: int
    """
    return platform.disc_status(drive_path)
