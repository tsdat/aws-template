#!/bin/bash
#####################################################################
# Script Name:  deploy_stack.sh
# Description:  Run this script to deploy an AWS Code Pipeline stack
#               for your pipelines repository.  Make sure that you
#               Fill out your pipelines_config.yml before running
#               this script.
#
#####################################################################
set -e

show_help() {
    echo ""
    echo "Deploy an AWS CodePipeline stack for the specified branch of your repository."
    echo "Make sure to fill out the pipelines_config.yml file first!"
    echo ""
    echo "SYNTAX:"
    echo "    ./deploy_stack.sh \$BRANCH "
    echo ""
    exit 1
}

# TODO: allow user to optionally pass specific config file to use
branch="$1"

if [[ -z $branch ]] ; then
    show_help
else
    echo "deploying ${branch} ..."
    export BRANCH=$branch

    # Deploy via cdk
    cdk deploy --require-approval never
fi




