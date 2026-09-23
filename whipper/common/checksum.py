# -*- Mode: Python; test-case-name: whipper.test.test_common_checksum -*-
# vi:si:et:sw=4:sts=4:ts=4

# Copyright (C) 2009 Thomas Vander Stichele

# This file is part of whipper.
#
# whipper is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# whipper is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with whipper.  If not, see <http://www.gnu.org/licenses/>.

import binascii
import wave
import tempfile
import subprocess
import os


from whipper.common import common
from whipper.extern.task import task as etask

import logging
logger = logging.getLogger(__name__)

# checksums are not CRC's. a CRC is a specific type of checksum.


class CRC32Task(etask.Task):
    description = 'Computing CRC checksum'
    # TODO: Support sampleStart, sampleLength later on (should be trivial, just
    # add change the read part in _crc32 to skip some samples and/or not
    # read too far)

    def __init__(self, path, sampleStart=0, sampleLength=-1, is_wave=True):
        self.path = path
        self.is_wave = is_wave
        self.checksum = None
        self.sampleCount = None
        self.sampleRate = None
        self.channels = None
        self.sampleWidth = None

    def start(self, runner):
        etask.Task.start(self, runner)
        self.schedule(0.0, self._crc32)

    def _crc32(self):
        try:
            if self.is_wave:
                self._read_wave(self.path)
            else:
                with tempfile.TemporaryDirectory(suffix='.whipper.crc') as tmp:
                    decoded = os.path.join(tmp, 'decoded.wav')
                    try:
                        subprocess.check_call(
                            ['flac', '-d', self.path, '-fo', decoded])
                    except subprocess.CalledProcessError as e:
                        raise common.MissingFrames(
                            'could not decode %r' % self.path) from e
                    self._read_wave(decoded)
        except (wave.Error, EOFError) as e:
            self.setException(common.MissingFrames(
                'invalid WAV data in %r: %s' % (self.path, e)))
        except Exception as e:
            self.setException(e)
        finally:
            self.stop()

    def _read_wave(self, path):
        with wave.open(path, 'rb') as audio:
            samples = audio.getnframes()
            channels = audio.getnchannels()
            sample_width = audio.getsampwidth()
            sample_rate = audio.getframerate()
            frame_size = channels * sample_width
            # Hash the WAV byte order; readframes swaps bytes on big-endian hosts.
            data = audio._data_chunk.read()
        if not samples or len(data) != samples * frame_size:
            raise common.MissingFrames(
                'expected %d PCM bytes in %r, read %d'
                % (samples * frame_size, self.path, len(data)))
        self.sampleCount = len(data) // frame_size
        self.sampleRate = sample_rate
        self.channels = channels
        self.sampleWidth = sample_width
        self.checksum = binascii.crc32(data) & 0xffffffff
