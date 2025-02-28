#!/usr/bin/env python3

"""

    Entry point of file-sorting program.
    Sorts, labels, and creates stabilized videos
    of images taken by root robot.

"""

import src.sorting_functions as sf
import argparse
import os
import sys

# Dynamically add `bin/src/` to sys.path
#sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

parser = argparse.ArgumentParser(description="Script for sorting images and creating videos.")
parser.add_argument("-i", "--images_path",
                    action="store",
                    dest="images_path",
                    help="Path to images to be sorted (zip or directory)",
                    required=True)
parser.add_argument("-d", "--destination_path",
                    action="store",
                    dest="sort_path",
                    help="Base directory for file sorting project",
                    required=True)
parser.add_argument("-m", "--model_path",
                    action="store",
                    dest="model_path",
                    help="Path to model files")
parser.add_argument("-b", "--boxes_per_shelf",
                    action="store",
                    dest="boxes_per_shelf",
                    help="Boxes per shelf.")
parser.add_argument("-f", "--finish_only",
                    help="Transfer all experiments to finished/ and create videos",
                    action="store_true")
parser.add_argument("-s", "--stabilize",
                    help="Do not stabilize videos",
                    action="store_true")
parser.add_argument("-u", "--unzip",
                    help="Unzip the images",
                    action="store_true")
args = parser.parse_args()

# Override paths with sort_path
images_path = args.images_path
sort_path = args.sort_path
boxes_per_shelf = args.boxes_per_shelf
model_path = args.model_path

sf.init(boxes_per_shelf, sort_path, images_path, model_path)

# Ensure directory structure exists
directories = [
    "data/unsorted_unlabeled_processed",
    "data/master_data/unsorted_unlabeled",
    "data/master_data/sorted_unlabeled",
    "data/master_data/current_exp",
    "data/master_data/finished_exp",
    "data/master_data/junk_exp",
    "data/master_data/junk_review",
    "data/videos/unstabilized",
    "data/videos/stabilized"
]

for d in directories:
    os.makedirs(os.path.join(sort_path, d), exist_ok=True)

print(args)

# check if there are experiments that were wanted from junk_review and re_merge them into current_exp
# remove junk from previous robot run in case items were sent to junk review
sf.re_merge()
sf.clear_junk()

current_exp_list = []

if args.finish_only:
    current_exp_list = sf.update(current_exp_list)
    sf.final_transfer(current_exp_list)
else:

    # move images to unsorted_unlabeled
    sf.transfer_to_processing(images_path, args.unzip)

    current_exp_list = sf.update(current_exp_list)
    run_name = os.path.splitext(images_path)[0]
    sf.sort(run_name, run_name[-1:])
    sf.label(run_name)    

    review_needed = sf.junk_review()

    if not review_needed:
        sf.final_transfer(current_exp_list, stabilize = args.stabilize)
    else:
        print("skipping final transfer, there are junk review items to be dealt with\n*****************")