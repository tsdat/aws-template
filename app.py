#!/usr/bin/env python3
import os

import aws_cdk as cdk

from code_pipeline.code_pipeline_stack import CodePipelineStack
from utils.pipelines_config import PipelinesConfig

app = cdk.App()
config = PipelinesConfig()
env = cdk.Environment(account=config.account_id, region=config.region)

CodePipelineStack(app, config.pipeline_stack_name, env=env, config=config)

app.synth()
