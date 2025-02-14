#!/usr/bin/env nextflow

params.sort_path = "/mnt/c/Users/iwt/Desktop/file_sorting_test/"
params.staging_path = "/mnt/c/Users/iwt/Desktop/sorting_files/zips/"
params.model_path = "/mnt/c/Users/iwt/Desktop/sorting_files/"
params.robot_number = 1
params.boxes_per_shelf = 3
params.transfer = false
params.do_not_stabilize = false

path_ch = Channel.of([params.sort_path, params.staging_path, params.model_path])

process file_sorting {
    container 'ghcr.io/the-rhizodynamics-robot/file-sorting-env:latest'

    input:
    tuple path(sort_path), path(staging_path), path(model_path)
    script:
    """
    robot_image_sorting.py \
        --sort_path ${sort_path} \
        --staging_path ${staging_path} \
        --model_path ${model_path} \
        --robot_number ${params.robot_number} \
        --boxes_per_shelf ${params.boxes_per_shelf} \
        ${params.transfer ? '--transfer' : ''} \
        ${params.do_not_stabilize ? '--do_not_stabilize' : ''}
    """
}

workflow {
    file_sorting(path_ch)
}