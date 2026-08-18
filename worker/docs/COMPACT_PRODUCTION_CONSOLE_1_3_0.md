# RenderHive Worker Compact Production Console 1.3.0

This release replaces the large dashboard and sidebar with a compact operator
console inspired by the information hierarchy of Deadline Worker while keeping
RenderHive's visual identity.

## Main interface

- Default size: 820 x 560, minimum 740 x 500.
- Two primary tabs: Job Information and Worker Information.
- Compact status, connection, DCC, settings, start, and stop controls in the header.
- Scheduling controls remain available in a fixed bottom command bar.
- The full live log is collapsed by default and can be opened without changing tabs.

## Reduced information density

The main window shows only operationally useful fields. Full DCC installation
paths are moved to a separate details dialog. Long explanations are removed
from the working area and exposed through tooltips where useful.

## Preserved behavior

The Maya and Houdini adapters, version discovery, backend heartbeat, task
claiming, progress reporting, Hython/Husk routing, system tray, and worker
settings behavior are unchanged.
