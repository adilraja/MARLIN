# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT
#


#!/usr/bin/env python3
"""
Upload Omniverse Kit artifacts (logs, profiler traces, etc.) to cloud storage on container termination.

This script collects Kit logs, profiler traces, and metadata from containerized applications
and uploads them to cloud storage (Azure Blob, AWS S3, or Google Cloud Storage) using
configurable path templates that support NVCF environment variables.

Profiler traces (Chrome tracing format) are automatically detected by scanning the Kit log
for "Opened chrome tracefile for writing:" messages and also by looking for ct-profile*.json.gz
files in the current working directory.

Configuration is done via NVCF secrets or environment variables:
  - ARTIFACT_STORAGE_URI: Cloud storage URI (e.g., az://container, s3://bucket, gs://bucket)
  - ARTIFACT_PATH_TEMPLATE: Path template with variable substitution (optional)
  - ARTIFACT_MAX_FILE_SIZE_MB: Maximum file size in MB for uploads (default: 512 MB)
  - ARTIFACT_UPLOAD_ON_ERROR_ONLY: Upload only on non-zero exit code (default: false)

Cloud Storage Credentials (via NVCF secrets):
  - Azure (connection string): AZURE_STORAGE_CONNECTION_STRING
  - Azure (Entra ID): AZURE_STORAGE_ACCOUNT_URL + Entra ID credentials
    (AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET for service principal,
     or managed identity when running on Azure infrastructure)
  - AWS S3: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
    (AWS_SESSION_TOKEN is also required when using temporary STS credentials, e.g. from
    IAM Identity Center / SSO — keys prefixed with ASIA...)
  - Google Cloud: GOOGLE_APPLICATION_CREDENTIALS (file path) or
                  GOOGLE_APPLICATION_CREDENTIALS_JSON (JSON content as string)

Default path template: {NVCF_FUNCTION_NAME}/{session_id}

Files exceeding the maximum size limit will be skipped and logged in metadata.json.

See repo_kit_tools documentation for configuration details.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from string import Template

# NVCF secrets are mounted at this standard location
NVCF_SECRETS_PATH = "/var/secrets/secrets.json"

# Cloud storage URI configured via secrets or environment
CLOUD_STORAGE_URI_KEY = "ARTIFACT_STORAGE_URI"

# Configurable path template (supports variable substitution)
PATH_TEMPLATE_KEY = "ARTIFACT_PATH_TEMPLATE"

# Default path template using NVCF variables
DEFAULT_PATH_TEMPLATE = "{NVCF_FUNCTION_NAME}/{session_id}"

# Maximum file size for uploads (in MB) - configurable via environment
MAX_FILE_SIZE_MB_KEY = "ARTIFACT_MAX_FILE_SIZE_MB"
DEFAULT_MAX_FILE_SIZE_MB = 512

# Upload artifacts only on error (non-zero exit code or signal termination)
UPLOAD_ON_ERROR_ONLY_KEY = "ARTIFACT_UPLOAD_ON_ERROR_ONLY"

# NVCF environment variables to capture
NVCF_ENV_VARS = [
    "NVCF_FUNCTION_ID",
    "NVCF_FUNCTION_NAME",
    "NVCF_FUNCTION_VERSION_ID",
    "NVCF_NCA_ID",
    "NVCF_BACKEND",
    "NVCF_INSTANCETYPE",
    "NVCF_REGION",
    "NVCF_ENV",
    "NVCF_REQID",
    "NVCF-REQID",
]

# Azure Storage account URL for Entra ID authentication (alternative to connection string)
AZURE_STORAGE_ACCOUNT_URL_KEY = "AZURE_STORAGE_ACCOUNT_URL"

# Provider-specific credential keys (read from secrets and exported to environment)
CREDENTIAL_KEYS = [
    # Azure (connection string auth)
    "AZURE_STORAGE_CONNECTION_STRING",
    # Azure (Entra ID auth)
    "AZURE_STORAGE_ACCOUNT_URL",
    "AZURE_TENANT_ID",
    "AZURE_CLIENT_ID",
    "AZURE_CLIENT_SECRET",
    # AWS S3
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",  # Required for temporary STS credentials (IAM Identity Center / SSO)
    "AWS_DEFAULT_REGION",
    "AWS_ENDPOINT_URL",  # For S3-compatible services like MinIO
    # GCS - Note: GOOGLE_APPLICATION_CREDENTIALS expects a file path, not the JSON content
    # If you need to pass the JSON content via NVCF secrets, use GOOGLE_APPLICATION_CREDENTIALS_JSON instead
    "GOOGLE_APPLICATION_CREDENTIALS",
    "STORAGE_EMULATOR_HOST",  # For GCS emulator/fake-gcs-server
]

# Special key for GCS credentials JSON content (will be written to temp file)
GCS_CREDENTIALS_JSON_KEY = "GOOGLE_APPLICATION_CREDENTIALS_JSON"


def log(msg, level="INFO"):
    """Print log message with timestamp."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"{timestamp} [{level}] [ARTIFACT_COLLECTOR] {msg}", flush=True)


