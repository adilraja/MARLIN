# Installing and Running MARLIN

This guide describes how to build MARLIN from a fresh clone on Linux.
MARLIN is an NVIDIA Omniverse Kit application, so it requires an NVIDIA RTX
GPU and a working NVIDIA graphics driver. The repository bootstrap downloads
the pinned Kit SDK, extensions, and Python dependencies; do not create a
separate Python or Conda environment for the application.

Windows builds are currently disabled in `repo.toml`. The supported path for
this repository is therefore Linux x86-64. Ubuntu 22.04 or newer is
recommended.

## 1. Check the machine

Confirm that the machine is x86-64 and that its NVIDIA GPU is visible:

```bash
uname -m
nvidia-smi
```

`uname -m` should print `x86_64`. `nvidia-smi` should list an NVIDIA RTX GPU
and its installed driver. MARLIN's current Kit branch requires at least NVIDIA
driver `550.54.15` on Linux; a current production driver supported by the GPU
is recommended.

If `nvidia-smi` is missing on Ubuntu, install the driver recommended by
Ubuntu, reboot, and check again:

```bash
sudo apt-get update
sudo apt-get install -y ubuntu-drivers-common
sudo ubuntu-drivers install
sudo reboot
```

After rebooting:

```bash
nvidia-smi
```

For alternative installation methods, use NVIDIA's official
[Ubuntu driver installation guide](https://docs.nvidia.com/datacenter/tesla/driver-installation-guide/latest/ubuntu.html).

## 2. Install host tools

Install Git, the Linux compiler toolchain, cURL, and Vulkan utilities:

```bash
sudo apt-get update
sudo apt-get install -y \
  build-essential \
  ca-certificates \
  curl \
  git \
  libvulkan1 \
  vulkan-tools
```

Confirm that Vulkan can see the NVIDIA GPU:

```bash
vulkaninfo --summary
```

CUDA Toolkit, Docker, a system Python installation, and Omniverse Launcher
are not required for a normal local MARLIN build.

## 3. Clone MARLIN

```bash
git clone https://github.com/adilraja/MARLIN.git
cd MARLIN
```

The first build downloads several large Kit packages. Ensure the machine has
a stable internet connection and sufficient free disk space:

```bash
df -h .
```

## 4. Bootstrap and build

```bash
chmod +x repo.sh
./repo.sh build
```

`repo.sh` bootstraps Packman and its own Python runtime, downloads the pinned
Kit SDK and extensions, and creates the release build. On first use, read and
accept the NVIDIA Omniverse licensing prompt to continue.

A successful build ends with a message similar to:

```text
BUILD (RELEASE) SUCCEEDED
```

The generated application will be under:

```text
_build/linux-x86_64/release/
```

Do not edit files in `_build`; make source changes under `source/` and rebuild.

## 5. Launch MARLIN

From the repository root:

```bash
cd _build/linux-x86_64/release
./cris.madil.kit.sh --enable cris.madil.render_service
```

Run MARLIN as the logged-in desktop user, not with `sudo`. The first RTX
launch may spend several minutes compiling shaders; later launches are much
faster.

Keep this terminal open while MARLIN is running. Stop the application with
`Ctrl+C` after closing its window.

## 6. Verify the HTTP service

Open a second terminal. The interactive API documentation should be available
at [http://localhost:8011/docs](http://localhost:8011/docs).

Check the OpenAPI document from the command line:

```bash
curl http://localhost:8011/openapi.json
```

Create the default marine scene:

```bash
curl -X POST http://localhost:8011/scene/marine/setup \
  -H "Content-Type: application/json" \
  -d '{}'
```

The default setup creates MARLIN's 16,000-unit animated ocean, physical water
material, environment, underwater cue, animated dolphin, and camera.

To display and animate every converted marine mammal instead:

```bash
curl -X POST http://localhost:8011/scene/cetaceans/gallery \
  -H "Content-Type: application/json" \
  -d '{}'

curl -X POST http://localhost:8011/scene/cetaceans/gallery/swim/start \
  -H "Content-Type: application/json" \
  -d '{"deformation_fps":12,"travel_half_extent":6500}'
```

Check that both controllers are running:

```bash
curl http://localhost:8011/scene/ocean/animation/status
curl http://localhost:8011/scene/cetaceans/gallery/swim/status
```

## 7. Rebuild after pulling updates

```bash
cd /path/to/MARLIN
git pull
./repo.sh build
```

Then launch the release application again using the command from step 5.

## Troubleshooting

### Black viewport or renderer does not initialize

Check the driver and Vulkan runtime first:

```bash
nvidia-smi
vulkaninfo --summary
```

Make sure MARLIN is running in a graphical desktop session on the NVIDIA GPU.
Do not launch it through `sudo` or on a compute-only driver installation that
omits Vulkan/OpenGL components.

### Port 8011 is already in use

```bash
ss -ltnp | grep 8011
```

Stop the older MARLIN process before launching another copy.

### Stale local application state

Close MARLIN, then launch once with its local cache and settings reset:

```bash
cd _build/linux-x86_64/release
./cris.madil.kit.sh \
  --enable cris.madil.render_service \
  --clear-cache \
  --clear-data \
  --reset-user
```

Do not manually delete `_build` or global Omniverse caches as a first
troubleshooting step.

## Optional: reconvert source cetacean assets

The converted USD files needed to run MARLIN are already committed. Blender
is needed only by contributors changing the source glTF assets. The current
conversion workflow is validated with the official Blender 5.0.1 Linux build.

Example conversion:

```bash
/path/to/blender-5.0.1-linux-x64/blender \
  --background \
  --factory-startup \
  --python tools/gltf_to_usd.py \
  -- \
  --input assets/cetaceans/<species>/source/scene.gltf \
  --output assets/cetaceans/<species>/usd/<species>.usd
```

Do not use `omni.kit.asset_converter` for these assets; MARLIN's documented
conversion path is Blender to USD.
