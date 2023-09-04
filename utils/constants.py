import os

class Env:
    """This class contains a mixture of environment variables used in the CDK deploy as well as in the
    aws code build.
    """
    # Deploment name must match a branch in your tsdat pipelines repository (e.g., test or release)
    DEPLOYMENT_NAME = os.environ.get('DEPLOYMENT_NAME', 'test')
    
    # Passed in to the build node from the stack, this provides the real name of the repository
    PIPELINES_REPO_NAME = os.environ.get('PIPELINES_REPO_NAME')
    
    # Local path to the pipelines repo on the aws build node.  This source folder is located at env $CODEBUILD_SRC_DIR_pipelines
    PIPELINES_REPO_PATH = os.environ.get('CODEBUILD_SRC_DIR_pipelines')
    
    # Local path to the aws template repo on the aws build node.  This source folder is located at env $CODEBUILD_SRC_DIR
    AWS_REPO_PATH = os.environ.get('CODEBUILD_SRC_DIR')
    
    # The branch of the pipelines repository that is being deployed (i.e., release, test, etc.)
    BRANCH = os.environ.get('PIPELINES_REPO_NAME')
    
    # The name of the CodeBuild Pipeline that is running the build
    CODEBUILD_PIPELINE_NAME = os.environ.get('CODEBUILD_PIPELINE_NAME')
    
    AWS_ACCOUNT_ID = os.environ.get('AWS_ACCOUNT_ID')
    AWS_DEFAULT_REGION = os.environ.get('AWS_DEFAULT_REGION')
    

class StackNames:
    CODE_PIPELINE = f'code-pipeline-{Env.DEPLOYMENT_NAME}'
