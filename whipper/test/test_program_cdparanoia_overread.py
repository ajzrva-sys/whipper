# -*- Mode: Python; test-case-name: whipper.test.test_program_cdparanoia_overread -*-
# vi:si:et:sw=4:sts=4:ts=4

import subprocess
from unittest import mock

from whipper.program import cdparanoia
from whipper.test import common


class ForceOverreadSupportTestCase(common.TestCase):

    def test_freebsd_stock_build_reports_unsupported(self):
        help_out = b"cdparanoia III release 10.2\n  -O --sample-offset <n>\n"
        with mock.patch('whipper.program.cdparanoia.subprocess.run') as run:
            run.return_value = mock.Mock(stdout=help_out)
            self.assertFalse(cdparanoia.supports_force_overread())

    def test_patched_build_reports_supported(self):
        help_out = b"  -x --force-overread : force overread\n"
        with mock.patch('whipper.program.cdparanoia.subprocess.run') as run:
            run.return_value = mock.Mock(stdout=help_out)
            self.assertTrue(cdparanoia.supports_force_overread())

    def test_missing_binary_is_unsupported(self):
        with mock.patch('whipper.program.cdparanoia.subprocess.run',
                        side_effect=FileNotFoundError('cd-paranoia')):
            self.assertFalse(cdparanoia.supports_force_overread())
