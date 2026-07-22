# Pool Targeting v1.9.4

- Backend pools are the only scheduling unit exposed by the Maya plugin.
- Select all pools, selected pools only, or all pools except selected pools.
- Pool selections are stored by stable backend ID in SQLite scene state.
- Worker selection and RAM/VRAM targeting were removed.
- The task payload includes selected, excluded and effective pool IDs/names.
