#!/bin/bash
#####################################################################
# Script Name:  find_modified_pipelines.sh
# Description:  Script that uses git diff to find out which tsdat
#               pipelines had recent code changes.
#
#               This script needs to be called from the root of your 
#               deployment's pipelines repository.
#####################################################################

CHANGE_FILE=/tmp/changelist

# Use AWS CLI to look up the previous commit hash
    # AWS_PIPELINE_NAME (e.g., ingest-buoy-dev-build-pipline) is passed into the
    # environment from the stack.
    # Alternatively, we could parse it from the $CODEBUILD_INITIATOR param that is set
    # by AWS.  (e.g., CODEBUILD_INITIATOR=codepipeline/ingest-buoy-dev-build-pipline)
PREVIOUS_COMMIT_HASH=$(aws codepipeline list-pipeline-executions --pipeline-name $AWS_PIPELINE_NAME | jq -r '[.pipelineExecutionSummaries[] | select(.status == "Succeeded") | .sourceRevisions][0][] | select(.actionName == "pipelines-source-action") | .revisionId')

# Do a git diff to get the list of files that were changed in the latest commit
    # CODEBUILD_RESOLVED_SOURCE_VERSION is set by CodePipeline and points to the most recent commit hash
CURRENT_COMMIT_HASH=$CODEBUILD_RESOLVED_SOURCE_VERSION
git diff --name-only $CURRENT_COMMIT_HASH $PREVIOUS_COMMIT_HASH > $CHANGE_FILE

# Parse out only the pipelines that changed
egrep '^pipelines/' $CHANGE_FILE | awk -F'/' '{print $2}' | sort | uniq
