"""Aborted and skipped rips must leave usable output and allow a retry."""

import argparse
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from whipper.command.cd import Rip
from whipper.common.program import Program
from whipper.common.yaml import YAML
from whipper.image.table import Table, Track
from whipper.result.logger import WhipperLogger, is_complete_rip_log
from whipper.result.result import RipResult, TrackResult


class PartialRipTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.disc = str(self.directory / 'disc')
        self.table = Table()
        for number in (1, 2, 3):
            track = Track(number)
            track.index(1, absolute=(number - 1) * 750, path='data.wav',
                        relative=(number - 1) * 750, counter=1)
            self.table.tracks.append(track)
        self.table.leadout = 2250
        self.table.getMusicBrainzDiscId = mock.Mock(return_value='mbid')
        self.table.getMusicBrainzSubmitURL = mock.Mock(return_value='url')
        self.program = Program.__new__(Program)
        self.program.result = RipResult()
        self.program.result.table = self.table
        self.program.getHTOA = mock.Mock(return_value=None)
        self.program.setWorkingDirectory = mock.Mock()
        self.program.getTagList = mock.Mock(return_value={})
        self.program.getPath = mock.Mock(side_effect=self.path)
        self.program.ripTrack = mock.Mock(side_effect=self.rip)
        self.program.verifyImage = mock.Mock()
        self.failed_track = 2

    def path(self, outdir, template, discid, metadata, track_number=None):
        return self.disc if track_number is None else str(
            self.directory / ('%02d' % track_number))

    def rip(self, runner, track, **kwargs):
        if track.number == self.failed_track:
            raise RuntimeError('drive read failed')
        Path(track.filename).write_bytes(b'completed audio')
        track.testcrc = track.copycrc = 1234
        track.peak = 100

    def command(self, keep_going=False):
        command = Rip.__new__(Rip)
        command.program = self.program
        command.itable = self.table
        command.mbdiscid = 'mbid'
        command.device = '/dev/cd0'
        command.runner = mock.Mock()
        command.logger = WhipperLogger()
        command.skipped_tracks = []
        command.options = argparse.Namespace(
            working_directory=None, output_directory=str(self.directory),
            offset=0, overread=False, logger=None, cover_art=None,
            disc_template='%A', track_template='%n', max_retries=1,
            keep_going=keep_going)
        return command

    def test_abort_outputs_only_completed_files_and_remains_retryable(self):
        with self.assertRaisesRegex(RuntimeError, 'track 2'):
            self.command().doCommand()
        cue = Path(self.disc + '.cue').read_text()
        playlist = Path(self.disc + '.m3u').read_text()
        log = Path(self.disc + '.log').read_text()
        self.assertIn('FILE "01.flac"', cue)
        self.assertNotIn('TRACK 02', cue)
        self.assertNotIn('TRACK 03', cue)
        self.assertNotIn('data.wav', cue)
        self.assertNotIn('02.flac', playlist)
        self.assertIn(self.table.accuraterip_path(), cue)
        parsed = YAML().load(log)
        self.assertEqual(parsed['Tracks'][2]['Status'], 'Error, missing CRC')
        self.assertFalse(parsed['Conclusive status report']['Rip completed'])
        self.assertFalse(is_complete_rip_log(self.disc + '.log'))
        self.assertEqual(self.table.tracks[1].getIndex(1).path, 'data.wav')
        self.program.verifyImage.assert_not_called()

    def test_keep_going_preserves_numbers_and_omits_failed_file(self):
        self.assertEqual(self.command(keep_going=True).doCommand(), 5)
        cue = Path(self.disc + '.cue').read_text()
        playlist = Path(self.disc + '.m3u').read_text()
        self.assertIn('TRACK 01', cue)
        self.assertIn('TRACK 03', cue)
        self.assertNotIn('TRACK 02', cue)
        self.assertNotIn('02.flac', cue + playlist)
        self.assertIn('03.flac', cue + playlist)
        self.assertFalse(is_complete_rip_log(self.disc + '.log'))
        self.program.verifyImage.assert_not_called()

    def test_failure_on_first_track_still_writes_playlist_and_log(self):
        self.failed_track = 1
        with self.assertRaises(RuntimeError):
            self.command().doCommand()
        self.assertFalse(Path(self.disc + '.cue').exists())
        self.assertEqual(Path(self.disc + '.m3u').read_text(), '#EXTM3U\n')
        self.assertFalse(is_complete_rip_log(self.disc + '.log'))
        self.assertIn('missing CRC', Path(self.disc + '.log').read_text())

    def test_artifact_failure_does_not_prevent_other_outputs(self):
        with mock.patch.object(self.program, 'writeCue',
                               side_effect=OSError('cue unavailable')), \
                mock.patch.object(self.program, 'write_m3u') as playlist, \
                mock.patch.object(self.program, 'writeLog') as log:
            self.program.writePartialResults(self.disc, WhipperLogger())
        playlist.assert_called_once_with(self.disc, partial=True)
        log.assert_called_once()

    def test_completed_result_without_audio_is_not_listed(self):
        track = TrackResult()
        track.number = 1
        track.filename = str(self.directory / 'missing.flac')
        track.testcrc = track.copycrc = 1234
        self.program.result.tracks.append(track)
        self.assertIsNone(self.program.writeCue(self.disc, partial=True))
        self.program.write_m3u(self.disc, partial=True)
        self.assertNotIn('missing.flac', Path(self.disc + '.m3u').read_text())

    def test_successful_audio_coverage_excludes_data_and_optional_htoa(self):
        rip = self.program.result
        self.table.tracks[2].audio = False
        for number in (1, 2):
            track = TrackResult()
            track.number = number
            track.filename = '%02d.flac' % number
            track.testcrc = track.copycrc = 0
            rip.tracks.append(track)
        self.assertTrue(rip.isComplete())
        rip.tracks[1].copycrc = None
        self.assertFalse(rip.isComplete())


class CompletedLogTest(unittest.TestCase):
    def test_legacy_missing_track_and_missing_crcs_remain_retryable(self):
        from whipper.test.test_result_logger import CompleteRipLogTestCase
        complete = CompleteRipLogTestCase.COMPLETE
        incomplete = [
            complete.replace('  1: {}', '  1: {}\n  2: {}'),
            complete.replace('    Test CRC: ABCD\n', ''),
            complete.replace('    Copy CRC: ABCD', '    Copy CRC: 1234'),
            complete.replace('Status: Copy OK', 'Status: Track not ripped'),
            complete.replace('  EOF:', '  Rip completed: false\n  EOF:'),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'rip.log')
            for content in incomplete:
                with self.subTest(content=content):
                    Path(path).write_text(content)
                    self.assertFalse(is_complete_rip_log(path))
