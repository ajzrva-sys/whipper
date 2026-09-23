from __future__ import print_function
import hashlib
import os
import re
import tempfile
import unittest

from whipper.common.yaml import YAML
from whipper.result.result import TrackResult, RipResult
from whipper.result.logger import WhipperLogger, is_complete_rip_log


class MockImageTrack:
    def __init__(self, number, start, end):
        self.number = number
        self.absolute = self.start = start
        self.end = end

    def getIndex(self, num):
        if num == 0:
            raise KeyError
        else:
            return self


class MockImageTable:
    """Mock of whipper.image.table.Table, with fake information."""
    def __init__(self):
        self.tracks = [
            MockImageTrack(1, 0,  16263),
            MockImageTrack(2, 16264, 33487)
        ]

    @staticmethod
    def getCDDBDiscId():
        return "c30bde0d"

    @staticmethod
    def getMusicBrainzDiscId():
        return "eyjySLXGdKigAjY3_C0nbBmNUHc-"

    @staticmethod
    def getMusicBrainzSubmitURL():
        return (
            "https://musicbrainz.org/cdtoc/attach?toc=1+13+228039+150+16414+"
            "33638+51378+69369+88891+104871+121645+138672+160748+178096+194680"
            "+212628&tracks=13&id=eyjySLXGdKigAjY3_C0nbBmNUHc-"
        )

    def getTrackLength(self, number):
        return self.tracks[number-1].end - self.tracks[number-1].start + 1

    def getTrackEnd(self, number):
        return self.tracks[number-1].end


