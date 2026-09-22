import sys

from setuptools import Extension, setup

# FreeBSD keeps third-party headers and libraries under /usr/local (the
# libsndfile-backed accuraterip C extension lives there). Add those paths
# automatically so `pip install .` works without a CFLAGS/LDFLAGS dance.
include_dirs = []
library_dirs = []
if sys.platform.startswith('freebsd'):
    include_dirs.append('/usr/local/include')
    library_dirs.append('/usr/local/lib')

setup(
    ext_modules=[
        Extension(
            name="accuraterip",
            libraries=['sndfile'],
            sources=["src/accuraterip-checksum.c"],
            include_dirs=include_dirs,
            library_dirs=library_dirs,
        ),
    ]
)
