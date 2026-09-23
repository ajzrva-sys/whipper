# -*- Mode: Python; test-case-name: whipper.test.test_common_program -*-
# vi:si:et:sw=4:sts=4:ts=4


import os
import unittest
import wave
from unittest import mock

from tempfile import TemporaryDirectory
from whipper.common import program, mbngs, config

# Keep in sync with whipper.command.cd.DEFAULT_DISC_TEMPLATE.
# Imported as a literal so this unit test does not need pycdio/cdio.
DEFAULT_DISC_TEMPLATE = '%r/%A - %d/%A - %d'


class PathTestCase(unittest.TestCase):

    def testTemplateUsesDestinationFilenameLimit(self):
        prog = program.Program(config.Config())
        with mock.patch('whipper.common.common.name_max_for',
                        side_effect=lambda p: 143 if p.startswith('/destination')
                        else 255) as limit:
            path = prog.getPath('/destination', '%A/%d', 'x' * 300, None)
        self.assertTrue(all(call.args[0].startswith('/destination')
                            for call in limit.call_args_list))
        self.assertLessEqual(len((os.path.basename(path) + '.flac').encode()),
                             143)

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

    def testIssue585UnknownDiscDiscNumberTemplate(self):
        """%N/%M must not KeyError when ripping without MusicBrainz data."""
        prog = program.Program(config.Config())
        path = prog.getPath('/tmp', '%A - %d/%N-%t %n',
                            'mbdiscid', None, 3)
        self.assertEqual(
            path,
            '/tmp/Unknown Artist - mbdiscid/1-03 Unknown Track 3')

    def testIssue585UnknownDiscDiscTotals(self):
        prog = program.Program(config.Config())
        path = prog.getPath('/tmp', '%M-%N', 'mbdiscid', None)
        self.assertEqual(path, '/tmp/1-1')

    def testIssue585MetadataWithoutDiscNumbers(self):
        prog = program.Program(config.Config())
        md = mbngs.DiscMetadata()
        md.artist = md.sortName = 'Jeff Buckley'
        md.releaseTitle = 'Grace'
        # discNumber/discTotal remain None
        path = prog.getPath('/tmp', '%A/%M-%N', 'mbdiscid', md)
        self.assertEqual(path, '/tmp/Jeff Buckley/1-1')

    def testIssue453LongTitlesTruncated(self):
        """#453: extremely long release titles must not exceed NAME_MAX."""
        prog = program.Program(config.Config())
        md = mbngs.DiscMetadata()
        md.artist = md.sortName = 'Soulwax'
        # Path length that historically raised ENAMETOOLONG
        md.releaseTitle = (
            "Most of the remixes we've made for other people over the "
            "years except for the one for Einstürzende Neubauten because "
            "we lost it and a few we didn't think sounded good enough "
            "or just didn't fit in length-wise, but including some that "
            "are hard to find because either people forgot about them or "
            "just simply because they haven't been released yet"
        )
        md.title = md.releaseTitle
        path = prog.getPath('/tmp', '%A - %d/%A - %d',
                            'mbdiscid', md, 0)
        for part in path.split(os.sep):
            if part:
                self.assertLessEqual(len(part.encode('utf-8')), 255)
        self.assertTrue(path.startswith('/tmp/Soulwax'))
        # Adding extensions must stay within NAME_MAX too
        flac = path + '.flac'
        self.assertLessEqual(len(os.path.basename(flac).encode('utf-8')), 255)


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

    def testExistingAudioMustMatchDiscLengthAndFormat(self):
        from whipper.extern.task.task import SyncRunner
        from whipper.result.result import TrackResult
        for samples, rate, channels, width, accepted in (
                (588, 44100, 2, 2, False),
                (1176, 48000, 2, 2, False),
                (1176, 44100, 1, 2, False),
                (1176, 44100, 2, 1, False),
                (1176, 44100, 2, 2, True)):
            with self.subTest(samples=samples, rate=rate,
                              channels=channels, width=width):
                with TemporaryDirectory() as directory:
                    track = TrackResult()
                    track.filename = os.path.join(directory, 'track.wav')
                    with wave.open(track.filename, 'wb') as audio:
                        audio.setnchannels(channels)
                        audio.setsampwidth(width)
                        audio.setframerate(rate)
                        audio.writeframes(b'\0' * (samples * channels * width))
                    self.assertEqual(program.Program.verifyTrack(
                        SyncRunner(), track, expectedFrames=2), accepted)
                    if not accepted:
                        self.assertIsNone(track.testcrc)
                        self.assertIsNone(track.copycrc)

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
        """Save fetched cover bytes under the expected name, offline."""
        release_id = '76df3287-6cda-33eb-8e9a-044b5e15ffdd'
        payload = self._mock_get_front_image(release_id)
        with TemporaryDirectory() as directory:
            with mock.patch.object(program, 'fetch_front_image',
                                   return_value=payload) as fetch:
                path = program.Program.getCoverArt(directory, release_id)
            fetch.assert_called_once_with(release_id)
            self.assertEqual(path, os.path.join(directory, 'cover.jpg'))
            with open(path, 'rb') as cover:
                self.assertEqual(cover.read(), payload)

    def testFetchFrontImageUsesGetImageFront(self):
        payload = b'\xff\xd8fakejpeg'
        with mock.patch.object(program.musicbrainzngs, 'get_image_front',
                               return_value=payload) as front:
            data = program.fetch_front_image('release-id', 500)
        self.assertEqual(data, payload)
        front.assert_called_once_with('release-id', 500)

    def testBackOnlyImageIsNotUsedAsFront(self):
        listing = {'images': [{'front': False,
                               'image': 'https://example.invalid/back.jpg'}]}
        with mock.patch.object(program.musicbrainzngs, 'get_image_front',
                               None), \
                mock.patch.object(program.musicbrainzngs, 'get_image_list',
                                  return_value=listing), \
                mock.patch('urllib.request.urlopen') as fetch:
            self.assertIsNone(program.fetch_front_image('release-id'))
        fetch.assert_not_called()

    def testFetchFrontImageFallbackWithoutGetImageFront(self):
        """Issue #554: some musicbrainzngs builds lack get_image_front."""
        payload = b'\xff\xd8fallback'
        listing = {
            'images': [{
                'front': True,
                'image': 'https://coverartarchive.org/release/x/front',
                'thumbnails': {
                    '500': 'https://coverartarchive.org/release/x/front-500',
                },
            }]
        }

        class FakeResponse:
            def read(self):
                return payload

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        with mock.patch.object(program.musicbrainzngs, 'get_image_front',
                               None), \
                mock.patch.object(program.musicbrainzngs, 'get_image_list',
                                  return_value=listing) as image_list, \
                mock.patch('urllib.request.urlopen',
                           return_value=FakeResponse()) as urlopen:
            data = program.fetch_front_image('release-id', 500)

        self.assertEqual(data, payload)
        image_list.assert_called_once_with('release-id')
        urlopen.assert_called_once()
        self.assertIn('front-500', urlopen.call_args[0][0])
