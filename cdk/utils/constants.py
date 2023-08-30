import os

class Env:
    # Names must match the branches in your pipelines repository (e.g., test or release)
    DEPLOYMENT_NAME = os.environ.get("DEPLOYMENT_NAME", 'test')
    

class StackNames:
    CODE_PIPELINE = f"code-pipeline-{Env.DEPLOYMENT_NAME}"
