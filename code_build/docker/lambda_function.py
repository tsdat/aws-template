import logging
import os
import json
import tempfile
from typing import Dict, List, Generator
from urllib.parse import unquote_plus
from pathlib import Path

import boto3

from utils.pipelines_config import PipelinesConfig, PipelineConfig, RunConfig
from utils.constants import PipelineType, Trigger
from utils.registry import PipelineRegistry
from utils.logger import configure_logger, DelayedJSONStreamHandler


logger = logging.getLogger(__name__)

class EventTrigger():
    def __init__(self, aws_event, pipeline_config: PipelineConfig):
        # TODO: parse the aws event and determine if this is a cron or s3 trigger
        self.type = Trigger.S3
        self.input_files = None
        self.pipeline_config = pipeline_config
        
        if self.type == Trigger.S3:
            self.input_files: List[str] = self.get_input_files_from_event(aws_event)
        else:
            self.config_id: str = None  # parsed if this is cron event

    def get_input_files_from_event(self, event) -> List[str]:
        tmp_dir = tempfile.TemporaryDirectory()
        tmp_dirpath = Path(tmp_dir.name)

        input_files: List[str] = []
        sns = json.loads(event["Records"][0]["Sns"]["Message"])
        for record in sns["Records"]:
            record_path = download_s3_record(json.loads(record), tmp_dirpath)
            input_files.append(record_path)
      
        return input_files
    
    def get_config_id_from_event(self, event):
        return ''
    
    def get_config_id_from_files(self):
        # This might not work if files from different paths got uploaded in same event.
        # Could this happen?
        return ''

def download_s3_record(record: Dict, target_dir: Path) -> str:
    bucket_name = record["s3"]["bucket"]["name"]
    bucket_path = Path(unquote_plus(record["s3"]["object"]["key"]))

    local_path = target_dir / bucket_path
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path = str(local_path)

    session = boto3.session.Session()
    bucket = session.resource("s3").Bucket(bucket_name)
    bucket.download_file(
        Key=str(bucket_path),
        Filename=local_path,
    )
    return local_path


def set_env_vars():
    """-------------------------------------------------------------------
    Environment variables are used to set values in the pipelines'
    storage_config.yml file.  If running from a deployed lambda environment,
    then some of these environment variables will be set based upon the
    parameters in the deployment template.

    If running from a local test environment, these environment variables
    must be set in the unit test configuration.

    This method will make sure all values are set if not specified by
    external sources.
    -------------------------------------------------------------------"""

    # Name of storage bucket where output files are written
    # Set the TSDAT_S3_BUCKET_NAME environment variable
    # bucket_name = os.environ["STORAGE_BUCKET"]

    # Logging level to use. If provided from an environment variable, it must match one
    # of the levels here: https://docs.python.org/3/library/logging.html#logging-levels
    root_logging_level = os.environ.get("ROOT_LOG_LEVEL", "WARNING").upper()
    os.environ["ROOT_LOG_LEVEL"] = root_logging_level

    logging_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    os.environ["LOG_LEVEL"] = logging_level

    storage_classname = os.environ.get("STORAGE_CLASSNAME", "tsdat.FileSystemS3")
    os.environ["STORAGE_CLASSNAME"] = storage_classname

    try:
        version = (
            Path(".version").read_text().strip()
        )  # Created by the Dockerfile via dunamai
    except IOError:
        version = "N/A"
    os.environ["CODE_VERSION"] = os.environ.get("CODE_VERSION", version)


def get_shortened_input_files(files: List[str]) -> List[str]:
    """Input files always look like `data-a2e$$$bdda6da226.0/buoy/buoy.z05.a0.20220109.112944.imu.a2e.nc`,
    which can be hard to read. This method shortens this filename to look like this:
    `buoy/buoy.z05.a0.20220109.112944.imu.a2e.nc`. This method performs this operation
    on any number of input files.

    Args:
        files (List[str]): The list of input files to shorten.

    Returns:
        List[str]: The shortened list of input files.
    """
    return ["/".join(file.split("/")[1:]) for file in files]


def lambda_handler(event, context):
    logger.info(event)
    logger.info(context)


def lambda_handler_old(event, context):
    """--------------------------------------------------------------------------------
    Lambda function to run a tsdat pipeline. The function will be triggered by either
    1) a bucket event for an incoming raw data file, or
    2) a cron event for pipelines that need to run on a schedule.

    The pipeline will process the raw files using the specified configuration (either
    ingest or vap) and save the file to an S3 bucket specified by an environment
    variable.

    Args:
        event (Dict): Dictionary of event parameters. This will either include the S3 file
        that triggered the event or the pipeline and config id if it was triggered via a
        cron.
        context (object): Lambda context. Documentation for the methods and attributes
        this context provides is specified by AWS here:
        https://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html
    --------------------------------------------------------------------------------"""
    # This is passed to the lambda configuration via the build
    pipeline_name = os.environ.get("PIPELINE_NAME")
    trigger = EventTrigger(event)
    pipelines_config: PipelinesConfig = PipelinesConfig()
    pipeline_config: PipelineConfig = pipelines_config.pipelines.get(pipeline_name)
    
    set_env_vars()
    configure_logger(logger)
    extra_context = {}
    success = False
    
    try:
        if trigger.type == Trigger.Cron and pipeline_config.type == PipelineType.VAP:
            # Open pipeline's retriever config file to find the input datastreams.  Then we
            # need to find the last datetime the pipeline was run (we assume this is the last
            # modified date of the pipeline output).  Then we find the data dates of any files
            # that were modified after that datetime.  We will run the VAP for any days
            # that were changed/added.  For now we will run the full range of days.  Later
            # we can split into non-contiguous segments to improve processing.
            pass
        
        elif pipeline_config.type == PipelineType.Ingest:
            
            if trigger.type == Trigger.Cron:
                input_bucket_arn = pipelines_config.input_bucket_arn
                run_config: RunConfig = pipeline_config.configs.get(trigger.config_id)
                bucket_path = run_config.input_bucket_path
                
                # We need to find the last modified date for this pipeline's output datastream.

                # Then we need to query the input bucket/prefix for all files modified since
                # last output time.  Then we run the pipeline same as below.
                input_files = []
        
            else:
                input_files = trigger.input_files
                
            logger.info(f"Running on input files: {input_files}")
            assert len(input_files) >= 1, "No input files found!"

            cache = PipelineRegistry()
            discovered = sorted(list(cache._cache))
            logger.info(f"Discovered pipelines: {discovered}")
            assert len(discovered) >= 1, "Lambda environment was configured incorrectly"
            
            config_files = cache._match_input_key(input_files[0])
            assert len(config_files) > 0, f"No config files were matched by the input_file '{input_files[0]}'"
            assert len(config_files) == 1, f"Multiple config files were matched by input_file '{input_files[0]}': {config_files}"
            config_file = config_files[0]

            # Record information for extra context
            mapping_name = str(config_file)
            successes, failures, skipped = cache.dispatch(input_files, clump=True)
            
            success = successes >= 1 and failures == 0

    except BaseException:
        logger.exception("Failed to run the pipeline.")

    finally:
        extra_context = {
            "mapping_name": mapping_name,
            "success": success,
            "input_files": input_files,
            "short_input_files": get_shortened_input_files(input_files),
            "code_version": os.environ.get("CODE_VERSION", "")
        }

        for handler in logging.getLogger().handlers:
            if isinstance(handler, DelayedJSONStreamHandler):
                handler.flush(context=extra_context)

    return not success  # Convert successful exit codes to 0

