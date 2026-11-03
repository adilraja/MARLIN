# Responsive regression execution

The first five-phase/240-step production-controller comparison passed with
zero errors, but its synchronous work exceeded the HTTP client's 120-second
timeout. The retained server result is `regression_40f9eja5/result.json`.
A capture queued behind it also exceeded its client wait, then reported an
anonymous-layer save error; that failure is retained separately.

The follow-up uses the same five geometry phases and both controller cases,
20 steps of .3 seconds per trajectory, with diving/surfacing commands in
three segments. It yields to Kit between small batches while controllers are
paused, retains the 1e-8 equivalence tolerance, and never changes wave or
controller equations. Render-only corner-normal/array preparation was
vectorized and uses native Vt arrays to reduce Python conversion overhead.
The M3 viewport setup now skips saving anonymous live root layers and allows
M4 to hide only its saved guide flags, preserving all animal/type visibility.
M3's file-backed/default behaviour was retained.
