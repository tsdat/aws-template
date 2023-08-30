import os
from pathlib import Path
from typing import Union
import yaml


class PipelinesConfig():
    
    def __init__(self):
        """Constructor
        Loads the config settings from the given config file.
        """   
        config_file_path = PipelinesConfig.get_config_file_path()
                   
        with open(config_file_path, 'r') as file:
            config = yaml.full_load(file)
        
        self.github_org = config.get('github_org')
        self.pipelines_repo = config.get('pipelines_repo')
        self.aws_build_repo = config.get('aws_build_repo')
        self.account_id = config.get('account_id')
        self.region = config.get('region')
        self.vpc_id = config.get('vpc_id')
        self.github_codestar_arn = config.get('github_codestar_arn')
      

    @staticmethod
    def get_config_file_path():
        utils_dir = os.path.dirname(os.path.realpath(__file__))
        cdk_dir = os.path.dirname(utils_dir)
        repo_dir = os.path.dirname(cdk_dir)
        config_file_path = os.path.join(repo_dir, 'pipelines_config.yml')
        return config_file_path

