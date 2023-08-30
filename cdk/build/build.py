from utils.constants import Env


class PipelineBuild():
    
    def build(self):
        print(f'Environment is {Env.DEPLOYMENT_NAME}')
        
        # This build runs from the $CODEBUILD_SRC_DIR/cdk folder
        # Pipelines repo is located at env $CODEBUILD_SRC_DIR_pipelines
        
        # Build Docker image for the changed pipelines
        # ENV Parameters needed, passed from our stack:
        #   PIPELINES_REPO_NAME
        #   BRANCH 
        #   CODEBUILD_PIPELINE_NAME
        #   input and output bucket names  (needed for permissions on the lambda function and sns triggers)
        
        # ecr_repo_name = PIPELINES_REPO_NAME
        # image_tag_name = f'{PIPELINES_REPO_NAME}-{BRANCH}.{PIPELINE_NAME}
        
        # ECR_REPO=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com/$PIPELINES_REPO_NAME
        
       
        # Can we figure out what tsdat pipeline triggered the build?
        # TSDAT_PIPELINE = ?
        
        # What does Matt do?
        # 1) copies the Dockerfile.ingest into the $CODEBUILD_SRC_DIR_pipelines/pipelines folder
        # 2) Uses git diff with $CODEBUILD_RESOLVED_SOURCE_VERSION $LAST_SUCCESSFUL_COMMIT_ID to figure out which files were changed
             # they get written to $BUILd_FILE

        # For each pipeline that had changed code:
        # 1) build the pipeline image (copy over only the folders we need from the pipelines source; add the lambda)
        # 2) deploy the lambda function to run the pipeline
        # 3) if cron, deploy the cron lambda
        # 4) if s3, add config to the input bucket to send sns event when new data comes in