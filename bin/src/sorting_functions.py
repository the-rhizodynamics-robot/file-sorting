"""
    Module that defines functions used to sort, label, and manipulate images
    taken by root robot.

"""

import os
from os import listdir
from os.path import isfile, join
import numpy as np
import subprocess
import cv2
from pyzbar.pyzbar import decode, ZBarSymbol
import shutil
from pathlib import Path
import zipfile
import random
import tensorflow as tf
import keras
from keras_retinanet import models
from keras_retinanet.utils.image import preprocess_image, resize_image 
import time
from PIL import Image
from src import qr_stabilize


# Image file extensions the pipeline ingests. Used to (a) discover images
# regardless of capture software and (b) skip non-image files (manifests,
# .DS_Store, thumbnails) that would otherwise crash the frame-index parser.
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}

# The capture manifest robot-control writes into every run folder: imaging geometry, cycle interval,
# camera settings and (in time) the rig's px_per_mm. Downstream analysis needs those numbers, and
# today an operator has to supply them by hand, so each finished experiment gets a copy.
#
# It is held in memory between capture and write rather than carried along the pipeline: label()
# parses filenames as int(name[0:8]), so a manifest sitting in a box folder mid-run would crash it.
RUN_CONFIG_NAME = "run_config.json"
_RUN_MANIFEST = None   # the run's manifest as bytes, or None when the run has none


def _image_files(path):
    """List image files in `path` (by extension), non-hidden, sorted."""
    return [f for f in sorted(os.listdir(path))
            if not f.startswith(".")
            and isfile(join(path, f))
            and os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS]


def _dominant_ext(folder):
    """The most common image extension in `folder` (defaults to .png).

    Used to pick the ffmpeg glob so a folder of .jpg frames builds a video
    the same way a legacy folder of .png frames does. A single experiment is
    one continuous imaging campaign with one camera, so it is normally uniform.
    """
    counts = {}
    for f in listdir_nohidden(folder):
        e = os.path.splitext(f)[1].lower()
        if e in IMAGE_EXTENSIONS:
            counts[e] = counts.get(e, 0) + 1
    if not counts:
        return ".png"
    return max(counts, key=counts.get)


def capture_run_manifest(run_dir):
    """Remember this run's run_config.json, from the ingested copy or the staging folder.

    Returns True when a manifest was found. A run without one is normal (captures before
    2026-09-14 have none) and is not an error -- downstream is simply told nothing.
    """
    global _RUN_MANIFEST
    candidates = [os.path.join(run_dir, RUN_CONFIG_NAME)]
    staging = globals().get("STAGING_PATH")
    if staging:
        candidates.append(os.path.join(staging, RUN_CONFIG_NAME))
    for candidate in candidates:
        if isfile(candidate):
            with open(candidate, "rb") as f:
                _RUN_MANIFEST = f.read()
            print("Captured " + RUN_CONFIG_NAME + " from " + candidate)
            return True
    _RUN_MANIFEST = None
    print("No " + RUN_CONFIG_NAME + " in this run; downstream analysis will need the run's settings by hand")
    return False


def write_run_manifest(dest_dir):
    """Write the captured manifest into a finished experiment, so the run's own settings travel with it."""
    if not _RUN_MANIFEST:
        return False
    with open(os.path.join(dest_dir, RUN_CONFIG_NAME), "wb") as f:
        f.write(_RUN_MANIFEST)
    return True


