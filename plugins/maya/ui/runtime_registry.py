from __future__ import absolute_import


# Shared widget registry used by the Maya-facing window and extracted
# controller mixins. Keep the object identity stable for the lifetime of the
# Python module so imported controller modules always observe the same state.
WIDGETS = {}


