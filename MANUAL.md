# Making videos from robot runs: quick manual

How to turn the robot's image folders into one time-lapse video per box. For the full
details see the [README](README.md).

Everything below is typed into **Ubuntu** (the WSL terminal) on the processing PC.
Paste Windows paths as they are (`C:\Users\...`). Keep the single quotes around them.

---

## 1. Update the tool (once, and after any change)

The installed `image-sort` doesn't update itself. Run this once now, and again whenever
you're told the tool changed:

```bash
curl -fsSL https://raw.githubusercontent.com/the-rhizodynamics-robot/file-sorting/main/image-sort -o ~/.local/bin/image-sort && chmod +x ~/.local/bin/image-sort
```

(First time on a new PC? Do the one-time setup in the README first:
[Running on Windows](README.md#running-on-windows-wsl2--docker-ce).)

---

## 2. Sort your runs

Point it at the folder that holds the robot's run folders:

```bash
image-sort --images 'C:\Users\zhu.lab\Desktop\robotic_imaging'
```

Or just type `image-sort` and choose **1) Sort run(s)** from the menu.

What happens:

1. It lists the runs it found, **oldest first**, and the ones it will skip (already sorted,
   or empty). Check the list and press Enter.
2. It asks two questions:
   - **Make videos for boxes still being imaged in the newest run?** Answer **No** if the
     experiment is still going, so the next run continues those boxes. Answer **Yes** if the
     experiment is over.
   - **Where to put the videos.** Press Enter for the default:
     `Desktop\final_imaging_data`.
3. It sorts each run in turn. Expect about 10–20 minutes per run, plus about an hour for
   each batch of videos.

**Run it again any time.** Runs that are already sorted are skipped, so pointing at the
same folder later only picks up the new runs. Nothing is processed twice.

### When does a box get its video?

When the robot **stops imaging it**: the first run that has no new images of that box.
A box that's still being imaged has no video yet. That's normal, not an error.

### Interrupted experiments

If an experiment was split across several runs (for example a reboot, then a restart), just
sort them all as above. The QR code on each box joins its images from every run into one
video, in time order.

**Don't copy run folders together by hand.** That mixes up the boxes.

---

## 3. Make videos now, without waiting

For specific boxes:

```bash
image-sort --mode finish --exp 17,18,19,20
```

For every box still in progress:

```bash
image-sort --mode finish-all
```

---

## 4. If it stops

It stops on purpose rather than lose data. Fix the problem, then **run the same command
again**. It carries on from where it stopped.

| Message | What to do |
|---|---|
| **junk review** | It couldn't read a box's QR code. Open the `junk_review` folder it shows you. For each folder you want to keep, rename it to the correct box number and move it into `re_merge`. Delete the rest. Then re-run. |
| **in BOTH current_exp/ and finished_exp/** | A box number was used before (an old test, or reused labels). Open the `finished_exp` folder it shows you, and rename or move out the **old** folder with that number. Then re-run. |
| **Sorting ... failed** | Something went wrong in the pipeline. Copy the error above it and send it to Isaiah. |
| **Can't order these runs** | A folder name doesn't start with the robot's date and time (like `20260902080000_1_8`). Rename it, or sort it on its own. |

### Runs sorted before this version

The tool only remembers runs it has sorted since this update. If you sorted a run earlier
**without** `--archive`, tell it so before sorting that folder again, or its images will be
added twice:

```bash
image-sort --mark-sorted --images 'C:\Users\zhu.lab\Desktop\robotic_imaging\20260902080000_1_8'
```

---

## Quick reference

| I want to… | Type |
|---|---|
| Sort everything new | `image-sort --images 'C:\…\robotic_imaging'` |
| …and make videos for every box now | add `--finish-remaining` |
| Make videos for some boxes now | `image-sort --mode finish --exp 17,18` |
| Make videos for all boxes now | `image-sort --mode finish-all` |
| Sort a run again anyway | add `--resort` (adds its images a second time) |
| Use the menu | `image-sort` |

Your videos land in `Desktop\final_imaging_data` (or wherever you chose). The tool also keeps
a copy of everything in its own store, and prints where at the end.