def init(boxes_per_shelf, sort_path, staging_path, model_path):
    """ Declare constants for save paths"""

    global ARCHIVE_PATH
    global STAGING_PATH
    global UNSORTED_UNLABELED_PATH
    global SORTED_UNLABELED_PATH
    global CURRENT_EXP_PATH
    global FINISHED_EXP_PATH
    global JUNK_EXP_PATH
    global JUNK_REVIEW_PATH
    global FINAL_VIDEO_PATH
    global QR_MODEL_PATH
    global QR_MODEL
    global BOXES_PER_SHELF
    global STABILIZED_VIDEO_PATH
    global _RUN_MANIFEST

    SORT_PATH = os.path.abspath(sort_path)
    DATA_PATH = os.path.join(SORT_PATH, "data", "")
    STAGING_PATH = os.path.join(staging_path, "")
    ARCHIVE_PATH = os.path.join(DATA_PATH, "unsorted_unlabeled_processed", "")
    UNSORTED_UNLABELED_PATH = os.path.join(DATA_PATH, "master_data", "unsorted_unlabeled", "")
    SORTED_UNLABELED_PATH = os.path.join(DATA_PATH, "master_data", "sorted_unlabeled", "")
    CURRENT_EXP_PATH = os.path.join(DATA_PATH, "master_data", "current_exp", "")
    FINISHED_EXP_PATH = os.path.join(DATA_PATH, "master_data", "finished_exp", "")
    JUNK_EXP_PATH = os.path.join(DATA_PATH, "master_data", "junk_exp", "")
    JUNK_REVIEW_PATH = os.path.join(DATA_PATH, "master_data", "junk_review", "")
    FINAL_VIDEO_PATH = os.path.join(DATA_PATH, "videos", "unstabilized", "")
    STABILIZED_VIDEO_PATH = os.path.join(DATA_PATH, "videos", "stabilized", "")
    BOXES_PER_SHELF = int(boxes_per_shelf)
    _RUN_MANIFEST = None # a fresh run: forget anything captured by an earlier call
    

    # load all retinanet models
    keras.backend.tensorflow_backend.set_session(get_session())
    QR_MODEL_PATH = os.path.join(model_path, "qrInference.h5")
    QR_MODEL = models.load_model(QR_MODEL_PATH, backbone_name='resnet50')


def sort(base_path, shelves):
    
    # number of boxes in this experiment.
    num_boxes = BOXES_PER_SHELF * int(shelves)

    # where unsorted, unlabelled images are located
    mypathin = UNSORTED_UNLABELED_PATH + base_path
   
    # mypathout is the directory where the sorted but unlabelled images will go
    mypathout = SORTED_UNLABELED_PATH + base_path

    # create onlyfiles w column list with file name in first column and parsed image # as second column
    # list the image files only (skip manifests/hidden/non-image files)
    onlyfiles = _image_files(mypathin)

    # Both capture tools put the frame index as the LAST '-'-separated segment
    # before the extension, so one parse covers both:
    #   FlyCap    fc2_save_<date>-<HHMMSS>-<frame####>.png  -> frame####
    #   Spinnaker <name>-<timestamp>-<frame#>.jpg           -> frame#
    filenum = [int(c.rsplit('-',1)[1].rsplit('.',1)[0]) for c in onlyfiles]

    # final list
    files=list(zip(onlyfiles,filenum))
    files=sorted(files,key=lambda l:l[1], reverse=False)
    os.chdir("/home")

    # this will make the out directory
    if not os.path.isdir(mypathout):
        os.mkdir(mypathout)
        
    timestamps = []
    current_dir = Path(mypathin)
    for element in current_dir.iterdir():
        if element.is_file() and element.suffix.lower() in IMAGE_EXTENSIONS:
            timestamps.append(element.stat().st_mtime)
    timestamps.sort()
    # this will make a number of directories in the out directory equal to the number of boxes, names 1\, 2\, 3\, etc
    for x in range(num_boxes):
        os.makedirs(mypathout+"/"+str(x+1), exist_ok=True)
    os.chdir("/home")

    # this double loop will loop over the sequence 1:len(onlyfiles),
    # while also saving each file to the appropriate folder in the
    # out directory
    count = 0

    # Changed to move instead of copy files when sorting
    for z in range(1,int(len(files)/num_boxes)*num_boxes,num_boxes):
        count = count +1
        for y in range(num_boxes):
            # keep the source extension (.jpg stays .jpg, .png stays .png)
            ext = os.path.splitext(files[z+y-1][0])[1].lower()
            savefile=mypathout + "/" + str(y+1) + "/" + str(100000000 + count)[-8:] + "_" + str(timestamps[z+y-1]) + ext
            filename = mypathin + "/" + files[z+y-1][0]
            shutil.move(filename, savefile)
    os.chdir("/home")


