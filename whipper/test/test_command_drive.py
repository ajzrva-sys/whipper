# -*- Mode: Python; test-case-name: whipper.test.test_command_drive -*-
# vi:si:et:sw=4:sts=4:ts=4

import sys
from unittest import mock

from whipper.command import drive as drive_cmd
from whipper.test import common


class DriveListTestCase(common.TestCase):

    def _list_without_pycdio(self, paths):
        cmd = drive_cmd.List.__new__(drive_cmd.List)
        cmd.config = mock.Mock()
        with mock.patch.object(drive_cmd.drive, 'getAllDevicePaths',
                               return_value=paths), \
             mock.patch.dict(sys.modules, {'cdio': None}):
            cmd.do()

    def test_lists_paths_without_pycdio(self):
        # FreeBSD boxes may have no pycdio package; paths must still print.
        paths = ['/dev/cd0']
        cmd = drive_cmd.List.__new__(drive_cmd.List)
        cmd.config = mock.Mock()
        printed = []
        with mock.patch.object(drive_cmd.drive, 'getAllDevicePaths',
                               return_value=paths), \
             mock.patch.dict(sys.modules, {'cdio': None}), \
             mock.patch('builtins.print',
                        side_effect=lambda *a, **k: printed.append(a)):
            cmd.do()
        self.assertTrue(any('/dev/cd0' in str(chunk) for chunk in printed))
        self.assertTrue(
            any('unknown' in str(chunk) for chunk in printed))

    def test_empty_paths_returns_without_import(self):
        cmd = drive_cmd.List.__new__(drive_cmd.List)
        cmd.config = mock.Mock()
        with mock.patch.object(drive_cmd.drive, 'getAllDevicePaths',
                               return_value=[]), \
             mock.patch('builtins.print') as print_:
            cmd.do()
        print_.assert_not_called()
