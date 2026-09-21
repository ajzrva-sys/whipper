# -*- Mode: Python; test-case-name: whipper.test.test_command_drive -*-
# vi:si:et:sw=4:sts=4:ts=4

import sys
from unittest import mock

from whipper.command import drive as drive_cmd
from whipper.common import drive as common_drive
from whipper.test import common


class DriveListTestCase(common.TestCase):

    def test_lists_paths_with_unknown_identity(self):
        cmd = drive_cmd.List.__new__(drive_cmd.List)
        cmd.config = mock.Mock()
        paths = ['/dev/cd0']
        printed = []
        with mock.patch.object(drive_cmd.drive, 'getAllDevicePaths',
                               return_value=paths), \
             mock.patch.object(drive_cmd.drive, 'getDeviceInfo',
                               return_value=None), \
             mock.patch('builtins.print',
                        side_effect=lambda *a, **k: printed.append(a)):
            cmd.do()
        self.assertTrue(any('/dev/cd0' in str(chunk) for chunk in printed))
        self.assertTrue(
            any('unknown' in str(chunk) for chunk in printed))

    def test_lists_paths_with_camcontrol_identity(self):
        cmd = drive_cmd.List.__new__(drive_cmd.List)
        cmd.config = mock.Mock()
        cmd.config.getReadOffset.side_effect = KeyError
        cmd.config.getDefeatsCache.side_effect = KeyError
        printed = []
        with mock.patch.object(drive_cmd.drive, 'getAllDevicePaths',
                               return_value=['/dev/cd0']), \
             mock.patch.object(
                 drive_cmd.drive, 'getDeviceInfo',
                 return_value=('PLEXTOR', 'DVDR PX-750A', '1.02')), \
             mock.patch('builtins.print',
                        side_effect=lambda *a, **k: printed.append(a)):
            cmd.do()
        joined = ' '.join(str(c) for c in printed)
        self.assertIn('/dev/cd0', joined)
        self.assertIn('PLEXTOR', joined)
        self.assertIn('PX-750A', joined)

    def test_empty_paths_returns_without_import(self):
        cmd = drive_cmd.List.__new__(drive_cmd.List)
        cmd.config = mock.Mock()
        with mock.patch.object(drive_cmd.drive, 'getAllDevicePaths',
                               return_value=[]), \
             mock.patch('builtins.print') as print_:
            cmd.do()
        print_.assert_not_called()


class CamcontrolDeviceInfoTestCase(common.TestCase):

    _INQUIRY = (
        'pass1: <PLEXTOR DVDR   PX-750A 1.02> Removable CD-ROM SCSI device\n'
        'pass1: Serial Number 20770101\n'
    )

    def test_parses_camcontrol_inquiry(self):
        with mock.patch('whipper.common.drive.subprocess.check_output',
                        return_value=self._INQUIRY.encode()), \
             mock.patch('whipper.common.drive.os.path.realpath',
                        side_effect=lambda p: p):
            info = common_drive._getDeviceInfoCamcontrol('/dev/cd0')
        # preserve inquiry spacing inside the model string
        self.assertEqual(info, ('PLEXTOR', 'DVDR   PX-750A', '1.02'))

    def test_getDeviceInfo_falls_back_on_freebsd_without_pycdio(self):
        with mock.patch.dict(sys.modules, {'cdio': None}), \
             mock.patch('whipper.common.drive.sys.platform', 'freebsd15'), \
             mock.patch.object(
                 common_drive, '_getDeviceInfoCamcontrol',
                 return_value=('PLEXTOR', 'PX-750A', '1.02')) as fb:
            info = common_drive.getDeviceInfo('/dev/cd0')
        self.assertEqual(info, ('PLEXTOR', 'PX-750A', '1.02'))
        fb.assert_called_once_with('/dev/cd0')

    def test_getDeviceInfo_returns_none_on_linux_without_pycdio(self):
        with mock.patch.dict(sys.modules, {'cdio': None}), \
             mock.patch('whipper.common.drive.sys.platform', 'linux'), \
             mock.patch.object(common_drive, '_getDeviceInfoCamcontrol') as fb:
            info = common_drive.getDeviceInfo('/dev/sr0')
        self.assertIsNone(info)
        fb.assert_not_called()