def _file_into_exp(d, exp_name):
    """Move position folder `d`'s frames into current_exp/<exp_name>, appending after any frames already there."""
    temp_path = CURRENT_EXP_PATH + "/" + str(exp_name)
    if not os.path.isdir(temp_path):
        os.chdir("/home")
        shutil.move(d, temp_path)
    else:
        os.chdir(d)
        base = len(listdir_nohidden(temp_path))
        for g in listdir_nohidden("."):
            file_counter = int(g[0:8])
            stamps = g.split("_")[1]
            savefile = temp_path + "/" + str(100000000 + file_counter + base)[-8:] + "_" + stamps
            shutil.move(g, savefile)


def label(base_path, known = None):
    """ Label each position folder by its QR and move it into current_exp (or junk).

        `known` is check_positions()'s result: {position folder: label, or EMPTY_SLOT}. Those
        positions are filed from it without reading the QR again; any other position is read
        here, from up to 10 random frames. """
    known = known or {}
    current_exp_path = CURRENT_EXP_PATH
    mypathout = SORTED_UNLABELED_PATH + base_path
    junk_exp_path=JUNK_EXP_PATH
    junk_review_path = JUNK_REVIEW_PATH
    finished_exp_path = FINISHED_EXP_PATH
    mypathin = UNSORTED_UNLABELED_PATH + base_path
        
    # Make directories if they don't already exist
    os.makedirs(current_exp_path, exist_ok=True)
    os.makedirs(junk_exp_path, exist_ok=True)
    os.makedirs(finished_exp_path, exist_ok=True)


    # This is intended to loop over all folders in sorted, unlabelled directory.
    # It will scan for QR codes until 3 codes are found, then take the modal code and move the images into the current
    # sorted-labelled directory.
    dirlist = [x[0] for x in os.walk(mypathout)]
    #print(dirlist)

    # starting at index 1 skips the parent directory, which os.walk includes.  
    for d in dirlist[1:]:
        found = known.get(os.path.normpath(d))
        if found == EMPTY_SLOT:
            print("Position number = " + str(os.path.basename(d)) + ": empty slot (no QR in the frame-order check). Moving to Junk Exp.")
            os.chdir("/home")
            shutil.move(d, junk_exp_path + "/" + os.path.splitext(os.path.basename(d))[0] + "_" + os.path.basename(mypathin) + "_0")
            continue
        if found is not None:
            print("Position number = " + str(os.path.basename(d)))
            print("Box number = " + str(found) + " (from the frame-order check)")
            _file_into_exp(d, found)
            os.chdir("/home")
            continue

        # change to each subdirectory of sorted, unlabelled data
        os.chdir(d)
        im_list = random.choices(listdir_nohidden(d), k=10)
        crop_sum=0

        for img in im_list:
            box = qr_detection(d + "/" + img)
            image_name = img
            if len(box) > 0:
                break
        
        if len(box) > 0:
            
            img = cv2.imread(d + "/" + image_name, 0)
            box = box.astype(float)
            box = box.astype(int)
            barcode = _decode_qr(img, box)
                
            crop_sum = crop_sum + np.sum(img[box[1]:box[3],box[0]:box[2]])
            if len(barcode)>0:
                # QR payload is the experiment/container label. Keep it as a
                # string so both numeric (legacy, e.g. 100001) and alphanumeric
                # (e.g. B4) codes work; sanitize path separators for a safe
                # folder name. A numeric code yields the same folder it always did.
                exp_name = barcode[0][0].decode('utf-8', 'ignore').strip()
                exp_name = exp_name.replace('/', '_').replace('\\', '_')
                print("Position number = " + str(os.path.basename(d)))
                print("Box number = " + str(exp_name))
                _file_into_exp(d, exp_name)
            else:
                print("QR code exists but barcode could not be read! See Junk Review.")
                os.chdir("/home")
                shutil.move(d, junk_review_path + "/" + os.path.splitext(os.path.basename(d))[0] + "_" + os.path.basename(mypathin) + "_" + str(crop_sum))
        else:
            print("QR not found, box may be placeholder or missing. Moving to Junk Exp.")
            os.chdir("/home")
            shutil.move(d, junk_exp_path + "/" + os.path.splitext(os.path.basename(d))[0] + "_" + os.path.basename(mypathin) + "_" + str(crop_sum))
        os.chdir("/home")

    shutil.rmtree(mypathin)
    
    # cleanup sorted_unlabelled
    try:
        shutil.rmtree(mypathout)
    except OSError as e:
        print("unable to remove sorted_unlabeled direcctory.")
        print(e)
    except Exception as e:
        print(e)
        
