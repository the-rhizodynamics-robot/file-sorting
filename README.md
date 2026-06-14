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
| Track | [groot-sorting-tracking](https://github.com/isaiahwtaylor/groot-sorting-tracking) | Downstream root-tip tracking. |

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
   If virtualization is disabled in firmware, enable it (VT-x / AMD-V) — on a managed
   machine this is an IT request. After the reboot, Ubuntu finishes first-time setup.

2. **Inside Ubuntu — install Docker CE** and enable systemd so the daemon autostarts:
   ```bash
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker "$USER"
   ```
   Add the following to `/etc/wsl.conf`:
   ```ini
   [boot]
   systemd=true
   ```
   then, from Windows, run `wsl --shutdown` once and reopen Ubuntu.

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

## Citing

This pipeline is part of the Rhizodynamics Robot. If you use it, please cite:

> Rajanala A, Taylor IW, McCaskey E, et al. **The rhizodynamics robot: Automated imaging
> system for studying long-term dynamic root growth.** *PLOS ONE* 18(12): e0295823 (2023).
> https://doi.org/10.1371/journal.pone.0295823

---

## Status

This README is a first pass. The Windows/WSL2 setup is being validated end-to-end on a
test machine; steps may be refined as we confirm them.
