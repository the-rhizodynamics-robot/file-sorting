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

- **Nextflow** (needs Java 11+). **Pin to `24.10.x`** — see the version note below.
- **A Docker engine** that can run `linux/amd64` images.

That's it on the host. Nextflow pulls
`ghcr.io/the-rhizodynamics-robot/file-sorting-env:latest` on first run.

> ⚠️ **Nextflow version — pin to `24.10.x`.** Nextflow **25.x+** makes its strict
> "Nextflow language" parser the default, and that parser rejects the top-level
> statements in `main.nf` (the `Channel.of(...)` channel definition and the
> `workflow.onComplete { … }` hook) with
> `Statements cannot be mixed with script declarations`. The code is still valid
> DSL2 — only the **parser** changed — so the fix is to pin the version, not rewrite
> the pipeline. Prefix any run with `NXF_VER=24.10.0`:
> ```bash
> NXF_VER=24.10.0 nextflow run …
> ```
> Modernizing `main.nf` for the strict parser is on the [Roadmap](#roadmap).

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

### Notes for IT administrators (managed machines)

On a lab-managed or domain-joined Windows machine, some of this needs an administrator and
some is worth setting as policy.

**One-time privileged setup (admin required).**
- **Firmware virtualization.** WSL2 needs hardware virtualization (Intel VT-x / AMD-V)
  enabled in BIOS/UEFI. The toggle is sometimes labeled differently (we hit one labeled
  *VT-d*), and on some boards it only applies after a **full power-off**, not a warm
  reboot. See [Troubleshooting](#troubleshooting-windows--wsl2).
- **Install WSL2 + a pinned Ubuntu LTS** — `wsl --install -d Ubuntu`, or push the distro
  via Intune / SCCM / Group Policy on a fleet. Keep the WSL kernel current with
  `wsl --update`.

**Run as a normal user, not root (least privilege).**
- The pipeline does not need root. Keep the default non-root user and add it to the
  `docker` group (`sudo usermod -aG docker <user>`); that user then runs `nextflow` and
  `docker` without `sudo`. Running everything as root (e.g. `wsl -u root`) is a bad habit
  and also dumps outputs into `/root`, which other users can't read.
- **Caveat worth flagging:** membership in the `docker` group is effectively
  **root-equivalent** on that machine — a member can bind-mount the host filesystem into a
  container and escalate. That's inherent to the classic Docker daemon, not specific to
  this pipeline. If your security posture forbids that, use **rootless Docker** (the daemon
  runs as the unprivileged user — no `docker` group, no root daemon). It's more setup but
  removes the root-equivalent group.
- With the classic (root) daemon, files the container writes are **owned by root** on the
  host even when a normal user launched the run. Add `-u $(id -u):$(id -g)` as a container
  run option if you need outputs owned by the launching user.

**Docker engine: Docker CE, not Docker Desktop.** Docker Desktop requires a paid
subscription for larger organizations (universities included). Docker CE installed inside
WSL is free and works identically with Nextflow — don't install Docker Desktop just for
this.

**Network egress (proxies / firewalls).** A first run reaches out to the internet;
allowlist outbound HTTPS to at least:
- `github.com` (pulls the pipeline) and `ghcr.io` + `*.githubusercontent.com` (pulls the
  container image),
- `get.nextflow.io` plus your `apt` mirror and a JDK source (one-time tool install),
- `huggingface.co` — **only** when *rebuilding* the container; the published image already
  bakes in the models, so normal runs don't need it.

Once the pipeline and container are cached locally, steady-state runs need far less, but
plan for these on the first run.

**Resource limits (optional).** Cap WSL's memory/CPU via `%UserProfile%\.wslconfig` on a
shared machine, e.g.:
```ini
[wsl2]
memory=8GB
processors=4
```

**Filesystem access note.** The `\\wsl.localhost\<distro>` share Windows uses to browse the
Linux filesystem is served by a process running **as root** inside the VM, so Explorer can
see files (e.g. under `/root`) that a normal WSL shell cannot. Prefer writing outputs under
the normal user's home (`/home/<user>/…`) so they're readable both from Explorer and from a
plain user shell.

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

> ✅ **Strongly recommended: run straight from GitHub — do not clone the repo to run
> it.** Point Nextflow at the repo and let it pull `main`. This works identically on
> Linux, macOS, and Windows/WSL2, always runs a known-good revision, and on Windows it
> sidesteps the CRLF line-ending bug that breaks a local Windows clone (explained below).

```bash
NXF_VER=24.10.0 nextflow run the-rhizodynamics-robot/file-sorting -r main -profile local \
  --images_path /mnt/c/Users/you/Desktop/run_7_7 \
  --sort_path   /home/you/sorting_project \
  --boxes_per_shelf 3 \
  --unzip false \
  --archive false
```

That single command pulls the pipeline, pulls the container, and runs it — no clone, no
build. `-r main` pins the revision (use a tag or commit SHA for full reproducibility);
`NXF_VER=24.10.0` pins Nextflow to the legacy parser (see [Requirements](#requirements)).

> **`--sort_path` must be an existing, absolute directory.** It's staged as a Nextflow
> `path()` input, so a relative path is rejected (`Not a valid path value: './…'`).
> Create it first: `mkdir -p /home/you/sorting_project`.

**Why from GitHub and not a local clone?** Nextflow clones the repo on the **Linux** side
(into `~/.nextflow/assets/`), so the `bin/` scripts are checked out with **LF** line
endings. A clone made on the **Windows** filesystem instead gets **CRLF** endings (via
git's `autocrlf`), which turns the container shebang `#!/usr/bin/env python3` into
`python3\r` and fails the run with:

```
/usr/bin/env: 'python3\r': No such file or directory
```

Nextflow's `-resume` flag re-uses cached work if a run is interrupted.

### Running from a local clone (alternative)

If you do clone the repo, run `main.nf` directly:

```bash
NXF_VER=24.10.0 nextflow run main.nf -profile local \
  --images_path /path/to/run_images_or_zip \
  --sort_path   /path/to/project_dir \
  --boxes_per_shelf 3
```

On **Windows**, a local clone needs LF line endings on the `bin/` scripts or it hits the
`python3\r` error above — add a `.gitattributes` forcing `*.py`/`*.sh` to `eol=lf`, or
strip CRs from `bin/` before running. Running from GitHub avoids this entirely.

### Producing videos: the two-phase workflow

Sorting a run does **not** by itself produce a video. The pipeline only renders a video
once an experiment is considered **finished**, and it detects "finished" as *a run that
adds **no new images** to an already-existing experiment* (i.e. the robot has stopped
imaging it). So a brand-new experiment created by its first sorting run has no video yet
— that's expected, not a failure.

To finalize one or more batches and render their videos, run a second pass with
**`--finish_only true`** against the **same `--sort_path`**:

```bash
# 1) Sort a run (creates / grows experiments under current_exp/)
NXF_VER=24.10.0 nextflow run the-rhizodynamics-robot/file-sorting -r main -profile local \
  --images_path /mnt/c/Users/you/Desktop/run_7_7 \
  --sort_path   /home/you/sorting_project \
  --boxes_per_shelf 3 --unzip false --archive false

# 2) Finish: move current_exp/ -> finished_exp/ and render the (stabilized) videos
NXF_VER=24.10.0 nextflow run the-rhizodynamics-robot/file-sorting -r main -profile local \
  --images_path /mnt/c/Users/you/Desktop/run_7_7 \
  --sort_path   /home/you/sorting_project \
  --boxes_per_shelf 3 --finish_only true --unzip false --archive false
```

`--finish_only` skips ingest/sort and just finalizes whatever sits in `current_exp/`,
writing `<exp>.mp4` to both `data/videos/unstabilized/` and (by default)
`data/videos/stabilized/`. In normal operation across many robot runs this happens on
its own — an experiment finishes the first run after imaging stops — and `--finish_only`
is the manual way to force it for a one-off batch.

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

### Generalize image ingestion (don't assume FlyCap filenames)

The sorter currently hard-codes the legacy **FlyCap** naming scheme — it expects files
like `fc2_save_…-0000.png` and parses the frame index from the `-####` suffix
(`sorting_functions.py`). FlyCap is old software; newer capture tools (e.g. FLIR
Spinnaker / SpinView, or any replacement camera software) almost certainly use a
different prefix and numbering format, which would break ingestion.

Make image ingestion **capture-software-agnostic**:
- Don't filter or order by a hard-coded prefix. Discover images by **extension**
  (`.png/.jpg/…`) and derive ordering from a robust source — a configurable filename
  pattern, EXIF/file mtime, or an explicit index — rather than assuming `-####`.
- Allow the expected filename pattern to be supplied (param or the run-config manifest
  above), defaulting to the FlyCap pattern for backward compatibility.
- This pairs naturally with the manifest work: the capture software and its filename
  convention can be recorded at capture time and honored at processing time.

### Fix the image-ordering / frame-numbering bug (round-robin desync)

The sorter has **no per-image record of which box a frame belongs to** — it infers it
purely from *position in a global ordering* and deals frames round-robin into
`boxes_per_shelf × shelves` folders (`sort()` in `sorting_functions.py`). That ordering is
built by parsing **only the trailing `-####`** of the FlyCap filename and sorting by it,
which silently breaks in two common ways:

- **Counter resets / multiple capture sessions.** FlyCap names files
  `fc2_save_<date>-<HHMMSS>-<frame####>`, where `frame####` restarts at 0 each time capture
  is (re)started. The parser ignores the `<HHMMSS>` prefix, so two sessions produce
  **duplicate frame numbers** that interleave when sorted, scrambling the box assignment.
  *(Observed directly: a run spanning a camera restart produced duplicate frame numbers,
  and the labeled experiment folder ended up mixing images from several physical boxes,
  including QR-less ones.)*
- **Dropped or extra frames.** A single missing/duplicated capture shifts everything after
  it by one slot, so every folder downstream becomes a rotating mix of boxes. The camera is
  known to occasionally drop saves, so this is not hypothetical.

Because labeling only needs to find the QR in ~10 random samples of a folder, a scrambled
folder still gets stamped with that experiment and drags the wrong images in.

**Fixes to consider:**
- Order frames by their **full capture identity** (timestamp prefix *and* frame number, or
  file mtime) rather than the trailing counter alone, so session restarts don't collide.
- Detect resets/gaps explicitly and refuse to silently round-robin across them — fail loud,
  or segment per session — instead of mis-sorting.
- Best: give each frame a **real box identity** instead of inferring it positionally (encode
  position in the capture filename/metadata at the robot, or QR-detect per image), removing
  the "one bad frame scrambles everything" fragility entirely.
- Pairs with the run-config manifest and generalized-ingestion items above: a per-run
  manifest can also record frames-per-cycle and capture-session boundaries.

### Modernize `main.nf` for the Nextflow strict parser (run on Nextflow 25+/26)

Runs are currently pinned to `24.10.x` because Nextflow 25.x+ defaults to the strict
"Nextflow language" parser, which rejects `main.nf`'s top-level `Channel.of(...)`
definition and `workflow.onComplete { … }` hook (see the [version note](#requirements)).
The code is valid DSL2 — only the parser changed — so the long-term fix is to bring the
syntax up to what the strict parser accepts (move the channel construction inside
`workflow { }`, and replace/relocate `onComplete` — likely folding the archive step into
the workflow or an `output`/`publishDir` mechanism). Doing this lets the pipeline run on
current Nextflow without the `NXF_VER` pin. Until then, pinning is the supported path.

---

## Citing

This pipeline is part of the Rhizodynamics Robot. If you use it, please cite:

> Rajanala A, Taylor IW, McCaskey E, et al. **The rhizodynamics robot: Automated imaging
> system for studying long-term dynamic root growth.** *PLOS ONE* 18(12): e0295823 (2023).
> https://doi.org/10.1371/journal.pone.0295823

---

## Status

**Validated end-to-end on Windows 10 (WSL2 + Docker CE).** On a Lenovo ThinkCentre test
machine the full path is confirmed working: `wsl --install -d Ubuntu`, Docker CE under
systemd, and a complete pipeline run that pulled the `file-sorting-env` container, sorted
and labeled a real image set, and — via the `--finish_only` pass — produced both
unstabilized and stabilized `.mp4` videos. The run was launched **from GitHub** under
**`NXF_VER=24.10.0`**; both choices are load-bearing (LF line endings and the legacy
parser, respectively, as documented above).