def _decode_qr(img, box):
    """zbar results for the QR in `box` of grayscale `img`, trying several preprocessings."""
    blur = cv2.GaussianBlur(img[box[1]:box[3], box[0]:box[2]], (3, 3), 0)
    thr = [img, blur,
           cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 69, 2),
           cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 69, 2),
           cv2.threshold(blur, 0, 255, cv2.THRESH_OTSU)[1],
           cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 89, 2),
           cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 31, 11),
           cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 55, 11)]
    for counter, t in enumerate(thr):
        barcode = decode(t, symbols=[ZBarSymbol.QRCODE])
        if len(barcode) > 0:
            print("threshold technique: " + str(counter))
            return barcode
    return []


def read_qr(image_path):
    """The QR label in one frame, as label() would name it, or None if none can be read."""
    return _read_qr(image_path)[1]


def _read_qr(image_path):
    """(whether a QR was detected at all, its label or None if none could be read)."""
    box = qr_detection(image_path)
    if len(box) == 0:
        return False, None
    barcode = _decode_qr(cv2.imread(image_path, 0), np.asarray(box).astype(float).astype(int))
    if not barcode:
        return True, None
    return True, barcode[0][0].decode('utf-8', 'ignore').strip().replace('/', '_').replace('\\', '_')


# check_positions() result for a position with no QR detected in any sample: no box there.
EMPTY_SLOT = "<empty slot>"
EMPTY_AFTER = 3   # this many leading samples with no QR detected = an empty slot (the detector is the slow part)


class FrameOrderError(RuntimeError):
    """A position folder holds different boxes at different points in the run."""


def check_positions(base_path, samples = 8):
    """ Verify, before anything is labeled or moved, that each position folder holds ONE box.

        sort() deals frames to positions purely by order, so a frame dropped or added
        mid-run puts box A's frames and then box B's into the same folder, and label()
        (one QR read per folder) would silently name it all after one of them. This reads
        the QR in `samples` frames spread across each folder, first and last included
        (~8 reads x positions per run). If the readable labels agree, the run goes on.
        If only the very first frame disagrees -- a stray trigger before the first sweep
        (seen on the A&M rig) -- that frame is set aside in junk_exp with a warning; a
        leading shift like that leaves every other frame correctly grouped. Any other
        disagreement is bisected to the frame where the label changes and raised as
        FrameOrderError: nothing has been labeled or moved yet, and the source run is
        untouched.

        Returns what it learned for label(), so the QR isn't read all over again:
        {position folder: its label, or EMPTY_SLOT if no QR was detected in the first
        EMPTY_AFTER samples}. A position where a QR was detected but never read is left
        out, and label() reads it itself (and sends it to junk review if it can't). """
    run_dir = SORTED_UNLABELED_PATH + base_path
    known = {}
    for pos in sorted(os.listdir(run_dir), key = lambda n: int(n) if n.isdigit() else 0):
        folder = os.path.join(run_dir, pos)
        files = sorted(listdir_nohidden(folder))
        if not files:
            continue
        cache = {}
        def read(i):
            if i not in cache:
                cache[i] = _read_qr(os.path.join(folder, files[i]))
            return cache[i]
        def lab(i):
            return read(i)[1]
        n = len(files)
        idx = sorted(set(int(round(k * (n - 1) / max(samples - 1, 1))) for k in range(samples)))
        if not any(read(i)[0] for i in idx[:EMPTY_AFTER]):
            print("position " + pos + ": no QR in its first " + str(min(EMPTY_AFTER, len(idx))) + " samples -- an empty slot")
            known[os.path.normpath(folder)] = EMPTY_SLOT
            continue
        reads = [(i, lab(i)) for i in idx]
        readable = [(i, l) for i, l in reads if l is not None]
        if len(readable) < 2:
            print("position " + pos + ": too few readable QR codes to check (" + str(len(readable)) + ")")
            if readable:
                known[os.path.normpath(folder)] = readable[0][1]
            continue
        labels = [l for _, l in readable]
        if len(set(labels)) == 1:
            print("position " + pos + ": frame order OK (" + labels[0] + ", " + str(len(readable)) + " reads)")
            known[os.path.normpath(folder)] = labels[0]
            continue
        last = readable[-1][1]
        # Only the first frame disagrees, and the next one already reads the right label: a stray lead frame.
        if all(l == last for _, l in readable[1:]) and readable[0][0] == 0 and n > 1 and lab(1) == last:
            dst = os.path.join(JUNK_EXP_PATH, "stray_first_frame_" + os.path.basename(os.path.normpath(base_path)) + "_pos" + pos)
            os.makedirs(dst, exist_ok = True)
            shutil.move(os.path.join(folder, files[0]), os.path.join(dst, files[0]))
            print("WARNING position " + pos + ": the first frame reads '" + str(readable[0][1]) + "' but the rest read '"
                  + last + "' -- a stray frame before the first sweep; set aside in " + dst)
            known[os.path.normpath(folder)] = last
            continue
        # Find the first change and bisect it down to the exact frame.
        for (a, la), (b, lb) in zip(readable, readable[1:]):
            if la != lb:
                break
        while b - a > 1:
            m = (a + b) // 2
            lm = lab(m)
            if lm is None:  # unreadable: try its neighbours before giving up on narrowing further
                lm = next((lab(j) for j in (m + 1, m - 1) if a < j < b and lab(j) is not None), None)
                if lm is None:
                    break
            if lm == la:
                a = m
            else:
                b = m
        raise FrameOrderError(
            "FRAME ORDER SHIFTED in run " + str(base_path) + ", position " + pos + ": frames up to #" + str(a)
            + " read QR '" + str(la) + "', from #" + str(b) + " they read '" + str(lb) + "' (file " + files[b]
            + "). A frame was probably dropped or added mid-run, so boxes would be mixed. Nothing was labeled"
            + " or moved; the source run is untouched. Check the run around that point. Labels sampled: "
            + ", ".join(str(i) + ":" + str(l) for i, l in reads))
    return known