class LoggerTestCase(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(os.path.dirname(__file__))

    def testLogger(self):
        ripResult = RipResult()
        ripResult.offset = 6
        ripResult.overread = False
        ripResult.isCdr = False
        ripResult.table = MockImageTable()
        ripResult.artist = "Example - Symbol - Artist"
        ripResult.title = "Album With: - Dashes"
        ripResult.vendor = "HL-DT-STBD-RE  "
        ripResult.model = "WH14NS40"
        ripResult.release = "1.03"
        ripResult.cdrdaoVersion = "1.2.4"
        ripResult.cdparanoiaVersion = (
            "cdparanoia III 10.2 "
            "libcdio 2.0.0 x86_64-pc-linux-gnu"
        )
        ripResult.cdparanoiaDefeatsCache = True

        trackResult = TrackResult()
        trackResult.number = 1
        trackResult.filename = (
            "./soundtrack/Various Artists - Shark Tale - Motion Picture "
            "Soundtrack/01. Sean Paul & Ziggy Marley - Three Little Birds.flac"
        )
        trackResult.pregap = 0
        trackResult.peak = 29503
        trackResult.quality = 1
        trackResult.copyspeed = 7
        trackResult.testduration = 10
        trackResult.copyduration = 10
        trackResult.testcrc = 0x0025D726
        trackResult.copycrc = 0x0025D726
        trackResult.AR = {
            "v1": {
                "DBConfidence": 14,
                "DBCRC": "95E6A189",
                "CRC": "95E6A189"
            },
            "v2": {
                "DBConfidence": 11,
                "DBCRC": "113FA733",
                "CRC": "113FA733"
            }
        }
        ripResult.tracks.append(trackResult)

        trackResult = TrackResult()
        trackResult.number = 2
        trackResult.filename = (
            "./soundtrack/Various Artists - Shark Tale - Motion Picture "
            "Soundtrack/02. Christina Aguilera feat. Missy Elliott - Car "
            "Wash (Shark Tale mix).flac"
        )
        trackResult.pregap = 0
        trackResult.peak = 31862
        trackResult.quality = 1
        trackResult.copyspeed = 7.7
        trackResult.testduration = 10
        trackResult.copyduration = 10
        trackResult.testcrc = 0xF77C14CB
        trackResult.copycrc = 0xF77C14CB
        trackResult.AR = {
            "v1": {
                "DBConfidence": 14,
                "DBCRC": "0B3316DB",
                "CRC": "0B3316DB"
            },
            "v2": {
                "DBConfidence": 10,
                "DBCRC": "A0AE0E57",
                "CRC": "A0AE0E57"
            }
        }
        ripResult.tracks.append(trackResult)
        logger = WhipperLogger()
        actual = logger.log(ripResult)
        actualLines = actual.splitlines()
        with open(os.path.join(self.path,
                               'test_result_logger.log'), 'r') as f:
            expectedLines = f.read().splitlines()
        # do not test on version line, date line, or SHA-256 hash line
        self.assertListEqual(actualLines[2:-1], expectedLines[2:-1])

        # Accept setuptools-scm / PEP 440 local versions, including
        # distro or CI labels such as 0.10.0+freebsd686 (issue #686).
        # https://github.com/pypa/setuptools_scm/#default-versioning-scheme
        # https://peps.python.org/pep-0440/#local-version-identifiers
        versionSchemes = [
            actualLines[0],
            'Log created by: whipper 0.7.4.dev87+gb71ec9f.d20191026 (internal logger)',  # noqa: E501
            'Log created by: whipper 0.7.4.dev87+gb71ec9f (internal logger)',
            'Log created by: whipper 0.7.4+d20191026 (internal logger)',
            'Log created by: whipper 0.7.4 (internal logger)',
            'Log created by: whipper 0.10.0+freebsd686 (internal logger)',
            'Log created by: whipper 0.10.0+ci (internal logger)',
        ]
        created_by_re = re.compile((
                            r'Log created by: whipper '
                            r'\d+\.\d+\.\d+'
                            r'(\.dev[\w.+]+)?'
                            r'(\+[\w.]+)? '
                            r'\(internal logger\)'
                        ))
        for versionScheme in versionSchemes:
            self.assertRegex(versionScheme, created_by_re)
        self.assertRegex(
            actualLines[1],
            re.compile((
                r'Log creation date: '
                r'20[\d]{2}-[\d]{2}-[\d]{2}T[\d]{2}:[\d]{2}:[\d]{2}Z'
            ))
        )

        yaml = YAML(
            typ='rt',
            pure=True
        )
        parsedLog = yaml.load(actual)
        self.assertEqual(
            actual,
            yaml.dump(parsedLog)
        )
        log_body = "\n".join(actualLines[:-1]).encode()
        self.assertEqual(
            parsedLog['SHA-256 hash'],
            hashlib.sha256(log_body).hexdigest().upper()
        )


class PeakQualityGuardTestCase(unittest.TestCase):
    """Issues #601 / #621: None peak and missing quality must not crash."""

    def testLoggerPeakNone(self):
        ripResult = RipResult()
        ripResult.offset = 0
        ripResult.overread = False
        ripResult.isCdr = False
        ripResult.table = MockImageTable()
        ripResult.artist = "Artist"
        ripResult.title = "Title"
        ripResult.vendor = "VEN"
        ripResult.model = "MOD"
        ripResult.release = "1"
        ripResult.cdrdaoVersion = "1.2.4"
        ripResult.cdparanoiaVersion = "cdparanoia III 10.2"
        ripResult.cdparanoiaDefeatsCache = True
        trackResult = TrackResult()
        trackResult.number = 1
        trackResult.filename = "./01.flac"
        trackResult.peak = None  # soxi failed / skipped track
        trackResult.quality = None
        trackResult.testduration = 1
        trackResult.copyduration = 1
        trackResult.testcrc = 0x1
        trackResult.copycrc = 0x1
        trackResult.AR = {
            "v1": {"DBConfidence": None, "DBCRC": None, "CRC": None},
            "v2": {"DBConfidence": None, "DBCRC": None, "CRC": None},
        }
        ripResult.tracks.append(trackResult)
        log = WhipperLogger().log(ripResult, epoch=0)
        self.assertIn("Peak level:", log)
        self.assertIn("Peak level:\n", log)
        self.assertNotIn("Extraction quality", log)

    def testLoggerNormalPeakStillWorks(self):
        ripResult = RipResult()
        ripResult.offset = 0
        ripResult.overread = False
        ripResult.isCdr = False
        ripResult.table = MockImageTable()
        ripResult.artist = "Artist"
        ripResult.title = "Title"
        ripResult.vendor = "VEN"
        ripResult.model = "MOD"
        ripResult.release = "1"
        ripResult.cdrdaoVersion = "1.2.4"
        ripResult.cdparanoiaVersion = "cdparanoia III 10.2"
        ripResult.cdparanoiaDefeatsCache = True
        trackResult = TrackResult()
        trackResult.number = 1
        trackResult.filename = "./01.flac"
        trackResult.peak = 32768
        trackResult.quality = 1.0
        trackResult.copyspeed = 2.0
        trackResult.testduration = 1
        trackResult.copyduration = 1
        trackResult.testcrc = 0x1
        trackResult.copycrc = 0x1
        trackResult.AR = {
            "v1": {"DBConfidence": None, "DBCRC": None, "CRC": None},
            "v2": {"DBConfidence": None, "DBCRC": None, "CRC": None},
        }
        ripResult.tracks.append(trackResult)
        log = WhipperLogger().log(ripResult, epoch=0)
        self.assertIn("Peak level: 1.0", log)
        self.assertIn("Extraction quality: 100.00 %", log)


class CompleteRipLogTestCase(unittest.TestCase):
    """Issue #352: only complete whipper logs count as finished rips."""

    COMPLETE = """Log created by: whipper 0.10.0 (internal logger)
Log creation date: 2020-01-01T00:00:00Z

TOC:
  1: {}
Tracks:
  1:
    Test CRC: ABCD
    Copy CRC: ABCD
    Status: Copy OK
Conclusive status report:
  AccurateRip summary: All tracks accurately ripped
  Health status: No errors occurred
  EOF: End of status report

SHA-256 hash: DEADBEEF
"""

    def _write(self, content):
        fd, path = tempfile.mkstemp(suffix='.log')
        os.close(fd)
        if content is not None:
            with open(path, 'w') as handle:
                handle.write(content)
        else:
            os.unlink(path)
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        return path

    def testCompleteLogIsFinished(self):
        path = self._write(self.COMPLETE)
        self.assertTrue(is_complete_rip_log(path))

    def testEmptyLogIsNotFinished(self):
        path = self._write('')
        self.assertFalse(is_complete_rip_log(path))

    def testMissingPathIsNotFinished(self):
        self.assertFalse(is_complete_rip_log('/nonexistent/rip.log'))
        self.assertFalse(is_complete_rip_log(None))
        self.assertFalse(is_complete_rip_log(''))

    def testTruncatedLogWithoutEndMarkersIsNotFinished(self):
        partial = """Log created by: whipper 0.10.0 (internal logger)
Log creation date: 2020-01-01T00:00:00Z

Conclusive status report:
  AccurateRip summary: ...
"""
        path = self._write(partial)
        self.assertFalse(is_complete_rip_log(path))

    def testForeignLogFileIsNotFinished(self):
        path = self._write('INFO:whipper.command.cd:checking device\n')
        self.assertFalse(is_complete_rip_log(path))

    def testFixtureCompleteLogIsFinished(self):
        fixture = os.path.join(os.path.dirname(__file__),
                               'test_result_logger.log')
        self.assertTrue(is_complete_rip_log(fixture))

    def testGeneratedLogIsFinished(self):
        """A log produced by WhipperLogger must pass the completeness check."""
        ripResult = RipResult()
        ripResult.offset = 0
        ripResult.overread = False
        ripResult.isCdr = False
        ripResult.table = MockImageTable()
        ripResult.table.tracks = ripResult.table.tracks[:1]
        ripResult.artist = "Artist"
        ripResult.title = "Title"
        ripResult.vendor = "VEN"
        ripResult.model = "MOD"
        ripResult.release = "1.0"
        ripResult.cdrdaoVersion = "1.2.4"
        ripResult.cdparanoiaVersion = "cdparanoia III 10.2"
        ripResult.cdparanoiaDefeatsCache = True
        trackResult = TrackResult()
        trackResult.number = 1
        trackResult.filename = "./01.flac"
        trackResult.peak = 1000
        trackResult.quality = 1
        trackResult.copyspeed = 1.0
        trackResult.testduration = 1
        trackResult.copyduration = 1
        trackResult.testcrc = 0x1
        trackResult.copycrc = 0x1
        trackResult.AR = {
            "v1": {"DBConfidence": None, "DBCRC": None, "CRC": None},
            "v2": {"DBConfidence": None, "DBCRC": None, "CRC": None},
        }
        ripResult.tracks.append(trackResult)
        log_text = WhipperLogger().log(ripResult, epoch=0)
        path = self._write(log_text)
        self.assertTrue(is_complete_rip_log(path))


class CdparanoiaEventsTestCase(unittest.TestCase):
    """Tests for cdparanoia event reporting in the rip log."""

    def testLoggerReportsCdparanoiaErrors(self):
        """Suspicious positions and non-fatal events appear in the log."""
        ripResult = RipResult()
        ripResult.offset = 6
        ripResult.overread = False
        ripResult.isCdr = False
        ripResult.table = MockImageTable()
        ripResult.artist = "Example Artist"
        ripResult.title = "Example Album"
        ripResult.vendor = "HL-DT-ST"
        ripResult.model = "DVDRAM"
        ripResult.release = "1.00"
        ripResult.cdrdaoVersion = "1.2.4"
        ripResult.cdparanoiaVersion = "cdparanoia III 10.2"
        ripResult.cdparanoiaDefeatsCache = True

        trackResult = TrackResult()
        trackResult.number = 1
        trackResult.filename = "./01 - Example.flac"
        trackResult.pregap = 0
        trackResult.peak = 29503
        trackResult.quality = 0.80
        trackResult.copyspeed = 2.0
        trackResult.testduration = 10
        trackResult.copyduration = 10
        trackResult.testcrc = 0x0025D726
        trackResult.copycrc = 0x0025D726
        trackResult.cdparanoiaEvents = {
            "jitter": 3,
            "transport error": 1,
            "skip": 0,
            "scsi_read error": 2,
        }
        trackResult.suspiciousPositions = [(90, 91), (4500, 4510)]
        trackResult.AR = {
            "v1": {"DBConfidence": None, "DBCRC": None, "CRC": None},
            "v2": {"DBConfidence": None, "DBCRC": None, "CRC": None},
        }
        ripResult.tracks.append(trackResult)

        log = WhipperLogger().log(ripResult, epoch=0)
        self.assertIn("cdparanoia events:", log)
        self.assertIn("jitter: 3", log)
        self.assertIn("transport error: 1", log)
        self.assertIn("scsi_read error: 2", log)
        self.assertNotIn("skip:", log)
        self.assertIn("Suspicious positions:", log)
        self.assertIn("00:01:15 - 00:01:16", log)
        self.assertIn("01:00:00 - 01:00:10", log)
        self.assertIn("Copy OK (cdparanoia reported severe recoverable", log)
        self.assertIn("Health status: There were errors", log)
        self.assertIn("cdparanoia health:", log)
        self.assertIn("severe recoverable errors", log)
        self.assertNotIn("definitely lossy", log)

    def testLoggerCorrectionsOnlyHealth(self):
        """Corrections without severe events keep 'No errors occurred'."""
        from whipper.program.cdparanoia import classify_cdparanoia_events
        severe, corrections, lossy = classify_cdparanoia_events(
            {"jitter": 3, "overlap": 1})
        self.assertEqual(severe, 0)
        self.assertEqual(corrections, 4)
        self.assertEqual(lossy, [])

    def testClassifyCdparanoiaEvents(self):
        from whipper.program.cdparanoia import classify_cdparanoia_events
        severe, corrections, lossy = classify_cdparanoia_events({
            "read": 10, "jitter": 5, "skip": 2, "scratch": 1,
            "transport error": 1, "scsi_read error": 3,
            "drift": 2, "unknown_event": 4,
        })
        self.assertEqual(severe, 2 + 1 + 1 + 3)
        self.assertEqual(corrections, 5 + 2 + 4)
        self.assertEqual(lossy, ["scratch", "skip"])

    def testClassifyTransportErrorNotInLossyNames(self):
        from whipper.program.cdparanoia import classify_cdparanoia_events
        severe, corrections, lossy = classify_cdparanoia_events(
            {"transport error": 2})
        self.assertEqual(severe, 2)
        self.assertEqual(corrections, 0)
        self.assertEqual(lossy, [])

    def testLoggerTransportErrorOnlyHealth(self):
        """Severe recoverable events still set 'There were errors'."""
        ripResult = RipResult()
        ripResult.offset = 0
        ripResult.overread = False
        ripResult.isCdr = False
        ripResult.table = MockImageTable()
        ripResult.artist = "A"
        ripResult.title = "T"
        ripResult.vendor = "V"
        ripResult.model = "M"
        ripResult.release = "1"
        ripResult.cdrdaoVersion = "1.2.4"
        ripResult.cdparanoiaVersion = "cdparanoia III 10.2"
        ripResult.cdparanoiaDefeatsCache = True

        trackResult = TrackResult()
        trackResult.number = 1
        trackResult.filename = "./01.flac"
        trackResult.peak = 1000
        trackResult.quality = 0.95
        trackResult.copyspeed = 2.0
        trackResult.testduration = 1
        trackResult.copyduration = 1
        trackResult.testcrc = 0x22222222
        trackResult.copycrc = 0x22222222
        trackResult.cdparanoiaEvents = {"transport error": 2}
        trackResult.suspiciousPositions = [(5, 6)]
        trackResult.AR = {
            "v1": {"DBConfidence": None, "DBCRC": None, "CRC": None},
            "v2": {"DBConfidence": None, "DBCRC": None, "CRC": None},
        }
        ripResult.tracks.append(trackResult)

        log = WhipperLogger().log(ripResult, epoch=0)
        self.assertIn("Health status: There were errors", log)
        self.assertIn("cdparanoia health: severe recoverable errors", log)
        self.assertIn("Copy OK (cdparanoia reported severe recoverable", log)

    def testLoggerCleanTrackStatusUnchanged(self):
        ripResult = RipResult()
        ripResult.offset = 0
        ripResult.overread = False
        ripResult.isCdr = False
        ripResult.table = MockImageTable()
        ripResult.table.tracks = ripResult.table.tracks[:1]
        ripResult.artist = "Example Artist"
        ripResult.title = "Example Album"
        ripResult.vendor = "HL-DT-ST"
        ripResult.model = "DVDRAM"
        ripResult.release = "1.00"
        ripResult.cdrdaoVersion = "1.2.4"
        ripResult.cdparanoiaVersion = "cdparanoia III 10.2"
        ripResult.cdparanoiaDefeatsCache = True

        trackResult = TrackResult()
        trackResult.number = 1
        trackResult.filename = "./01 - Example.flac"
        trackResult.pregap = 0
        trackResult.peak = 29503
        trackResult.quality = 1
        trackResult.copyspeed = 7
        trackResult.testduration = 10
        trackResult.copyduration = 10
        trackResult.testcrc = 0x0025D726
        trackResult.copycrc = 0x0025D726
        trackResult.AR = {
            "v1": {"DBConfidence": None, "DBCRC": None, "CRC": None},
            "v2": {"DBConfidence": None, "DBCRC": None, "CRC": None},
        }
        ripResult.tracks.append(trackResult)

        log = WhipperLogger().log(ripResult, epoch=0)
        self.assertNotIn("cdparanoia events:", log)
        self.assertNotIn("Suspicious positions:", log)
        self.assertIn("Status: Copy OK\n", log)
        self.assertIn("Health status: No errors occurred", log)
        self.assertIn("cdparanoia health: clean", log)
