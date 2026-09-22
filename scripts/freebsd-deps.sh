#!/bin/sh
# Install FreeBSD system packages whipper needs (cdrdao, cd-paranoia, flac, ...).
# Does not install whipper itself. See freebsd-packages.txt.

set -eu

if [ "$(id -u)" -ne 0 ]; then
    echo "pkg install needs root. Try: su -m root -c 'sh $0'" >&2
    exit 1
fi

root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
list="$root/freebsd-packages.txt"
if [ ! -f "$list" ]; then
    echo "missing $list" >&2
    exit 1
fi

# shellcheck disable=SC2046
pkg install -y $(grep -vE '^[[:space:]]*(#|$)' "$list")

PATH="/usr/local/bin:$PATH"
pyver=$(python3 -c 'import sys; print("%d%d" % (sys.version_info[0], sys.version_info[1]))')
pkg install -y "py${pyver}-pip"

echo
echo "Then:"
echo "  export CFLAGS=-I/usr/local/include LDFLAGS=-L/usr/local/lib"
echo "  python3 -m pip install ."
echo "Or pip-install the v0.11.0 tarball from the README."