def qr_detection(image_path):
    
    confidence_cutoff = 0.1
    
    model = QR_MODEL
    
    image = cv2.imread(image_path)    
    image = image.copy()
            
    width = [0, 1]

    image = (image[:,int(width[0]*np.shape(image)[1]):int(width[1]*np.shape(image)[1])])
    draw = image.copy()
        
    image = preprocess_image(image)
    image, scale = resize_image(image)
            
    # predict tip on image
    start = time.time()
    boxes, scores, labels = model.predict_on_batch(np.expand_dims(image, axis=0))
    print("QR RETINANET processing time: ", time.time() - start)

    boxes /= scale
        
    top = np.argmax(scores[0])
    box = boxes[0][top]
    score = scores[0][top]
    # label = labels[0][top]
        
    if score >= confidence_cutoff:
        print("QR code has been found!!! ")
           
        color = (255, 0, 0)
        thickness = 2
        box = box.astype(int) 
        cv2.rectangle(draw, (box[0], box[1]), (box[2], box[3]), color, thickness, cv2.LINE_AA)

        # draw = Image.fromarray(draw)
        # draw.save("/qrbox.png")
        # box = np.append(box, image_name)
        return box
    return []



def junk_review():
    count = len(listdir_nohidden(JUNK_REVIEW_PATH))-1
    if count > 0:
        print("\n*****************")
        print("There are " + str(count) + " experiment folders that have been sent to junk_review. Please manually move these experiments to the 're_merge' folder in 'junk_review' if you wish to keep them and rename the experiments with the correct experiment number.")
        print("PROGRAM ENDING AFTER CURRENT ROBOT RUN")
        return True
    else:
        print("No experiments in junk review.")
        return False

def re_merge():
    try:
        for x in (listdir_nohidden(JUNK_REVIEW_PATH+"/re_merge/")):
            src = JUNK_REVIEW_PATH+"/re_merge/" + x
            dst = CURRENT_EXP_PATH + x
            if not os.path.exists(dst):
                shutil.move(src, CURRENT_EXP_PATH)
                print(str(x) + " successfully moved!")
            else:
                dst_list = [f for f in listdir_nohidden(dst) if not f.startswith('.')]
                dst_len = len(dst_list)
                files_list = [f for f in listdir_nohidden(src) if not f.startswith('.')]
                count = dst_len
                for f in files_list:
                    count += 1
                    filenamesplit = f.split("_")
                    os.rename(src + "/" + f, dst + "/" + str(100000000 + count)[-8:] + "_" + filenamesplit[1])
    except Exception as e:
        print("No experiments found to re-merge.")
        print(e)
    
