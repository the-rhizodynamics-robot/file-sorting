#!/usr/bin/env nextflow

params.images_path = ""
params.sort_path = ""
params.model_path = "/mnt/c/Users/iwt/Desktop/sorting_files/"
params.boxes_per_shelf = 3
params.finish_only = false
params.stabilize = true
params.unzip = true
params.archive = true

path_ch = Channel.of([params.images_path, params.sort_path, params.model_path])

process file_sorting {
    container 'ghcr.io/the-rhizodynamics-robot/file-sorting-env:latest'

    input:
    tuple path(images_path), path(sort_path), path(model_path)
    script:
    """
    robot_image_sorting.py \
        --images_path ${images_path} \
        --destination_path ${sort_path} \
        --model_path ${model_path} \
        --boxes_per_shelf ${params.boxes_per_shelf} \
        ${params.finish_only ? '--finish_only' : ''} \
        ${params.stabilize ? '--stabilize' : ''} \
        ${params.unzip ? '--unzip' : ''} 
    """
}

workflow {
    file_sorting(path_ch)
}

workflow.onComplete { 
    if (workflow.success && params.archive) {
        def source = file(params.images_path)
        def destination = file("${params.sort_path}/data/unsorted_unlabeled_processed/${source.name}")

        if (source.exists()) {
            if (source.isDirectory()) {
                println "Moving directory ${source} to ${destination}"
                destination.mkdirs()
                source.eachFile { file ->
                    file.moveTo(destination.resolve(file.name))
                }
            } else {
                println "Moving file ${source} to ${destination}"
                destination.parent.mkdirs()
                source.moveTo(destination)
            }
        } else {
            println "Source path ${source} does not exist."
        }
    } else {
        println "Skipping file/directory archive step."
    }
}