def _setup_gcs_credentials(gcs_creds_json):
    """Write GCS credentials JSON to temp file and set GOOGLE_APPLICATION_CREDENTIALS env var."""
    try:
        # Ensure it's a string (handle both string and dict)
        creds_str = gcs_creds_json if isinstance(gcs_creds_json, str) else json.dumps(gcs_creds_json)
        
        # Write to temp file
        temp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, prefix='gcs_', encoding="utf-8")
        temp.write(creds_str)
        temp.close()
        
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = temp.name
        log(f"Set GOOGLE_APPLICATION_CREDENTIALS={temp.name}")
        return True
    except Exception as e:
        log(f"Failed to setup GCS credentials: {e}", "ERROR")
        return False


def load_secrets():
    """
    Load secrets from NVCF secrets file and export credentials to environment.

    Special handling for GCS: If GOOGLE_APPLICATION_CREDENTIALS_JSON is provided,
    writes it to a temp file and sets GOOGLE_APPLICATION_CREDENTIALS to that path.
    """
    if not Path(NVCF_SECRETS_PATH).exists():
        log(f"Secrets file not found at {NVCF_SECRETS_PATH}", "WARN")
        return {}

    try:
        with open(NVCF_SECRETS_PATH, "r", encoding="utf-8") as f:
            secrets = json.load(f)
            log(f"Loaded secrets: {list(secrets.keys())}")

            # Handle GCS credentials JSON content
            if GCS_CREDENTIALS_JSON_KEY in secrets and "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
                _setup_gcs_credentials(secrets[GCS_CREDENTIALS_JSON_KEY])

            # Export other credential keys to environment
            for key in CREDENTIAL_KEYS:
                if key in secrets and key not in os.environ:
                    os.environ[key] = secrets[key]
                    log(f"Exported {key} to environment")

            return secrets
    except Exception as e:
        log(f"Failed to load secrets: {e}", "ERROR")
        return {}


def extract_nvcf_reqid_from_log(log_file_path):
    """Extract NVCF-REQID from Kit log file using grep."""
    try:
        # Pattern: [NVCF-REQID:uuid]
        cmd = f"tail -n 10000 '{log_file_path}' | grep -o '\\[NVCF-REQID:[^]]*\\]' | head -1"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)

        if result.returncode == 0 and result.stdout.strip():
            match = re.search(r"\[NVCF-REQID:([a-f0-9-]+)\]", result.stdout.strip())
            if match:
                return match.group(1)
    except Exception as e:
        log(f"Error extracting NVCF-REQID from log: {e}", "WARN")
    return None


