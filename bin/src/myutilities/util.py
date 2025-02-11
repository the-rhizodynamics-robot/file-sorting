import src.myutilities.constants as c
import subprocess
import shutil
import time

"""
General purpose utility module for convenience functions

"""

import os

def listdir_nohidden(path):
    """
    :param path: directory path
    :return: list of files within directory excluding any hidden files starting with .
    """
    return [f for f in sorted(os.listdir(path)) if not f.startswith('.')]


def sync_for_rstudio():
    """Wrapper for rsync. Syncs csv files of tip coordinates to Rstudio user folder (because Rstudio Server requires a dedicated non-super user).
    The source and destination directories are set in the constants.py file variables QUANTIFICATION_OUT_PATH and RSTUDIO_OUT_PATH, respectively.
    """
    
    in_path = c.QUANTIFICATION_OUT_PATH + "tip_coordinates/"
    out_path = c.RSTUDIO_OUT_PATH + "tip_coordinates/"
    command = "sudo rsync -t " +  in_path + "*.csv " + out_path
    subprocess.call(command,shell=True)
    print(command)
    

#NEED TO TROUBLESHOOT THIS
def sync_traced_tips():
    """Wrapper for rsync. Syncs traced tip videos to bucket.
    The source and destination directories are set in the constants.py file variables QUANTIFICATION_OUT_PATH and TRACED_TIPS_VIDS_PATH, respectively.
    """
    
    in_path = c.QUANTIFICATION_OUT_PATH + "stabilized_videos_single_seed/"
    out_path = c.TRACED_TIPS_VIDS_BUCKET_PATH
    command = "gsutil rsync " +  in_path + " " + out_path
    subprocess.call(command,shell=True)
    print(command)
    
def archive(source : str):
    """Function to clear out pre_quantification_stabilized directory and move experiment folders to pre_quantificaiton archive. Need to build in a way to clear
    archive because disk will rapidly fill up. Maybe check about removing existing directories when running this function?
    
    Parameters
    ----------
    source : str
        source directory to archive within pre_quantification. Usually "stabilized" or "unstabilized"
    """
    
    in_path = c.QUANTIFICATION_IN_PATH + source + "/"
    out_path = c.QUANTIFICATION_IN_PATH + "archive/"
    old_expts = listdir_nohidden(out_path)
    new_expts = listdir_nohidden(in_path)
    
    print("The following experiments are in the archive already.")
    print(old_expts)  
    response = check_input("Would you like to delete these experiments? (y) or (n)", range_ = ("y","n"))
    if response == "y":
        response = check_input("Are you sure you want to delete these experiments? (y) or (n)", range_ = ("y","n"))
        if response == "y":
            for d in old_expts:
                shutil.rmtree(out_path + d)
        else:
            print("Not deleting experiments.")
    
    timestamp = time.time()
    print(timestamp)
    for d in new_expts:
        try:
            shutil.move(in_path + d, out_path + d + "_" + str(timestamp) + "_" + source) #make different name to differentiate stabilized from unstabilized
        except:
            print("Failed to archive " + d +". Perhaps directory already exists.")

    #print out contents of archive directory. Ask if would like to delete. 
    #Then move new experiments there. Or perhaps just experiment that have been quantified?
    
def check_input(prompt, type_=None, min_=None, max_=None, range_=None):
    """
    Function to check user input
    Function modified from https://stackoverflow.com/questions/23294658/asking-the-user-for-input-until-they-give-a-valid-response
    
    Parameters
    ----------
    prompt: str
        User prompt
    type_ : None
        expected datatype
    min_ : 
        minimum valid numerical input
    max_ : 
        maximum valid numerical input
    range :
        list of acceptable responses to check
    
    """
    
    if min_ is not None and max_ is not None and max_ < min_:
        raise ValueError("min_ must be less than or equal to max_.")
    while True:
        ui = input(prompt)
        if type_ is not None:
            try:
                ui = type_(ui)
            except ValueError:
                print("Input type must be {0}.".format(type_.__name__))
                continue
        if max_ is not None and ui > max_:
            print("Input must be less than or equal to {0}.".format(max_))
        elif min_ is not None and ui < min_:
            print("Input must be greater than or equal to {0}.".format(min_))
        elif range_ is not None and ui not in range_:
            if isinstance(range_, range):
                template = "Input must be between {0.start} and {0.stop}."
                print(template.format(range_))
            else:
                template = "Input must be {0}."
                if len(range_) == 1:
                    print(template.format(*range_))
                else:
                    expected = " or ".join((
                        ", ".join(str(x) for x in range_[:-1]),
                        str(range_[-1])
                    ))
                    print(template.format(expected))
        else:
            return ui
        
            
def unspool_video(full_path : str, out_dir : str, remove : bool = False):
    """
    Function for unspooling images from videos. This would allow reanalysis of videos from prior experiments without saving the raw PNGs.
    
    Parameters
    ----------
    full_path : str 
        full path of movie file to be converted to image sequence
    out_dir : str
        path of the directory to place images. Should be named the same as the experiment number for consistency.
    remove : bool
        Whether to delete the video after unspooling. Default is false.
    """
    if (not os.path.isdir(out_dir)):
        os.mkdir(out_dir)
    
    command = "ffmpeg -i " + full_path + " -r 15 " + out_dir + "/%08d.png"
    subprocess.call(command,shell=True)
    
    if (remove):
        os.remove(full_path)
    
def copy_videos(video_list : tuple, source = "unstabilized", dest = c.QUANTIFICATION_IN_PATH + "to_unspool//"):
    """
    This function copies videos from the cloud bucket to a local directory.
    
    Parameters
    ----------
    video_list : tuple
        A tuple containing the experiment numbers to be copied
    dest : str
        Location on the instance to copy the videos. Default is to_unspool/ in pre_quantification
    source  : str
        Location from where to copy videos (stabilized or unstabilized)
    """
    for v in video_list:
        if source == "stabilized":
            try:
                shutil.copyfile(c.STABILIZED_VIDEO_PATH + str(v) + ".mp4", dest + str(v) + ".mp4") 
            except:
                print("Unable to copy video " + str(v) +". Perhaps you are trying to move a video from stabilized directory that wasn't stabilized?")
        else:
            try:
                shutil.copyfile(c.VIDEO_BUCKET_PATH + str(v) + ".mp4", dest + str(v) + ".mp4") 
            except:
                print("Unable to copy video " + str(v) +". Perhaps there was a type?")
                
def empty_trash():
    """
    When you delete files from Jupyter lab they are put into a trash directory. This will clear that directory.
    """
    
    response = check_input("Would you like to empty the trash? (y) or (n)", range_ = ("y","n"))
    if response == "y":
        response = check_input("Are you sure? (y) or (n)", range_ = ("y","n"))
        if response == "y":
                command = "rm -rf $HOME/.local/share/Trash/files"
                subprocess.call(command,shell=True)
        else:
            print("Not emptying trash.")
