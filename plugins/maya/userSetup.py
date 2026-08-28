"""RenderHive Maya Module Startup Hook.

Executed by Maya when the RenderHive module is loaded.
Safely registers the RenderHive top menu deferred after UI initialization.
"""

try:
    import maya.utils as _maya_utils

    def _renderhive_init_deferred():
        try:
            import renderhive_installer
            renderhive_installer.ensure_main_menu()
        except Exception:
            pass

    _maya_utils.executeDeferred(_renderhive_init_deferred)
except Exception:
    pass
