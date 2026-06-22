#!/usr/bin/env nextflow

params.images_path = ""
params.sort_path = ""
params.boxes_per_shelf = 3
params.finish_only = false
params.stabilize = true
params.unzip = true
params.archive = true
params.finish_experiments = ""

// Interpret boolean params robustly. On the command line, `--unzip false` arrives
// as the STRING "false", which is truthy in Groovy -- so a plain `params.unzip ?`
// test would wrongly enable it. (Older Nextflow coerced "false" -> boolean; 25+/26
// does not.) asBool() makes "false"/"0"/"no" behave as false.
def asBool(v) {
    def s = v.toString().toLowerCase()
    return s == 'true' || s == '1' || s == 'yes' || s == 'y'
}

process file_sorting {
    container 'ghcr.io/the-rhizodynamics-robot/file-sorting-env:latest'

    input:
    tuple path(images_path), path(sort_path)
    script:
    """
    robot_image_sorting.py \
        --images_path ${images_path} \
        --destination_path ${sort_path} \
        --model_path /app/models/ \
        --boxes_per_shelf ${params.boxes_per_shelf} \
        ${asBool(params.finish_only) ? '--finish_only' : ''} \
        ${asBool(params.stabilize) ? '--stabilize' : ''} \
        ${asBool(params.unzip) ? '--unzip' : ''} \
        ${params.finish_experiments ? "--finish_experiments '" + params.finish_experiments + "'" : ''}
    """
}

workflow {
    path_ch = Channel.of([params.images_path, params.sort_path])
    file_sorting(path_ch)

    workflow.onComplete = {
        if (workflow.success && asBool(params.archive)) {
            def source = file(params.images_path)
            def destination = file("${params.sort_path}/data/unsorted_unlabeled_processed/${source.name}")

            if (source.exists()) {
                if (source.isDirectory()) {
                    println "Moving directory ${source} to ${destination}"
                    destination.mkdirs()
                    source.eachFile { f ->
                        f.moveTo(destination.resolve(f.name))
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
}