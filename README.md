# file-sorting

A [Nextflow](https://www.nextflow.io/) pipeline that turns the raw still images
captured by the [GROOT root-imaging robot](https://github.com/the-rhizodynamics-robot/robot-control)
into **sorted, labeled, stabilized time-lapse videos** of root growth.

The pipeline runs entirely inside a published Docker container, so the only things
you install on the host are **Nextflow** and a **Docker engine** — every scientific
dependency (OpenCV, ffmpeg, zbar, the Keras/RetinaNet models, Python 3.7) is baked
into the image.

---

## Quickstart

Process a robot run in a few minutes from a Linux/WSL shell.

**Requirements**
- A Linux shell with a **Docker engine** and **Nextflow** (needs Java 11+). On **Windows**
  that means **WSL2 + Docker CE + Nextflow** — see the one-time
  [setup](#running-on-windows-wsl2--docker-ce).
- That's all you install; the processing container and ML models are pulled automatically on
  the first run. Runs on current Nextflow (tested on 26.04) — no version pin needed.

**1. Install the `image-sort` launcher** (no `sudo`, no clone):

```bash
mkdir -p ~/.local/bin && \
curl -fsSL https://raw.githubusercontent.com/the-rhizodynamics-robot/file-sorting/main/image-sort -o ~/.local/bin/image-sort && \
chmod +x ~/.local/bin/image-sort && \
{ grep -qxF 'export PATH="$HOME/.local/bin:$PATH"' ~/.bashrc || echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc; } && \
export PATH="$HOME/.local/bin:$PATH"
```

This also adds `~/.local/bin` to your `PATH` (in `~/.bashrc`) and activates it in the
current shell, so `image-sort` works immediately — no need to reopen Ubuntu.

**2. Run it:**

```bash
image-sort
```

With no arguments `image-sort` shows a short menu — **1) Sort a run into a project ·
2) Finish specific experiments · 3) Finish all (turn over)** — then asks only what that action
needs. A **project** is a named workspace you feed runs into over time. For a *sort* it asks for
the images folder (paste the Windows `C:\…` path — it converts it for you), the project to add
the run to, boxes-per-shelf (remembered after the first run), and — optionally — a `C:\…` folder
to copy finished videos to. The **number of shelves is read automatically from the run-folder
name** (the robot names runs ending in the shelf count, e.g. `20260613_120000_3`).

Runs accumulate in the project's `current_exp/`; each experiment's **stabilized video is rendered
automatically once a later run adds nothing to it** (the experiment is done), or immediately via
the Finish actions. Processing happens on fast Linux storage under `~/image-sort-runs/<project>/`;
it prints the `\\wsl.localhost\…` path and copies any newly-finished videos to your `--dest`.
Before starting it checks Nextflow, Java, and a running Docker engine, and tells you what's missing.

Prefer flags (scriptable)?

```bash
# sort a run into a project (shelves read from the folder name)
image-sort --mode sort --project barley_2026 \
  --images 'C:\Users\you\Desktop\20260613_120000_3' \
  --boxes-per-shelf 2 --dest 'C:\Users\you\Desktop\barley_videos'

# later: finish specific experiments, or turn the whole project over
image-sort --mode finish     --project barley_2026 --exp 100001,100002 --dest 'C:\Users\you\Desktop\barley_videos'
image-sort --mode finish-all --project barley_2026                     --dest 'C:\Users\you\Desktop\barley_videos'
```