def get_session_id(log_file_path=None):
    """Get session ID from environment or log file.

    Priority order:
    1. NVCF-REQID or NVCF_REQID environment variable
    2. Extract from log file
    3. Fallback to hostname_timestamp
    """
    # Try NVCF request ID from environment
    session_id = os.environ.get("NVCF-REQID") or os.environ.get("NVCF_REQID")
    if session_id:
        log(f"Session ID from environment: {session_id}")
        return session_id

    # Try extracting from log file
    if log_file_path and Path(log_file_path).exists():
        session_id = extract_nvcf_reqid_from_log(log_file_path)
        if session_id:
            log(f"Session ID from log file: {session_id}")
            return session_id

    # Fallback: hostname + timestamp
    hostname = os.environ.get("HOSTNAME", "unknown")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    fallback_id = f"{hostname}_{timestamp}"
    log(f"Using fallback session ID: {fallback_id}", "WARN")
    return fallback_id


def get_nvcf_metadata():
    """Collect all available NVCF environment variables and metadata.

    Returns:
        dict: Dictionary containing NVCF variables and additional metadata
    """
    metadata = {}

    # Capture all NVCF environment variables
    for var in NVCF_ENV_VARS:
        value = os.environ.get(var)
        if value:
            metadata[var] = value

    # Add additional metadata
    metadata["hostname"] = os.environ.get("HOSTNAME", "unknown")
    metadata["timestamp"] = datetime.now(timezone.utc).isoformat()

    return metadata


def build_artifact_path(session_id, secrets):
    """Build the artifact upload path using configurable template.

    Supports variable substitution with:
    - All NVCF environment variables (NVCF_FUNCTION_ID, NVCF_REGION, etc.)
    - {session_id} - NVCF request ID or fallback identifier
    - {date} - Current date in YYYY-MM-DD format
    - {datetime} - Current datetime in YYYY-MM-DD_HH-MM-SS format
    - {hostname} - Container hostname

    Args:
        session_id: Session identifier (NVCF request ID or fallback)
        secrets: Dictionary of secrets (may contain path template override)

    Returns:
        str: Formatted path string
    """
    # Get path template from secrets or environment, or use default
    path_template = secrets.get(PATH_TEMPLATE_KEY) or os.environ.get(PATH_TEMPLATE_KEY) or DEFAULT_PATH_TEMPLATE

    # Build substitution variables
    template_vars = {}

    # Add all NVCF environment variables
    for var in NVCF_ENV_VARS:
        value = os.environ.get(var, "")
        template_vars[var] = value

    # Add helper variables
    now = datetime.now(timezone.utc)
    template_vars["session_id"] = session_id
    template_vars["date"] = now.strftime("%Y-%m-%d")
    template_vars["datetime"] = now.strftime("%Y-%m-%d_%H-%M-%S")
    template_vars["hostname"] = os.environ.get("HOSTNAME", "unknown")

    # Perform substitution using str.format() for {var} syntax
    try:
        formatted_path = path_template.format(**template_vars)
        log(f"Using path template: {path_template}")

        # Clean up the path: remove leading/trailing slashes and collapse multiple slashes
        # This handles cases where variables in the template are empty (e.g., NVCF_FUNCTION_NAME)
        formatted_path = formatted_path.strip("/")
        # Collapse multiple consecutive slashes into one
        while "//" in formatted_path:
            formatted_path = formatted_path.replace("//", "/")
        
        log(f"Resolved artifact path: {formatted_path}")
        return formatted_path
    except KeyError as e:
        log(f"Invalid variable in path template: {e}. Using default.", "WARN")
        # Fallback to simple session_id path
        return session_id


def find_kit_log_file():
    """Find the most recent Kit log file."""
    log_base_path = Path.home() / ".nvidia-omniverse" / "logs" / "Kit"

    if not log_base_path.exists():
        log(f"Kit log directory not found: {log_base_path}", "WARN")
        return None

    # Find all kit*.log files recursively
    log_files = list(log_base_path.rglob("kit*.log"))
    if not log_files:
        # Try any .log file as fallback
        log_files = list(log_base_path.rglob("*.log"))

    if not log_files:
        log(f"No log files found in {log_base_path}", "WARN")
        return None

    # Return most recently modified
    most_recent = max(log_files, key=lambda p: p.stat().st_mtime)
    log(f"Found log file: {most_recent} ({most_recent.stat().st_size} bytes)")
    return most_recent


