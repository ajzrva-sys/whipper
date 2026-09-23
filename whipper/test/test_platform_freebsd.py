import subprocess
import unittest
from unittest import mock

from whipper.platform.freebsd import FreeBSDPlatform


class MountTestCase(unittest.TestCase):

    def testMatchesCompleteDeviceField(self):
        mounts = (b'/dev/cd10 /media/disc cd9660 ro 0 0\n'
                  b'tmpfs /dev/cd1 tmpfs rw 0 0\n')
        platform = FreeBSDPlatform()
        with mock.patch('whipper.platform.freebsd.subprocess.check_output',
                        return_value=mounts) as command:
            self.assertFalse(platform.is_mounted('/dev/cd1'))
            self.assertTrue(platform.is_mounted('/dev/cd10'))
        command.assert_called_with(['mount', '-p'],
                                   stderr=subprocess.DEVNULL)

    def testMountCommandFailureReturnsFalse(self):
        with mock.patch('whipper.platform.freebsd.subprocess.check_output',
                        side_effect=OSError('mount unavailable')):
            self.assertFalse(FreeBSDPlatform().is_mounted('/dev/cd0'))

    def testUnmountUsesExactDeviceArgument(self):
        mounts = b'/dev/cd0 /media/disc cd9660 ro 0 0\n'
        with mock.patch('whipper.platform.freebsd.subprocess.check_output',
                        side_effect=[mounts, b'']) as command, \
                mock.patch('builtins.print'):
            FreeBSDPlatform().unmount('/dev/cd0')
        self.assertEqual(command.call_args_list, [
            mock.call(['mount', '-p'], stderr=subprocess.DEVNULL),
            mock.call(['umount', '/dev/cd0'], stderr=subprocess.STDOUT),
        ])

    def testUnmountCommandFailuresAreReported(self):
        mounts = b'/dev/cd0 /media/disc cd9660 ro 0 0\n'
        errors = [FileNotFoundError('umount unavailable'),
                  subprocess.CalledProcessError(1, ['umount', '/dev/cd0'])]
        for error in errors:
            with self.subTest(error=error), \
                    mock.patch('whipper.platform.freebsd.subprocess.'
                               'check_output', side_effect=[mounts, error]), \
                    mock.patch('builtins.print'), \
                    self.assertLogs('whipper.platform.base', 'WARNING') as log:
                FreeBSDPlatform().unmount('/dev/cd0')
            self.assertIn('could not unmount /dev/cd0', log.output[0])
