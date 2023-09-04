#!/usr/bin/bash
#####################################################################
# Script Name:  build_docker.sh
# Description:  Script to build a docker image.
# 
# Arguments:
#     1) folder to run the build from 
#     2) name of dockerfile to run
#     3) image url to push
#     4) name of pipeline to build
#####################################################################

context_folder="$1"
dockerfile="$2"
image_uri="$3"
pipeline_name="$4"

# First perform docker login into our ecr repository
aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin  $AWS_ACCOUNT_ID

# Build the image and push to ECR
cd ${context_folder}
docker build --build-arg PIPELINE_NAME=$pipeline_name -t $image_uri -f $dockerfile .
docker push $image_uri
