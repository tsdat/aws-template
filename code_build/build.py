import json
import os
import shutil
import subprocess
import sys
import traceback
from typing import List, Optional

import boto3
from botocore.exceptions import ClientError

from build_utils.constants import Env, PipelineType, Trigger, Schedule
from build_utils.pipelines_config import PipelinesConfig, PipelineConfig, RunConfig


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

        def get_revision_id(summary: dict):
            revs = summary["sourceRevisions"]
            for rev in revs:
                if rev["actionName"] == "pipelines-source-action":
                    return rev["revisionId"]
            return None

        # First get the aws pipeline executions so we can find the current and previous
        # commit hashes for the pipelines repo.
        changed_pipelines = []
        code_pipeline_name = Env.AWS_PIPELINE_NAME
        command = [
            "aws",
            "codepipeline",
            "list-pipeline-executions",
            "--pipeline-name",
            code_pipeline_name,
        ]
        with open("out.json", "w") as outfile:
            subprocess.run(command, stdout=outfile)

        with open("out.json") as json_file:
            executions = json.load(json_file)
            summaries = executions["pipelineExecutionSummaries"]
            if len(summaries) == 1:
                # This is the first time this pipeline has ever built, so we are
                # going to build all the tsdat pipelines
                changed_pipelines = list(self.config.pipelines.keys())

            else:
                # The first summary is always the current code revisions
                current_hash = get_revision_id(summaries[0])
                previous_hash = None

                # Then we loop through the rest of the executions to find the most
                # recent one that succeeded, and use that one for the previous commit hash
                for summary in summaries[1:]:
                    if summary["status"] == "Succeeded":
                        previous_hash = get_revision_id(summary)
                        break

                # If we don't have a previous one that succeeded, then we build all
                if not previous_hash:
                    changed_pipelines = list(self.config.pipelines.keys())
                else:
                    # Do a git diff to find out the pipelines that changed
                    print(f"current hash = {current_hash}")
                    print(f"previous hash = {previous_hash}")
                    command = [
                        f"{Env.AWS_REPO_PATH}/code_build/find_modified_pipelines.sh",
                        Env.PIPELINES_REPO_PATH,
                        current_hash,
                        previous_hash,
                    ]
                    output = subprocess.check_output(command)
                    print(f"Output of diff command = {output}")

                    # Parse the output
                    with open("/tmp/changed_pipelines", "r") as file:
                        output = file.read()
                        print(f"Output of diff command = {output}")
                        changed_pipelines = (
                            output.strip().split()
                        )  # Parse the newline separated text into a list

                    print(f"changed pipelines = {changed_pipelines}")

        return changed_pipelines

    def copy_file(self, source_folder, dest_folder, file_relative_path):
        source_file = os.path.join(source_folder, file_relative_path)
        dest_file = os.path.join(dest_folder, file_relative_path)
        shutil.copy(source_file, dest_file)

    def build_base_image(self):
        """
        build the base Docker image that is shared by all pipelines.  This build runs
        first.

        """
        # Build context is the pipeline repo root
        # Build file is code_build/docker/Dockerfile.base
        # Copy over all the build-provided files that need to be built into base image
        source_folder = os.path.join(Env.AWS_REPO_PATH, "code_build", "docker")
        destination_folder = Env.PIPELINES_REPO_PATH
        files = os.listdir(source_folder)
        for file in files:
            self.copy_file(source_folder, destination_folder, file)

        # We also need to copy the build utils into the pipelines repo
        shutil.copytree(
            os.path.join(Env.AWS_REPO_PATH, "build_utils"),
            os.path.join(destination_folder, "build_utils"),
        )

        # We also need to copy over the pipelines config file
        self.copy_file(Env.AWS_REPO_PATH, destination_folder, "pipelines_config.yml")

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

    def deploy_lambda(self, pipeline_config: PipelineConfig):
        pipeline_name = pipeline_config.name
        print(
            f"Deploying lambdas and associated resources for pipeline: {pipeline_name}"
        )
        run_config: RunConfig

        # We are creating lambdas for each config so that we can properly pass
        # relevant environment variables and control the S3 triggers
        for config_id, run_config in pipeline_config.configs.items():
            # TODO: we probably also want to add alarms for each lambda.
            f = self.get_lambda(pipeline_config, run_config)
            if not f:
                self.create_lambda(pipeline_config, run_config)
            else:
                self.update_lambda(pipeline_config, run_config)

    def get_lambda(
        self, pipeline_config: PipelineConfig, run_config: RunConfig
    ) -> Optional[dict]:
        """
        Gets data about a Lambda function.

        :return: The lambda function's data or None if it does not exist.
        """
        data = None
        try:
            data = self.lambda_client.get_function(
                FunctionName=self.config.get_lambda_name(
                    pipeline_config.name, run_config.id
                )
            )
        except self.lambda_client.exceptions.ResourceNotFoundException:
            # This means the lambda does not exist.
            pass

        return data

    def create_lambda(self, pipeline_config: PipelineConfig, run_config: RunConfig):
        """
        Creates a new Lambda function.

        """
        image_uri = self.config.get_image_uri(pipeline_config.name)
        lambda_name = self.config.get_lambda_name(pipeline_config.name, run_config.id)

        # This will raise an exception if something goes wrong
        # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/lambda/client/create_function.html
        response = self.lambda_client.create_function(
            FunctionName=lambda_name,
            PackageType="Image",
            Role=Env.LAMBDA_ROLE_ARN,
            Code={
                "ImageUri": image_uri,
            },
            Environment=self._get_lambda_env(pipeline_config, run_config),
            Timeout=120,
            MemorySize=1024,
        )
        lambda_arn = response["FunctionArn"]

        # Wait for the Lambda function to be fully created before continuing
        waiter = self.lambda_client.get_waiter("function_active_v2")
        waiter.wait(FunctionName=lambda_name)

        print(
            f"Lambda function '{lambda_name}' created successfully with ARN:"
            f" {lambda_arn}"
        )

    def update_lambda(self, pipeline_config: PipelineConfig, run_config: RunConfig):
        """
        Update the lambda's environment variables with new build number
        (The only thing we need to change are the environment variables.)
        """
        lambda_name = self.config.get_lambda_name(pipeline_config.name, run_config.id)
        image_uri = self.config.get_image_uri(pipeline_config.name)
        response = self.lambda_client.update_function_configuration(
            FunctionName=lambda_name,
            PackageType="Image",
            Role=Env.LAMBDA_ROLE_ARN,
            Code={
                "ImageUri": image_uri,
            },
            Environment=self._get_lambda_env(pipeline_config, run_config),
            Timeout=120,
            MemorySize=1024,
        )

        print(
            f"Lambda function '{lambda_name}' updated successfully with ARN:"
            f" {response['FunctionArn']}"
        )

    def _get_lambda_env(self, pipeline_config: PipelineConfig, run_config: RunConfig):
        return {
            "Variables": {
                "PIPELINE_NAME": pipeline_config.name,
                "CONFIG_ID": run_config.id,
                "RETAIN_INPUT_FILES": "true",
                "CODE_VERSION": Env.CODE_VERSION,
                "TSDAT_S3_BUCKET_NAME": self.config.output_bucket_name,
                "BRANCH": Env.BRANCH,
            }
        }

    def s3_policy_exists(self, pipeline_config: PipelineConfig, run_config: RunConfig):
        statement_id = self.config.get_bucket_trigger_statement_id(
            pipeline_config.name, run_config.id
        )
        try:
            lambda_arn = self.config.get_lambda_arn(pipeline_config.name, run_config.id)
            policy = self.lambda_client.get_policy(FunctionName=lambda_arn)
            return statement_id in policy["Policy"]
        except Exception:
            # traceback.print_exc(file=sys.stdout)
            return False

    def s3_folder_exists(self, bucket_name, path_to_folder):
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=bucket_name, Prefix=path_to_folder
            )
            return "Contents" in response
        except Exception:
            return False

    def add_or_update_s3_triggers(self):
        """
        For all pielines, add a single S3 notification configuration to trigger
        the respective lambdas depending upon the path.

        """
        bucket_name = self.config.input_bucket_name
        notification_configuration = {"LambdaFunctionConfigurations": []}
        print(f"Setting up S3 lambda triggers for bucket {bucket_name}.")

        for pipeline_config in self.config.pipelines.values():
            for run_config in pipeline_config.configs.values():
                lambda_arn = self.config.get_lambda_arn(
                    pipeline_config.name, run_config.id
                )

                # Add the S3 event trigger
                if pipeline_config.trigger == Trigger.S3:
                    # Give the S3 input bucket permission to invoke the lambda function
                    statement_id = self.config.get_bucket_trigger_statement_id(
                        pipeline_config.name, run_config.id
                    )
                    if not self.s3_policy_exists(pipeline_config, run_config):
                        self.lambda_client.add_permission(
                            FunctionName=lambda_arn,
                            StatementId=statement_id,
                            Action="lambda:InvokeFunction",
                            Principal="s3.amazonaws.com",
                            SourceArn=self.config.input_bucket_arn,
                        )

                    subpath: str = run_config.input_bucket_path
                    subpath = f"{subpath}/" if not subpath.endswith("/") else subpath
                    notification_configuration["LambdaFunctionConfigurations"].append(
                        {
                            "Id": self.config.get_bucket_notification_id(
                                pipeline_config.name, run_config.id
                            ),
                            "LambdaFunctionArn": lambda_arn,
                            "Events": ["s3:ObjectCreated:*"],
                            "Filter": {
                                "Key": {
                                    "FilterRules": [
                                        {"Name": "prefix", "Value": subpath},
                                    ]
                                }
                            },
                        },
                    )

                    # Make sure the bucket folder exists (so we can see it in the UI)
                    subpath: str = run_config.input_bucket_path
                    subpath = f"{subpath}/" if not subpath.endswith("/") else subpath
                    if not self.s3_folder_exists(bucket_name, subpath):
                        self.s3_client.put_object(Bucket=bucket_name, Key=(subpath))

        # Create the S3 event trigger (this will replace any existing notification config)
        print(f"notification configuration = {notification_configuration}")
        self.s3_client.put_bucket_notification_configuration(
            Bucket=bucket_name,
            NotificationConfiguration=notification_configuration,
        )
        print(f"S3 event trigger set up for bucket {self.config.input_bucket_arn}")

    def add_or_update_cron_schedules(self):
        """Update the cron rules for to trigger the lambda function for the
        given pipeline and config.

        """
        for pipeline_config in self.config.pipelines.values():
            for run_config in pipeline_config.configs.values():
                lambda_arn = self.config.get_lambda_arn(
                    pipeline_config.name, run_config.id
                )

                lambda_arn = self.config.get_lambda_arn(
                    pipeline_config.name, run_config.id
                )

                # TODO: Should we schedule all crons at same time, or should we stagger them?
                # Should we give user control to specify exact cron expression?
                cron_expression = pipeline_config.cron_expression

                # Create an eventbridge event rule
                rule_name = self.config.get_cron_rule_name(
                    pipeline_config.name, run_config.id
                )

                # put_rule will create or update the rule.  We are always creating the rule
                # so we can switch from Cron to S3 trigger if needed.  If the trigger is S3, then
                # we will disable the rule, so nothing happens.
                state = (
                    "ENABLED" if pipeline_config.trigger == Trigger.Cron else "DISABLED"
                )
                print(f"Updating cron rule for {lambda_arn} {cron_expression} {state}")
                response = self.events_client.put_rule(
                    Name=rule_name, ScheduleExpression=cron_expression, State=state
                )
                rule_arn = response[
                    "RuleArn"
                ]  # make sure this is the right field in the response

                # Add the Lambda function as a target for the rule
                print(f"Updating rule target for {lambda_arn}")
                response = self.events_client.put_targets(
                    Rule=rule_name,
                    Targets=[
                        {
                            "Id": "1",
                            "Arn": lambda_arn,
                        }
                    ],
                )

                # Now add permission for our lambda to be triggered by the cron rule
                statement_id = self.config.get_cron_trigger_statement_id(
                    pipeline_config.name, run_config.id
                )
                try:
                    self.lambda_client.add_permission(
                        FunctionName=lambda_arn,
                        StatementId=statement_id,
                        Action="lambda:InvokeFunction",
                        Principal="events.amazonaws.com",
                        SourceArn=rule_arn,
                    )
                except self.lambda_client.exceptions.ResourceConflictException:
                    # This means the permission already exists
                    pass

                print(
                    f"Cron trigger rule set up for pipeline{pipeline_config.name}, run"
                    f" {run_config.id}.  Schedule is: {cron_expression}.  Rule arn ="
                    f" {rule_arn}"
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
            pipeline_config: PipelineConfig = self.config.pipelines.get(
                tsdat_pipeline_name
            )
            self.build_pipeline_docker_image(tsdat_pipeline_name)
            self.deploy_lambda(pipeline_config)

        # If the pipeline is an S3 trigger, we have to set the notification policy all
        # in one big block
        self.add_or_update_s3_triggers()

        # Update cron triggers for all pipelines (will disable if not used)
        self.add_or_update_cron_schedules()
