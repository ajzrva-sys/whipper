# -*- Mode: Python; test-case-name: whipper.test.test_image_toc -*-
# vi:si:et:sw=4:sts=4:ts=4

"""Unit tests for crash guards #239/#550/#594/#654."""

import os
import tempfile
import unittest
from unittest import mock

from whipper.image import toc as toc_mod
from whipper.image import image as image_mod
from whipper.common import program as program_mod


class TocDecodeTestCase(unittest.TestCase):
    """#654: TOC/cue parse must not UnicodeDecodeError on bad bytes."""

    def testTocParseNonUtf8(self):
        fd, path = tempfile.mkstemp(suffix='.toc')
        os.close(fd)
        with open(path, 'wb') as f:
            f.write(b'CD_DA\nFILE "data.wav" 0 00:00:00\n'
                    b'TRACK AUDIO\nINDEX 00 00:00:00\n'
                    b'# bad byte \x89 here\n')
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        t = toc_mod.TocFile(path)
        try:
            t.parse()
        except UnicodeDecodeError:
            self.fail('TOC parse raised UnicodeDecodeError')
        except Exception:
            # other parse issues ok; must not be UnicodeDecodeError
            pass

    def testTocParseMissingFile(self):
        """#594: clear error when cdrdao never wrote the TOC."""
        t = toc_mod.TocFile('/nonexistent/tmp.cdrdao.read-toc.whipper.task')
        try:
            t.parse()
        except FileNotFoundError as e:
            self.assertIn('cdrdao', str(e).lower())
            return
        except Exception as e:
            self.fail('expected FileNotFoundError, got %r' % (e, ))
        self.fail('expected FileNotFoundError')


class CdrdaoDoneTestCase(unittest.TestCase):
    """#594: ReadTOCTask must not parse a missing TOC file."""

    def testDoneMissingTocRaisesCleanly(self):
        from whipper.program import cdrdao
        task = cdrdao.ReadTOCTask.__new__(cdrdao.ReadTOCTask)
        task.tocfile = '/nonexistent/no.cdrdao.toc'
        task.toc_path = None
        task.device = '/dev/sr0'
        task._buffer = 'ERROR: init failed\n'
        task._popen = mock.Mock(returncode=1)
        task._parser = cdrdao.ProgressParser()
        exceptions = []
        task.setAndRaiseException = exceptions.append
        task.stop = lambda: None
        task.setProgress = lambda v: None
        try:
            task._done()
        except Exception as e:
            # some task frameworks raise immediately
            self.assertIsInstance(e, (FileNotFoundError, OSError))
            return
        self.assertTrue(exceptions)
        self.assertIsInstance(exceptions[0], FileNotFoundError)


class ImageVerifyNonePathTestCase(unittest.TestCase):
    """#550: image verify must not AttributeError on None index.path."""

    def testConstructorSkipsNonePath(self):
        class FakeIndex:
            def __init__(self, path):
                self.path = path
                self.relative = 0

        class FakeTrack:
            def __init__(self, path):
                self.indexes = {0: FakeIndex(None), 1: FakeIndex(path)}
                self.number = 1

        class FakeCue:
            def __init__(self):
                self.table = mock.Mock()
                self.table.tracks = [FakeTrack(None)]

            @staticmethod
            def getTrackLength(track):
                return -1

        class FakeImage:
            def __init__(self):
                self.cue = FakeCue()

            @staticmethod
            def getRealPath(path):
                raise AttributeError("'NoneType' object has no attribute "
                                     "'path'")

        with mock.patch.object(image_mod.task.MultiSeparateTask, '__init__',
                               return_value=None):
            verify = image_mod.ImageVerifyTask(FakeImage(), skipped_tracks=[])
        self.assertEqual(getattr(verify, '_tasks', []), [])


class VerifyTrackNoPriorCrcTestCase(unittest.TestCase):
    """#239/#681: existing EAC files are not re-ripped when testcrc is None."""

    def testReuseWhenNoPriorCrc(self):
        from whipper.result.result import TrackResult
        track = TrackResult()
        track.filename = '/tmp/eac-01.flac'
        track.testcrc = None

        class FakeTask:
            checksum = 0xABCD1234

        class FakeRunner:
            def run(self, task):
                task.checksum = 0xABCD1234

        with mock.patch('whipper.common.program.checksum.CRC32Task',
                        side_effect=lambda *a, **k: FakeTask()):
            ok = program_mod.Program.verifyTrack(FakeRunner(), track)
        self.assertTrue(ok)
        self.assertEqual(track.testcrc, 0xABCD1234)
        self.assertEqual(track.copycrc, 0xABCD1234)

    def testMismatchStillFailsWhenCrcKnown(self):
        from whipper.result.result import TrackResult
        track = TrackResult()
        track.filename = '/tmp/eac-02.flac'
        track.testcrc = 0x1

        class FakeTask:
            checksum = 0x2

        class FakeRunner:
            def run(self, task):
                task.checksum = 0x2

        with mock.patch('whipper.common.program.checksum.CRC32Task',
                        side_effect=lambda *a, **k: FakeTask()):
            ok = program_mod.Program.verifyTrack(FakeRunner(), track)
        self.assertFalse(ok)
