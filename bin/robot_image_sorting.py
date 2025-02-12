#!/usr/bin/env python3

"""

    Entry point of file-sorting program.
    Sorts, labels, and creates stabilized videos
    of images taken by root robot.

"""

import src.sorting_functions as sf
import argparse
import os

# Dynamically add `bin/src/` to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

parser = argparse.ArgumentParser(description="Script for sorting images and creating videos.")
parser.add_argument("-i", "--sort_path",
                    action="store",
                    dest="sort_path",
                    help="Base directory for file sorting project",
                    default="/mnt/c/Users/iwt/Desktop/file_sorting_test/")
parser.add_argument("-s", "--staging_path",
                    action="store",
                    dest="staging_path",
                    help="Staging directory for file sorting project",
                    default="/mnt/c/Users/iwt/Desktop/sorting_files/zips/")
parser.add_argument("-b", "--boxes_per_shelf",
                    action="store",
                    dest="boxes_per_shelf",
                    help="Boxes per shelf.",
                    default=1)
parser.add_argument("-t", "--transfer",
                    help="Transfer all experiments to finished",
                    action="store_true")
parser.add_argument("-d", "--do_not_stabilize",
                    help="Do not stabilize videos",
                    action="store_true")
parser.add_argument("-r", "--robot_number",
                    action="store",
                    dest="robot_number",
                    help="Robot number where data was generated (1, 2, 3, etc).",
                    default="")
args = parser.parse_args()

# Override paths with sort_path
sort_path = args.sort_path
staging_path = args.staging_path
robot = f"robot{args.robot_number}/"
boxes_per_shelf = args.boxes_per_shelf

sf.init(robot, boxes_per_shelf, sort_path, staging_path)

# Ensure directory structure exists
directories = [
    "data/unsorted_unlabeled_zipped",
    "data/unsorted_unlabeled_processed",
    "data/" + robot + "/master_data/unsorted_unlabeled",
    "data/" + robot + "/master_data/sorted_unlabeled",
    "data/" + robot + "/master_data/current_exp",
    "data/" + robot + "/master_data/finished_exp",
    "data/" + robot + "/master_data/junk_exp",
    "data/" + robot + "/master_data/junk_review",
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
data_path_list = sf.listdir_nohidden(sf.STAGING_PATH)

# sort in ascending order by value
# in order to create a value representative of the date the sort_date function is used
data_path_list.sort(key=sf.sort_date)
print(data_path_list)

if args.transfer:
    current_exp_list = sf.update(current_exp_list)
    sf.final_transfer(current_exp_list)
else:
    data_path = data_path_list[0]
    # unzip and move images to unsorted_unlabeled
    sf.transfer_to_instance(data_path)

    current_exp_list = sf.update(current_exp_list)
    run_name = os.path.splitext(data_path)[0]
    print(run_name)
    sf.sort(run_name, run_name[-1:])
    sf.label(run_name)

    # safely removes zip of current run
    sf.clear_staging_bucket(data_path)        

    review_needed = sf.junk_review()

    if not review_needed:
        sf.final_transfer(current_exp_list, stabilize = not args.do_not_stabilize)
    else:
        print("skipping final transfer, there are junk review items to be dealt with\n*****************")