# initializes 2D array names temp_list in which the first element is the number of the exp and the second is the
# len of the exp (number of images)
def update(current_list):
    temp_list = sorted(listdir_nohidden(CURRENT_EXP_PATH))
    for x in temp_list:
        current_list.append([x, len(listdir_nohidden(CURRENT_EXP_PATH + x))])
    return current_list


def make_videos(exp_name, stabilize = True, parallax = None):
    """ Render a finished experiment's videos: unstabilized -> videos/unstabilized/<exp>.mp4,
        stabilized -> videos/stabilized/<exp>.mp4.

        Stabilization tracks the box's QR label (qr_stabilize.py): translation only, no zoom,
        and it writes stabilization.json beside the frames so root-tracking can stabilize the
        same frames exactly. If the label can't be used it falls back to ffmpeg vid.stab, which
        slides up to ~100 px over a video and zooms by an unrecorded amount. """
    if parallax is None:
        parallax = qr_stabilize.PARALLAX_COLLEGE_STATION
    start = time.time()
    src = FINISHED_EXP_PATH + exp_name + "/"
    os.chdir(src)
    # the unstabilized video straight from the frames; with QR stabilization it's instead
    # written in the same pass as the stabilized one, so each frame is decoded once
    command = 'ffmpeg -y -framerate 15 -pattern_type glob -i \"' + "*" + _dominant_ext(src) + '\" -c:v libx264 -preset faster -threads 4 -crf 24 -pix_fmt yuv420p outfile.mp4'

    if stabilize:
        try:
            info = qr_stabilize.stabilize_experiment(src, src + "outfile_stabilized.mp4", parallax=parallax,
                                                     plain_path=src + "outfile.mp4")
            print("Stabilized " + exp_name + " on its QR label (parallax " + str(parallax) + ")"
                  + ("; CHECK: possible box move at " + str(len(info["jumps"])) + " frame(s)" if info["jumps"] else ""))
        except Exception as e:
            print("WARNING: QR stabilization failed for " + exp_name + " (" + str(e) + "); falling back to vid.stab")
            subprocess.call(command, shell=True)
            command = 'ffmpeg -y -threads 4 -i outfile.mp4 -vf vidstabdetect=shakiness=5:accuracy=15:stepsize=6:mincontrast=0.1:result=transforms.trf -f null -'
            subprocess.call(command, shell=True)
            command = 'ffmpeg -y -threads 4 -i outfile.mp4 -vf vidstabtransform=input=transforms.trf:smoothing=30:optzoom=1 -c:v libx264 -preset faster -threads 4 outfile_stabilized.mp4'
            subprocess.call(command, shell=True)
            if os.path.exists(src + "transforms.trf"):
                os.remove(src + "transforms.trf")
        shutil.copy(src + "outfile_stabilized.mp4", STABILIZED_VIDEO_PATH + exp_name + ".mp4")
        os.remove(src + "outfile_stabilized.mp4")
    else:
        subprocess.call(command, shell=True)
        shutil.copy(src + "outfile.mp4", STABILIZED_VIDEO_PATH + exp_name + ".mp4")

    shutil.copy(src + "outfile.mp4", FINAL_VIDEO_PATH + exp_name + ".mp4")
    os.remove(src + "outfile.mp4")
    print("Video processing time: ", time.time() - start)


def final_transfer(current_exp_list, stabilize = True, parallax = None):
    if len(current_exp_list) == 0:
        current_exp_list = update(current_exp_list)
        print(current_exp_list)
    else:
        print(current_exp_list)
        for x in range(len(current_exp_list)):
            
            current_exp_name = current_exp_list[x][0]
            if len(listdir_nohidden(CURRENT_EXP_PATH + current_exp_list[x][0])) == current_exp_list[x][1]:
                print("No new images were added to " + current_exp_list[x][0] + ", moving to finished_exp")
                
                try:
                    shutil.move(CURRENT_EXP_PATH + current_exp_list[x][0], FINISHED_EXP_PATH)
                except FileExistsError as e:
                    print("WARNING: Experiment " +str(current_exp_list[x][0])+" already has a finished experiment folder")
                    print(e)
                except Exception as e:
                    print(e)

                write_run_manifest(FINISHED_EXP_PATH + current_exp_list[x][0]) # run settings travel with the experiment

                make_videos(current_exp_name, stabilize, parallax)
        