> **First time on this machine?** Do the one-time
> [WSL2 + Docker + Nextflow setup](#running-on-windows-wsl2--docker-ce) first.
> **Prefer to drive Nextflow directly?** See [Usage](#usage).

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

- **Nextflow** (needs Java 11+). Any current version works, including **25.x / 26.x**.
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

**Experimental, untested: macOS.** It *should* work (macOS is Unix), but on **Apple
Silicon — nearly every current Mac** — the `linux/amd64` container runs under emulation and
is **unverified**. See [macOS (Apple Silicon)](#macos-apple-silicon-experimental--untested).

### Setup — Linux / macOS

```bash
# Docker engine (Linux example; on macOS use Docker Desktop or Colima)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"   # log out/in after this

# Nextflow
curl -s https://get.nextflow.io | bash
sudo mv nextflow /usr/local/bin/
```

### macOS (Apple Silicon): experimental / untested

> ⚠️ **Not tested on macOS.** The pipeline *should* run — macOS is Unix, so Nextflow + a
> Docker engine are all it needs, and the `image-sort` launcher already tolerates POSIX
> paths. **But** the published container is **`linux/amd64` only**, and **nearly all current
> Macs are Apple Silicon (M-series)**, where Docker runs amd64 images under **emulation**. We
> have not run it on Apple Silicon and can't promise it works.

**What you can try (at your own risk):**
- Install **Docker Desktop** (turn on *Settings → General → Use Rosetta for x86/amd64
  emulation* for better speed) or **[Colima](https://github.com/abiosoft/colima)**
  (`colima start --arch x86_64`), plus **Nextflow**, **Java**, and **python3** (Homebrew or
  the Xcode command-line tools).
- Run normally, e.g. `nextflow run the-rhizodynamics-robot/file-sorting -r main …`. Expect it
  to be **slower** than native, and note the old TensorFlow 1.x / Python 3.7 stack may not
  emulate cleanly.

**What we actually recommend on a Mac:** run on a **Linux host or cloud VM** (native
`amd64`) rather than your laptop — that's the reliable path until there's a native build (see
[Roadmap](#roadmap)).

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

> **Just want to run it?** The `image-sort` launcher in the [Quickstart](#quickstart) wraps
> everything below — install it and you can skip this section. What follows is how to drive
> Nextflow directly, which is exactly what `image-sort` does under the hood.

### Running Nextflow directly

> ✅ **Strongly recommended: run straight from GitHub — do not clone the repo to run
> it.** Point Nextflow at the repo and let it pull `main`. This works identically on
> Linux, macOS, and Windows/WSL2, always runs a known-good revision, and on Windows it
> sidesteps the CRLF line-ending bug that breaks a local Windows clone (explained below).

```bash
nextflow run the-rhizodynamics-robot/file-sorting -r main -profile local \
  --images_path /mnt/c/Users/you/Desktop/run_7_7 \
  --sort_path   /home/you/sorting_project \
  --boxes_per_shelf 3 \
  --unzip false \
  --archive false
```

That single command pulls the pipeline, pulls the container, and runs it — no clone, no
build. `-r main` pins the revision (use a tag or commit SHA for full reproducibility).

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
nextflow run main.nf -profile local \
  --images_path /path/to/run_images_or_zip \
  --sort_path   /path/to/project_dir \
  --boxes_per_shelf 3
```

On **Windows**, a local clone needs LF line endings on the `bin/` scripts or it hits the
`python3\r` error above — add a `.gitattributes` forcing `*.py`/`*.sh` to `eol=lf`, or
strip CRs from `bin/` before running. Running from GitHub avoids this entirely.

### Finishing experiments and videos

Sorting a run does **not** by itself produce a video. The pipeline renders an experiment's
video only when that experiment is **finished**, defined as *a run that adds **no new images**
to an already-existing experiment* (the robot has stopped imaging it). So a brand-new experiment
has no video after its first run — expected, not a failure. Across many real runs each experiment
finishes (and gets its stabilized video) **on its own**, on the first run that doesn't add to it;
no extra step is needed in normal operation.

To finalize on demand there are two modes (the `image-sort` launcher exposes these as the
**Finish specific** and **Finish all** menu items):

```bash
# Finish ALL experiments currently in current_exp/ (turn the project over)
nextflow run the-rhizodynamics-robot/file-sorting -r main -profile local \
  --images_path /home/you/sorting_project --sort_path /home/you/sorting_project \
  --boxes_per_shelf 2 --finish_only true --unzip false --archive false

# Finish specific experiments by number (comma-separated)
nextflow run the-rhizodynamics-robot/file-sorting -r main -profile local \
  --images_path /home/you/sorting_project --sort_path /home/you/sorting_project \
  --boxes_per_shelf 2 --finish_experiments '100001,100002' --unzip false --archive false
```

Both skip ingest/sort and write `<exp>.mp4` to `data/videos/unstabilized/` and (by default)
`data/videos/stabilized/`. `--images_path` is unused by these modes but the pipeline still
requires a path — point it at any existing directory.

### Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `--images_path` | *(required)* | The run to process — a directory of images **or** a zip. |
| `--sort_path` | *(required)* | Project base directory; all outputs are written here. |
| `--boxes_per_shelf` | `3` | Containers per shelf, used to sort frames into experiments. |
| `--unzip` | `true` | Treat `images_path` as a zip and unzip it first. Set `false` for a plain folder. |
| `--stabilize` | `true` | Stabilize the generated time-lapse videos. |
| `--finish_only` | `false` | Skip ingest/sort; finalize **all** experiments in `current_exp/` and (re)build videos. |
| `--finish_experiments` | `""` | Skip ingest/sort; finalize only the comma-separated experiment numbers (e.g. `100001,100002`). |
| `--archive` | `true` | On success, move the consumed raw run into `data/unsorted_unlabeled_processed/`. |

> ⚠️ **Number of shelves is encoded in the input folder name.** There is no
> `--num_shelves` parameter (yet). The sorter reads the **number after the final
> underscore** of the `images_path` name as the shelf count, e.g.
> `…/20260613_120000_3` → **3 shelves** (the robot names runs `<timestamp>_<shelves>`).
> So the folder name **must end in `_<shelves>`**; a name whose final `_`-segment isn't
> a number is rejected (use `--shelves N` via the `image-sort` launcher to override).
> Multi-digit counts work. See [Roadmap](#roadmap) for the longer-term manifest plan.

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
the number after the final underscore of the input folder name (`<timestamp>_<shelves>`),
which works (including multi-digit counts) but is still implicit — not validated or
self-describing, and dependent on the capture side naming runs correctly.

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
the data (validated, not inferred from a folder name), and the per-experiment variable-shelf
feature is unlocked. This spans both repos: capture writes the manifest (robot-control),
processing consumes it (file-sorting).

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

### Native Apple Silicon (arm64) support — longer-term, lower priority

macOS is currently [untested](#macos-apple-silicon-experimental--untested) because the
container is `linux/amd64` only and most Macs are Apple Silicon, where it runs under
emulation. A native `linux/arm64` image is **not a simple rebuild**: TensorFlow 1.x has no
arm64 Linux wheels, so it would mean modernizing the inference stack (a newer TF or a
different runtime) and re-validating the QR/seed models — a substantial effort. **This is
deliberately low priority:** the immediate goal is a solid, tested **Linux + Windows/WSL2**
experience; native Mac support is a later infra-modernization nice-to-have.

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
systemd, and complete `image-sort` runs that pulled the `file-sorting-env` container, sorted
and labeled a real image set across multiple runs into one project, and produced stabilized
`.mp4` videos via natural finishing, the **Finish specific** mode, and the **Finish all** mode.
Runs are launched **from GitHub** (LF line endings, as documented above). `main.nf` uses the
strict "Nextflow language" syntax and parses on current Nextflow (25.x / 26.x) with no version pin.
