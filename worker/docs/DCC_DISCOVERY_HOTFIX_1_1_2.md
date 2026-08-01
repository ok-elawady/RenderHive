# DCC Discovery Hotfix 1.1.2

## Fixed

- Manual/explicit Maya and Houdini roots now always override registry and Program Files matches for the same version.
- The last explicit root wins when multiple manual roots describe the same Maya release or Houdini build.
- Real DCC installations on the test machine can no longer override temporary test installations.
- Automatic duplicates still prefer the record with the most valid executables.

This resolves Windows-only test failures where installed Maya 2023 or Houdini 20.5.278 was selected instead of the explicit temporary root used by the test suite.
