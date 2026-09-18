# -*- Mode: Python; test-case-name: whipper.test.test_common_drive -*-
# vi:si:et:sw=4:sts=4:ts=4

import os
import sys
import tempfile
import unittest
from unittest import mock

from whipper.test import common
from whipper.common import drive


class ListifyTestCase(common.TestCase):

    def testString(self):
        string = '/dev/sr0'
        self.assertEqual(drive._listify(string), [string, ])

    def testList(self):
        lst = ['/dev/scd0', '/dev/sr0']
        self.assertEqual(drive._listify(lst), lst)


class StaticDevicePathsTestCase(common.TestCase):

    def test_includes_freebsd_nodes(self):
        # Issue #686: FreeBSD optical devices are /dev/cd0 (CAM) or /dev/acd0
        self.assertIn('/dev/cd0', drive._STATIC_DEVICE_CANDIDATES)
        self.assertIn('/dev/acd0', drive._STATIC_DEVICE_CANDIDATES)
        self.assertIn('/dev/cdrom', drive._STATIC_DEVICE_CANDIDATES)

    def test_existing_nodes_listed(self):
        found = drive._getAllDevicePathsStatic()
        for path in found:
            self.assertTrue(os.path.exists(path))


class CdromDriveStatusTestCase(common.TestCase):

    def test_linux_uses_ioctl(self):
        with mock.patch.object(drive.sys, 'platform', 'linux'), \
             mock.patch.object(drive.os, 'open', return_value=3) as open_, \
             mock.patch.object(drive.os, 'close') as close, \
             mock.patch.object(drive, 'ioctl',
                               return_value=drive.CDS_DISC_OK) as ioctl:
            rc = drive.get_cdrom_drive_status('/dev/sr0')
        self.assertEqual(rc, drive.CDS_DISC_OK)
        open_.assert_called_once()
        ioctl.assert_called_once_with(3, drive._CDROM_DRIVE_STATUS)
        close.assert_called_once_with(3)

    def test_non_linux_skips_ioctl(self):
        # Issue #686: FreeBSD must not call the Linux-only ioctl
        with mock.patch.object(drive.sys, 'platform', 'freebsd15'), \
             mock.patch.object(drive.os, 'open') as open_, \
             mock.patch.object(drive, 'ioctl') as ioctl:
            rc = drive.get_cdrom_drive_status('/dev/cd0')
        self.assertEqual(rc, drive.CDS_NO_INFO)
        open_.assert_not_called()
        ioctl.assert_not_called()

    def test_linux_closes_fd_on_error(self):
        with mock.patch.object(drive.sys, 'platform', 'linux'), \
             mock.patch.object(drive.os, 'open', return_value=7), \
             mock.patch.object(drive.os, 'close') as close, \
             mock.patch.object(drive, 'ioctl',
                               side_effect=OSError('boom')):
            raised = False
            try:
                drive.get_cdrom_drive_status('/dev/sr0')
            except OSError:
                raised = True
        self.assertTrue(raised)
        close.assert_called_once_with(7)

    @unittest.skipUnless(sys.platform.startswith('linux'),
                         'real ioctl path only on Linux')
    def test_real_linux_ioctl_runs(self):
        # Smoke test: should not raise for a non-CD path on Linux
        # (ioctl may fail with ENOTTY — that is acceptable OS behaviour)
        try:
            drive.get_cdrom_drive_status('/dev/null')
        except OSError:
            pass

    def test_freebsd_path_tolerates_missing_node(self):
        with mock.patch.object(drive.sys, 'platform', 'freebsd15'):
            self.assertEqual(
                drive.get_cdrom_drive_status('/nonexistent/cd0'),
                drive.CDS_NO_INFO)

    def test_mkstemp_path_not_opened_on_freebsd(self):
        fd, path = tempfile.mkstemp()
        os.close(fd)
        try:
            with mock.patch.object(drive.sys, 'platform', 'freebsd15'), \
                 mock.patch.object(drive.os, 'open') as open_:
                self.assertEqual(drive.get_cdrom_drive_status(path),
                                 drive.CDS_NO_INFO)
            open_.assert_not_called()
        finally:
            os.unlink(path)
