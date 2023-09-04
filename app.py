#!/usr/bin/env python3
import os

import aws_cdk as cdk

from code_pipeline.code_pipeline_stack import CodePipelineStack
from utils.constants import StackNames
from utils.pipelines_config import PipelinesConfig

app = cdk.App()
config = PipelinesConfig()
env = cdk.Environment(account=config.account, region=config.region)

CodePipelineStack(app, StackNames.CODE_PIPELINE, env=env, config=config)

app.synth()