def finish_experiments(exp_list, stabilize = True, parallax = None):
    """ Explicitly finalize the named experiments: move each from current_exp to finished_exp
        and render its video(s), regardless of whether new images were added this run. Names
        not present in current_exp are skipped with a warning. This mirrors the move+video
        logic in final_transfer(); final_transfer() applies it automatically to experiments
        that went static, this applies it on demand to a caller-supplied list. """
    present = set(listdir_nohidden(CURRENT_EXP_PATH))
    for exp_name in exp_list:
        if exp_name not in present:
            print("WARNING: experiment " + str(exp_name) + " not found in current_exp; skipping")
            continue
        print("Finishing experiment " + str(exp_name) + ", moving to finished_exp")
        try:
            shutil.move(CURRENT_EXP_PATH + exp_name, FINISHED_EXP_PATH)
        except FileExistsError as e:
            print("WARNING: Experiment " + str(exp_name) + " already has a finished experiment folder")
            print(e)
        except Exception as e:
            print(e)

        write_run_manifest(FINISHED_EXP_PATH + exp_name) # run settings travel with the experiment

        make_videos(exp_name, stabilize, parallax)


def clear_junk():
    """ Clears out junk review and junk experiment folders """
    junk_exp_path = JUNK_EXP_PATH
    junk_review_path = JUNK_REVIEW_PATH
    remerge_path = JUNK_REVIEW_PATH + "re_merge/"
    os.makedirs(remerge_path, exist_ok=True)

    print("Clearing out junk folders")
    for file in listdir_nohidden(junk_exp_path):
        shutil.rmtree(junk_exp_path+file) 
    for file in listdir_nohidden(junk_review_path):
        if file == "re_merge":
            for data in listdir_nohidden(remerge_path):
                shutil.rmtree(remerge_path + data)
            continue
        shutil.rmtree(junk_review_path + file)

def clear_staging_area(images_to_archive_path):
    destination_path = os.path.join(ARCHIVE_PATH, os.path.basename(images_to_archive_path))
    shutil.move(images_to_archive_path, destination_path)

def sort_date(elem):
    """
        give high weight to year, low weight to RUN number
        format = M/D/YY/RUN(if any)/SHELVES
        sort_date will sort the data_path_list based on date and number of shelves
    """
    numberslist = elem.split("_")
    summation = int(numberslist[0]) * 32 + int(numberslist[1]) + (int(numberslist[2]) * 100) + (len(numberslist)-4)*.001*int(numberslist[3][0])
    return summation


def transfer_to_processing(images_path, unzip):
    """
        Function to unzip experimental runs from the staging area.
        It will make a directory in the unsorted_unlabelled directory in
        master data (if it isn't there already)
    """
    if unzip:
        run_name = os.path.splitext(os.path.basename(images_path))[0]
        try:
            os.makedirs(UNSORTED_UNLABELED_PATH + run_name, exist_ok=True)
        except Exception as e:
            print("file exists")
            print(e)
        with zipfile.ZipFile(images_path, "r") as zip_ref:
            zip_ref.extractall(UNSORTED_UNLABELED_PATH + run_name)
        os.chdir("/home")
        capture_run_manifest(UNSORTED_UNLABELED_PATH + run_name)
    else:
        destination_path = os.path.join(UNSORTED_UNLABELED_PATH, os.path.basename(images_path))
        shutil.copytree(images_path, destination_path)
        capture_run_manifest(destination_path)


def listdir_nohidden(path):
    """ for dealing with the infernal .ipynb_checkpoint files created everywhere """
    return [f for f in sorted(os.listdir(path)) if not f.startswith('.')]


def get_session():
    """ only needs to be called once """
    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True
    return tf.Session(config=config)
