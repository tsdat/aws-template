import logging
import os
import json
import tempfile
from datetime import datetime, timedelta
from typing import Dict, List, Generator, Optional
from urllib.parse import unquote_plus
from pathlib import Path

import boto3

from utils.pipelines_config import PipelinesConfig, PipelineConfig, RunConfig
from utils.constants import PipelineType, Trigger
from tsdat.config.pipeline import PipelineConfig as TsdatPipelineConfig
from utils.registry import PipelineRegistry
from utils.logger import configure_logger, DelayedJSONStreamHandler


logger = logging.getLogger(__name__)


class EventTrigger:
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


def get_next_day(date: datetime) -> Optional[datetime]:
    """
    Get the datetime for one day after the given date.

    Args:
        date (datetime):

    Returns:
        datetime:  datetime for one day after date or None if date is None
    """
    return date + timedelta(days=1) if date else None


def round_time_to_midnight(time: datetime) -> datetime:
    """
    Convert the given datetime to the same day at midnight.
    """
    return time.replace(hour=0, minute=0, second=0, microsecond=0)


def lambda_handler(event, context):
    print("Dumping event")
    print(json.dumps(event, indent=4))
    print("Dumping context")
    print(json.dumps(context, indent=4))


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
    config_id = os.environ.get("CONFIG_ID")
    trigger = EventTrigger(event)
    pipelines_config: PipelinesConfig = PipelinesConfig()
    pipeline_config: PipelineConfig = pipelines_config.pipelines.get(pipeline_name)
    run_config: RunConfig = pipeline_config.configs.get(config_id)
    inputs = []

    set_env_vars()
    configure_logger(logger)
    extra_context = {}
    success = False

    try:
        logger.info(f"Running pipeline {pipeline_name} {config_id}")
        tsdat_config = TsdatPipelineConfig.from_yaml(run_config.config_file_path)
        pipeline = tsdat_config.instantiate_pipeline()

        # Get the output datastream (e.g., humboldt.buoy_z06.a1)
        data_class = pipeline.dataset_config.attrs["datastream"]
        location = pipeline.dataset_config.attrs["location_id"]
        data_level = pipeline.dataset_config.attrs["data_level"]
        output_datastream = f"{location}.{data_class}.{data_level}"

        if trigger.type == Trigger.Cron and pipeline_config.type == PipelineType.VAP:
            # Get the input datastreams
            input_datastreams: List[str] = pipeline.parameters.datastreams

            # From storage, find the last datetime of the output datastream and any
            # input data dates that were modified since.
            last_modified: datetime = pipeline.storage.last_modified(output_datastream)
            modified_days: List[datetime] = []
            for input_datastream in input_datastreams:
                modified_days.extend(
                    pipeline.storage.modified_since(input_datastream, last_modified)
                )

            if len(modified_days) == 0:
                logger.info(f"No new input files available to run!")

            else:
                # We will run the VAP for any days that were changed/added.  For now we will
                # run the full range of days.  Later we can split into non-contiguous
                # segments to improve processing.
                modified_days = sorted(modified_days)
                start_day = round_time_to_midnight(modified_days[0])
                end_day = get_next_day(round_time_to_midnight(modified_days[-1]))

                # Start and end dates for the pipeline need to be strings in this
                # format: 20230101
                start_day = start_day.strftime("%Y%m%d")
                end_day = end_day.strftime("%Y%m%d")
                inputs = [start_day, end_day]

        elif pipeline_config.type == PipelineType.Ingest:
            if trigger.type == Trigger.Cron:
                input_bucket_arn = pipelines_config.input_bucket_arn
                bucket_path = run_config.input_bucket_path
                bucket_path = (
                    f"{bucket_path}/" if not bucket_path.endswith("/") else bucket_path
                )
                bucket_path = f"{bucket_path}*"

                # We need to find the last modified date for this pipeline's output datastream.
                last_modified: datetime = pipeline.storage.last_modified(
                    output_datastream
                )

                # Then we need to query the input bucket/prefix for all files modified since
                # last output time.  Then we run the pipeline same as below.
                inputs = []

            else:
                inputs = trigger.input_files

            assert len(inputs) >= 1, "No input files found!"

        if len(inputs) > 0:
            pipeline.run(inputs)

        success = True

    except BaseException:
        logger.exception("Failed to run the pipeline.")

    finally:
        extra_context = {
            "success": success,
            "inputs": inputs,
            "code_version": os.environ.get("CODE_VERSION", ""),
        }

        for handler in logging.getLogger().handlers:
            if isinstance(handler, DelayedJSONStreamHandler):
                handler.flush(context=extra_context)

    return not success  # Convert successful exit codes to 0
