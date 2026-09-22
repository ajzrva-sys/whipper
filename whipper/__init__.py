import logging
import os
import sys

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version('whipper')
except PackageNotFoundError:
    # not installed as package or is being run from source/git checkout
    from setuptools_scm import get_version
    __version__ = get_version()

# Subprocess tracing sits below DEBUG (10) so -vvv is strictly noisier than
# -vv. Enabled by ``whipper -vvv`` or ``whipper -vvv <subcommand>``.
SUBPROCESS = 5
logging.addLevelName(SUBPROCESS, 'SUBPROCESS')

level = logging.INFO
if 'WHIPPER_DEBUG' in os.environ:
    level = os.environ['WHIPPER_DEBUG'].upper()

log_init_func = logging.basicConfig
if 'WHIPPER_COLOR_LOG' in os.environ:
    import coloredlogs

    def init_coloredlogs(**kwargs):
        # coloredlogs comes with its own log format, we don't want to use that
        coloredlogs.install(fmt=logging.BASIC_FORMAT, **kwargs)
    log_init_func = init_coloredlogs

if 'WHIPPER_LOGFILE' in os.environ:
    log_init_func(filename=os.environ['WHIPPER_LOGFILE'],
                  filemode='w', level=level)
else:
    log_init_func(stream=sys.stderr, level=level)


def configure_logging(verbosity=0):
    """
    Reconfigure the root logger for a ``-v``/``-vv``/``-vvv`` count.

    ``verbosity`` 0 keeps the import-time level (INFO, or WHIPPER_DEBUG if
    set); 1 is INFO; 2 is DEBUG; 3 and above add subprocess traces
    (``SUBPROCESS``). Returns the effective numeric level.
    """
    if verbosity >= 3:
        new_level = SUBPROCESS
    elif verbosity == 2:
        new_level = logging.DEBUG
    else:
        new_level = logging.INFO

    logging.getLogger().setLevel(new_level)
    return new_level
