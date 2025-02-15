#!/usr/bin/env nextflow

params.images_path = ""
params.sort_path = ""
params.archive_path = ""
params.model_path = "/mnt/c/Users/iwt/Desktop/sorting_files/"
params.boxes_per_shelf = 3
params.transfer = false
params.do_not_stabilize = false
params.unzip = true

path_ch = Channel.of([params.images_path, params.sort_path, params.model_path])

process file_sorting {
    container 'ghcr.io/the-rhizodynamics-robot/file-sorting-env:latest'

    input:
    tuple path(images_path), path(staging_path), path(model_path)
    script:
    """
    robot_image_sorting.py \
        --images_path ${images_path} \
        --sort_path ${ssort_path} \
        --model_path ${model_path} \
        --boxes_per_shelf ${params.boxes_per_shelf} \
        ${params.transfer ? '--transfer' : ''} \
        ${params.do_not_stabilize ? '--do_not_stabilize' : ''} \
        ${params.unzip ? '--unzip' : ''}
    """
}

workflow {
    file_sorting(path_ch)
}

workflow.onComplete {
    if (params.images_path && params.archive_path) {
        def source = file(params.images_path)
        def destination = file(params.archive_path)
        if (source.exists()) {
            if (source.isDirectory()) {
                println "Moving directory ${source} to ${destination}"
                destination.mkdirs()
                source.eachFile { file ->
                    file.moveTo(destination.resolve(file.name))
                }
            } else {
                println "Moving file ${source} to ${destination}"
                destination.parentFile.mkdirs()
                source.moveTo(destination)
            }
        } else {
            println "Source path ${source} does not exist."
        }
    } else {
        println "Either images_path or archive_path is not set."
    }
}