def extract_profiler_paths_from_log(log_file_path):
    """Extract profiler output file paths from Kit log using grep.

    Looks for log messages like:
    - "Opened chrome tracefile for writing: <path>"

    Args:
        log_file_path: Path to Kit log file

    Returns:
        list: List of Path objects to profiler trace files
    """
    profiler_files = []

    try:
        # Use grep to quickly find profiler output lines in large logs
        cmd = f"grep 'Opened chrome tracefile for writing:' '{log_file_path}'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)

        if result.returncode == 0 and result.stdout.strip():
            for line in result.stdout.strip().split("\n"):
                # Extract path after the message
                match = re.search(r"Opened chrome tracefile for writing:\s*(.+?)(?:\s*$|\s*\[)", line)
                if match:
                    file_path = match.group(1).strip()
                    profiler_path = Path(file_path)

                    # If relative path, check in CWD and log directory
                    if not profiler_path.is_absolute():
                        # Try in current working directory
                        cwd_path = Path.cwd() / profiler_path
                        if cwd_path.exists():
                            profiler_files.append(cwd_path)
                            log(f"Found profiler trace (CWD): {cwd_path} ({cwd_path.stat().st_size} bytes)")
                            continue

                        # Try relative to log file location
                        log_dir_path = log_file_path.parent / profiler_path
                        if log_dir_path.exists():
                            profiler_files.append(log_dir_path)
                            log(f"Found profiler trace (log dir): {log_dir_path} ({log_dir_path.stat().st_size} bytes)")
                            continue
                    else:
                        # Absolute path
                        if profiler_path.exists():
                            profiler_files.append(profiler_path)
                            log(f"Found profiler trace: {profiler_path} ({profiler_path.stat().st_size} bytes)")

    except Exception as e:
        log(f"Error scanning log for profiler paths: {e}", "WARN")

    return profiler_files


def find_profiler_traces():
    """Find profiler trace files using common patterns.

    Looks for ct-profile*.json.gz files in common locations.

    Returns:
        list: List of Path objects to profiler trace files
    """
    profiler_files = []

    # Check current working directory for ct-profile files
    cwd = Path.cwd()
    for pattern in ["ct-profile*.json.gz", "ct-profile*.json"]:
        files = list(cwd.glob(pattern))
        for f in files:
            profiler_files.append(f)
            log(f"Found profiler trace: {f} ({f.stat().st_size} bytes)")

    return profiler_files


def get_storage_uri(secrets):
    """
    Get cloud storage URI from secrets or environment.

    Returns the URI (e.g., az://container, s3://bucket, gs://bucket) or None.
    """
    storage_uri = secrets.get(CLOUD_STORAGE_URI_KEY) or os.environ.get(CLOUD_STORAGE_URI_KEY)
    if storage_uri:
        return storage_uri.rstrip("/")
    return None


def get_max_file_size_mb(secrets):
    """
    Get maximum file size for uploads from secrets or environment.

    Returns the maximum file size in MB (default: 512 MB).
    """
    max_size_str = secrets.get(MAX_FILE_SIZE_MB_KEY) or os.environ.get(MAX_FILE_SIZE_MB_KEY)
    if max_size_str:
        try:
            return float(max_size_str)
        except ValueError:
            log(
                f"Invalid {MAX_FILE_SIZE_MB_KEY} value: {max_size_str}, using default {DEFAULT_MAX_FILE_SIZE_MB} MB",
                "WARN",
            )
    return DEFAULT_MAX_FILE_SIZE_MB


def should_upload_on_error_only(secrets):
    """
    Check if artifacts should only be uploaded on error (non-zero exit code).

    Returns True if upload should only happen on errors, False otherwise (default).
    """
    value_str = secrets.get(UPLOAD_ON_ERROR_ONLY_KEY) or os.environ.get(UPLOAD_ON_ERROR_ONLY_KEY)
    if value_str:
        # Accept various truthy values
        return value_str.lower() in ("true", "1", "yes", "on")
    return False


