# -*- Mode: Python; test-case-name: whipper.test.test_image_verify -*-
# vi:si:et:sw=4:sts=4:ts=4

"""Issue #508: image verification must not KeyError on missing cue FILE."""

import os
import unittest
from types import SimpleNamespace
from unittest import mock

from whipper.image import image as image_mod
from whipper.common import program
from whipper.result.result import RipResult, TrackResult


class FakeIndex:
    def __init__(self, path, relative=0, absolute=0, number=1, counter=1):
        self.path = path
        self.relative = relative
        self.absolute = absolute
        self.number = number
        self.counter = counter


class FakeTrack:
    def __init__(self, path, number=1):
        self.number = number
        self.audio = True
        self.indexes = {0: FakeIndex(None, number=0),
                        1: FakeIndex(path, number=1)}


class FakeCue:
    def __init__(self, tracks):
        self.table = mock.Mock()
        self.table.tracks = tracks

    @staticmethod
    def getTrackLength(track):
        return -1


class FakeImage:
    def __init__(self, tracks):
        self.cue = FakeCue(tracks)

    @staticmethod
    def getRealPath(path):
        raise KeyError("Cannot find file for %r" % (path, ))


class ImageVerifyMissingFileTestCase(unittest.TestCase):

    def testMissingFirstFileDoesNotShiftAccurateRipChecksums(self):
        prog = program.Program.__new__(program.Program)
        prog.cuePath = '/tmp/disc.cue'
        prog.skipped_tracks = None
        prog.result = RipResult()
        for number in (1, 2):
            track = TrackResult()
            track.number = number
            prog.result.tracks.append(track)
        cue = FakeImage([FakeTrack(None, 1), FakeTrack('02.flac', 2)])
        cue.accuraterip_path = 'test-entry'
        response = SimpleNamespace(cddbDiscId='test-disc', confidences=[1, 1],
                                   checksums=['11111111', '22222222'])
        with mock.patch.object(program.image, 'Image', return_value=cue), \
                mock.patch.object(program.image, 'ImageVerifyTask',
                                  return_value=SimpleNamespace(exception=None)), \
                mock.patch.object(program.accurip, 'get_db_entry',
                                  return_value=[response]), \
                mock.patch('whipper.common.accurip.os.path.exists',
                           return_value=True), \
                mock.patch.object(program.accurip, 'accuraterip_checksum',
                                  return_value=(0x22222222, 0x22222222)) as crc:
            verified = prog.verifyImage(mock.Mock(), mock.Mock())
        self.assertFalse(verified)
        crc.assert_called_once_with('/tmp/02.flac', 2, 2)
        self.assertIsNone(prog.result.tracks[0].AR['v1']['CRC'])
        self.assertEqual(prog.result.tracks[1].AR['v1']['CRC'], '22222222')

    def testConstructorSkipsUnresolvablePath(self):
        """Missing cue FILE paths must not raise KeyError (#508)."""
        fake = FakeImage([FakeTrack('../../data.wav')])
        with mock.patch.object(image_mod.task.MultiSeparateTask, '__init__',
                               return_value=None):
            verify = image_mod.ImageVerifyTask(fake, skipped_tracks=[])
        self.assertIsNotNone(verify)
        # No audio-length tasks scheduled for the unresolvable path
        self.assertEqual(getattr(verify, '_tasks', []), [])

    def testConstructorSkipsEmptyPath(self):
        fake = FakeImage([FakeTrack(None)])
        with mock.patch.object(image_mod.task.MultiSeparateTask, '__init__',
                               return_value=None):
            verify = image_mod.ImageVerifyTask(fake, skipped_tracks=[])
        self.assertEqual(getattr(verify, '_tasks', []), [])

    def testSkippedBasenameStillSkips(self):
        fake = FakeImage([FakeTrack('missing.flac')])
        with mock.patch.object(image_mod.task.MultiSeparateTask, '__init__',
                               return_value=None):
            verify = image_mod.ImageVerifyTask(
                fake, skipped_tracks=['missing.flac'])
        self.assertEqual(getattr(verify, '_tasks', []), [])
        self.assertTrue(os.path.basename('missing.flac') in
                        ['missing.flac'])
