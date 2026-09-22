"""The fast and ordinary paths must share full-track confirmation."""

import argparse
from contextlib import ExitStack
import os
import unittest
from unittest import mock

from whipper.command import offset
from whipper.common import common
from whipper.extern.task import task
from whipper.platform import freebsd
from whipper.test.test_common_offsetfind import FakeTable


class FindTest(unittest.TestCase):
    def make_command(self, explicit=None, no_fast=False, no_known=False):
        command = offset.Find.__new__(offset.Find)
        command.options = argparse.Namespace(
            offsets=explicit, device='/dev/sr0', drive_auto_close=False,
            no_frame450=no_fast, no_prioritize_known=no_known)
        command.handle_arguments()
        return command

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.runner = self.stack.enter_context(mock.patch.object(
            offset.ctask, 'SyncRunner')).return_value
        toc = self.stack.enter_context(mock.patch.object(
            offset.cdrdao, 'ReadTOCTask')).return_value
        self.table = mock.Mock(tracks=[1, 2, 3, 4])
        self.table.getCDDBDiscId.return_value = '12345678'
        toc.toc.table = self.table
        self.stack.enter_context(mock.patch.object(
            offset.utils, 'unmount_device'))
        self.identity = self.stack.enter_context(mock.patch.object(
            offset.drive, 'getDeviceInfo',
            return_value=('PLEXTOR', 'DVDR PX-750A', '1.02')))
        self.config = self.stack.enter_context(mock.patch.object(
            offset.config, 'Config')).return_value
        self.config.getReadOffset.return_value = 6
        response = mock.Mock(cddbDiscId='12345678',
                             checksums=['one', 'two', 'three', 'last'])
        self.responses = [response]
        self.stack.enter_context(mock.patch.object(
            offset.accurip, 'get_db_entry', return_value=self.responses))
        self.fast = self.stack.enter_context(mock.patch.object(
            offset.offsetfind, 'find_offsets', return_value=[102]))
        self.found = self.stack.enter_context(mock.patch.object(
            offset.Find, '_foundOffset'))

    def test_fast_candidate_confirms_every_nonfinal_track(self):
        command = self.make_command()
        with mock.patch.object(command, '_arcs', side_effect=[
                ('one', 'v2'), ('two', 'v2'), ('three', 'v2')]) as arcs:
            self.assertEqual(command.do(), 0)
            self.assertEqual([c[0][2:] for c in arcs.call_args_list],
                             [(1, 102), (2, 102), (3, 102)])
        self.found.assert_called_once_with('/dev/sr0', 102)
        self.assertEqual(self.fast.call_args[1]['guess'], 6)

    def test_track1_match_and_track2_mismatch_never_saves(self):
        command = self.make_command()
        command._offsets = [102]
        self.config.getReadOffset.side_effect = KeyError()
        with mock.patch.object(offset.drive_offsets, 'known_offsets_for',
                               return_value=[]), \
                mock.patch.object(command, '_arcs',
                                  side_effect=[('one', 'v2'), ('bad', 'v2')]):
            self.assertIsNone(command.do())
        self.found.assert_not_called()

    def test_failed_fast_candidate_falls_back_to_configured_offset(self):
        command = self.make_command()
        with mock.patch.object(command, '_arcs', side_effect=[
                ('bad', 'v2'), ('one', 'v2'), ('two', 'v2'),
                ('three', 'v2')]) as arcs:
            self.assertEqual(command.do(), 0)
            self.assertEqual([c[0][3] for c in arcs.call_args_list],
                             [102, 6, 6, 6])
        self.found.assert_called_once_with('/dev/sr0', 6)

    def test_ambiguous_fast_matches_prefer_configured_then_published(self):
        self.fast.return_value = [-574, 84, 102]
        for configured, expected in (
                (84, [84, 102, -574, 0, 30, 6]),
                (6, [102, -574, 84, 6, 0, 30])):
            with self.subTest(configured=configured):
                self.config.getReadOffset.return_value = configured
                command = self.make_command()
                command._offsets = [30, 6]
                with mock.patch.object(command, '_confirm_offset',
                                       return_value=False) as confirm:
                    command.do()
                    self.assertEqual([c[0][3] for c in confirm.call_args_list],
                                     expected)
        self.found.assert_not_called()

    def test_fast_hint_priority_can_be_disabled(self):
        self.fast.return_value = [-574, 84, 102]
        command = self.make_command(no_known=True)
        command._offsets = [30, 6]
        with mock.patch.object(command, '_confirm_offset',
                               return_value=False) as confirm:
            command.do()
            self.assertEqual([c[0][3] for c in confirm.call_args_list],
                             [-574, 84, 102, 30, 6])
        self.found.assert_not_called()

    def test_explicit_offsets_keep_order_and_exclude_hints(self):
        command = self.make_command('9,4:5,0')
        with mock.patch.object(command, '_confirm_offset',
                               return_value=False) as confirm:
            self.assertIsNone(command.do())
            self.assertEqual([c[0][3] for c in confirm.call_args_list],
                             [9, 4, 5, 0])
        self.fast.assert_not_called()
        self.identity.assert_not_called()
        self.found.assert_not_called()

    def test_default_hint_order_without_fast_window(self):
        command = self.make_command(no_fast=True)
        command._offsets = [30, 6]
        with mock.patch.object(command, '_confirm_offset',
                               return_value=False) as confirm:
            command.do()
            self.assertEqual([c[0][3] for c in confirm.call_args_list],
                             [6, 102, 0, 30])
        self.fast.assert_not_called()

    def test_opt_out_restores_ordinary_order(self):
        command = self.make_command(no_fast=True, no_known=True)
        command._offsets = [30, 6]
        with mock.patch.object(command, '_confirm_offset',
                               return_value=False) as confirm:
            command.do()
            actual = [c[0][3] for c in confirm.call_args_list]
            self.assertEqual(actual, [30, 6])

    def test_guess_uses_published_then_zero_for_unknown_drive(self):
        self.config.getReadOffset.side_effect = KeyError()
        command = self.make_command()
        with mock.patch.object(command, '_confirm_offset', return_value=True):
            command.do()
            self.assertEqual(self.fast.call_args[1]['guess'], 102)
            self.identity.return_value = None
            command.do()
            self.assertEqual(self.fast.call_args[1]['guess'], 0)

    def test_unavailable_fast_data_uses_ordinary_candidates(self):
        self.fast.return_value = []
        command = self.make_command()
        with mock.patch.object(command, '_confirm_offset',
                               return_value=True) as confirm:
            command.do()
            self.assertEqual(confirm.call_args[0][3], 6)

    def test_unavailable_drive_identity_does_not_prevent_probing(self):
        self.identity.side_effect = OSError('cannot identify drive')
        self.fast.return_value = []
        command = self.make_command()
        command._offsets = [30, 6]
        with mock.patch.object(command, '_confirm_offset',
                               return_value=True) as confirm:
            command.do()
            self.assertEqual(confirm.call_args[0][3], 30)
            self.assertEqual(self.fast.call_args[1]['guess'], 0)

    def test_missing_dependency_propagates_during_confirmation(self):
        command = self.make_command()
        for failing_track in (1, 2):
            results = [('one', 'v2')] * (failing_track - 1)
            results.append(task.TaskException(
                common.MissingDependencyException('cd-paranoia')))
            with mock.patch.object(command, '_arcs', side_effect=results):
                with self.assertRaises(task.TaskException):
                    command.do()
        self.found.assert_not_called()

    def test_no_stale_checksums_after_failed_confirmation_read(self):
        command = self.make_command()
        with mock.patch.object(command, '_arcs', side_effect=[
                ('one', 'v2'), task.TaskException(ValueError('bad rip'))]):
            self.assertFalse(command._confirm_offset(
                self.runner, self.table, self.responses, 102))

    def test_confirmation_temporary_file_is_removed_on_failure(self):
        command = self.make_command()
        self.runner.run.side_effect = task.TaskException(ValueError('bad rip'))
        with mock.patch.object(offset.cdparanoia, 'ReadTrackTask') as reader:
            with self.assertRaises(task.TaskException):
                command._arcs(self.runner, FakeTable(), 1, 102)
            self.assertFalse(os.path.exists(reader.call_args[0][0]))


class SaveOffsetTest(unittest.TestCase):
    def test_save_with_freebsd_identity_without_pycdio(self):
        inquiry = b'pass1: <PLEXTOR DVDR   PX-750A 1.02> Removable CD-ROM\n'
        with mock.patch.dict('sys.modules', {'cdio': None}), \
                mock.patch.object(offset.drive, 'platform',
                                  freebsd.FreeBSDPlatform()), \
                mock.patch('whipper.platform.freebsd.subprocess.check_output',
                           return_value=inquiry) as run, \
                mock.patch.object(offset.config, 'Config') as config:
            offset.Find._foundOffset('/dev/cd0', 102)
        self.assertEqual(run.call_args[0][0],
                         ['camcontrol', 'inquiry', 'cd0'])
        config.return_value.setReadOffset.assert_called_once_with(
            'PLEXTOR', 'DVDR   PX-750A', '1.02', 102)
