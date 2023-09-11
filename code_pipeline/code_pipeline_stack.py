from typing import Optional
from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_s3 as s3,
    aws_ecr as ecr,
    aws_lambda as _lambda,
    aws_iam as iam,
)
from aws_cdk.aws_codebuild import (
    PipelineProject,
    BuildSpec,
    BuildEnvironmentVariable,
    BuildEnvironment,
    LinuxBuildImage,
    ComputeType,
)
from aws_cdk.aws_codepipeline_actions import (
    CodeStarConnectionsSourceAction,
    CodeBuildAction,
)
from aws_cdk.aws_codepipeline import Artifact, Pipeline, StageProps
from aws_cdk.aws_iam import PolicyStatement, Effect

from constructs import Construct

from utils.pipelines_config import PipelinesConfig
from utils.constants import Env


class CodePipelineStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        config: Optional[PipelinesConfig],
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.config: PipelinesConfig = config if config else PipelinesConfig()

        # Create the input/output buckets
        self.create_buckets()

        # Create a role that will be used to execute lambda functions that gives them
        # read/write access to the input and output buckets
        lambda_role_arn = self.create_lambda_role()

        # Create the ECR repo
        self.create_ecr_repository()

        # Create the code pipeline
        self.create_code_pipeline(lambda_role_arn)

        # TODO: May need an sns topic for build alert messages

    def get_github_source(self, repo, output_name):
        """Create the GitHub source resource for a code pipeline via a CodeStar connection.
        The Artifact is the object used in the build.  The action is how the code is
        pulled from GitHub.

        Args:
            repo (str): a repository name from pipelines_config

        Returns:
            Tuple(Artifact, CodeStarConnectionsSourceAction):
        """
        output = Artifact(artifact_name=output_name)
        action = CodeStarConnectionsSourceAction(
            action_name=f"{repo}-source-action",
            owner=self.config.github_org,
            repo=repo,
            output=output,
            connection_arn=self.config.github_codestar_arn,
            branch=Env.BRANCH,
            trigger_on_push=True,
        )
        return (output, action)

    def create_code_pipeline(self, lambda_role_arn):
        """Create the code pipeline in AWS.
        This pipeline sets up an automated build that is connected to the two GitHub repositories
        (pipelines & aws template) via a CodeStar connection.  Whenever one of these repos change,
        then depending upon the modified files, the appropriate pipelines will be deployed to AWS.
        Pipeline deployment involves:
         1) creating the docker images for the pipeline lambdas
         2) deploying the lambda function for the pipeline
         3) if the trigger is cron, set a schedule for the lambda
         4) If the trigger is s3, create sns events to trigger lambda for the raw folder path
        """
        deployment_name = Env.BRANCH

        # Set up code sources used in the source stage of the code pipeline
        pipelines_artifact, pipelines_source_action = self.get_github_source(
            self.config.pipelines_repo_name, "pipelines"
        )
        aws_build_artifact, aws_build_source_action = self.get_github_source(
            self.config.aws_repo_name, "aws_build"
        )

        # Create a project to wrap the code pipeline and code build.  It will run from the aws-template repository.
        project_name = self.config.code_pipeline_project_name
        pipeline_name = f"{project_name}-pipeline"
        build_project = PipelineProject(
            self,
            f"{project_name}-project",
            build_spec=BuildSpec.from_source_filename("buildspec.yml"),
            environment=BuildEnvironment(
                build_image=LinuxBuildImage.AMAZON_LINUX_2_5,
                compute_type=ComputeType.MEDIUM,
                privileged=True,
            ),
            # BRANCH and REPO_NAME are used to name the image and AWS resources that are created by the build
            environment_variables={
                "AWS_ACCOUNT_ID": BuildEnvironmentVariable(
                    value=self.config.account_id
                ),
                "AWS_DEFAULT_REGION": BuildEnvironmentVariable(
                    value=self.config.region
                ),
                "PIPELINES_REPO_NAME": BuildEnvironmentVariable(
                    value=self.config.pipelines_repo_name
                ),
                "AWS_PIPELINE_NAME": BuildEnvironmentVariable(value=pipeline_name),
                "BRANCH": BuildEnvironmentVariable(value=Env.BRANCH),
                # This ARN is not one we can dynamically determine, so we have to pass it in
                "LAMBDA_ROLE_ARN": BuildEnvironmentVariable(value=lambda_role_arn),
            },
        )

        # Give the pipeline the correct permissions to read/write any images in Elastic Container Registry
        build_project.add_to_role_policy(
            PolicyStatement(
                effect=Effect.ALLOW,
                actions=[
                    "ecr:GetAuthorizationToken",
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:GetRepositoryPolicy",
                    "ecr:DescribeRepositories",
                    "ecr:ListImages",
                    "ecr:DescribeImages",
                    "ecr:BatchGetImage",
                    "ecr:GetLifecyclePolicy",
                    "ecr:GetLifecyclePolicyPreview",
                    "ecr:ListTagsForResource",
                    "ecr:DescribeImageScanFindings",
                    "ecr:InitiateLayerUpload",
                    "ecr:UploadLayerPart",
                    "ecr:CompleteLayerUpload",
                    "ecr:PutImage",
                    "ecs:UpdateService",
                    "codepipeline:ListPipelineExecutions",
                    "codepipeline:GetPipelineState",
                    "lambda:GetFunction",
                ],
                resources=["*"],
            )
        )

        # Now define the Code Build action to run in the build stage
        build_action = CodeBuildAction(
            action_name=f"{project_name}-action",
            input=aws_build_artifact,
            project=build_project,
            extra_inputs=[pipelines_artifact],
            variables_namespace="BuildVariables",
            environment_variables={},
        )

        # Define the pipeline
        Pipeline(
            self,
            pipeline_name,
            pipeline_name=pipeline_name,
            cross_account_keys=False,
            stages=[
                StageProps(
                    stage_name=f"{Env.BRANCH}-source",
                    actions=[aws_build_source_action, pipelines_source_action],
                ),
                StageProps(
                    stage_name=f"{deployment_name}-build", actions=[build_action]
                ),
            ],
        )

    def create_buckets(self):
        input_bucket = s3.Bucket(
            self,
            self.config.input_bucket_name,  # ID
            bucket_name=self.config.input_bucket_name,
            auto_delete_objects=True,  # Remove bucket when stack is destroyed
            removal_policy=RemovalPolicy.DESTROY,
        )

        output_bucket = s3.Bucket(
            self,
            self.config.output_bucket_name,  # ID
            bucket_name=self.config.output_bucket_name,
            auto_delete_objects=True,  # Remove bucket when stack is destroyed
            removal_policy=RemovalPolicy.DESTROY,
        )
        return input_bucket, output_bucket

    def create_ecr_repository(self):
        ecr_repository = ecr.Repository(
            self,
            self.config.ecr_repo_name,
            repository_name=self.config.ecr_repo_name,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # TODO: can we add tags to the repo?

    def create_lambda_role(self) -> str:
        # Create an IAM role for Lambda execution
        lambda_role = iam.Role(
            self,
            self.config.lambda_role_name,
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="IAM role for Lambda execution with access to S3 buckets.",
        )

        # Attach a basic Lambda execution policy to the role
        lambda_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSLambdaBasicExecutionRole"
            )
        )

        # Now add permissions to read and write to the input and output buckets
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                resources=[
                    f"arn:aws:s3:::{self.config.input_bucket_name}/*",
                    f"arn:aws:s3:::{self.config.output_bucket_name}/*",
                ],
                actions=["s3:*"],
            )
        )
        # return the arn of the role
        return lambda_role.role_arn
