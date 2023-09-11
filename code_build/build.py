import os
import shutil
import subprocess
from typing import List, Optional

import boto3
from botocore.exceptions import ClientError

from utils.constants import Env
from utils.pipelines_config import PipelinesConfig


class TsdatPipelineBuild:
    """TsdatPipelineBuild

    This build will run in CodePipeline from the $CODEBUILD_SRC_DIR folder, which
    is where the buildspec.yml file is located.  The other source repo (for the
    tsdat pipelines) will be in the $CODEBUILD_SRC_DIR_pipelines folder.

    All of the resource names, which can be derived from the account and region,
    will come from the PipelinesConfig object.  However, since the arns are
    dynamic, in cases where we have to pass an arn of an object that was
    created with the cdk stack, then the cdk stack will pass these arns to the
    build environment via an environment parameter.  These parameters can be
    accessed via the constants.Env object.

    """

    def __init__(self):
        """Constructor"""
        # TODO: allow user to specific pipelines config file location
        self.config: PipelinesConfig = PipelinesConfig()
        self.lambda_client = boto3.client("lambda", region_name=Env.AWS_DEFAULT_REGION)

    def find_changed_tsdat_pipelines(self) -> List[str]:
        """
        Use git diff to find out which pipelines have had modifications from the latest
        commit.

        Raises:
            Exception: If the git diff command fails.

        Returns:
            List[str]: List of pipeline names who have had code changes in the latest
            commit.

        """
        changed_pipelines = []
        command = (
            f"cd {Env.PIPELINES_REPO_PATH} &&"
            f" {Env.AWS_REPO_PATH}/code_build/find_modified_pipelines.sh"
        )

        completed_process = subprocess.run(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if completed_process.returncode == 0:
            output = completed_process.stdout
            changed_pipelines = (
                output.strip().split()
            )  # Parse the newline separated text into a list
            print(changed_pipelines)

        else:
            raise Exception(f"Failed to perform git diff: {completed_process.stderr}")

        return changed_pipelines

    def build_base_image(self):
        """
        build the base Docker image that is shared by all pipelines.  This build runs
        first.

        """
        # Build context is the pipeline repo root
        # Build file is code_build/docker/Dockerfile.base
        source_folder = os.path.join(Env.AWS_REPO_PATH, "code_build", "docker")
        destination_folder = Env.PIPELINES_REPO_PATH

        # Copy over all the build-provided files that need to be built into base image
        files = os.listdir(source_folder)
        for file in files:
            source_file = os.path.join(source_folder, file)
            destination_file = os.path.join(destination_folder, file)
            shutil.copy(source_file, destination_file)

        self.build_image(Env.PIPELINES_REPO_NAME, "Dockerfile.base")

    def build_pipeline_docker_image(self, pipeline_name: str):
        """
        Build and push the docker image for the given pipeline.

        Args:
            pipeline_name (str): name of the tsdat pipeline to build

        """
        self.build_image(pipeline_name, "Dockerfile.pipeline")

    def build_image(self, pipeline_name: str, dockerfile: str):
        """
        Run the docker build script for the given pipeline.

        Args:
            pipeline_name (str): pipeline name to build (e.g., metocean)
            dockerfile (str): dockerfile to use (e.g., Dockerfile.pipeline)

        Raises:
            Exception: If the docker command fails

        """

        # e.g., 809073466396.dkr.ecr.us-west-2.amazonaws.com/ingest-buoy-test
        image_tag_name = self.config.get_image_tag(pipeline_name)
        image_uri = self.config.get_image_uri(pipeline_name)
        base_image_uri = self.config.get_image_uri(Env.PIPELINES_REPO_NAME)
        print(f"Building image {image_tag_name} with file {dockerfile} ...")

        # Run the docker build command
        script_path = os.path.join(Env.AWS_REPO_PATH, "code_build", "build_docker.sh")
        cmd = (
            f"{script_path} {Env.PIPELINES_REPO_PATH} {dockerfile} {image_uri}"
            f" {base_image_uri} {pipeline_name}"
        )
        proc = subprocess.run(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if proc.returncode != 0:
            raise Exception(f"Failed to run docker build: {proc.stderr}")

    def deploy_lambda(self, pipeline_name: str):
        lambda_name = f"{pipeline_name}-{Env.BRANCH}"
        lambda_fn = self.get_lambda(lambda_name)

        if not lambda_fn:
            # Create the lambda

            # Env vars needed:
            # process type (Ingest or VAP)
            # pipeline name
            # Add permissions to the lambda to exec and read/write to buckets
            # Schedule the lambda if it's a cron
            # Set up bucket event triggers if not cron

            pass

        else:
            # We need to update the lambda's metadata
            pass

    def get_lambda(self, function_name: str) -> Optional[dict]:
        """
        Gets data about a Lambda function.

        Args:
            function_name (str): The name of the lambda function.

        Raises:
            Exception: If the lambda call fails.

        Returns:
            dict: A dict with parameters about the lambda function

        """
        try:
            return self.lambda_client.get_function(FunctionName=function_name)

        except ClientError as err:
            if err.response["Error"]["Code"] == "ResourceNotFoundException":
                return None
            else:
                raise err

    def build(self):
        print(f"Building CodeBuild pipeline: {Env.AWS_PIPELINE_NAME}")

        # Step 1:  Build the base image.
        # All the pipelines from the same repo share the same base image
        print("Building base image...")
        self.build_base_image()

        # Step 2: Build the pipeline images.

        # Get the trigger, one of two types: "StartPipelineExecution" or "Webhook"
        trigger = Env.TRIGGER
        print(f"Build trigger is {trigger}")

        if trigger == "StartPipelineExecution":
            print("This was a manual trigger, so we build all the pipelines.")
            tsdat_pipelines_to_build = list(self.config.pipelines.keys())
        else:
            # This was a code trigger, only build the pipelines that changed
            print(
                "This was a webhook trigger, so we build only pipelines that changed."
            )
            tsdat_pipelines_to_build = self.find_changed_tsdat_pipelines()

        for tsdat_pipeline_name in tsdat_pipelines_to_build:
            print(f"Building Tsdat pipeline: {tsdat_pipeline_name}")
            self.build_pipeline_docker_image(tsdat_pipeline_name)
            self.deploy_lambda(tsdat_pipeline_name)
