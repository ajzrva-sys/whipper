# -*- Mode: Python; test-case-name: whipper.test.test_program_utils -*-
# vi:si:et:sw=4:sts=4:ts=4

import subprocess
from unittest import mock

from whipper.program import utils
from whipper.test import common


class UnmountDeviceTestCase(common.TestCase):

    def test_linux_unmounts_listed_device(self):
        with mock.patch('whipper.program.utils.platform.system',
                        return_value='Linux'), \
             mock.patch('whipper.program.utils.os.path.realpath',
                        side_effect=lambda p: p), \
             mock.patch('builtins.open',
                        mock.mock_open(
                            read_data='/dev/sr0 /mnt iso9660 ro 0 0\n')), \
             mock.patch('whipper.program.utils.subprocess.check_output') as co:
            utils.unmount_device('/dev/sr0')
            co.assert_called_once_with(
                ['umount', '/dev/sr0'], stderr=subprocess.STDOUT)

    def test_linux_skips_unlisted_device(self):
        with mock.patch('whipper.program.utils.platform.system',
                        return_value='Linux'), \
             mock.patch('whipper.program.utils.os.path.realpath',
                        side_effect=lambda p: p), \
             mock.patch('builtins.open',
                        mock.mock_open(
                            read_data='/dev/other /mnt iso9660 ro 0 0\n')), \
             mock.patch('whipper.program.utils.subprocess.check_output') as co:
            utils.unmount_device('/dev/sr0')
            co.assert_not_called()

    def test_freebsd_uses_mount_table(self):
        def fake_check_output(cmd, **kwargs):
            if list(cmd) == ['mount']:
                return b'/dev/cd0 on /mnt (cd9660, local, noatime)\n'
            return b''

        with mock.patch('whipper.program.utils.platform.system',
                        return_value='FreeBSD'), \
             mock.patch('whipper.program.utils.os.path.realpath',
                        side_effect=lambda p: p), \
             mock.patch('whipper.program.utils.subprocess.check_output',
                        side_effect=fake_check_output) as co:
            utils.unmount_device('/dev/cd0')
            cmds = [c[0][0] for c in co.call_args_list]
            self.assertEqual(cmds[0], ['mount'])
            self.assertEqual(cmds[1], ['umount', '/dev/cd0'])

    def test_freebsd_no_open_proc_mounts(self):
        with mock.patch('whipper.program.utils.platform.system',
                        return_value='FreeBSD'), \
             mock.patch('whipper.program.utils.os.path.realpath',
                        side_effect=lambda p: p), \
             mock.patch('builtins.open',
                        side_effect=AssertionError('opened /proc?')), \
             mock.patch('whipper.program.utils.subprocess.check_output',
                        return_value=b'(nothing mounted here)\n') as co:
            utils.unmount_device('/dev/cd0')
            co.assert_called_once_with(['mount'], stderr=subprocess.DEVNULL)

    def test_freebsd_mount_failure_is_soft(self):
        with mock.patch('whipper.program.utils.platform.system',
                        return_value='FreeBSD'), \
             mock.patch('whipper.program.utils.os.path.realpath',
                        side_effect=lambda p: p), \
             mock.patch('whipper.program.utils.subprocess.check_output',
                        side_effect=FileNotFoundError('mount')):
            utils.unmount_device('/dev/cd0')


class TrayCommandTestCase(common.TestCase):

    def test_linux_uses_eject(self):
        with mock.patch('whipper.program.utils.platform.system',
                        return_value='Linux'), \
             mock.patch('whipper.program.utils.subprocess.check_output') as co:
            utils.eject_device('/dev/sr0')
            utils.load_device('/dev/sr0')
        co.assert_any_call(['eject', '/dev/sr0'], stderr=subprocess.STDOUT)
        co.assert_any_call(['eject', '-t', '/dev/sr0'],
                           stderr=subprocess.STDOUT)

    def test_freebsd_prefers_camcontrol(self):
        with mock.patch('whipper.program.utils.platform.system',
                        return_value='FreeBSD'), \
             mock.patch('whipper.program.utils.os.path.realpath',
                        side_effect=lambda p: p), \
             mock.patch('whipper.program.utils.subprocess.check_output') as co:
            utils.eject_device('/dev/cd0')
            utils.load_device('/dev/cd0')
        cmds = [c[0][0] for c in co.call_args_list]
        self.assertEqual(cmds[0], ['camcontrol', 'eject', 'cd0'])
        self.assertEqual(cmds[1], ['camcontrol', 'load', 'cd0'])
        # successful camcontrol means eject(1) is not attempted
        self.assertEqual(len(cmds), 2)

    def test_missing_eject_is_soft_on_linux(self):
        with mock.patch('whipper.program.utils.platform.system',
                        return_value='Linux'), \
             mock.patch('whipper.program.utils.subprocess.check_output',
                        side_effect=FileNotFoundError('eject')):
            utils.eject_device('/dev/sr0')
            utils.load_device('/dev/sr0')

    def test_freebsd_falls_back_to_eject_when_camcontrol_missing(self):
        def fake_check_output(cmd, **kwargs):
            if cmd[0] == 'camcontrol':
                raise FileNotFoundError('camcontrol')
            return b''

        with mock.patch('whipper.program.utils.platform.system',
                        return_value='FreeBSD'), \
             mock.patch('whipper.program.utils.os.path.realpath',
                        side_effect=lambda p: p), \
             mock.patch('whipper.program.utils.subprocess.check_output',
                        side_effect=fake_check_output) as co:
            utils.eject_device('/dev/cd0')
            utils.load_device('/dev/cd0')
        cmds = [c[0][0] for c in co.call_args_list]
        self.assertIn(['eject', '/dev/cd0'], cmds)
        self.assertIn(['eject', '-t', '/dev/cd0'], cmds)

    def test_missing_camcontrol_is_soft_on_freebsd(self):
        with mock.patch('whipper.program.utils.platform.system',
                        return_value='FreeBSD'), \
             mock.patch('whipper.program.utils.os.path.realpath',
                        side_effect=lambda p: p), \
             mock.patch('whipper.program.utils.subprocess.check_output',
                        side_effect=FileNotFoundError('camcontrol')):
            utils.eject_device('/dev/cd0')
            utils.load_device('/dev/cd0')
