# RenderHive Houdini Menu Compatibility Fix v0.1.5

The menu no longer depends on the Houdini-specific `help_menu` element.
Some Houdini builds use different internal menu IDs, so the RenderHive menu is
now appended safely by Houdini without a version-specific ordering anchor.

This keeps one `MainMenuCommon.xml` compatible across supported Houdini versions.
