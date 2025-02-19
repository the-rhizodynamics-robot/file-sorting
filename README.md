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

-remove box class code

-Create a second repo for tip tracking.

-Has to be interactive: need to containerize jupyerlab? Seems complex, need to render notebook in host 

"is it possible to containerize jupyterlab and have it run on a host machine? As in, access it from a web browser?"

The answer appears to be yes.

https://github.com/isaiahwtaylor/groot-sorting-tracking/tree/master/code