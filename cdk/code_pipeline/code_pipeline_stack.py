from aws_cdk import (
    Stack,
    Fn
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

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.config: PipelinesConfig = kwargs.get('config')
        
        # Create the code pipeline stack
        self.create_code_pipeline()
        
        # Create the input/output buckets
        self.create_buckets()
        
        
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
            branch=Env.DEPLOYMENT_NAME,
            trigger_on_push=False,
        )
        return (output, action)
    
    def create_code_pipeline(self):
        """Create the code pipeline in AWS.
        This pipeline sets up an automated build that is connected to the two GitHub repositories
        (pipelines & aws template) via a CodeStar connection.  Whenever one of these repos change,
        then depending upon the modified files, the appropriate pipelines will be deployed to AWS.
        Pipeline deployment involves:
         1) creating the docker image for the pipeline & lambda functions
         2) deploying the lambda function for the pipeline
         3) if the trigger is cron, also deploying the lambda function for the cron
         4) deploying sns event topics for the pipeline
         5) if the trigger is s3, hooking up the topics to the right folder path
        """
        deployment_name = Env.DEPLOYMENT_NAME

        # Set up code sources used in the source stage of the code pipeline
        pipelines_artifact, pipelines_source_action = self.get_github_source(self.config.pipelines_repo, 'pipelines')
        aws_build_artifact, aws_build_source_action = self.get_github_source(self.config.aws_build_repo, 'aws_build')
        
        # Create a project to wrap the code pipeline and code build.  It will run from the aws-template repository.
        project_name = f"{self.config.pipelines_repo}-build-{Env.DEPLOYMENT_NAME}"
        build_project = PipelineProject(
            self,
            project_name,
            build_spec=BuildSpec.from_source_filename("cdk/buildspec.yml"),
            environment=BuildEnvironment(
                build_image=LinuxBuildImage.AMAZON_LINUX_2_4,
                compute_type=ComputeType.MEDIUM,
                privileged=True,
            ),
            # BRANCH and REPO_NAME are used to name the image and AWS resources that are created by the build
            environment_variables={
                "AWS_ACCOUNT_ID": BuildEnvironmentVariable(value=self.config.account_id),
                "AWS_DEFAULT_REGION": BuildEnvironmentVariable(value=self.config.region),
                "PIPELINES_REPO_NAME":  BuildEnvironmentVariable(value=self.config.pipelines_repo),
                "CODEBUILD_PIPELINE_NAME": project_name,
                "BRANCH": BuildEnvironmentVariable(value=Env.DEPLOYMENT_NAME),
            },
        )

        # Give the pipeline the correct permissions to read/write images in Elastic Container Registry
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
                ],
                resources=["*"],
            )
        )

        # Now define the Code Build action to run in the build stage
        build_action = CodeBuildAction(
            action_name=project_name,
            input=aws_build_artifact,
            project=build_project,
            extra_inputs=[pipelines_artifact],
            variables_namespace="BuildVariables",
            environment_variables={},
        )

        # Define the pipeline
        Pipeline(
            self,
            project_name,
            pipeline_name=project_name,
            cross_account_keys=False,
            stages=[
                StageProps(
                    stage_name=f"{Env.DEPLOYMENT_NAME}-source",
                    actions=[
                        aws_build_source_action,
                        pipelines_source_action
                    ],
                ),
                StageProps(
                    stage_name=f"{deployment_name}-build", actions=[build_action]
                ),
            ],
        )  
        
    def create_buckets(self):
        pass