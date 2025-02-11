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


def init(robot, boxes_per_shelf):
    """ Declare constants for save paths"""

    global ARCHIVE_PATH
    global MOUNTED_BUCKET_STAGING_PATH
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

    abspath = os.path.split(os.path.split(os.path.abspath(__file__))[0])[0]
    INSTALL_PATH = os.path.dirname(abspath)
    DATA_PATH = os.path.join(INSTALL_PATH, "data", "robot", "")
    MOUNTED_BUCKET_STAGING_PATH = os.path.join(INSTALL_PATH, "data", "unsorted_unlabeled_zipped", "")
    ARCHIVE_PATH = os.path.join(INSTALL_PATH, "data", "unsorted_unlabeled_processed", "")
    UNSORTED_UNLABELED_PATH = os.path.join(DATA_PATH, "master_data", "unsorted_unlabeled", "")
    SORTED_UNLABELED_PATH = os.path.join(DATA_PATH, "master_data", "sorted_unlabeled", "")
    CURRENT_EXP_PATH = os.path.join(DATA_PATH, "master_data", "current_exp", "")
    FINISHED_EXP_PATH = os.path.join(DATA_PATH, "master_data", "finished_exp", "")
    JUNK_EXP_PATH = os.path.join(DATA_PATH, "master_data", "junk_exp", "")
    JUNK_REVIEW_PATH = os.path.join(DATA_PATH, "master_data", "junk_review", "")
    FINAL_VIDEO_PATH = os.path.join(INSTALL_PATH, "data", "videos", "unstabilized", "")
    STABILIZED_VIDEO_PATH = os.path.join(INSTALL_PATH, "data", "videos", "stabilized", "")
    BOXES_PER_SHELF = int(boxes_per_shelf)
    

    # load all retinanet models
    keras.backend.tensorflow_backend.set_session(get_session())
    QR_MODEL_PATH = os.path.join(INSTALL_PATH, "data", "models", "qrInference.h5")
    QR_MODEL = models.load_model(QR_MODEL_PATH, backbone_name='resnet50')


def sort(base_path, shelves):
    
    # number of boxes in this experiment.
    num_boxes = BOXES_PER_SHELF * int(shelves)

    # where unsorted, unlabelled images are located
    mypathin = UNSORTED_UNLABELED_PATH + base_path
   
    # mypathout is the directory where the sorted but unlabelled images will go
    mypathout = SORTED_UNLABELED_PATH + base_path

    # create onlyfiles w column list with file name in first column and parsed image # as second column
    # create a list of all the files in the image directory
    onlyfiles = [f for f in listdir(mypathin) if isfile(join(mypathin, f))]

    # flycap names images with a _####, from 0000 to 9999, then goes to 10000,
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
        info = element.stat()
        timestamps.append(info.st_mtime)
    timestamps.sort()
    # this will make a number of directories in the out directory equal to the number of boxes, names 1\, 2\, 3\, etc
    for x in range(num_boxes):
        os.mkdir(mypathout+"/"+str(x+1))
    os.chdir("/home")

    # this double loop will loop over the sequence 1:len(onlyfiles),
    # while also saving each file to the appropriate folder in the
    # out directory
    count = 0

    # Changed to move instead of copy files when sorting
    for z in range(1,int(len(files)/num_boxes)*num_boxes,num_boxes):
        count = count +1
        for y in range(num_boxes):
            savefile=mypathout + "/" + str(y+1) + "/" + str(100000000 + count)[-8:] + "_" + str(timestamps[z+y-1]) + ".png"
            filename = mypathin + "/" + files[z+y-1][0]
            shutil.move(filename, savefile)
    os.chdir("/home")


def label(base_path):
    current_exp_path = CURRENT_EXP_PATH
    mypathout = SORTED_UNLABELED_PATH + base_path
    junk_exp_path=JUNK_EXP_PATH
    junk_review_path = JUNK_REVIEW_PATH
    finished_exp_path = FINISHED_EXP_PATH
    mypathin = UNSORTED_UNLABELED_PATH + base_path
        
    # make current exp path, finished exp path, and junk exp path directory if they don't already exist.
    if not os.path.isdir(current_exp_path):
        os.mkdir(current_exp_path)
    if not os.path.isdir(junk_exp_path):
        os.mkdir(junk_exp_path)
    if not os.path.isdir(finished_exp_path):
        os.mkdir(finished_exp_path)

    # This is intended to loop over all folders in sorted, unlabelled directory.
    # It will scan for QR codes until 3 codes are found, then take the modal code and move the images into the current
    # sorted-labelled directory.
    dirlist = [x[0] for x in os.walk(mypathout)]
    #print(dirlist)

    # starting at index 1 skips the parent directory, which os.walk includes.  
    for d in dirlist[1:]:
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
            thr = []
            blur = cv2.GaussianBlur(img[box[1]:box[3],box[0]:box[2]],(3,3),0)
         
            #try several preprocessing approaches and see if any work
            thr.append(img)
            thr.append(blur)
            thr.append(cv2.adaptiveThreshold(blur, 255,cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY,69,2))
            thr.append(cv2.adaptiveThreshold(blur, 255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY,69,2))    
            thr.append(cv2.threshold(blur, 0, 255, cv2.THRESH_OTSU)[1])    
            thr.append(cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY,89,2))    
            thr.append(cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY,31,11))   
            thr.append(cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY,55,11))   
            
            counter = 0
            for t in thr:
                barcode = decode(t, symbols=[ZBarSymbol.QRCODE])
                if len(barcode)>0:
                    print("threshold technique: " + str(counter))
                    break
                counter = counter + 1 
                
            crop_sum = crop_sum + np.sum(img[box[1]:box[3],box[0]:box[2]])
            if len(barcode)>0:
                exp_name = (int((str(barcode[0][0]).split('\'')[1::2])[0])) 
                print("Position number = " + str(os.path.basename(d)))
                print("Box number = " + str(exp_name))
                temp_path = current_exp_path + "/" + str(exp_name)
                if not os.path.isdir(temp_path):
                    os.chdir("/home")
                    shutil.move(d, temp_path)
                else:
                    onlyfiles = listdir_nohidden(temp_path)
                    base = len(onlyfiles)
                    new_files = listdir_nohidden(".")
                    for g in new_files:
                        file_counter = int(g[0:8])
                        stamps = g.split("_")[1]
                        savefile = temp_path + "/" + str(100000000 + file_counter + base)[-8:] + "_" + stamps 
                        shutil.move(g, savefile)
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


