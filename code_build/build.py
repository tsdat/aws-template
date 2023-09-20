import json
import os
import shutil
import subprocess
from typing import List, Optional

import boto3
from botocore.exceptions import ClientError

from utils.constants import Env, PipelineType, Trigger, Schedule
from utils.pipelines_config import PipelinesConfig, PipelineConfig, RunConfig


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
        self.lambda_client = boto3.client("lambda", region_name=self.config.region)
        self.events_client = boto3.client("events", region_name=self.config.region)
        self.s3_client = boto3.client("s3", region_name=self.config.region)

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

        # We also need to copy over the pipelines config file
        source_file = os.path.join(Env.AWS_REPO_PATH, "pipelines_config.yml")
        dest_file = os.path.join(destination_folder, "pipelines_config.yml")
        shutil.copy(source_file, dest_file)

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
        print(
            f"Deploying lambda and associated resources for pipeline: {pipeline_name}"
        )
        pipeline_config: PipelineConfig = self.config.pipelines.get(pipeline_name)

        f = self.get_lambda(pipeline_name)
        if not f:
            self.create_lambda(pipeline_name)
        else:
            self.update_lambda(pipeline_name)

        if pipeline_config.trigger == Trigger.Cron:
            self.add_or_update_schedule(pipeline_name)

        elif pipeline_config.trigger == Trigger.S3:
            self.add_or_update_s3_trigger(pipeline_name)

    def get_lambda(self, tsdat_pipeline_name: str) -> Optional[dict]:
        """
        Gets data about a Lambda function.

        :param tsdat_pipeline_name: The name of the tsdat pipeline to get the lambda for.
        :
        :return: The lambda function's data or None if it does not exist.
        """
        data = None
        try:
            data = self.lambda_client.get_function(
                FunctionName=self.config.get_lambda_name(tsdat_pipeline_name)
            )
        except self.lambda_client.exceptions.ResourceNotFoundException:
            # This means the lambda does not exist.
            pass

        return data

    def create_lambda(self, tsdat_pipeline_name):
        """
        Creates a new Lambda function.

        :param tsdat_pipeline_name: The name of the tsdat pipeline to create a lambda for.

        """
        image_uri = self.config.get_image_uri(tsdat_pipeline_name)
        lambda_name = self.config.get_lambda_name(tsdat_pipeline_name)

        # This will raise an exception if something goes wrong
        # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/lambda/client/create_function.html
        response = self.lambda_client.create_function(
            FunctionName=lambda_name,
            PackageType="Image",
            Role=Env.LAMBDA_ROLE_ARN,
            Code={
                "ImageUri": image_uri,
            },
            Environment=self._get_lambda_env(tsdat_pipeline_name),
            Timeout=120,
            MemorySize=1024,
        )
        lambda_arn = response["FunctionArn"]

        print(
            f"Lambda function '{lambda_name}' created successfully with ARN:"
            f" {lambda_arn}"
        )

    def update_lambda(self, tsdat_pipeline_name):
        """
        Update the lambda's environment variables with new build number
        (The only thing we need to change are the environment variables.)

        Args:
            tsdat_pipeline_name (str): The name of the tsdat pipeline to update a lambda for
        """
        lambda_name = self.config.get_lambda_name(tsdat_pipeline_name)
        response = self.lambda_client.update_function_configuration(
            FunctionName=lambda_name,
            Environment=self._get_lambda_env(tsdat_pipeline_name),
        )

        print(
            f"Lambda function '{lambda_name}' updated successfully with ARN:"
            f" {response['FunctionArn']}"
        )

    def _get_lambda_env(self, tsdat_pipeline_name: str):
        return {
            "Variables": {
                "PIPELINE_NAME": tsdat_pipeline_name,
                "RETAIN_INPUT_FILES": "true",
                "CODE_VERSION": (
                    "aa61fff393e92591efa19e43ac2d1bcc428f5a8f"
                ),  # use $CODEBUILD_RESOLVED_SOURCE_VERSION (which is commit hash)
                "TSDAT_S3_BUCKET_NAME": self.config.input_bucket_name,
            }
        }

    def s3_policy_exists(self, tsdat_pipeline_name):
        try:
            lambda_arn = self.config.get_lambda_arn(tsdat_pipeline_name)
            policy = self.lambda_client.get_policy(FunctionName=lambda_arn)
            print(f"lambda policy is: {policy}")
            print(f"type of policy is {type(policy)}")
        except:
            return False
        return "S3InputBucketInvokeLambda" in policy["Policy"] 

    def add_or_update_s3_trigger(self, tsdat_pipeline_name):
        """
        For each run id in the pipeline, we look up the bucket subpath where
        its raw files will be dropped, and then we create an event trigger
        to trigger the pipeline's lambda function.

        Args:
            tsdat_pipeline_name (str): pipeline name
        """
        bucket_name = self.config.input_bucket_name
        lambda_arn = self.config.get_lambda_arn(tsdat_pipeline_name)
        pipeline_config: PipelineConfig = self.config.pipelines.get(tsdat_pipeline_name)
        run_config: RunConfig

        print(
            f"Setting up S3 trigger for Lambda function {lambda_arn} in bucket"
            f" {bucket_name}."
        )

        # Give the S3 input bucket permission to invoke the lambda function
        if not self.s3_policy_exists(tsdat_pipeline_name):
            self.lambda_client.add_permission(
                FunctionName=lambda_arn,
                StatementId="S3InputBucketInvokeLambda",
                Action="lambda:InvokeFunction",
                Principal="s3.amazonaws.com",
                SourceArn=self.config.input_bucket_arn,
            )

        # Create the S3 event trigger (this will replace any existing notification config)
        self.s3_client.put_bucket_notification_configuration(
            Bucket=bucket_name,
            NotificationConfiguration={
                "LambdaFunctionConfigurations": [
                    {
                        "Id": self.config.get_bucket_notification_id(
                            tsdat_pipeline_name
                        ),
                        "LambdaFunctionArn": lambda_arn,
                        "Events": ["s3:ObjectCreated:*"],
                    },
                ]
            },
        )
        print(f"S3 event trigger set up for bucket {self.config.input_bucket_arn}")

        run_config: RunConfig
        for run_config in pipeline_config.configs.values():
            subpath: str = run_config.input_bucket_path

            # Make sure the bucket folder exists (so we can see it in the UI)
            subpath = f"{subpath}/" if not subpath.endswith("/") else subpath
            self.s3_client.put_object(Bucket=bucket_name, Key=(subpath))

    def add_or_update_schedule(self, tsdat_pipeline_name: str):
        """Update the cron rules for to trigger the lambda function.

        Args:
            tsdat_pipeline_name (str): the tsdat pipeline name
        """
        lambda_arn = self.config.get_lambda_arn(tsdat_pipeline_name)
        pipeline_config: PipelineConfig = self.config.pipelines.get(tsdat_pipeline_name)

        # TODO: Should we schedule all crons at same time, or should we stagger them?
        # Should we give user control to specify exact cron expression?
        cron_expression = self.config.pipelines.get(tsdat_pipeline_name).cron_expression
        config: RunConfig

        for config_id, config in pipeline_config.configs.items():
            # Create an eventbridge event rule
            rule_name = self.config.get_cron_rule_name(tsdat_pipeline_name, config_id)

            # Check if the rule exists:
            rule_exists = True
            try:
                response = self.events_client.describe_rule(Name=rule_name)
            except self.events_client.exceptions.ResourceNotFoundException as e:
                rule_exists = False

            # put_rule will create or update the rule
            response = self.events_client.put_rule(
                Name=rule_name, ScheduleExpression=cron_expression, State="ENABLED"
            )
            rule_arn = response[
                "RuleArn"
            ]  # make sure this is the right field in the response

            # Add the Lambda function as a target for the rule
            # We need to pass custom input identifying the pipeline and run id
            input = {"config_id": config_id}

            # We only need to set the target and permissions if the rule doesn't already exist
            if not rule_exists:
                response = self.events_client.put_targets(
                    Rule=rule_name,
                    Targets=[
                        {
                            "Id": "1",
                            "Arn": lambda_arn,
                            "Input": json.dumps(input),
                        }
                    ],
                )

                # Now add permission for our lambda to be triggered by the cron rule
                self.lambda_client.add_permission(
                    FunctionName=self.config.get_lambda_name(tsdat_pipeline_name),
                    StatementId="cron-lambda-trigger",
                    Action="lambda:InvokeFunction",
                    Principal="events.amazonaws.com",
                    SourceArn=rule_arn,
                )

            print(
                f"Cron trigger rule set up for pipeline{tsdat_pipeline_name}, run"
                f" {config_id}.  Schedule is: {cron_expression}.  Rule arn = {rule_arn}"
            )

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
