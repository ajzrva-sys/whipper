# -*- Mode: Python; test-case-name: whipper.test.test_program_cdparanoia -*-
# vi:si:et:sw=4:sts=4:ts=4

import os
from unittest import mock

from whipper.program import cdrdao
from whipper.test import common

# TODO: Current test architecture makes testing cdrdao difficult. Revisit.


class VersionTestCase(common.TestCase):
    def testGetVersion(self):
        v = cdrdao.version()
        self.assertTrue(v)
        # make sure it starts with a digit
        self.assertTrue(int(v[0]))


class ReadTOCErrorTestCase(common.TestCase):

    def testMissingTocIncludesParsedStderr(self):
        task = cdrdao.ReadTOCTask('/dev/test')
        os.close(task.fd)
        os.unlink(task.tocfile)
        task._popen = mock.Mock()
        task._popen.recv_err.side_effect = [
            b'ERROR: Cannot open device\xff\n', b'']
        task._popen.poll.return_value = 1
        task._popen.returncode = 1
        task.schedule = mock.Mock()
        task.stop = mock.Mock()

        task._read(None)
        self.assertEqual(task._buffer, '')
        task._read(None)

        self.assertIsInstance(task.exception, FileNotFoundError)
        self.assertIn('Cannot open device\ufffd', str(task.exception))
        self.assertIn('returncode=1', str(task.exception))

    def testStderrTailIsBounded(self):
        task = cdrdao.ReadTOCTask('/dev/test')
        os.close(task.fd)
        self.addCleanup(os.unlink, task.tocfile)
        task._popen = mock.Mock()
        task._popen.recv_err.return_value = b'x' * 1000 + b'last error\n'
        task.schedule = mock.Mock()

        task._read(None)

        self.assertEqual(len(task._stderr_tail), 500)
        self.assertTrue(task._stderr_tail.endswith('last error\n'))
