from subprocess import check_call, CalledProcessError, PIPE

from whipper.common import common

import logging
logger = logging.getLogger(__name__)


def encode(infile, outfile):
    """
    Encode infile to outfile, with flac.

    Uses ``-f`` because whipper already creates the file.
    """
    argv = ['flac', '--silent', '--verify', '-o', outfile, '-f', infile]
    try:
        check_call(argv, stderr=PIPE)
    except CalledProcessError as e:
        common.subprocess_trace(argv, returncode=e.returncode,
                                stderr=e.stderr)
        logger.exception('flac failed')
        raise
