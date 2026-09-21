# -*- Mode: Python; test-case-name: whipper.test.test_common_drive_offsets -*-
# vi:si:et:sw=4:sts=4:ts=4

from whipper.common import drive_offsets
from whipper.test import common


class KnownOffsetsTestCase(common.TestCase):

    def test_px750a_is_102(self):
        offsets = drive_offsets.known_offsets_for(
            'PLEXTOR', 'DVDR   PX-750A')
        self.assertEqual(offsets[0], 102)

    def test_longest_token_wins(self):
        # model contains both PX-75 and PX-750A; 750A is more specific
        offsets = drive_offsets.known_offsets_for(
            'PLEXTOR', 'DVDR PX-750A 1.02')
        self.assertEqual(offsets[0], 102)

    def test_unknown_model_empty(self):
        self.assertEqual(
            drive_offsets.known_offsets_for('ACME', 'TOASTER 9000'),
            [])


class OrderOffsetsTestCase(common.TestCase):

    def test_known_offset_prepended_even_if_absent_from_list(self):
        # regression: short custom lists used to omit +102 for PX-750A
        ordered = drive_offsets.order_offsets(
            [30, 6, 48],
            drive_info=('PLEXTOR', 'DVDR PX-750A', '1.02'),
        )
        self.assertEqual(ordered[0], 102)
        self.assertIn(30, ordered)
        self.assertEqual(len(ordered), len(set(ordered)))

    def test_configured_offset_first(self):
        ordered = drive_offsets.order_offsets(
            [30],
            drive_info=('PLEXTOR', 'DVDR PX-750A', '1.02'),
            configured=0,
        )
        self.assertEqual(ordered[:2], [0, 102])

    def test_no_prioritize_keeps_user_list(self):
        ordered = drive_offsets.order_offsets(
            [30, 6],
            drive_info=('PLEXTOR', 'DVDR PX-750A', '1.02'),
            prioritize_known=False,
        )
        self.assertEqual(ordered, [30, 6])

    def test_parse_offset_list_ranges(self):
        self.assertEqual(
            drive_offsets.parse_offset_list('+6, +30, 10:12'),
            [6, 30, 10, 11, 12])
