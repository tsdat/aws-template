#!/bin/bash
#####################################################################
# Script Name:  find_modified_pipelines.sh
# Description:  Script that uses git diff to find out which tsdat
#               pipelines had recent code changes.
#
#               This script needs to be called from the root of your 
#               deployment's pipelines repository.
#####################################################################
PIPELINES_DIR=$1
CURRENT_COMMIT_HASH=$2
PREVIOUS_COMMIT_HASH=$3

CHANGE_FILE=/tmp/changelist
OUT_FILE=/tmp/changed_pipelines

# Do a git diff to get the list of files that were changed in the latest commit
cd $PIPELINES_DIR
git diff --name-only $CURRENT_COMMIT_HASH $PREVIOUS_COMMIT_HASH
git diff --name-only $CURRENT_COMMIT_HASH $PREVIOUS_COMMIT_HASH > $CHANGE_FILE

# Parse out only the pipelines that changed
egrep '^pipelines/' $CHANGE_FILE | awk -F'/' '{print $2}' | sort | uniq
egrep '^pipelines/' $CHANGE_FILE | awk -F'/' '{print $2}' | sort | uniq > $OUT_FILE
