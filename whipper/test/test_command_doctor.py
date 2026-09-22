# -*- Mode: Python; test-case-name: whipper.test.test_command_doctor -*-
# vi:si:et:sw=4:sts=4:ts=4

import unittest
from unittest import mock

from whipper.command import doctor as doctor_cmd


def _make_config():
    cfg = mock.Mock()
    cfg.getReadOffset.return_value = 102
    cfg.getDefeatsCache.return_value = True
    cfg.get_musicbrainz_server.return_value = {
        'scheme': 'https', 'netloc': 'musicbrainz.org'}
    return cfg


def _printed(print_mock):
    return ' '.join(
        str(a) for call in print_mock.call_args_list for a in call.args)


class DoctorTestCase(unittest.TestCase):

    def test_not_ready_without_drive_or_tools(self):
        with mock.patch.object(doctor_cmd.drive, 'getAllDevicePaths',
                               return_value=[]), \
             mock.patch.object(doctor_cmd.config, 'Config',
                               return_value=_make_config()), \
             mock.patch('whipper.program.cdparanoia.getCdParanoiaVersion',
                        side_effect=Exception('missing')), \
             mock.patch('whipper.program.cdrdao.version',
                        return_value=None), \
             mock.patch.object(doctor_cmd, '_probe_version',
                               return_value=None), \
             mock.patch.object(doctor_cmd, '_reachable',
                               return_value=True), \
             mock.patch('builtins.print') as print_:
            ret = doctor_cmd.Doctor([], 'whipper doctor', None).do()

        self.assertEqual(ret, 1)
        self.assertIn('MISSING', _printed(print_))
        self.assertIn('Not ready to rip', _printed(print_))

    def test_ready_with_full_env(self):
        with mock.patch.object(doctor_cmd.drive, 'getAllDevicePaths',
                               return_value=['/dev/cd0']), \
             mock.patch.object(doctor_cmd.drive, 'getDeviceInfo',
                               return_value=('PLEXTOR', 'PX-750A', '1.02')), \
             mock.patch.object(doctor_cmd.config, 'Config',
                               return_value=_make_config()), \
             mock.patch('whipper.program.cdparanoia.getCdParanoiaVersion',
                        return_value='cdparanoia 10.2'), \
             mock.patch('whipper.program.cdrdao.version',
                        return_value='1.2.5'), \
             mock.patch.object(doctor_cmd, '_probe_version',
                               side_effect=['flac 1.5.0', 'sox v14.4.2']), \
             mock.patch.object(doctor_cmd, '_reachable',
                               return_value=True), \
             mock.patch('builtins.print') as print_:
            ret = doctor_cmd.Doctor([], 'whipper doctor', None).do()

        self.assertEqual(ret, 0)
        joined = _printed(print_)
        self.assertIn('Ready to rip', joined)
        self.assertIn('PLEXTOR', joined)

    def test_missing_offset_is_a_warning_not_fatal(self):
        cfg = _make_config()
        cfg.getReadOffset.side_effect = KeyError
        with mock.patch.object(doctor_cmd.drive, 'getAllDevicePaths',
                               return_value=['/dev/cd0']), \
             mock.patch.object(doctor_cmd.drive, 'getDeviceInfo',
                               return_value=('PLEXTOR', 'PX-750A', '1.02')), \
             mock.patch.object(doctor_cmd.config, 'Config',
                               return_value=cfg), \
             mock.patch('whipper.program.cdparanoia.getCdParanoiaVersion',
                        return_value='cdparanoia 10.2'), \
             mock.patch('whipper.program.cdrdao.version',
                        return_value='1.2.5'), \
             mock.patch.object(doctor_cmd, '_probe_version',
                               side_effect=['flac 1.5.0', 'sox v14.4.2']), \
             mock.patch.object(doctor_cmd, '_reachable',
                               return_value=True), \
             mock.patch('builtins.print') as print_:
            ret = doctor_cmd.Doctor([], 'whipper doctor', None).do()

        # offset is a warning; still ready to rip
        self.assertEqual(ret, 0)
        self.assertIn('offset find', _printed(print_))
