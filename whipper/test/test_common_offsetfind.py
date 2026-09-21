# -*- Mode: Python; test-case-name: whipper.test.test_common_offsetfind -*-
# vi:si:et:sw=4:sts=4:ts=4

import array
import struct
import unittest
from unittest import mock

from whipper.common import accurip, offsetfind
from whipper.test import common


def _pack_ar_response(track_crcs, offsetfind_crcs, confidences=None):
    """Build a minimal AR binary entry (1 disc record)."""
    n = len(track_crcs)
    confidences = confidences or [1] * n
    data = bytearray()
    data.append(n)
    data += struct.pack('<L', 0x11111111)
    data += struct.pack('<L', 0x22222222)
    data += struct.pack('<L', 0x33333333)
    for i in range(n):
        data.append(confidences[i] & 0xFF)
        data += struct.pack('<L', track_crcs[i] & 0xFFFFFFFF)
        data += struct.pack('<L', offsetfind_crcs[i] & 0xFFFFFFFF)
    return bytes(data)


class OffsetFindParseTestCase(common.TestCase):

    def test_parses_offsetfind_crc_bytes_5_8(self):
        raw = _pack_ar_response(
            [0xAAAAAAAA, 0xBBBBBBBB],
            [0x01020304, 0x05060708],
        )
        resp = accurip._AccurateRipResponse(raw)
        self.assertEqual(resp.checksums, ['aaaaaaaa', 'bbbbbbbb'])
        self.assertEqual(resp.offsetfind_checksums,
                         ['01020304', '05060708'])

    def test_collect_track1_crcs(self):
        raw = _pack_ar_response([1, 2], [0x100, 0x200])
        resp = accurip._AccurateRipResponse(raw)
        self.assertEqual(
            offsetfind.collect_track1_offsetfind_crcs([resp]),
            [0x100])


class Frame450CrcTestCase(common.TestCase):

    def _synth_pcm(self, n_frames, amp=1000):
        # stereo int16: simple deterministic pattern
        pcm = array.array('h')
        for i in range(n_frames):
            l = (amp + i) & 0x7FFF
            r = (amp + 2 * i) & 0x7FFF
            pcm.append(l)
            pcm.append(r)
        return pcm

    def test_local_and_global_crc_differ(self):
        pcm = self._synth_pcm(600)
        start = 12
        a = offsetfind.offsetfind_crc(pcm, start)
        b = offsetfind.offsetfind_crc(
            pcm, start, global_base=offsetfind.FRAME450_GLOBAL_START)
        self.assertNotEqual(a, b)

    def test_match_finds_true_offset(self):
        # Build a buffer whose "track" starts at sample_base=0
        # Place known CRC at true offset +102
        true_off = 102
        # Need pcm covering FRAME450 + true_off + 588
        n_frames = offsetfind.FRAME450_TRACK_REL + true_off + 588 + 10
        pcm = self._synth_pcm(n_frames)
        start = offsetfind.FRAME450_TRACK_REL + true_off
        target = offsetfind.offsetfind_crc(pcm, start)
        found = offsetfind.match_offset_in_pcm(
            pcm, 0, offset_guess=0, db_crcs=[target], sweep=200)
        self.assertEqual(found, true_off)

    def test_match_none_when_absent(self):
        pcm = self._synth_pcm(offsetfind.FRAME450_TRACK_REL + 700)
        found = offsetfind.match_offset_in_pcm(
            pcm, 0, 0, db_crcs=[0xDEADBEEF], sweep=50)
        self.assertIsNone(found)

    def test_detect_skips_without_db_field(self):
        raw = _pack_ar_response([1], [0])  # OffsetFindCRC 0 may still parse
        # empty seq via mock responses without attribute
        class R:
            offsetfind_checksums = []
        self.assertEqual(
            offsetfind.collect_track1_offsetfind_crcs([R()]), [])
        self.assertIsNone(
            offsetfind.detect_offset_frame450(
                mock.Mock(), mock.Mock(), '/dev/null', [R()]))


class ReadTrackSpanTestCase(common.TestCase):

    def test_mid_track_span_sets_stop_track(self):
        """Regression: frame-450 windows are mid-track; stopTrack was 0."""
        from whipper.extern.task import task as etask
        from whipper.image import table as table_mod
        from whipper.program import cdparanoia

        class Idx:
            def __init__(self, abs_):
                self.absolute = abs_

        class Trk:
            def __init__(self, starts):
                self._starts = starts

            def getIndex(self, n):
                return Idx(self._starts[n])

        class FakeTable:
            def __init__(self):
                # track 1: 32..13886, track 2: 13887..
                self.tracks = [Trk({1: 32, 0: 0}), Trk({1: 13887, 0: 0})]
                self.leadout = 20000

            def getTrackStart(self, n):
                return self.tracks[n - 1].getIndex(1).absolute

            def getTrackEnd(self, n):
                if n < len(self.tracks):
                    return self.tracks[n].getIndex(1).absolute - 1
                return self.leadout - 1

        t = cdparanoia.ReadTrackTask.__new__(cdparanoia.ReadTrackTask)
        t.path = '/tmp/x.wav'
        t._table = FakeTable()
        t._start = 474
        t._stop = 490
        t._offset = 0
        t._parser = cdparanoia.ProgressParser(474, 490)
        t._device = '/dev/cd0'
        t._start_time = None
        t._overread = False
        t._buffer = ''
        t._errors = []
        t.description = 'x'

        captured = {}

        class Stop(Exception):
            pass

        def fake_popen(argv, **kwargs):
            captured['argv'] = argv
            raise Stop()

        with mock.patch('whipper.program.cdparanoia.asyncsub.Popen',
                        side_effect=fake_popen):
            try:
                t.start(mock.Mock())
            except Stop:
                pass
        argv = captured.get('argv', [])
        self.assertTrue(argv)
        span = [a for a in argv if a.startswith('1[') and ']-1[' in a]
        self.assertTrue(span, argv)
        self.assertFalse(any(a.startswith('0[') for a in argv), argv)


class DetectFallbackTestCase(common.TestCase):

    def test_detect_returns_none_on_read_failure(self):
        class R:
            offsetfind_checksums = ['00000102']

        with mock.patch.object(offsetfind, 'read_frame450_window',
                               return_value=(None, None)):
            self.assertIsNone(
                offsetfind.detect_offset_frame450(
                    mock.Mock(), mock.Mock(), '/dev/cd0', [R()]))


if __name__ == '__main__':
    unittest.main()
