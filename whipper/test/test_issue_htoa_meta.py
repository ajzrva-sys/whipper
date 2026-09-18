# -*- Mode: Python; test-case-name: whipper.test.test_issue_htoa_meta -*-
# vi:si:et:sw=4:sts=4:ts=4

"""Unit tests for #282/#346/#309/#485 HTOA skip, default device, tags."""

import os
import tempfile
import unittest
from unittest import mock

from whipper.common import config as config_mod
from whipper.common import mbngs
from whipper.common import program as program_mod


class ConfigDefaultDeviceTestCase(unittest.TestCase):
    """#346: [main] device / command-section device sets default drive."""

    def testGetSetDefaultDevice(self):
        fd, path = tempfile.mkstemp(suffix='.whipperrc')
        os.close(fd)
        with open(path, 'w') as f:
            f.write('[main]\ndevice = /dev/sr1\n')
        self.addCleanup(lambda p=path: os.path.exists(p) and os.unlink(p))
        cfg = config_mod.Config(path)
        self.assertEqual(cfg.getDefaultDevice(), '/dev/sr1')

    def testSetDefaultDevice(self):
        fd, path = tempfile.mkstemp(suffix='.whipperrc')
        os.close(fd)
        with open(path, 'w') as f:
            f.write('')
        self.addCleanup(lambda p=path: os.path.exists(p) and os.unlink(p))
        cfg = config_mod.Config(path)
        cfg.setDefaultDevice('/dev/sr0')
        cfg2 = config_mod.Config(path)
        self.assertEqual(cfg2.getDefaultDevice(), '/dev/sr0')

    def testNoDefaultDevice(self):
        fd, path = tempfile.mkstemp(suffix='.whipperrc')
        os.close(fd)
        with open(path, 'w') as f:
            f.write('[whipper]\n')
        self.addCleanup(lambda p=path: os.path.exists(p) and os.unlink(p))
        cfg = config_mod.Config(path)
        self.assertIsNone(cfg.getDefaultDevice())


class GenreNamesTestCase(unittest.TestCase):
    """#309: extract genre names from MusicBrainz entities."""

    def testExtractGenres(self):
        entity = {'genre-list': [
            {'name': 'Rock', 'count': 5},
            {'name': 'Indie Rock', 'count': 2},
            {'name': 'Rock'},  # duplicate
            {'count': 1},  # missing name
        ]}
        self.assertEqual(mbngs._genre_names(entity),
                         ['Rock', 'Indie Rock'])

    def testEmptyGenres(self):
        self.assertEqual(mbngs._genre_names({}), [])
        self.assertEqual(mbngs._genre_names({'genre-list': []}), [])


