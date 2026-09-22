===================
whipper-offset-find
===================

--------------------------------------------------------------------------------
Find drive's read offset by ripping tracks from a CD in the AccurateRip database
--------------------------------------------------------------------------------

:Author: Louis-Philippe Véronneau
:Date: 2020
:Manual section: 1

Synopsis
========

| whipper offset find [**-o** *<OFFSETS>*] [**-d** *<DEVICE>*]
|                     [**--no-frame450**] [**--no-prioritize-known**]
| whipper offset find **-h**

Options
=======

| **-h** | **--help**
|     Show this help message and exit

| **-o** *<OFFSETS>* | **--offsets** *<OFFSETS>*
|     Probe only these offsets, in order; commas separate values and colons
|     specify inclusive ranges. Bypasses automatic candidate selection.

| **-d** *<DEVICE>* | **--device** *<DEVICE>*
|     Path to the CD-DA device

| **--no-frame450**
|     Skip the short AccurateRip checksum window and use full-track probes.

| **--no-prioritize-known**
|     Do not prioritize configured or published drive-model offsets in the probe
|     list. Combine with **--no-frame450** for the original probing order.

Detection
=========

Without **--offsets**, whipper reads a short window around frame 450 of track 1
and searches within 3,000 samples of the configured offset, the most frequently
reported model offset, or zero if neither is available. It confirms suggested
offsets with the AccurateRip checksums of every track except the last. The
existing minimum of three tracks and configuration format are unchanged.
When several offsets match the short window, configured and published offsets
are tried first among those matches, unless **--no-prioritize-known** is set.

If window data is unavailable or candidates fail confirmation, ordinary probing
continues, trying configured and published offsets before the existing list.
Model names must match completely, ignoring case and whitespace. Conflicting
published offsets remain candidates; a lookup never bypasses confirmation.
No drive-table download is made at runtime.

See Also
========

whipper(1), whipper-offset(1)
