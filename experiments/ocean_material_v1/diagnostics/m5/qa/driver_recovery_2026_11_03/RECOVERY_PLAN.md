# NVIDIA driver recovery — prepared 3 November 2026

Resolution: the user rebooted the computer on 3 November 2026. Loaded NVIDIA module, installed module and `nvidia-smi` now agree on **595.99.02**, with kernel **7.0.0-42-generic**. MARLIN was restored from the verified checkpoint and the M5 capture audit was executed. Post-reboot evidence is retained in `post_reboot/`, `post_reboot_retry02/` and `post_reboot_retry03/`; final live-state verification is in `../final_live_verification.json`.

The remaining sections preserve the diagnosis and recovery procedure prepared before the user's reboot. The agent did not request the actual host reboot or change driver packages. Two later checkpointed Kit restarts loaded the local audit corrections; they did not reboot the host.

The loaded module is 595.91.07. The installed NVML library and the NVIDIA kernel modules for both 7.0.0-38-generic and 7.0.0-42-generic are 595.99.02. `dpkg --audit` returned successfully with no output. Ubuntu reports a required system restart. This is consistent with an updated driver installation awaiting a reboot; no package replacement, purge, downgrade or module unloading has been performed.

Ubuntu documents this mismatch and recommends rebooting to load the updated module:
https://ubuntu.com/server/docs/how-to/graphics/install-nvidia-drivers/#driver-library-version-mismatch-error

## Saved state

Fresh checkpoint: `checkpoint_6x3ggjpt`.

Scene: `/home/madil/kit-app-template/artifacts/scene_checkpoints/checkpoint_6x3ggjpt/scene.usdc`.

SHA-256: `2101ae85f6eafef78968e656c5db442e921642c90e9b021229600456fd394ff7`.

`pre_reboot_checkpoint.json` contains viewport resolution, camera and renderer settings. `pre_reboot_live_state.json` contains ocean/chase/swimming status and scene inspection. The ocean and chase camera were running, swimming was stopped and the original water preset was selected. All 113 application source pins and 2,342 historical evidence entries were verified before this checkpoint.

A checkpoint preserves frozen visual state and external asset references. It does not serialize procedural controller phase or GPU render history. A reboot closes the desktop applications; other unsaved work must be saved by its owner first.

## Approved execution and verification procedure

1. Only after the user authorizes a whole-computer reboot, recheck that the checkpoint hash is intact, then request a normal system reboot. Do not force termination or unload the NVIDIA display modules from the running desktop. Record the actual reboot command/result. No reboot has been requested yet.
2. After login and reopening this chat, run `nvidia-smi`, inspect `/proc/driver/nvidia/version` and `modinfo -F version nvidia`, and confirm the driver versions match. Record the new boot ID and GPU free/used memory. If they still differ, stop and investigate the booted module/initramfs before changing packages. A successful reboot is not a permanent GPU memory fix or proof of renderer correctness.
3. Verify the protected evidence and source pins again. Reuse MARLIN if already running; do not create a duplicate Kit process. If MARLIN is stopped, require at least 2,048 MiB free before launching the documented existing application from `/home/madil/kit-app-template/_build/linux-x86_64/release` with `./cris.madil.kit.sh --enable cris.madil.render_service`. This is a launch path only; do not inspect or edit generated runtime files.
4. Restore the saved frozen scene through `POST /debug/scene/checkpoint/checkpoint_6x3ggjpt/restore`. Check the saved camera, viewport and renderer settings. This route does not start procedural controllers. Use the recorded live-state parameters when restoring controllers; if the existing standard `/scene/marine/setup` route is used to reconstruct the standard scene, record that reconstruction and its phase reset explicitly rather than claiming exact animation continuity. The recorded standard scene used `start_swimming: false`.
5. Run the predeclared M5 protocol only after the 768 MiB capture guard succeeds. Record all new captures, effective controls, image/state comparisons, timing, sampled GPU peaks, failures and restoration. Keep the previous guard failure and prior M4 evidence unchanged. M4's NVIDIA camera-inside case remains open independently.
