# -*- Mode: Python; test-case-name: whipper.test.test_common_offsetfind -*-
# vi:si:et:sw=4:sts=4:ts=4
"""
Fast drive-offset detection via AccurateRip OffsetFindCRC (frame 450).

Per Spoon's AccurateRip spec, bytes 5-8 of each track record are a CRC
over one frame (588 samples) at sector 450 of track 1. Discussion #691:
read one short window once, sweep candidate offsets in memory, match
against the database — no full-track probe rips required.
"""

import array
import logging
import os
import tempfile
import wave

logger = logging.getLogger(__name__)

SECTOR_SAMPLES = 588
# Track-relative sample index of the OffsetFindCRC window
FRAME450_TRACK_REL = 450 * SECTOR_SAMPLES  # 264600
# Global disc sample index used by some historical AR submitters
FRAME450_GLOBAL_START = FRAME450_TRACK_REL + 1  # 264601
# Default half-width of the candidate-offset sweep (samples)
DEFAULT_SWEEP = 3000
# Extra CD frames of margin around the sweep window
_READ_MARGIN_FRAMES = 2


def offsetfind_crc(pcm, start_sample, global_base=None):
    """
    Compute an AccurateRip OffsetFindCRC over 588 stereo 16-bit samples.

    Sample packing is L | (R << 16), matching accuraterip-checksum.c.
    If global_base is None, multipliers are local (1..588); otherwise
    they start at global_base (e.g. 264601). Historical AR clients were
    inconsistent, so callers should try both.
    """
    crc = 0
    n = SECTOR_SAMPLES
    for k in range(n):
        idx = (start_sample + k) * 2
        left = pcm[idx] & 0xFFFF
        right = pcm[idx + 1] & 0xFFFF
        s = left | (right << 16)
        mult = (k + 1) if global_base is None else (global_base + k)
        crc = (crc + s * mult) & 0xFFFFFFFF
    return crc


def match_offset_in_pcm(pcm, sample_base, offset_guess, db_crcs,
                        sweep=DEFAULT_SWEEP):
    """
    Sweep candidate offsets against a PCM buffer.

    :param pcm: interleaved stereo int16 samples (array/list)
    :param sample_base: track-relative sample index of pcm[0]
    :param offset_guess: center of the sweep (usually 0 or configured)
    :param db_crcs: iterable of int OffsetFindCRC values for track 1
    :param sweep: half-width in samples
    :returns: matching total sample offset (int) or None
    """
    targets = set(int(c) for c in db_crcs)
    if not targets:
        return None
    if sample_base < 0:
        return None
    frames = len(pcm) // 2
    for O in range(offset_guess - sweep, offset_guess + sweep + 1):
        start = FRAME450_TRACK_REL + O - sample_base
        if start < 0 or start + SECTOR_SAMPLES > frames:
            continue
        crc_local = offsetfind_crc(pcm, start)
        if crc_local in targets:
            return O
        crc_global = offsetfind_crc(pcm, start, global_base=FRAME450_GLOBAL_START)
        if crc_global in targets:
            return O
    return None


def read_frame450_window(runner, table, device, offset_guess=0,
                         sweep=DEFAULT_SWEEP):
    """
    Rip a short track-1 span covering frame 450 ± sweep at sample-offset 0.

    Returns (pcm_array, sample_base) where sample_base is the track-relative
    sample index of pcm[0], or (None, None) on failure.
    """
    from whipper.program import cdparanoia

    track_start = table.getTrackStart(1)
    track_end = table.getTrackEnd(1)  # inclusive last frame
    rel_lo = FRAME450_TRACK_REL + offset_guess - sweep - SECTOR_SAMPLES
    rel_hi = FRAME450_TRACK_REL + offset_guess + sweep + SECTOR_SAMPLES
    if rel_lo < 0:
        rel_lo = 0
    first_frame = rel_lo // SECTOR_SAMPLES - _READ_MARGIN_FRAMES
    last_frame = rel_hi // SECTOR_SAMPLES + _READ_MARGIN_FRAMES
    if first_frame < 0:
        first_frame = 0
    start_abs = track_start + first_frame
    stop_abs = track_start + last_frame
    if stop_abs > track_end:
        stop_abs = track_end
    if start_abs >= stop_abs:
        logger.warning('frame-450 window outside track 1')
        return None, None

    fd, path = tempfile.mkstemp(suffix='.frame450.whipper.wav')
    os.close(fd)
    try:
        t = cdparanoia.ReadTrackTask(
            path, table, start_abs, stop_abs,
            overread=False, offset=0, device=device)
        t.description = 'Reading frame-450 window for offset find'
        runner.run(t)
        with wave.open(path, 'rb') as w:
            raw = w.readframes(w.getnframes())
        pcm = array.array('h')
        pcm.frombytes(raw)
        sample_base = first_frame * SECTOR_SAMPLES
        return pcm, sample_base
    except Exception as e:  # noqa: BLE001 - treat as fast-path failure
        logger.warning('frame-450 window read failed: %s', e)
        return None, None
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def collect_track1_offsetfind_crcs(responses):
    """Return int OffsetFindCRC values for AR track 1 from responses."""
    out = []
    for r in responses or []:
        seq = getattr(r, 'offsetfind_checksums', None)
        if not seq:
            continue
        try:
            out.append(int(seq[0], 16))
        except (TypeError, ValueError, IndexError):
            continue
    return out


def detect_offset_frame450(runner, table, device, responses,
                           offset_guess=0, sweep=DEFAULT_SWEEP):
    """
    Fast offset detection using AR OffsetFindCRC at frame 450.

    Returns the detected sample offset (int) or None if no match / failure.
    """
    db_crcs = collect_track1_offsetfind_crcs(responses)
    if not db_crcs:
        logger.debug('no OffsetFindCRC data in AccurateRip responses')
        return None
    pcm, sample_base = read_frame450_window(
        runner, table, device, offset_guess=offset_guess, sweep=sweep)
    if pcm is None:
        return None
    found = match_offset_in_pcm(
        pcm, sample_base, offset_guess, db_crcs, sweep=sweep)
    if found is not None:
        logger.info('OffsetFindCRC match at offset %d (frame 450 sweep)',
                    found)
    else:
        logger.info('no OffsetFindCRC match in ±%d sweep; '
                    'falling back to probe rips', sweep)
    return found
