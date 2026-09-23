import binascii
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
import wave

from whipper.common import checksum, common
from whipper.extern.task import task


class CRC32TaskTestCase(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = os.path.join(self.directory.name, 'track.wav')
        self.pcm = b'\x01\x00\x02\x00' * 1176

    def write_wave(self, pcm):
        with wave.open(self.path, 'wb') as audio:
            audio.setnchannels(2)
            audio.setsampwidth(2)
            audio.setframerate(44100)
            audio.writeframes(pcm)

    def run_task(self, path=None, is_wave=True):
        crc = checksum.CRC32Task(path or self.path, is_wave=is_wave)
        task.SyncRunner(verbose=False).run(crc)
        return crc

    def assert_missing_frames(self, path=None, is_wave=True):
        with self.assertRaises(task.TaskException) as caught:
            self.run_task(path, is_wave)
        self.assertIsInstance(caught.exception.exception, common.MissingFrames)

    def test_wave_crc_and_sample_count(self):
        self.write_wave(self.pcm)
        crc = self.run_task()
        self.assertEqual(crc.checksum, binascii.crc32(self.pcm) & 0xffffffff)
        self.assertEqual(crc.sampleCount, 1176)
        self.assertEqual((crc.sampleRate, crc.channels, crc.sampleWidth),
                         (44100, 2, 2))

    def test_big_endian_host_keeps_wave_crc(self):
        self.write_wave(self.pcm)
        with mock.patch('wave.sys.byteorder', 'big'):
            crc = self.run_task()
        self.assertEqual(crc.checksum, binascii.crc32(self.pcm) & 0xffffffff)

    def test_generic_pcm_metadata_is_preserved(self):
        pcm = bytes(range(256)) * 4
        with wave.open(self.path, 'wb') as audio:
            audio.setnchannels(1)
            audio.setsampwidth(1)
            audio.setframerate(8000)
            audio.writeframes(pcm)
        crc = self.run_task()
        self.assertEqual(crc.checksum, binascii.crc32(pcm) & 0xffffffff)
        self.assertEqual(crc.sampleCount, 1024)
        self.assertEqual((crc.sampleRate, crc.channels, crc.sampleWidth),
                         (8000, 1, 1))

    def test_empty_wave_is_rejected(self):
        self.write_wave(b'')
        self.assert_missing_frames()

    def test_truncated_wave_is_rejected(self):
        self.write_wave(self.pcm)
        with open(self.path, 'r+b') as audio:
            audio.truncate(os.path.getsize(self.path) - 2352)
        self.assert_missing_frames()

    def test_incomplete_sample_frame_is_rejected(self):
        self.write_wave(self.pcm + b'\x01')
        self.assert_missing_frames()

    def test_truncated_header_is_rejected(self):
        with open(self.path, 'wb') as audio:
            audio.write(b'RIFF')
        self.assert_missing_frames()

    @unittest.skipUnless(shutil.which('flac'), 'flac is unavailable')
    def test_flac_crc_and_sample_count_match_wave(self):
        self.write_wave(self.pcm)
        flac_path = os.path.join(self.directory.name, 'track.flac')
        subprocess.check_call(['flac', '-s', '-f', self.path, '-o', flac_path])
        crc = self.run_task(flac_path, is_wave=False)
        self.assertEqual(crc.checksum, binascii.crc32(self.pcm) & 0xffffffff)
        self.assertEqual(crc.sampleCount, 1176)
        self.assertEqual((crc.sampleRate, crc.channels, crc.sampleWidth),
                         (44100, 2, 2))

    @unittest.skipUnless(shutil.which('flac'), 'flac is unavailable')
    def test_truncated_flac_is_rejected(self):
        self.write_wave(self.pcm)
        flac_path = os.path.join(self.directory.name, 'track.flac')
        subprocess.check_call(['flac', '-s', '-f', self.path, '-o', flac_path])
        with open(flac_path, 'r+b') as audio:
            audio.truncate(os.path.getsize(flac_path) - 10)
        self.assert_missing_frames(flac_path, is_wave=False)
