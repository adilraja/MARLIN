#!/usr/bin/env bash
# Container entrypoint script with artifact collection support.
# Runs Kit application as child process and uploads logs/metadata to cloud storage on termination.
# Supports Azure Blob Storage, AWS S3, and Google Cloud Storage with configurable paths.
# See repo_kit_tools documentation for configuration details.

set -u  # Exit on undefined variables

# ============================================================================
# Artifact Collection Setup
# ============================================================================
KIT_PID=""
KIT_EXIT_CODE=0
UPLOAD_SCRIPT="/app/upload_kit_artifacts.py"
ARTIFACT_PYTHON="/home/ubuntu/.artifact_collector_venv/bin/python3"

upload_artifacts() {
    if [ -f "$${UPLOAD_SCRIPT}" ] && [ -f "$${ARTIFACT_PYTHON}" ]; then
        echo "[ARTIFACT_COLLECTOR] Uploading Kit artifacts..."
        "$${ARTIFACT_PYTHON}" "$${UPLOAD_SCRIPT}" "$${KIT_EXIT_CODE}" || echo "[ARTIFACT_COLLECTOR] Upload failed (non-fatal)"
    else
        echo "[ARTIFACT_COLLECTOR] Upload script or Python not available, skipping"
    fi
}

handle_shutdown() {
    echo "[ARTIFACT_COLLECTOR] Shutdown signal received"
    if [ -n "$${KIT_PID}" ] && kill -0 $${KIT_PID} 2>/dev/null; then
        echo "[ARTIFACT_COLLECTOR] Forwarding SIGTERM to Kit (PID: $${KIT_PID})..."
        kill -TERM $${KIT_PID} 2>/dev/null || true
        echo "[ARTIFACT_COLLECTOR] Waiting for Kit to exit..."
        # Wait captures the actual exit code (including signal termination: 128+signal)
        wait $${KIT_PID} 2>/dev/null
        KIT_EXIT_CODE=$$?
    fi
    upload_artifacts
    exit $${KIT_EXIT_CODE}
}

trap 'handle_shutdown' SIGTERM SIGINT

# ============================================================================
# Configuration
# ============================================================================
write_omniverse_toml() {
    local nucleus_server=$$1
    mkdir --parents /home/ubuntu/.nvidia-omniverse/config
    cat <<EOF > /home/ubuntu/.nvidia-omniverse/config/omniverse.toml
[bookmarks]
"$${nucleus_server}" = "omniverse://$${nucleus_server}"
EOF
}

USER_ID="$${USER_ID:-""}"
if [ -z "$${USER_ID}" ]; then
    echo "User id is not set"
fi

# If NVDA_KIT_NUCLEUS is set, write out the omniverse.toml value
if [ -n "$${NVDA_KIT_NUCLEUS:-}" ]; then
    write_omniverse_toml "$${NVDA_KIT_NUCLEUS}"
    nucleus_cmd="--/ovc/nucleus/server=$${NVDA_KIT_NUCLEUS}"
fi

# Display session info for debugging
echo "============================================"
echo "NVCF Session Information"
echo "============================================"
echo "NVCF-REQID: $${NVCF_REQID:-$${NVCF-REQID:-not set}}"
echo "HOSTNAME: $${HOSTNAME:-not set}"
echo "Secrets available: $$(test -f /var/secrets/secrets.json && echo 'YES' || echo 'NO')"
echo "============================================"

# Hard-coded defaults for containerized Kit Applications
HARDCODED_KIT_ARGS=(
    "--no-window"
    "--ext-folder /home/ubuntu/.local/share/ov/data/exts/v2"
)

CMD="/app/${kit_subpath}kit"
ARGS=(
    "/app/apps/${kit_app_whole}"
    "$${HARDCODED_KIT_ARGS[@]}"
    $${NVDA_KIT_ARGS:-""}
    $${nucleus_cmd:-""}
)

# Emit the .kit file to be executed if kit_verbose is set
if [ $${OM_KIT_VERBOSE:-0} = "1" ]; then
    export KIT_FILE=/app/apps/${kit_app_whole}
    echo "==== Print out kit config $${KIT_FILE} for debugging ===="
    cat $${KIT_FILE}
    echo "==== End of kit config $${KIT_FILE} ===="
fi

echo "Starting Kit with $$CMD $${ARGS[@]} $$@"

# Chown the Kit caching directories to avoid permissions issues
chown -R ubuntu:ubuntu /home/ubuntu/.cache/ov || true
chown -R ubuntu:ubuntu /home/ubuntu/.local/share/ov || true

# ============================================================================
# Run Kit as background process and wait for it
# ============================================================================
eval "$$CMD" "$${ARGS[@]}" "$$@" &
KIT_PID=$$!

echo "[ARTIFACT_COLLECTOR] Kit started with PID: $${KIT_PID}"

# Wait for Kit to exit and capture exit code
# Exit code will be 0 for success, 1-255 for errors, or 128+N for signal termination
wait $${KIT_PID}
KIT_EXIT_CODE=$$?

echo "[ARTIFACT_COLLECTOR] Kit exited with code: $${KIT_EXIT_CODE}"

# Upload artifacts on normal exit
upload_artifacts

exit $${KIT_EXIT_CODE}
