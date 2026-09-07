# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import omni.ext
import carb.settings
from omni.services.core import main
from .camera import shutdown_chase_camera
from .service import router, shutdown_cetacean_swimming, shutdown_ocean_animation
from .underwater_api import (
    shutdown_underwater_cue,
)
from .underwater_cue import (
    DEFAULT_UNDERWATER_FOG_SETTINGS,
    UNDERWATER_CUE_REQUESTED_SETTING,
)
from .water_material import RTX_WATER_SETTINGS

# Any class derived from `omni.ext.IExt` in the top level module (defined in
# `python.modules` of `extension.toml`) will be instantiated when the extension
# gets enabled, and `on_startup(ext_id)` will be called. Later when the
# extension gets disabled on_shutdown() is called.
class MyExtension(omni.ext.IExt):
    """This extension manages the service setup"""
    # ext_id is the current extension id. It can be used with the extension
    # manager to query additional information, like where this extension is
    # located on the filesystem.
    def on_startup(self, _ext_id):
        """This is called every time the extension is activated."""
        settings = carb.settings.get_settings()
        for path, value in RTX_WATER_SETTINGS.items():
            settings.set(path, value)
        for path, value in DEFAULT_UNDERWATER_FOG_SETTINGS.items():
            settings.set(path, value)
        settings.set(UNDERWATER_CUE_REQUESTED_SETTING, True)
        main.register_router(router)
        print("[CRIS Render Service] MyExtension startup : Local Docs -  http://localhost:8011/docs")

    def on_shutdown(self):
        shutdown_chase_camera(restore_viewport=True)
        shutdown_cetacean_swimming()
        shutdown_ocean_animation()
        shutdown_underwater_cue()
        main.deregister_router(router)