def _create_azure_entra_client(secrets):
    """Create an AzureBlobClient using Entra ID (DefaultAzureCredential).

    This enables authentication via service principal (AZURE_TENANT_ID, AZURE_CLIENT_ID,
    AZURE_CLIENT_SECRET), managed identity, Azure CLI, or other methods supported by
    DefaultAzureCredential.

    Returns:
        AzureBlobClient or None if Entra ID auth is not configured or unavailable.
    """
    account_url = secrets.get(AZURE_STORAGE_ACCOUNT_URL_KEY) or os.environ.get(AZURE_STORAGE_ACCOUNT_URL_KEY)
    if not account_url:
        return None

    # Don't use Entra ID if a connection string is already available (it takes precedence)
    if os.environ.get("AZURE_STORAGE_CONNECTION_STRING"):
        log("AZURE_STORAGE_CONNECTION_STRING is set, skipping Entra ID auth")
        return None

    try:
        from azure.identity import DefaultAzureCredential
        from cloudpathlib import AzureBlobClient
    except ImportError as e:
        log(f"azure-identity not installed, cannot use Entra ID auth: {e}", "WARN")
        return None

    try:
        credential = DefaultAzureCredential()
        client = AzureBlobClient(account_url=account_url, credential=credential)
        log(f"Using Entra ID authentication with account URL: {account_url}")
        return client
    except Exception as e:
        log(f"Failed to create Entra ID client: {e}", "ERROR")
        return None


def upload_file_to_cloud(file_path, dest_path, chunk_size_mb=64, large_file_threshold_mb=100):
    """Upload a single file to cloud storage with chunked upload for large files.

    Args:
        file_path: Path object of the file to upload
        dest_path: CloudPath destination for the file
        chunk_size_mb: Chunk size in MB for large file uploads (default: 64MB)
        large_file_threshold_mb: Size threshold in MB to trigger chunked upload (default: 100MB)

    Returns:
        bool: True if upload succeeded, False otherwise
    """
    size_bytes = file_path.stat().st_size
    size_mb = size_bytes / (1024 * 1024)

    # For large files, use chunked upload to avoid memory issues
    if size_mb > large_file_threshold_mb:
        log(f"Uploading large file {file_path.name} ({size_mb:.2f} MB) in chunks...")
        try:
            with file_path.open("rb") as src:
                with dest_path.open("wb") as dst:
                    chunk_size = chunk_size_mb * 1024 * 1024  # Convert to bytes
                    while True:
                        chunk = src.read(chunk_size)
                        if not chunk:
                            break
                        dst.write(chunk)
            return True
        except Exception as e:
            log(f"Failed to upload {file_path.name}: {e}", "ERROR")
            return False
    else:
        # Small files can be uploaded in one go
        try:
            dest_path.write_bytes(file_path.read_bytes())
            log(f"Uploaded {file_path.name} ({size_mb:.2f} MB)")
            return True
        except Exception as e:
            log(f"Failed to upload {file_path.name}: {e}", "ERROR")
            return False


