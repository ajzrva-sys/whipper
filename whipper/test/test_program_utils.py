# -*- Mode: Python; test-case-name: whipper.test.test_program_utils -*-
# vi:si:et:sw=4:sts=4:ts=4

import subprocess
from unittest import mock

from whipper.platform import base, freebsd, linux
from whipper.test import common


class LinuxUnmountTestCase(common.TestCase):

    def test_unmounts_listed_device(self):
        p = linux.LinuxPlatform()
        with mock.patch.object(base.os.path, 'realpath',
                               side_effect=lambda p: p), \
             mock.patch('builtins.open',
                        mock.mock_open(
                            read_data='/dev/sr0 /mnt iso9660 ro 0 0\n')), \
             mock.patch('whipper.platform.base.subprocess.check_output') as co:
            p.unmount('/dev/sr0')
            co.assert_called_once_with(
                ['umount', '/dev/sr0'], stderr=subprocess.STDOUT)

    def test_skips_unlisted_device(self):
        p = linux.LinuxPlatform()
        with mock.patch.object(base.os.path, 'realpath',
                               side_effect=lambda p: p), \
             mock.patch('builtins.open',
                        mock.mock_open(
                            read_data='/dev/other /mnt iso9660 ro 0 0\n')), \
             mock.patch('whipper.platform.base.subprocess.check_output') as co:
            p.unmount('/dev/sr0')
            co.assert_not_called()


class FreeBSDUnmountTestCase(common.TestCase):

    def test_uses_mount_table(self):
        calls = []

        def fake_check_output(cmd, **kwargs):
            calls.append(list(cmd))
            if list(cmd) == ['mount']:
                return b'/dev/cd0 on /mnt (cd9660, local, noatime)\n'
            return b''

        p = freebsd.FreeBSDPlatform()
        with mock.patch.object(base.os.path, 'realpath',
                               side_effect=lambda p: p), \
             mock.patch('subprocess.check_output',
                        side_effect=fake_check_output):
            p.unmount('/dev/cd0')
        self.assertEqual(calls[0], ['mount'])
        self.assertEqual(calls[1], ['umount', '/dev/cd0'])

    def test_no_open_proc_mounts(self):
        p = freebsd.FreeBSDPlatform()
        with mock.patch.object(base.os.path, 'realpath',
                               side_effect=lambda p: p), \
             mock.patch('builtins.open',
                        side_effect=AssertionError('opened /proc?')), \
             mock.patch('whipper.platform.freebsd.subprocess.check_output',
                        return_value=b'(nothing mounted here)\n') as co:
            p.unmount('/dev/cd0')
            co.assert_called_once_with(['mount'], stderr=subprocess.DEVNULL)

    def test_mount_failure_is_soft(self):
        p = freebsd.FreeBSDPlatform()
        with mock.patch.object(base.os.path, 'realpath',
                               side_effect=lambda p: p), \
             mock.patch('whipper.platform.freebsd.subprocess.check_output',
                        side_effect=FileNotFoundError('mount')):
            p.unmount('/dev/cd0')


class TrayCommandTestCase(common.TestCase):

    def test_linux_uses_eject(self):
        p = linux.LinuxPlatform()
        with mock.patch('whipper.platform.base.subprocess.check_output') as co:
            p.eject('/dev/sr0')
            p.load('/dev/sr0')
        co.assert_any_call(['eject', '/dev/sr0'], stderr=subprocess.STDOUT)
        co.assert_any_call(['eject', '-t', '/dev/sr0'],
                           stderr=subprocess.STDOUT)

    def test_freebsd_prefers_camcontrol(self):
        p = freebsd.FreeBSDPlatform()
        with mock.patch.object(freebsd.os.path, 'realpath',
                               side_effect=lambda p: p), \
             mock.patch('whipper.platform.base.subprocess.check_output') as co:
            p.eject('/dev/cd0')
            p.load('/dev/cd0')
        cmds = [c[0][0] for c in co.call_args_list]
        self.assertEqual(cmds[0], ['camcontrol', 'eject', 'cd0'])
        self.assertEqual(cmds[1], ['camcontrol', 'load', 'cd0'])
        # successful camcontrol means eject(1) is not attempted
        self.assertEqual(len(cmds), 2)

    def test_missing_eject_is_soft_on_linux(self):
        p = linux.LinuxPlatform()
        with mock.patch('whipper.platform.base.subprocess.check_output',
                        side_effect=FileNotFoundError('eject')):
            p.eject('/dev/sr0')
            p.load('/dev/sr0')

    def test_freebsd_falls_back_to_eject_when_camcontrol_missing(self):
        def fake_check_output(cmd, **kwargs):
            if cmd[0] == 'camcontrol':
                raise FileNotFoundError('camcontrol')
            return b''

        p = freebsd.FreeBSDPlatform()
        with mock.patch.object(freebsd.os.path, 'realpath',
                               side_effect=lambda p: p), \
             mock.patch('whipper.platform.base.subprocess.check_output',
                        side_effect=fake_check_output) as co:
            p.eject('/dev/cd0')
            p.load('/dev/cd0')
        cmds = [c[0][0] for c in co.call_args_list]
        self.assertIn(['eject', '/dev/cd0'], cmds)
        self.assertIn(['eject', '-t', '/dev/cd0'], cmds)

    def test_missing_camcontrol_is_soft_on_freebsd(self):
        p = freebsd.FreeBSDPlatform()
        with mock.patch.object(freebsd.os.path, 'realpath',
                               side_effect=lambda p: p), \
             mock.patch('whipper.platform.base.subprocess.check_output',
                        side_effect=FileNotFoundError('camcontrol')):
            p.eject('/dev/cd0')
            p.load('/dev/cd0')
