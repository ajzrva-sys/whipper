# -*- Mode: Python; test-case-name: whipper.test.test_command_doctor -*-
# vi:si:et:sw=4:sts=4:ts=4

"""
``whipper doctor`` — diagnose the environment and report readiness to rip.

The command makes the C toolchain invisible: instead of a pip traceback or a
``TaskException``, it prints a human-readable table and exits non-zero when
something is missing, with the exact install/repair command for each failure.
"""

import platform as _ospy
import subprocess

from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from whipper.command.basecommand import BaseCommand
from whipper.common import accurip, config, drive
from whipper.platform import platform

import logging
logger = logging.getLogger(__name__)


# Human label -> (kind, detail)
# kind: 'ok' (informational), 'required' (breaks the rip), 'optional',
#        'warn' (works but should be fixed)
_OK = 'OK'
_MISSING = 'MISSING'
_WARN = 'WARN'


def _probe_version(argv, timeout=10):
    """Return the first non-empty output line of ``argv``, or None."""
    try:
        out = subprocess.check_output(argv, stderr=subprocess.STDOUT,
                                      timeout=timeout)
    except (OSError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired):
        return None
    text = out.decode('utf-8', errors='replace')
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return None


def _reachable(url, timeout=10):
    """True if an HTTP GET to ``url`` succeeds."""
    try:
        with urlopen(Request(url, headers={'User-Agent': 'whipper-doctor'}),
                     timeout=timeout) as resp:
            resp.read(1)
        return True
    except (URLError, HTTPError, OSError):
        return False


class Doctor(BaseCommand):
    summary = "diagnose the rip environment"
    description = """Check the OS, drive, helper programs and services whipper
needs, and report whether it is ready to rip."""
    device_option = False

    def _rows(self):
        """Yield (label, value, status, hint) tuples in display order."""
        yield ('OS', '%s %s' % (_ospy.system(), _ospy.release()), _OK, None)
        yield ('Python', _ospy.python_version(), _OK, None)
        yield ('Platform', platform.name, _OK, None)

        # -- drives --------------------------------------------------------
        paths = drive.getAllDevicePaths()
        if not paths:
            yield ('Drive', 'none found', _MISSING,
                   'create /dev/cdrom (Linux) or ensure a /dev/cdN node '
                   'exists (FreeBSD); installing pycdio improves detection')
        else:
            for path in paths:
                info = drive.getDeviceInfo(path)
                if info:
                    vendor, model, release = info
                    label = 'Drive'
                    value = '%s %s %s (%s)' % (vendor, model, release, path)
                else:
                    label = 'Drive'
                    value = '%s (unknown identity)' % path
                yield (label, value, _OK, None)

                # read offset / cache defeat are per-drive and optional but
                # worth surfacing (doctor points at the right command).
                cfg = config.Config()
                if info:
                    try:
                        offset = cfg.getReadOffset(vendor, model, release)
                        yield ('Read offset', '+%d samples' % offset, _OK,
                               None)
                    except (KeyError, TypeError, ValueError):
                        yield ('Read offset', 'not configured', _WARN,
                               "run 'whipper offset find'")
                    try:
                        defeats = cfg.getDefeatsCache(
                            vendor, model, release)
                        yield ('Cache defeat', str(defeats), _OK, None)
                    except KeyError:
                        yield ('Cache defeat', 'unknown', _WARN,
                               "run 'whipper drive analyze'")
                else:
                    yield ('Read offset', 'unknown (no drive identity)',
                           _WARN, "install pycdio, or on FreeBSD check "
                                  "camcontrol")

        # -- tools ---------------------------------------------------------
        from whipper.program import cdparanoia, cdrdao

        try:
            version = cdparanoia.getCdParanoiaVersion()
            yield ('cd-paranoia', version, _OK, None)
        except Exception:
            yield ('cd-paranoia', 'not found', _MISSING,
                   'install cd-paranoia (pkg install cdparanoia; '
                   'apt install cd-paranoia)')

        cdrdao_version = cdrdao.version()
        if cdrdao_version:
            yield ('cdrdao', cdrdao_version, _OK, None)
        else:
            yield ('cdrdao', 'not found', _MISSING,
                   'install cdrdao (pkg install cdrdao; apt install cdrdao)')

        flac_version = _probe_version(['flac', '--version'])
        if flac_version:
            yield ('FLAC', flac_version, _OK, None)
        else:
            yield ('FLAC', 'not found', _MISSING,
                   'install flac (pkg install flac; apt install flac)')

        sox_version = _probe_version(['sox', '--version'])
        if sox_version:
            yield ('sox', sox_version, _OK, None)
        else:
            yield ('sox', 'not found', _MISSING,
                   'install sox (pkg install sox; apt install sox)')

        # optional libs
        try:
            import pycdio  # noqa: F401
            yield ('libcdio', 'installed (optional)', _OK, None)
        except ImportError:
            yield ('libcdio', 'not installed (optional)', _OK, None)

        # -- services ------------------------------------------------------
        server = config.Config().get_musicbrainz_server()
        mb_url = '%s://%s' % (server['scheme'], server['netloc'])
        if _reachable(mb_url):
            yield ('MusicBrainz', 'reachable', _OK, None)
        else:
            yield ('MusicBrainz', 'not reachable', _WARN,
                   'check your network; tagging will be skipped')
        if _reachable(accurip.ACCURATERIP_URL):
            yield ('AccurateRip', 'reachable', _OK, None)
        else:
            yield ('AccurateRip', 'not reachable', _WARN,
                   'ripping still works, but verification will not match '
                   'the database')

    def do(self):
        ready = True
        rows = list(self._rows())

        # determine column widths
        label_w = max((len(r[0]) for r in rows), default=4)
        value_w = max((len(r[1]) for r in rows), default=8)

        for label, value, status, hint in rows:
            print('%s %s %s' % (
                label.ljust(label_w), value.ljust(value_w), status))
            if hint and status != _OK:
                print('  -> %s' % hint)
            if status == _MISSING:
                ready = False

        if ready:
            print('\nReady to rip.')
            return 0
        print('\nNot ready to rip. Fix the rows above and re-run '
              "'whipper doctor'.")
        return 1