def upload_to_cloud(artifact_path, files, exit_code, storage_uri, max_file_size_mb, azure_client=None):
    """Upload Kit artifacts to cloud storage (Azure, S3, or GCS).

    Args:
        artifact_path: Formatted path within the bucket/container
        files: List of file paths to upload
        exit_code: Kit application exit code
        storage_uri: Cloud storage URI (az://, s3://, or gs://)
        max_file_size_mb: Maximum file size in MB for uploads
        azure_client: Optional pre-configured AzureBlobClient for Entra ID auth

    Returns:
        bool: True if upload succeeded, False otherwise
    """
    try:
        from cloudpathlib import CloudPath
    except ImportError:
        log("cloudpathlib not installed, skipping upload", "WARN")
        return False

    full_path = f"{storage_uri}/{artifact_path}"
    log(f"Uploading to: {full_path}")

    try:
        # Use pre-configured Azure client (Entra ID) if provided, otherwise default credentials
        if azure_client is not None:
            base_path = azure_client.CloudPath(storage_uri)
        else:
            base_path = CloudPath(storage_uri)
        session_path = base_path / artifact_path

        # Collect comprehensive metadata
        metadata = get_nvcf_metadata()
        metadata["exit_code"] = exit_code
        metadata["upload_timestamp"] = datetime.now(timezone.utc).isoformat()
        metadata["max_file_size_mb"] = max_file_size_mb

        # Upload files, skipping those that exceed size limit
        skipped_files = []
        for file_path in files:
            file_size_mb = file_path.stat().st_size / (1024 * 1024)

            if file_size_mb > max_file_size_mb:
                log(
                    f"Skipping {file_path.name} ({file_size_mb:.2f} MB) - exceeds maximum size limit of {max_file_size_mb} MB",
                    "WARN",
                )
                skipped_files.append({"name": file_path.name, "size_mb": round(file_size_mb, 2)})
                continue

            dest = session_path / file_path.name
            upload_file_to_cloud(file_path, dest)

        # Upload metadata
        if skipped_files:
            metadata["skipped_files"] = skipped_files
        metadata_path = session_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        log("Uploaded metadata.json")

        return True

    except Exception as e:
        log(f"Upload failed: {e}", "ERROR")
        return False


def main(exit_code=0):
    """Main artifact collection routine.

    Collects Kit logs, profiler traces, and metadata, then uploads to configured
    cloud storage using a configurable path template.

    Args:
        exit_code: Kit application exit code (passed from entrypoint script)

    Returns:
        int: Always returns 0 to allow container to exit normally
    """
    log("=" * 60)
    log("Kit Artifact Collection Starting")
    log("=" * 60)

    secrets = load_secrets()

    # Check if we should only upload on errors
    if should_upload_on_error_only(secrets):
        if exit_code == 0:
            log("ARTIFACT_UPLOAD_ON_ERROR_ONLY is enabled and exit code is 0 (success)")
            log("Skipping artifact upload")
            return 0
        else:
            log(f"ARTIFACT_UPLOAD_ON_ERROR_ONLY is enabled and exit code is {exit_code} (error)")
            log("Proceeding with artifact upload")

    log_file_path = find_kit_log_file()

    if not log_file_path:
        log("No log file to upload, exiting")
        return 0

    session_id = get_session_id(log_file_path)

    # Check if cloud storage is configured
    storage_uri = get_storage_uri(secrets)
    if not storage_uri:
        log("Cloud storage not configured, skipping upload")
        log(f"Set {CLOUD_STORAGE_URI_KEY} in NVCF secrets (e.g., az://container, s3://bucket, gs://bucket)")
        return 0

    # Get maximum file size for uploads
    max_file_size_mb = get_max_file_size_mb(secrets)

    # Build artifact path using configurable template
    artifact_path = build_artifact_path(session_id, secrets)

    # Try to create an Azure Entra ID client (returns None if not configured or not Azure)
    azure_client = None
    if storage_uri.startswith("az://"):
        azure_client = _create_azure_entra_client(secrets)

    # Collect all files to upload
    files = [log_file_path]

    # Look for profiler traces by scanning the log file
    profiler_files = extract_profiler_paths_from_log(log_file_path)
    files.extend(profiler_files)

    # Also check for common profiler file patterns in CWD
    if not profiler_files:
        log("No profiler traces found in log, checking common patterns...")
        profiler_files = find_profiler_traces()
        files.extend(profiler_files)

    if profiler_files:
        log(f"Found {len(profiler_files)} profiler trace(s) to upload")
    else:
        log("No profiler traces found")

    success = upload_to_cloud(artifact_path, files, exit_code, storage_uri, max_file_size_mb, azure_client=azure_client)

    log("=" * 60)
    if success:
        log("Artifact collection complete")
        log(f"Artifacts uploaded to: {storage_uri}/{artifact_path}")
    else:
        log("Artifact collection failed (non-fatal)")
    log("=" * 60)

    return 0  # Always return success so container exits normally


if __name__ == "__main__":
    exit_code = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    sys.exit(main(exit_code))
