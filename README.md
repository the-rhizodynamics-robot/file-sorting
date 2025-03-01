-images stored on computer: images sorted on computer or vm-images are sorted, movie made, and stabilized.

-external process to zip, transfer, and unzip

Next steps:
-Parameterize NF script. CHECK (almost certainly wrong, but need data from next step to test)

-log into VM and get maybe 3 zips? successive runs with overlaping and non-overlapping boxes (at least get one), also get models (qr and seed)... I think that's all. CHECK

-test basic implementation and iterate. CHECK.

-Need to re-implement archive function call.

-rethink global variables (or at least reduce to minimum)

-implement optional zipped processing

FEATURES:

-work on the rotation thing.

-add onComplete hook to (on success) clear staging_area.

////////////////////////
/// SORTING/BOX CLASS //
////////////////////////

-It appears the box class is not used in the file sorting.

Plan:

-remove box class code. CHECK

-Create a second repo for tip tracking. CHECK

///////////////////////
////// NEXT STEP //////
///////////////////////
-Has to be interactive: need to containerize jupyerlab? Seems complex, need to render notebook in host.

"is it possible to containerize jupyterlab and have it run on a host machine? As in, access it from a web browser?"

The answer appears to be yes.

https://github.com/isaiahwtaylor/groot-sorting-tracking/tree/master/code

/////////////////
//// Testing ////
/////////////////

nextflow run /home/iwtwb8/gitrepos/file-sorting/main.nf -profile local --images_path /mnt/c/Users/iwt/Desktop/sorting_files/zips/7_7_unzip_1/ --unzip false --sort_path /mnt/c/Users/iwt/Desktop/file_sorting_test/ --archive false

# to do
write readme
optimize code

# Actual readme

# file-sorting

This is a nextflow pipeline for taking still images generated with the [GROOT robot] (https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0295823) and creating stabilized, time-lapse videos. 

## Dependancies

Nextflow

Docker

## Usage

## Example Usage

To run the Nextflow pipeline, use the following command:

```
nextflow run /path/to/main.nf -profile local \
  --images_path /path/to/images_directory \
  --sort_path /path/to/sorted_images_directory \
  --boxes_per_shelf <number_of_boxes_per_shelf> \
  --finish_only <true_or_false> \
  --stabilize <true_or_false> \
  --unzip <true_or_false> \
  --archive <true_or_false>
```

Input Parameters

--images_path: The path to the directory containing the images to be processed. This parameter is required.

Example: --images_path /path/to/images

--sort_path: The path to the directory where the sorted images and results will be saved. This parameter is required.

Example: --sort_path /path/to/

--boxes_per_shelf: The number of boxes per shelf. This parameter is optional and defaults to 3.

Example: --boxes_per_shelf 4

--finish_only: A boolean flag to indicate whether to only finish the sorting process. This parameter is optional and defaults to false.

Example: --finish_only

--stabilize: A boolean flag to indicate whether to stabilize the images. This parameter is optional and defaults to true.

Example: --stabilize 

--unzip: A boolean flag to indicate whether the input files are zipped. This parameter is optional and defaults to true.

Example: --unzip false

--archive: A boolean flag to indicate whether to archive the processed files. This parameter is optional and defaults to true.

Example: --archive false


nextflow run /home/iwtwb8/gitrepos/file-sorting/main.nf -profile local \
  --images_path /mnt/c/Users/iwt/Desktop/sorting_files/zips/7_7_unzip_1/ \
  --sort_path /mnt/c/Users/iwt/Desktop/file_sorting_test/ \
  --boxes_per_shelf 4 \
  --finish_only false \
  --stabilize true \
  --unzip false \
  --archive false

## Example Usage

nextflow run /home/iwtwb8/gitrepos/file-sorting/main.nf -profile local --images_path /mnt/c/Users/iwt/Desktop/sorting_files/zips/7_7_unzip_1/ --unzip false --sort_path /mnt/c/Users/iwt/Desktop/file_sorting_test/ --archive false
