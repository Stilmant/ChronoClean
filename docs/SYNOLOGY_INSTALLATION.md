# Synology Installation (Entware + Python 3.10+)

ChronoClean requires **Python 3.10+**. On many Synology DSM setups, **Package Center** only provides Python up to **3.9**, so the recommended approach is to use **Entware** to install a newer Python (3.10+).

## Why Entware?

Entware acts as an **isolated userland** on Synology:

- Everything installed via Entware lives under `/opt` (binaries, libraries, Python, pip packages).
- It does **not** modify DSM system components or Synology packages.
- For this guide, Entware is the “environment isolation”, so you don’t need (and we don’t use) Python virtual environments.

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

Python 3.11+ is fine for this project (it's "3.10+", not "exactly 3.10").

## 4) (Optional) Install ffprobe for better video metadata

ChronoClean can extract video “taken date” using:
- `ffprobe` (preferred, external binary)
- `hachoir` (pure-Python fallback; optional pip install)

If you want `ffprobe`, install FFmpeg via Entware:

```sh
sudo /opt/bin/opkg install ffmpeg
ffprobe -version
```

If you cannot/won't install FFmpeg, you can instead install the fallback:

```sh
/opt/bin/pip3 install --user hachoir
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

## 6) Install ChronoClean (editable)

Install ChronoClean using Entware’s pip, in editable mode, from the cloned repository:

```sh
/opt/bin/pip3 install --user -e .
```

This is intentionally done **without `sudo`**:
- `--user` installs ChronoClean into your user’s Python site-packages (still using Entware’s Python, not DSM).
- Editable mode (`-e`) means the installed package points to your local working tree.

Verify:

```sh
/opt/bin/python3 -m chronoclean --help
```

If you prefer the `chronoclean` command, ensure your user-level scripts directory is on your `PATH` (typically `~/.local/bin`).

## 7) Updating ChronoClean

Because ChronoClean is installed in editable mode, updating is usually just a pull:

```sh
cd /volume1/tools/ChronoClean
git pull
```

You only need to re-run `pip` when Python dependencies changed (i.e., when `pyproject.toml` changed):

```sh
cd /volume1/tools/ChronoClean
/opt/bin/pip3 install --user -e .
```

## 8) When to update Python dependencies

Do **not** update/reinstall dependencies on every code update. Only do it when `pyproject.toml` changes (new dependency, version bump, etc.).

## 9) Uninstall

Uninstall ChronoClean (installed via `pip --user`):

```sh
/opt/bin/pip3 uninstall chronoclean
```

Optionally remove the local sources:

```sh
rm -rf /volume1/tools/ChronoClean
```

If you no longer want Entware at all: everything Entware installed lives under `/opt`. Removing `/opt` removes Entware entirely (and all Entware packages). This is a destructive action and typically requires `sudo`.

## 10) First safe test run (recommended)

Create a small workspace (separate from your real photo library) and only test on copies:

```sh
mkdir -p /volume1/chrono_test/incoming /volume1/chrono_test/archive
```

Put a few copied photos/videos in `/volume1/chrono_test/incoming`, then:

```sh
/opt/bin/python3 -m chronoclean apply /volume1/chrono_test/incoming /volume1/chrono_test/archive --dry-run
```

When you’re confident, run with `--no-dry-run` (ChronoClean defaults to copy mode unless `--move` is specified):

```sh
/opt/bin/python3 -m chronoclean apply /volume1/chrono_test/incoming /volume1/chrono_test/archive --no-dry-run
```
