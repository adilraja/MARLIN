# Prospective startup-readiness correction for attempt02

Attempt01 restored the checkpoint and entered its capture wait before the first `RTX ready` message. The baseline wait timed out after 30.03 seconds; its image was not accepted. The first RTX-ready message appeared at app time 79.17 seconds, after the capture had failed. All six restoration checks passed and the standard live controllers were reconstructed. The sampled minimum free GPU memory was 3,508 MiB, so the failed wait did not establish memory exhaustion.

For attempt02 only, establish initial renderer readiness on the restored checkpoint with three completed rendered frames, bounded at 90 seconds, before entering the capture suite. Record this startup preparation separately from capture timing. Preserve the failed first attempt and its exact script sources.

The capture itself still requires 64 rendered frames within 30 seconds, a 60-second per-capture bound and a 300-second suite bound. Output size, camera, medium, exposure, denoising and sample configuration are unchanged. This correction does not reinterpret attempt01 as a pass, increase its capture budget or establish an exact hardware sample count.

One checkpointed, graceful Kit restart is needed to load the corrected local `--exec` audit. It does not reboot the host. GPU history and reconstructed controller phase reset again and must be reported. Historical evidence and canonical application source remain unchanged.
