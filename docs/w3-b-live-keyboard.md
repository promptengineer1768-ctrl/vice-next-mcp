# W3-B live keyboard capability boundary

`validation/live_keyboard_feed.py` was run against the official VICE 3.10
`x64sc` and `x128` binaries.  The binary-monitor keyboard-feed command
(`0x72`, API v2) accepts text and is recorded separately in
`validation/results/w3-b-keyboard-feed-live.json`; it is not a physical
matrix event.

`validation/live_keyboard_matrix.py` then attempted `vice.keyboard.matrix`
(row 1, column 2, press) and `vice.keyboard.restore` (press) on both hosts.
Both calls were rejected explicitly with `RuntimeError`: the upstream binary
monitor has no row/column or RESTORE/NMI event primitive.  The result is
`validation/results/w3-b-keyboard-matrix-live.json`.

Consequently this is a verified capability boundary, not a passing physical
matrix test.  Completing the remaining W3-B matrix/RESTORE scenarios requires
an event-capable VICE backend (or a VICE build exposing those monitor
commands); direct KERNAL buffer writes must not be counted as matrix evidence.
