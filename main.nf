#!/usr/bin/env nextflow

params.sort_path = "/mnt/c/Users/iwt/Desktop/file_sorting_test/"
params.staging_path = "/mnt/c/Users/iwt/Desktop/sorting_files/zips/"
params.robot_number = 1
params.boxes_per_shelf = 7
params.transfer = false
params.do_not_stabilize = false

process file_sorting {
    container 'ghcr.io/the-rhizodynamics-robot/file-sorting-env:latest'

    script:
    """
    robot_image_sorting.py \
        --sort_path ${params.sort_path} \
        --staging_path ${params.staging_path} \
        --robot_number ${params.robot_number} \
        --boxes_per_shelf ${params.boxes_per_shelf} \
        ${params.transfer ? '--transfer' : ''} \
        ${params.do_not_stabilize ? '--do_not_stabilize' : ''}
    """
}

workflow {
    file_sorting()
}