def final_transfer(current_exp_list, stabilize = True):
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
                
                # # remove qrbox.png and put in showcase folder
                # if not os.path.isdir(FINAL_SHOWCASE_PATH + current_exp_name):
                #     os.mkdir(FINAL_SHOWCASE_PATH + current_exp_name)
                # if os.path.exists(FINISHED_EXP_PATH + current_exp_name + "/qrbox.png"):
                #     shutil.copy(FINISHED_EXP_PATH + current_exp_name + "/qrbox.png", FINAL_SHOWCASE_PATH + current_exp_name)
                #     os.remove(FINISHED_EXP_PATH + current_exp_name + "/qrbox.png")

                # make video and move it
                src = FINISHED_EXP_PATH + current_exp_list[x][0] + "/"
                os.chdir(src)
  
                start = time.time()

                src = FINISHED_EXP_PATH + current_exp_name + "/"
                os.chdir(src)
                command = 'ffmpeg -framerate 15 -pattern_type glob -i \"*.png\" -c:v libx264 -crf 24 -pix_fmt yuv420p outfile.mp4'
                subprocess.call(command,shell=True)     
                
                if stabilize:
                    command = 'ffmpeg -i outfile.mp4 -vf vidstabdetect=stepsize=32:shakiness=10:accuracy=10:result=transforms.trf -f null -'
                    subprocess.call(command,shell=True)
                    
                    command = 'ffmpeg -i outfile.mp4 -vf vidstabtransform=smoothing:input=\"transforms.trf\" outfile_stabilized.mp4'
                    subprocess.call(command,shell=True)

                    shutil.copy(FINISHED_EXP_PATH + current_exp_list[x][0] + "/outfile_stabilized.mp4", STABILIZED_VIDEO_PATH + current_exp_name + ".mp4")
                    os.remove(FINISHED_EXP_PATH + current_exp_list[x][0] + "/outfile_stabilized.mp4") 
                    os.remove(FINISHED_EXP_PATH + current_exp_list[x][0] + "/transforms.trf")  
                else:
                    shutil.copy(FINISHED_EXP_PATH + current_exp_list[x][0] + "/outfile.mp4", STABILIZED_VIDEO_PATH + current_exp_name + ".mp4") 
                
                shutil.copy(FINISHED_EXP_PATH + current_exp_list[x][0] + "/outfile.mp4", FINAL_VIDEO_PATH + current_exp_name + ".mp4") 
                os.remove(FINISHED_EXP_PATH + current_exp_list[x][0] + "/outfile.mp4")   
                
                print("Video processing time: ", time.time() - start)            
        

def clear_junk():
    """ Clears out junk review and junk experiment folders """
    junk_exp_path = JUNK_EXP_PATH
    junk_review_path = JUNK_REVIEW_PATH
    remerge_path = JUNK_REVIEW_PATH + "re_merge/"
    
    print("Clearing out junk folders")
    for file in listdir_nohidden(junk_exp_path):
        shutil.rmtree(junk_exp_path+file) 
    for file in listdir_nohidden(junk_review_path):
        if file == "re_merge":
            for data in listdir_nohidden(remerge_path):
                shutil.rmtree(remerge_path + data)
            continue
        shutil.rmtree(junk_review_path + file)
            

def sort_date(elem):
    """
        give high weightage to year, low weightage to RUN number
        format = M/D/YY/RUN(if any)/SHELVES
        sort_date will sort the data_path_list based on date and number of shelves
    """
    numberslist = elem.split("_")
    summation = int(numberslist[0]) * 32 + int(numberslist[1]) + (int(numberslist[2]) * 100) + (len(numberslist)-4)*.001*int(numberslist[3][0])
    return summation


def transfer_to_instance(run_name):
    """
        Function to unzip experimental runs from the staging area.
        It will make a directory in the unsorted_unlabelled directory in
        master data (if it isn't there already)
    """
    directory = (os.path.splitext(run_name)[0])
    print(directory)
    try:
        os.makedirs(UNSORTED_UNLABELED_PATH + directory)
    except Exception as e:
        print("file exists")
        print(e)
    with zipfile.ZipFile(MOUNTED_BUCKET_STAGING_PATH + run_name,"r") as zip_ref:
        zip_ref.extractall(UNSORTED_UNLABELED_PATH + directory)
    os.chdir("/home")


def clear_staging_bucket(zip_to_remove):
    #os.remove(MOUNTED_BUCKET_STAGING_PATH + "/" + zip_to_remove)
    shutil.move(MOUNTED_BUCKET_STAGING_PATH + "/" + zip_to_remove, ARCHIVE_PATH + "/" + zip_to_remove)


def listdir_nohidden(path):
    """ for dealing with the infernal .ipynb_checkpoint files created everywhere """
    return [f for f in sorted(os.listdir(path)) if not f.startswith('.')]


def get_session():
    """ only needs to be called once """
    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True
    return tf.Session(config=config)
