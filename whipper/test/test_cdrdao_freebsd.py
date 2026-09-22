# -*- Mode: Python; test-case-name: whipper.test.test_cdrdao_freebsd -*-
# vi:si:et:sw=4:sts=4:ts=4

from unittest import mock

from whipper.common import checksum
from whipper.program import cdrdao
from whipper.result import logger as result_logger
from whipper.test import common


class FormatDriveTestCase(common.TestCase):

    def test_never_formats_nonenone(self):
        s = result_logger._format_drive(None, None, None)
        self.assertNotIn('None', s)
        self.assertIn('unknown', s)

    def test_formats_vendor_model_release(self):
        s = result_logger._format_drive('PLEXTOR', 'DVDR PX-750A', '1.02')
        self.assertEqual(s, 'PLEXTOR DVDR PX-750A (revision 1.02)')

    def test_formats_linux_pycdio_strings(self):
        # historical pycdio values may already include spacing quirks
        s = result_logger._format_drive('HL-DT-STBD-RE', ' WH14NS40', '1.03')
        self.assertEqual(s, 'HL-DT-STBD-RE WH14NS40 (revision 1.03)')


class Crc32TaskDescriptionTestCase(common.TestCase):

    def test_description_is_not_placeholder(self):
        self.assertNotEqual(checksum.CRC32Task.description,
                            'I am doing something.')
        self.assertIn('CRC', checksum.CRC32Task.description)


class CdrdaoCommandTestCase(common.TestCase):

    def test_linux_read_toc_command(self):
        with mock.patch('whipper.platform.platform.cdrdao_driver_args',
                        return_value=[]):
            cmd = cdrdao.read_toc_command('/dev/sr0', fast_toc=True,
                                           tocfile='/tmp/t.toc')
        self.assertEqual(
            cmd,
            ['cdrdao', 'read-toc', '--fast-toc',
             '--device', '/dev/sr0', '/tmp/t.toc'])

    def test_freebsd_read_toc_forces_generic_mmc(self):
        with mock.patch('whipper.platform.platform.cdrdao_driver_args',
                        return_value=['--driver', 'generic-mmc']):
            cmd = cdrdao.read_toc_command('/dev/cd0', fast_toc=False,
                                           tocfile='/tmp/t.toc')
        self.assertEqual(
            cmd,
            ['cdrdao', 'read-toc',
             '--driver', 'generic-mmc',
             '--device', '/dev/cd0', '/tmp/t.toc'])


class CdrdaoProgressFreeBsdTestCase(common.TestCase):

    def test_finish_line_sets_track_count_from_current(self):
        p = cdrdao.ProgressParser()
        p.parse(
            "Analyzing track 24 (AUDIO): start 68:34:30, length 04:09:22")
        self.assertEqual(p.currentTrack, 24)
        p.parse("Reading of toc data finished successfully.")
        self.assertEqual(p.tracks, 24)

    def test_leadout_audio_prefix_still_matches(self):
        p = cdrdao.ProgressParser()
        p.parse("24  18697  308580  68:36:30")
        p.parse("Leadout AUDIO 1 72:45:52(327427)")
        self.assertEqual(p.tracks, 24)
