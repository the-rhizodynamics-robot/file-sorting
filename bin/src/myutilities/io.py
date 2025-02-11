
"""
Module dealing with io bound tasks, reading and writing to disk, and conversions

"""

import os
import cv2
import subprocess
import numpy as np
from PIL import Image as Pillow
from typing import List


def read_image_single_channel(path):
    return cv2.imread(path, 0)

def read_image_queue(queue, path):
    queue.put([cv2.imread(path, 0), path])

def save_image(image: Pillow.Image, image_output_path:str):
    try:
        image.save(image_output_path)
    except FileNotFoundError:
        root = os.path.split(image_output_path)[0]
        os.makedirs(root)
        image.save(image_output_path)

def to_pil(image: np.ndarray):
    return Pillow.fromarray(image)

def save_image_from_array(image: np.ndarray, image_output_path : str):
    image = to_pil(image)
    try:
        image.save(image_output_path)
    except FileNotFoundError:
        root = os.path.split(image_output_path)[0]
        os.makedirs(root)
        image.save(image_output_path)

def make_video_cv2(frames: List[np.ndarray], save_path:str, filename:str=""):
    video = cv2.VideoWriter(save_path + filename, cv2.VideoWriter_fourcc(*'mp4v'), 15,
                            (np.shape(frames[0])[1], np.shape(frames[0])[0]))
    for frame in frames:
        video.write(frame)
    video.release()

def make_video_ffmpeg(save_path : str):
    os.chdir(save_path)
    command = 'ffmpeg -framerate 15 -pattern_type glob -i \'*.png\' -pix_fmt yuv420p outfile.mp4'
    subprocess.call(command, shell=True)

def save_plot(fig, save_path : str):
    fig.savefig(save_path)