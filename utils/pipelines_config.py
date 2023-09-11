import os
from pathlib import Path
from typing import Dict, List, Union
import yaml

from .constants import Env


class PipelineConfig:
    def __init__(self, values: dict):
        self.name: str = values.get("name")
        self.type: str = values.get("type")
        self.input_dir: str = values.get("input_dir")
        self.config_file_path: str = values.get("config_file_path")
        self.trigger: str = values.get("trigger")
        self.schedule: str = values.get("schedule")


class PipelinesConfig:
    def __init__(self):
        """Constructor
        Loads the config settings from the given config file.
        """
        config_file_path = PipelinesConfig.get_config_file_path()

        with open(config_file_path, "r") as file:
            config = yaml.full_load(file)

        self.github_org = config.get("github_org")
        self.pipelines_repo_name = config.get("pipelines_repo_name")
        self.aws_repo_name = config.get("aws_repo_name")
        self.account_id = config.get("account_id")
        self.region = config.get("region")
        self.github_codestar_arn = config.get("github_codestar_arn")

        self.pipelines: Dict[str, PipelineConfig] = {}
        pipelines_to_deploy: List[dict] = config.get("pipelines_to_deploy", [])
        for p in pipelines_to_deploy:
            name = p["name"]
            self.pipelines[name] = PipelineConfig(p)

    @property
    def base_name(self):
        return f"{self.pipelines_repo_name}-{Env.BRANCH}"

    @property
    def pipeline_stack_name(self):
        return f"{self.base_name}-CodePipelineStack"

    @property
    def codestar_connection_name(self):
        return f"{self.base_name}-CodeStarConnection"

    @property
    def lambda_role_name(self):
        return f"{self.base_name}-LambdaRole"

    @property
    def code_pipeline_project_name(self):
        return f"{self.base_name}-build"

    @property
    def input_bucket_name(self):
        return f"{self.base_name}-raw"

    @property
    def output_bucket_name(self):
        return f"{self.base_name}-output"

    @property
    def ecr_repo_name(self):
        return self.base_name

    @property
    def ecr_repo(self):
        # 332883119153.dkr.ecr.us-west-2.amazonaws.com/ingest-buoy-dev
        return f"{self.account_id}.dkr.ecr.{self.region}.amazonaws.com/{self.ecr_repo_name}"

    def get_image_uri(self, tsdat_pipeline_name: str):
        # "332883119153.dkr.ecr.us-west-2.amazonaws.com/ingest-buoy-dev:ingest-buoy-dev"
        image_tag_name = f"{tsdat_pipeline_name}-{Env.BRANCH}"
        return f"{self.ecr_repo}:{image_tag_name}"

    def get_lambda_name(self, tsdat_pipeline_name: str):
        return f"{self.base_name}-lambda-{tsdat_pipeline_name}"

    def get_cron_rule_name(self, tsdat_pipeline_name: str):
        return f"{self.get_lambda_name(tsdat_pipeline_name)}-cron-rule"

    @staticmethod
    def get_config_file_path():
        utils_dir = os.path.dirname(os.path.realpath(__file__))
        repo_dir = os.path.dirname(utils_dir)
        config_file_path = os.path.join(repo_dir, "pipelines_config.yml")
        return config_file_path
