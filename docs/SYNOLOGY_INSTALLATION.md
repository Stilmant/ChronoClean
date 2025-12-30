# Synology Installation (Entware + Python 3.10+)

ChronoClean requires **Python 3.10+**. On many Synology DSM setups, **Package Center** only provides Python up to **3.9**, so the recommended approach is to use **Entware** to install a newer Python (3.10+).

## 1) Check your architecture

On the NAS, run:

```sh
uname -m
```

Example output for ARM64:

```txt
aarch64
```

## 2) Install Entware

Use the installer link that matches your NAS/architecture from the Entware documentation.

- Entware install guide (Synology): https://github.com/Entware/Entware/wiki/Install-on-Synology-NAS
- Example (ARM64 / `aarch64`) used successfully on some DSM systems:

```sh
wget -O - https://bin.entware.net/aarch64-k3.10/installer/generic.sh | sudo sh
```

If you’re unsure, download the script first and inspect it before running it.

## 3) Install Python via Entware

```sh
sudo /opt/bin/opkg update
sudo /opt/bin/opkg install python3 python3-pip
```

Verify versions:

```sh
/opt/bin/python3 --version
/opt/bin/pip3 --version
```

Python 3.11+ is fine for this project (it’s “3.10+”, not “exactly 3.10”).

## 4) (Optional) Install ffprobe for better video metadata

ChronoClean can extract video “taken date” using:
- `ffprobe` (preferred, external binary)
- `hachoir` (pure-Python fallback; optional pip install)

If you want `ffprobe`, install FFmpeg via Entware:

```sh
sudo /opt/bin/opkg install ffmpeg
ffprobe -version
```

If you cannot/won’t install FFmpeg, you can instead install the fallback:

```sh
/opt/bin/python3 -m pip install hachoir
```

## 4bis) (Optional) ExifTool (usually not needed)

ChronoClean reads image EXIF using the Python dependency `exifread` (installed via `pip` with the project), so **ExifTool is not required**.

If you already use ExifTool for other workflows, you can install it via Entware:

```sh
sudo /opt/bin/opkg install exiftool
exiftool -ver
```

## 5) Get the project on the NAS

Pick a location on a volume where you have write access. Example:

```sh
mkdir -p /volume1/tools
cd /volume1/tools
```

If you want to clone from GitHub, you need `git`:

```sh
sudo /opt/bin/opkg install git
git --version
```

Clone and enter the repo:

```sh
git clone https://github.com/Stilmant/ChronoClean.git
cd ChronoClean
```

## 6) Create a virtual environment

Create a venv using the Entware Python:

```sh
/opt/bin/python3 -m venv .venv
. .venv/bin/activate
python --version
python -m pip install --upgrade pip
```

## 7) Install ChronoClean

On a NAS, the simplest (non-dev) install is:

```sh
python -m pip install .
```

**Side note (dev / frequent updates):** if you *do* plan to `git pull` updates and want code changes to be picked up without reinstalling each time, use an editable install instead:

```sh
python -m pip install -e .
```

Development tools (tests, linting) are intentionally omitted from this NAS guide. If you want a dev setup, use the README instructions instead.

Verify the CLI:

```sh
chronoclean --help
```

## 8) First safe test run (recommended)

Create a small workspace (separate from your real photo library) and only test on copies:

```sh
mkdir -p /volume1/chrono_test/incoming /volume1/chrono_test/archive
```

Put a few copied photos/videos in `/volume1/chrono_test/incoming`, then:

```sh
chronoclean apply /volume1/chrono_test/incoming /volume1/chrono_test/archive --dry-run
```

When you’re confident, run with `--no-dry-run` (ChronoClean defaults to copy mode unless `--move` is specified):

```sh
chronoclean apply /volume1/chrono_test/incoming /volume1/chrono_test/archive --no-dry-run
```
