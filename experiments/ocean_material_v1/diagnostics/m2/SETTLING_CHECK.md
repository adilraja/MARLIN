# One bounded rendered-frame settling check

The positive-depth oblique probe showed a target, but a fresh acceptance image
with identical material values did not. Preserve both. The accepted request
pipeline therefore has not yet established reconstructible transmission.

Before the final check, retain the same positive-depth fixture, original image
measurement and tolerances, renderer, ray budgets and output size. Wait for
64 rendered frames through the installed existing ViewportAPI method, with a
30-second wait timeout, in addition to the previous update settling and warm-up.
Garbage-collect unreachable Python objects before the unchanged 768 MiB GPU guard,
as the existing marine capture implementation already does. Do not clear shader
caches or increase ray/sample budgets. This is not a measured sample-count claim.

Run one six-condition set and stop on resource or capability failure. If the
water result remains inconsistent, report M2 as partial instead of repeating
until a favourable image is obtained. UI callback errors during temporary
viewport cleanup remain logged as an existing SDK limitation; do not patch
vendor code to hide them.
