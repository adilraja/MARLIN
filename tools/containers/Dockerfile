# syntax=docker/dockerfile:1
# This Dockerfile is used as the base for containerizing applications rendered out via repo_kit_template.

# This is the base image for the container. It is based on Ubuntu 22.04.
FROM nvcr.io/nvidia/omniverse/ov-base-ubuntu-22:2026.2.3

# root user to bootstrap the container
USER root

# Create local user
RUN useradd --create-home --shell /bin/bash ubuntu || echo "User already exists."

# Create the 'ubuntu' user and add it to the 'sudo' group
RUN usermod -aG sudo ubuntu

# nopasswd sudo
RUN mkdir -p /etc/sudoers.d/
RUN echo "ubuntu ALL=(ALL:ALL) NOPASSWD: ALL" | tee /etc/sudoers.d/ubuntu

# Layer separation for Docker build caching:
# kit kernel and extension cache are copied first as a stable base layer,
# then the remaining app files are copied as a volatile layer.
# This optimizes build, pull and push time since the base rarely changes.
# The '# syntax=docker/dockerfile:1' directive on line 1 ensures BuildKit
# uses a frontend that supports COPY --exclude.
ARG APP_LAYER

WORKDIR /app
# Set StreamSDK extended timeout config file
RUN mkdir -p /home/ubuntu/.config
RUN echo "SenderTimeout=1000000" > /home/ubuntu/.config/regkeys.txt && \
    chown root:root /home/ubuntu/.config/regkeys.txt && \
    chmod 555 /home/ubuntu/.config/regkeys.txt

# Base layer: kit kernel and extension cache (rarely changes)
COPY --chown=root:root --chmod=555 ${APP_LAYER}/kit/ /app/kit/
COPY --chown=root:root --chmod=555 ${APP_LAYER}/extscache/ /app/extscache/

# App layer: everything else (changes frequently)
COPY --chown=root:root --chmod=555 --exclude=kit --exclude=extscache ${APP_LAYER}/ /app/

USER ubuntu
WORKDIR /app

# Create Kit expected caching directories that we'll map a volume onto.
RUN mkdir -p /home/ubuntu/.cache/ov
RUN mkdir -p /home/ubuntu/.local/share/ov
RUN mkdir -p /home/ubuntu/.nvidia-omniverse/config

# Create StreamSDK extended timeout config file
RUN mkdir -p /home/ubuntu/.config
RUN if [ -f stream_sdk.txt ]; then \
        cp stream_sdk.txt /home/ubuntu/.config/regkeys.txt && \
        chown root:root /home/ubuntu/.config/regkeys.txt && \
        chmod 555 /home/ubuntu/.config/regkeys.txt; \
    fi

# Create isolated venv for artifact collection (uses Kit's bundled Python as base)
# Supports Azure Blob Storage, AWS S3, and Google Cloud Storage via cloudpathlib.
# See repo_kit_tools documentation for configuration details.
RUN /app/${kit_subpath}python/bin/python3 -m venv /home/ubuntu/.artifact_collector_venv && \
    /home/ubuntu/.artifact_collector_venv/bin/pip install --quiet "cloudpathlib[azure]" "cloudpathlib[gs]" "cloudpathlib[s3]" "azure-identity"

# Copy extra files from build context (artifact collector scripts)
# These are copied by package_container.py based on extra_files config (default: *.py)
COPY --chown=ubuntu:ubuntu --chmod=555 *.py /app/

# Label for discovering kit_app_template built images within the docker registry.
LABEL kit_app_template=${kit_app}

# Open ports for live streaming
EXPOSE 47995-48012/udp \
       47995-48012/tcp \
       49000-49007/udp \
       49000-49007/tcp \
       8011/tcp \
       8111/tcp \
       49100/tcp

# This specifies the container's default entrypoint that will be called by "> docker run".
# Uncomment to simply launch the Kit app.
# ENTRYPOINT ["/app/${kit_app_whole}.sh"]

# Otherwise use the entrypoint script that supports passing extra arguments to the Kit App via environment variable injection along with some standard Kit args for containerized execution.
ENTRYPOINT ["/app/${entrypoint}"]