class GetTagListTestCase(unittest.TestCase):
    """#485/#309: HTOA and genres tags."""

    def _program_with_meta(self):
        prog = program_mod.Program.__new__(program_mod.Program)
        md = mbngs.DiscMetadata()
        md.artist = 'Mates of State'
        md.sortName = 'Mates of State'
        md.title = 'Bring It Back'
        md.mbid = 'release-mbid'
        md.mbidReleaseGroup = 'rg-mbid'
        md.mbidArtist = ['artist-mbid']
        md.release = '2006-03-07'
        md.discNumber = 1
        md.discTotal = 1
        md.genres = ['Indie Pop', 'Indie Rock']
        track = mbngs.TrackMetadata()
        track.artist = 'Mates of State'
        track.title = 'Think Long'
        track.mbid = 'track-mbid'
        track.mbidRecording = 'rec-mbid'
        track.mbidArtist = ['artist-mbid']
        track.mbidWorks = []
        track.composers = []
        track.performers = []
        md.tracks.append(track)
        prog.metadata = md
        return prog

    def testHtoaGetsAlbumMbidsAndDiscid(self):
        """#485: track 0 must include MusicBrainz IDs like other tracks."""
        prog = self._program_with_meta()
        tags = prog.getTagList(0, 'discid123')
        self.assertEqual(tags['MUSICBRAINZ_DISCID'], 'discid123')
        self.assertEqual(tags['MUSICBRAINZ_ALBUMID'], 'release-mbid')
        self.assertEqual(tags['MUSICBRAINZ_RELEASEGROUPID'], 'rg-mbid')
        self.assertEqual(tags['MUSICBRAINZ_ALBUMARTISTID'], ['artist-mbid'])
        self.assertEqual(tags['TITLE'], 'Hidden Track One Audio')
        self.assertEqual(tags['TRACKNUMBER'], '0')
        # no track-level recording id on HTOA
        self.assertNotIn('MUSICBRAINZ_TRACKID', tags)
        self.assertNotIn('MUSICBRAINZ_RELEASETRACKID', tags)
        self.assertEqual(tags['GENRE'], ['Indie Pop', 'Indie Rock'])

    def testHtoaUsesMbhTitleWhenPresent(self):
        prog = self._program_with_meta()
        prog.metadata.htoaTitle = 'How Hard'
        tags = prog.getTagList(0, 'discid123')
        self.assertEqual(tags['TITLE'], 'How Hard')

    def testNormalTrackStillHasTrackMbids(self):
        prog = self._program_with_meta()
        tags = prog.getTagList(1, 'discid123')
        self.assertEqual(tags['MUSICBRAINZ_TRACKID'], 'rec-mbid')
        self.assertEqual(tags['MUSICBRAINZ_RELEASETRACKID'], 'track-mbid')
        self.assertEqual(tags['MUSICBRAINZ_ALBUMID'], 'release-mbid')
        self.assertEqual(tags['TITLE'], 'Think Long')
        self.assertEqual(tags['GENRE'], ['Indie Pop', 'Indie Rock'])

    def testUnknownDiscNoCrash(self):
        prog = program_mod.Program.__new__(program_mod.Program)
        prog.metadata = None
        tags = prog.getTagList(0, 'mbid')
        self.assertEqual(tags['TITLE'], 'Unknown Track')
        self.assertNotIn('MUSICBRAINZ_DISCID', tags)


class SkipHtoaOptionTestCase(unittest.TestCase):
    """#282: --skip-htoa is parsed and defaults to False."""

    def testRipHasSkipHtoaFlag(self):
        path = os.path.join(os.path.dirname(__file__), '..',
                            'command', 'cd.py')
        with open(path) as f:
            src = f.read()
        self.assertIn('skip_htoa', src)
        self.assertIn('--skip-htoa', src)

    def testDefaultValueFalse(self):
        path = os.path.join(os.path.dirname(__file__), '..',
                            'command', 'cd.py')
        with open(path) as f:
            src = f.read()
        self.assertIn("dest='skip_htoa'", src.replace('"', "'"))
        self.assertIn('default=False', src)


class BaseCommandDefaultDeviceFromConfigTestCase(unittest.TestCase):
    """#346: device default comes from config when present."""

    def testUsesConfigDevice(self):
        from whipper.command import basecommand as bc

        class Dummy(bc.BaseCommand):
            summary = 'dummy'
            description = 'dummy'
            device_option = True

        with mock.patch.object(config_mod.Config, 'get', create=True), \
                mock.patch('whipper.command.basecommand.config.Config') as C, \
                mock.patch('whipper.command.basecommand.drive.'
                           'getAllDevicePaths',
                           return_value=['/dev/sr0']), \
                mock.patch('os.path.exists', return_value=True), \
                mock.patch('os.path.realpath', side_effect=lambda p: p):
            C.return_value.get.side_effect = (
                lambda sec, opt: '/dev/sr7' if opt == 'device' else None)
            C.return_value.getDefaultDevice.return_value = '/dev/sr7'
            cmd = Dummy([], 'whipper dummy', None)
        self.assertEqual(cmd.options.device, '/dev/sr7')

    def testFallsBackToFirstDrive(self):
        from whipper.command import basecommand as bc

        class Dummy(bc.BaseCommand):
            summary = 'dummy'
            description = 'dummy'
            device_option = True

        with mock.patch('whipper.command.basecommand.config.Config') as C, \
                mock.patch('whipper.command.basecommand.drive.'
                           'getAllDevicePaths',
                           return_value=['/dev/sr2']), \
                mock.patch('os.path.exists', return_value=True), \
                mock.patch('os.path.realpath', side_effect=lambda p: p):
            C.return_value.get.return_value = None
            C.return_value.getDefaultDevice.return_value = None
            cmd = Dummy([], 'whipper dummy', None)
        self.assertEqual(cmd.options.device, '/dev/sr2')
