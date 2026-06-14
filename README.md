# file-sorting

A [Nextflow](https://www.nextflow.io/) pipeline that turns the raw still images
captured by the [GROOT root-imaging robot](https://github.com/the-rhizodynamics-robot/robot-control)
into **sorted, labeled, stabilized time-lapse videos** of root growth.

The pipeline runs entirely inside a published Docker container, so the only things
you install on the host are **Nextflow** and a **Docker engine** — every scientific
dependency (OpenCV, ffmpeg, zbar, the Keras/RetinaNet models, Python 3.7) is baked
into the image.

---

## Where this fits

The GROOT system is three repositories:

| Stage | Repo | Role |
|-------|------|------|
| Capture | [robot-control](https://github.com/the-rhizodynamics-robot/robot-control) | Drives the robot and saves raw images. |
| **Process** | **file-sorting** *(this repo)* | Sorts images into experiments, labels them, builds stabilized videos. |
| Track | [root-tracking](https://github.com/the-rhizodynamics-robot/root-tracking) | Downstream root-tip tracking. |

---

## What the pipeline does

Given a folder (or zip) of raw images from one robot run, the pipeline:

1. **Unzips / ingests** the run into a working area (`--unzip`).
2. **Sorts** images into per-container experiments, using the box position in each frame.
3. **Labels** each container by reading its QR code and detecting seeds, via two
   bundled inference models (`qrInference.h5`, `SeedInference.h5`).
4. **Routes** anything ambiguous to a `junk_review` area for a human to resolve, and
   re-merges reviewed items on the next run.
5. **Builds time-lapse videos** for each finished experiment and, by default,
   **stabilizes** them (`--stabilize`) so the root — not camera jitter — is what moves.
6. **Archives** the consumed raw run into the project's processed area (`--archive`).

Outputs land under your `--sort_path` in a fixed directory layout (see
[Output layout](#output-layout)).

---

## Requirements

- **Nextflow** (needs Java 11+).
- **A Docker engine** that can run `linux/amd64` images.

That's it on the host. Nextflow pulls
`ghcr.io/the-rhizodynamics-robot/file-sorting-env:latest` on first run.

> **Note on platforms.** Nextflow is a POSIX/Linux tool — it does **not** run on
> native Windows (PowerShell/CMD/Git Bash). On Windows it runs inside **WSL2**, which
> is also what Docker needs in order to run Linux containers. See
> [Running on Windows](#running-on-windows-wsl2--docker-ce).

---

## Where to run it

**Recommended: a Linux host or cloud VM.** No caveats — install Nextflow + a Docker
engine and go. This is also how the pipeline scales later (the same `main.nf` can target
an HPC scheduler or cloud batch by changing only the executor).

**Also supported: a Windows machine, via WSL2.** Fully workable and documented below;
it just requires the one-time WSL2 + Docker setup.

### Setup — Linux / macOS

```bash
# Docker engine (Linux example; on macOS use Docker Desktop or Colima)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"   # log out/in after this

# Nextflow
curl -s https://get.nextflow.io | bash
sudo mv nextflow /usr/local/bin/
```

### Running on Windows (WSL2 + Docker CE)

Windows hosts the robot's capture PC, so this path matters. We use **WSL2** for the
Linux environment and **Docker CE inside WSL** — *not* Docker Desktop, which carries a
paid-license requirement for larger organizations (every university qualifies). Docker
CE is free and talks to Nextflow identically.

1. **Install WSL2 + Ubuntu** (Windows PowerShell, as Administrator — needs a reboot):
   ```powershell
   wsl --install -d Ubuntu
   ```
   WSL2 requires hardware virtualization to be **enabled in firmware** (BIOS/UEFI). If
   `wsl --install` fails with `HCS_E_HYPERV_NOT_INSTALLED` / "virtualization is not
   enabled," see [Troubleshooting](#troubleshooting-windows--wsl2) — on the test
   machine this required a BIOS toggle **and a full power-off**. On a managed machine
   the BIOS change is typically an IT request.

2. **Inside Ubuntu — install Docker CE** and enable systemd so the daemon autostarts:
   ```bash
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker "$USER"
   ```
   Recent Ubuntu WSL images already run **systemd**, so the Docker daemon is enabled
   and started automatically. If `systemctl is-active docker` doesn't return `active`,
   ensure `/etc/wsl.conf` contains:
   ```ini
   [boot]
   systemd=true
   ```
   then run `wsl --shutdown` from Windows once and reopen Ubuntu.

3. **Inside Ubuntu — install Java + Nextflow:**
   ```bash
   sudo apt update && sudo apt install -y openjdk-17-jre
   curl -s https://get.nextflow.io | bash
   sudo mv nextflow /usr/local/bin/
   ```

4. **Run from inside Ubuntu**, referencing files on the Windows drive via `/mnt/c/...`
   (for large batches, copying images onto the WSL filesystem first is noticeably faster).

> **Keep the host alive during a run.** As with the capture PC, the machine running the
> pipeline should not sleep or auto-reboot mid-run. See robot-control's README for the
> sleep / Windows-Update settings.

### Troubleshooting (Windows / WSL2)

- **`wsl --install` fails with `HCS_E_HYPERV_NOT_INSTALLED` / "virtualization is not
  enabled on this machine."** Virtualization is off in firmware. Reboot into BIOS/UEFI
  and enable it. On the Lenovo ThinkCentre test machine the relevant option was labeled
  **Intel VT-d** (under *Security → Virtualization*); enable that **and** *Intel
  Virtualization Technology* if both are present.
- **It still reads disabled after enabling it in BIOS.** A warm restart may not apply the
  change — do a **full power-off** (shut down completely, then power back on), not just a
  restart. On the test machine, only a cold boot made it take effect. Disabling Windows
  "Fast Startup" first makes the shutdown a true cold boot.
- **`Get-WindowsOptionalFeature` / `VirtualizationFirmwareEnabled` says `False` even when
  it's working.** That WMI field is unreliable once a hypervisor is running. Trust the
  functional test instead: `wsl --install -d Ubuntu` succeeding, and `docker run
  hello-world` working inside the distro.
- **The Windows hypervisor can start a bit late after boot.** Immediately after a cold
  boot, a WSL VM launch may briefly fail before the hypervisor is up; retrying after a
  short wait (no reboot needed) succeeds.

---

## Usage

```bash
nextflow run main.nf -profile local \
  --images_path /path/to/run_images_or_zip \
  --sort_path   /path/to/project_dir \
  --boxes_per_shelf 3
```

Windows / WSL2 example:

```bash
nextflow run main.nf -profile local \
  --images_path /mnt/c/Users/you/Desktop/run_7_7 \
  --sort_path   /mnt/c/Users/you/Desktop/sorting_project \
  --boxes_per_shelf 3 \
  --unzip false \
  --archive false
```

Nextflow's `-resume` flag re-uses cached work if a run is interrupted.

### Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `--images_path` | *(required)* | The run to process — a directory of images **or** a zip. |
| `--sort_path` | *(required)* | Project base directory; all outputs are written here. |
| `--boxes_per_shelf` | `3` | Containers per shelf, used to sort frames into experiments. |
| `--unzip` | `true` | Treat `images_path` as a zip and unzip it first. Set `false` for a plain folder. |
| `--stabilize` | `true` | Stabilize the generated time-lapse videos. |
| `--finish_only` | `false` | Skip ingest/sort; only finalize existing experiments and (re)build videos. |
| `--archive` | `true` | On success, move the consumed raw run into `data/unsorted_unlabeled_processed/`. |

> ⚠️ **Number of shelves is currently encoded in the input folder name.** There is no
> `--num_shelves` parameter (yet). The sorter reads the **last character** of the
> `images_path` name as the shelf count, e.g. `…/20260613_test2` → **2 shelves**. This
> means the folder name **must end in the shelf-count digit**, and the scheme only works
> for **1–9 shelves** — a name ending in a non-digit crashes, and ≥10 shelves
> mis-parses (ends in `0` → divide-by-zero; `11`/`12`/… → reads only the last digit).
> See [Roadmap](#roadmap) for the planned fix.

---

## Output layout

All paths are relative to `--sort_path`:

```
data/
  unsorted_unlabeled_processed/   # raw runs after processing (the archive target)
  master_data/
    unsorted_unlabeled/
    sorted_unlabeled/
    current_exp/                  # experiments in progress
    finished_exp/                 # completed experiments
    junk_exp/
    junk_review/                  # ambiguous items awaiting human review
  videos/
    unstabilized/
    stabilized/                   # final stabilized time-lapse videos
```

The directory tree is created automatically on first run.

---

## How it works

- **`main.nf`** declares a single `file_sorting` process that runs
  `robot_image_sorting.py` (in `bin/`) inside the container, plus an `onComplete` hook
  that performs the optional archive move.
- **`bin/robot_image_sorting.py`** is the entry point; the sorting/labeling/video logic
  lives in `bin/src/sorting_functions.py`.
- **The container** is defined in `docker_files/` and published to GHCR by the
  `.github/workflows/docker-publish.yml` workflow on pushes that touch `docker_files/`.
  The base image (`Dockerfile.baseimage`) carries the system + Python dependencies; the
  run image (`Dockerfile_file_sorting`) layers in the QR and seed models from
  Hugging Face.

### Rebuilding the container

Only needed if you change the dependencies or models — for normal runs the published
image is pulled automatically. Edit the files in `docker_files/` and push to `main`; CI
builds and pushes a new `:latest` (and a SHA-tagged) image to GHCR.

---

## Roadmap

### Run-config manifest (replace the folder-name shelf encoding)

**Motivation.** The number of shelves is a *per-experiment* choice — an operator with
only a few samples may image a single shelf and skip the empty ones — so it can't be
inferred from the rig or reconstructed from memory weeks later. Today it survives only as
the last character of the input folder name, which is fragile (see the warning above) and
breaks for ≥10 shelves.

**Plan.** Persist the run configuration *at capture time* and have this pipeline read it:

1. **Capture writes a manifest.** The robot-control host (`robot_host`) already prompts
   for `num_shelves`, `boxes_per_shelf`, etc. at the handshake, so it knows them at run
   start. It writes a **visible** `run_config.json` (or `.toml`, to match the host's
   existing `config.toml`) into the image directory. Visible — not hidden — so it survives
   the external zip → transfer → unzip step (many tools silently drop dotfiles).
2. **Pipeline gains optional params.** Add `--num_shelves` (and optionally
   `--photos_per_shelf`) to `main.nf`, defaulting to null.
3. **Resolution + precedence**, resolved and logged once in `main.nf`:
   `explicit param  >  run_config manifest in the run dir  >  fail fast`
   (a clear error if neither is supplied — never a silent mis-sort).
4. **Harden the sorter.** Make the image listing filter to known image extensions
   (`.png/.jpg/…`) instead of "every file in the directory," so the manifest (and any
   stray file) can sit alongside the images without breaking the FlyCap filename parser.

**Result.** Each run becomes self-describing and reproducible; shelf count is carried by
the data, the ≥10-shelf bug disappears, and the per-experiment variable-shelf feature is
unlocked. This spans both repos: capture writes the manifest (robot-control), processing
consumes it (file-sorting).

---

## Citing

This pipeline is part of the Rhizodynamics Robot. If you use it, please cite:

> Rajanala A, Taylor IW, McCaskey E, et al. **The rhizodynamics robot: Automated imaging
> system for studying long-term dynamic root growth.** *PLOS ONE* 18(12): e0295823 (2023).
> https://doi.org/10.1371/journal.pone.0295823

---

## Status

First pass. The WSL2 + Docker CE + Nextflow setup has been validated on a Windows 10
test machine (Lenovo ThinkCentre): `wsl --install -d Ubuntu`, Docker CE under systemd,
and `docker run hello-world` all confirmed working. Still to validate end-to-end: a full
pipeline run against a real image set (pulling the `file-sorting-env` container and
producing stabilized videos).
