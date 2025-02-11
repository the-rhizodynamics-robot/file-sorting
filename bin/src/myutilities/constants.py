"""
Module to store global constants
"""

import os
abspath = os.path.split(os.path.split(os.path.split(os.path.abspath(__file__))[0])[0])[0]

INSTALL_PATH = os.path.dirname(abspath)

SEED_MODEL_PATH = os.path.join(INSTALL_PATH, "data", "models", "SeedInference.h5")

QR_MODEL_PATH =  os.path.join(INSTALL_PATH, "data", "models", "qrInference.h5")

#Pre-quantified data path
QUANTIFICATION_IN_PATH = os.path.join(INSTALL_PATH, "data", "pre_quantification")

#LOCAL quantification data location
QUANTIFICATION_OUT_PATH = os.path.join(INSTALL_PATH, "data", "post_quantification")

#Stabilized video path
STABILIZED_VIDEO_PATH = os.path.join(INSTALL_PATH, "processed_bucket", "stabilized_videos")

#traced tips path local
TRACED_TIPS_VIDS_PATH_LOCAL = os.path.join(INSTALL_PATH, "data", "post_quantification", "stabilized_videos_single_seed")

#robot data path. Add robot number and "/master_data/"
ROBOT_DATA_PATH =  os.path.join(INSTALL_PATH, "data", "robot")

VIDEO_BUCKET_PATH =  os.path.join(INSTALL_PATH, "data", "videos")

SOURCE_PATH = os.path.join(INSTALL_PATH, "code", "file_sorting", "src")

FRAC_HEIGHT = [1/20, 1/20]  # proportion of cropped height
FRAC_WIDTH = [1/10, 1/10]     # proportion of cropped width

MARKER_THICKNESS = 3
COLOR_WHITE = (255, 0, 0)
