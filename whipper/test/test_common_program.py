# -*- Mode: Python; test-case-name: whipper.test.test_common_program -*-
# vi:si:et:sw=4:sts=4:ts=4


import os
import shutil
import unittest
from unittest import mock

from tempfile import NamedTemporaryFile
from whipper.common import program, mbngs, config

# Keep in sync with whipper.command.cd.DEFAULT_DISC_TEMPLATE.
# Literal avoids importing command.cd (requires pycdio).
DEFAULT_DISC_TEMPLATE = '%r/%A - %d/%A - %d'


class PathTestCase(unittest.TestCase):

    def testStandardTemplateEmpty(self):
        prog = program.Program(config.Config())

        path = prog.getPath('/tmp', DEFAULT_DISC_TEMPLATE,
                            'mbdiscid', None)
        self.assertEqual(path, ('/tmp/unknown/Unknown Artist - mbdiscid/'
                                'Unknown Artist - mbdiscid'))

    def testStandardTemplateFilled(self):
        prog = program.Program(config.Config())
        md = mbngs.DiscMetadata()
        md.artist = md.sortName = 'Jeff Buckley'
        md.releaseTitle = 'Grace'

        path = prog.getPath('/tmp', DEFAULT_DISC_TEMPLATE,
                            'mbdiscid', md, 0)
        self.assertEqual(path, ('/tmp/unknown/Jeff Buckley - Grace/'
                                'Jeff Buckley - Grace'))

    def testIssue66TemplateFilled(self):
        prog = program.Program(config.Config())
        md = mbngs.DiscMetadata()
        md.artist = md.sortName = 'Jeff Buckley'
        md.releaseTitle = 'Grace'

        path = prog.getPath('/tmp', '%A/%d', 'mbdiscid', md, 0)
        self.assertEqual(path,
                         '/tmp/Jeff Buckley/Grace')


class _FakeChecksumTask:
    def __init__(self, checksum):
        self.checksum = checksum


class _FakeRunner:
    def __init__(self, checksum):
        self._checksum = checksum
        self.ran = False

    def run(self, task):
        self.ran = True
        task.checksum = self._checksum


class VerifyTrackResumeTestCase(unittest.TestCase):
    """Issue #681: resume must not always re-rip when testcrc is None."""

    def testReuseExistingFileWhenNoPriorCrc(self):
        from whipper.result.result import TrackResult
        track = TrackResult()
        track.filename = '/tmp/01. Track.flac'
        track.testcrc = None
        runner = _FakeRunner(0xABCDEF01)
        with mock.patch('whipper.common.program.checksum.CRC32Task',
                        side_effect=lambda path, is_wave=False:
                        _FakeChecksumTask(0xABCDEF01)):
            ok = program.Program.verifyTrack(runner, track)
        self.assertTrue(ok)
        self.assertTrue(runner.ran)
        self.assertEqual(track.testcrc, 0xABCDEF01)
        self.assertEqual(track.copycrc, 0xABCDEF01)

    def testMismatchStillFailsWhenPriorCrcKnown(self):
        from whipper.result.result import TrackResult
        track = TrackResult()
        track.filename = '/tmp/01. Track.flac'
        track.testcrc = 0x11111111
        runner = _FakeRunner(0x22222222)
        with mock.patch('whipper.common.program.checksum.CRC32Task',
                        side_effect=lambda path, is_wave=False:
                        _FakeChecksumTask(0x22222222)):
            ok = program.Program.verifyTrack(runner, track)
        self.assertFalse(ok)

    def testMatchSucceedsWhenPriorCrcKnown(self):
        from whipper.result.result import TrackResult
        track = TrackResult()
        track.filename = '/tmp/01. Track.flac'
        track.testcrc = 0xABCDABCD
        runner = _FakeRunner(0xABCDABCD)
        with mock.patch('whipper.common.program.checksum.CRC32Task',
                        side_effect=lambda path, is_wave=False:
                        _FakeChecksumTask(0xABCDABCD)):
            ok = program.Program.verifyTrack(runner, track)
        self.assertTrue(ok)


# TODO: Test cover art embedding too.
class CoverArtTestCase(unittest.TestCase):

    @staticmethod
    def _mock_get_front_image(release_id):
        filename = '%s.jpg' % release_id
        path = os.path.join(os.path.dirname(__file__), filename)
        with open(path, 'rb') as f:
            return f.read()

    def testCoverArtPath(self):
        path = os.path.dirname(__file__)
        release_id = "76df3287-6cda-33eb-8e9a-044b5e15ffdd"
        cover_art_path = os.path.join(path, 'cover.jpg')
        data = self._mock_get_front_image(release_id)
        with NamedTemporaryFile(suffix='.cover.jpg', delete=False) as f:
            f.write(data)
        os.chmod(f.name, 0o644)
        shutil.move(f.name, cover_art_path)
        self.assertTrue(os.path.isfile(cover_art_path))
