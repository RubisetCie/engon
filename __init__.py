# copyright (c) 2018- polygoniq xyz s.r.o.

# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

import bpy
import os
import sys
import tempfile
import logging
import logging.handlers
import importlib
import typing

root_logger = logging.getLogger("polygoniq")
logger = logging.getLogger(f"polygoniq.{__name__}")
if not getattr(root_logger, "polygoniq_initialized", False):
    root_logger_formatter = logging.Formatter(
        "P%(process)d:%(asctime)s:%(name)s:%(levelname)s: [%(filename)s:%(lineno)d] %(message)s",
        "%H:%M:%S",
    )
    try:
        root_logger.setLevel(int(os.environ.get("POLYGONIQ_LOG_LEVEL", "0")))
    except (ValueError, TypeError):
        root_logger.setLevel(0)
    root_logger.propagate = False
    root_logger_stream_handler = logging.StreamHandler()
    root_logger_stream_handler.setFormatter(root_logger_formatter)
    root_logger.addHandler(root_logger_stream_handler)
    try:
        log_path = os.path.join(tempfile.gettempdir(), "polygoniq_logs")
        os.makedirs(log_path, exist_ok=True)
        root_logger_handler = logging.handlers.TimedRotatingFileHandler(
            os.path.join(log_path, f"blender_addons.txt"),
            when="h",
            interval=1,
            backupCount=2,
            utc=True,
        )
        root_logger_handler.setFormatter(root_logger_formatter)
        root_logger.addHandler(root_logger_handler)
    except:
        logger.exception(
            f"Can't create rotating log handler for polygoniq root logger "
            f"in module \"{__name__}\", file \"{__file__}\""
        )
    setattr(root_logger, "polygoniq_initialized", True)
    logger.info(
        f"polygoniq root logger initialized in module \"{__name__}\", file \"{__file__}\" -----"
    )


# To comply with extension encapsulation, after the addon initialization:
# - sys.path needs to stay the same as before the initialization
# - global namespace can not contain any additional modules outside of __package__

# Dependencies for all 'production' addons are shipped in folder `./python_deps`
# So we do the following:
# - Add `./python_deps` to sys.path
# - Import all dependencies to global namespace
# - Manually remap the dependencies from global namespace in sys.modules to a subpackage of __package__
# - Clear global namespace of remapped dependencies
# - Remove `./python_deps` from sys.path
# - For developer experience, import "real" dependencies again, only if TYPE_CHECKING is True

# See https://docs.blender.org/manual/en/4.2/extensions/addons.html#extensions-and-namespace
# for more details
ADDITIONAL_DEPS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "python_deps"))
try:
    if os.path.isdir(ADDITIONAL_DEPS_DIR) and ADDITIONAL_DEPS_DIR not in sys.path:
        sys.path.insert(0, ADDITIONAL_DEPS_DIR)

    dependencies = {"polib", "hatchery", "mapr"}
    for dependency in dependencies:
        logger.debug(f"Importing additional dependency {dependency}")
        dependency_module = importlib.import_module(dependency)
        local_module_name = f"{__package__}.{dependency}"
        sys.modules[local_module_name] = dependency_module
    for module_name in list(sys.modules.keys()):
        if module_name.startswith(tuple(dependencies)):
            del sys.modules[module_name]

    from . import polib
    from . import hatchery
    from . import mapr

    from . import ui_utils
    from . import asset_registry
    from . import pack_info_search_paths
    from . import asset_helpers
    from . import preferences
    from . import convert_selection
    from . import panel
    from . import browser
    from . import blend_maintenance

    from . import aquatiq
    from . import botaniq
    from . import materialiq
    from . import traffiq
    from . import scatter

    from . import keymaps

    if typing.TYPE_CHECKING:
        import polib
        import hatchery
        import mapr

finally:
    if ADDITIONAL_DEPS_DIR in sys.path:
        sys.path.remove(ADDITIONAL_DEPS_DIR)

bl_info = {
    "name": "Engon",
    "author": "Polygoniq XYZ S.R.O.",
    "version": (1, 2, 1),  # bump doc_url and version in register as well!
    "blender": (3, 3, 0),
    "location": "Engon tab in the sidebar of the 3D View window",
    "description": "Browse assets, filter and sort them, scatter, animate, manipulate rigs",
    "category": "Object",
    "doc_url": "https://docs.polygoniq.com/engon/1.2.1/",
    "tracker_url": "https://polygoniq.com/discord/",
}


def _post_register():
    prefs = preferences.prefs_utils.get_preferences(bpy.context)
    prefs.general_preferences.refresh_packs()
    # Make engon preferences open after first registration
    if prefs.first_time_register:
        polib.ui_bpy.expand_addon_prefs(__package__)
        prefs.first_time_register = False


def register():
    ui_utils.register()
    pack_info_search_paths.register()
    preferences.register()
    convert_selection.register()
    panel.register()
    scatter.register()
    blend_maintenance.register()
    browser.register()
    aquatiq.register()
    botaniq.register()
    materialiq.register()
    traffiq.register()
    keymaps.register()

    bpy.app.timers.register(
        _post_register,
        first_interval=0,
        # This is important. If an existing blend file is opened with double-click or on command
        # line with e.g. "blender.exe path/to/blend", this register() is called in the startup blend
        # file but right after the target blend file is opened which would discards the callback
        # without persistent=True.
        persistent=True,
    )


def unregister():
    keymaps.unregister()
    traffiq.unregister()
    materialiq.unregister()
    botaniq.unregister()
    aquatiq.unregister()
    browser.unregister()
    blend_maintenance.unregister()
    scatter.unregister()
    panel.unregister()
    convert_selection.unregister()
    preferences.unregister()
    pack_info_search_paths.unregister()
    ui_utils.unregister()

    # Remove all nested modules from module cache, more reliable than importlib.reload(..)
    # Idea by BD3D / Jacques Lucke
    for module_name in list(sys.modules.keys()):
        if module_name.startswith(__package__):
            del sys.modules[module_name]

    # We clear the master 'polib' icon manager to prevent ResourceWarning and leaks.
    # If other addons uses the icon_manager, the previews will be reloaded on demand.
    polib.ui_bpy.icon_manager.clear()
