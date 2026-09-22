# -*- Mode: Python; test-case-name: whipper.test.test_common_drive -*-
# vi:si:et:sw=4:sts=4:ts=4

import os
import sys
import unittest
from unittest import mock

from whipper.test import common
from whipper.common import drive
from whipper.platform import base, freebsd, linux


class ListifyTestCase(common.TestCase):

    def testString(self):
        string = '/dev/sr0'
        self.assertEqual(base._listify(string), [string, ])

    def testList(self):
        lst = ['/dev/scd0', '/dev/sr0']
        self.assertEqual(base._listify(lst), lst)


class StaticDevicePathsTestCase(common.TestCase):

    def test_includes_freebsd_nodes(self):
        # Issue #686: FreeBSD optical devices are /dev/cd0 (CAM) or /dev/acd0
        self.assertIn('/dev/cd0', base.STATIC_DEVICE_CANDIDATES)
        self.assertIn('/dev/acd0', base.STATIC_DEVICE_CANDIDATES)
        self.assertIn('/dev/cdrom', base.STATIC_DEVICE_CANDIDATES)

    def test_existing_nodes_listed(self):
        found = base.static_device_paths()
        for path in found:
            self.assertTrue(os.path.exists(path))


class CamcontrolDevicePathsTestCase(common.TestCase):

    _DEVLIST = (
        "<WD_BLACK SN770 2TB>          at scbus0 target 0 lun 1 (pass0,nda0)\n"
        "<PLEXTOR DVDR   PX-750A 1.02> at scbus1 target 0 lun 0 (cd0,pass1)\n"
        "<HL-DT-ST DVDR GH24NSD1>      at scbus2 target 0 lun 0 (cd1,pass2)\n"
        "<ATAPI DVD A>                 at scbus3 target 0 lun 0 (acd0,pass3)\n"
    )

    def test_parses_multiple_optical_units(self):
        with mock.patch('whipper.platform.freebsd.subprocess.check_output',
                        return_value=self._DEVLIST.encode()), \
             mock.patch('whipper.platform.freebsd.os.path.exists',
                        side_effect=lambda p: p.startswith('/dev/cd')
                        or p.startswith('/dev/acd')):
            paths = freebsd._camcontrol_devlist()
        self.assertEqual(paths, ['/dev/cd0', '/dev/cd1', '/dev/acd0'])

    def test_freebsd_device_paths_uses_camcontrol(self):
        p = freebsd.FreeBSDPlatform()
        with mock.patch.dict(sys.modules, {'pycdio': None}), \
             mock.patch('whipper.platform.freebsd._camcontrol_devlist',
                        return_value=['/dev/cd0', '/dev/cd1']) as cam, \
             mock.patch('whipper.platform.base.static_device_paths') as static:
            paths = p.get_all_device_paths()
        self.assertEqual(paths, ['/dev/cd0', '/dev/cd1'])
        cam.assert_called_once()
        static.assert_not_called()

    def test_freebsd_falls_back_to_static_when_camcontrol_empty(self):
        p = freebsd.FreeBSDPlatform()
        with mock.patch.dict(sys.modules, {'pycdio': None}), \
             mock.patch('whipper.platform.freebsd._camcontrol_devlist',
                        return_value=[]), \
             mock.patch('whipper.platform.base.static_device_paths',
                        return_value=['/dev/cd0']) as static:
            self.assertEqual(p.get_all_device_paths(), ['/dev/cd0'])
        static.assert_called_once()

    def test_linux_device_paths_uses_static(self):
        p = linux.LinuxPlatform()
        with mock.patch.dict(sys.modules, {'pycdio': None}), \
             mock.patch('whipper.platform.base.static_device_paths',
                        return_value=['/dev/cdrom']) as static:
            self.assertEqual(p.get_all_device_paths(), ['/dev/cdrom'])
        static.assert_called_once()


class DeviceInfoTestCase(common.TestCase):

    def test_freebsd_identify_uses_camcontrol(self):
        p = freebsd.FreeBSDPlatform()
        with mock.patch.dict(sys.modules, {'cdio': None}), \
             mock.patch('whipper.platform.freebsd._camcontrol_inquiry',
                        return_value=('PLEXTOR', 'PX-750A', '1.02')) as fb:
            info = p.get_device_info('/dev/cd0')
        self.assertEqual(info, ('PLEXTOR', 'PX-750A', '1.02'))
        fb.assert_called_once_with('/dev/cd0')

    def test_linux_identify_returns_none_without_pycdio(self):
        p = linux.LinuxPlatform()
        with mock.patch.dict(sys.modules, {'cdio': None}):
            info = p.get_device_info('/dev/sr0')
        self.assertIsNone(info)


class CdromDriveStatusTestCase(common.TestCase):

    def test_linux_uses_ioctl(self):
        p = linux.LinuxPlatform()
        with mock.patch.object(linux.os, 'open', return_value=3) as open_, \
             mock.patch.object(linux.os, 'close') as close, \
             mock.patch.object(linux, 'ioctl',
                               return_value=base.CDS_DISC_OK) as ioctl:
            rc = p.disc_status('/dev/sr0')
        self.assertEqual(rc, base.CDS_DISC_OK)
        open_.assert_called_once()
        ioctl.assert_called_once_with(3, linux.CDROM_DRIVE_STATUS)
        close.assert_called_once_with(3)

    def test_linux_closes_fd_on_error(self):
        p = linux.LinuxPlatform()
        with mock.patch.object(linux.os, 'open', return_value=7), \
             mock.patch.object(linux.os, 'close') as close, \
             mock.patch.object(linux, 'ioctl', side_effect=OSError('boom')):
            raised = False
            try:
                p.disc_status('/dev/sr0')
            except OSError:
                raised = True
        self.assertTrue(raised)
        close.assert_called_once_with(7)

    def test_freebsd_skips_ioctl(self):
        # Issue #686: FreeBSD must not call the Linux-only ioctl
        p = freebsd.FreeBSDPlatform()
        with mock.patch.object(freebsd.os, 'open') as open_:
            rc = p.disc_status('/dev/cd0')
        self.assertEqual(rc, base.CDS_NO_INFO)
        open_.assert_not_called()

    def test_freebsd_tolerates_missing_node(self):
        p = freebsd.FreeBSDPlatform()
        self.assertEqual(p.disc_status('/nonexistent/cd0'), base.CDS_NO_INFO)


class DriveDelegationTestCase(common.TestCase):

    def test_get_cdrom_drive_status_delegates(self):
        with mock.patch.object(drive.platform, 'disc_status',
                               return_value=base.CDS_DISC_OK) as ds:
            rc = drive.get_cdrom_drive_status('/dev/sr0')
        self.assertEqual(rc, base.CDS_DISC_OK)
        ds.assert_called_once_with('/dev/sr0')

    def test_getAllDevicePaths_delegates(self):
        with mock.patch.object(drive.platform, 'get_all_device_paths',
                               return_value=['/dev/sr0']) as gap:
            self.assertEqual(drive.getAllDevicePaths(), ['/dev/sr0'])
        gap.assert_called_once()

    def test_getDeviceInfo_delegates(self):
        with mock.patch.object(drive.platform, 'get_device_info',
                               return_value=('PLEXTOR', 'PX-750A', '1.02')) \
                as gdi:
            self.assertEqual(
                drive.getDeviceInfo('/dev/cd0'),
                ('PLEXTOR', 'PX-750A', '1.02'))
        gdi.assert_called_once_with('/dev/cd0')


if __name__ == '__main__':
    unittest.main()
