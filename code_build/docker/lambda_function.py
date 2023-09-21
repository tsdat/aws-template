import logging
import os
import json
import tempfile
from datetime import datetime, timedelta
from typing import Dict, List, Generator, Optional
from urllib.parse import unquote_plus
from pathlib import Path

import boto3

from build_utils.pipelines_config import PipelinesConfig, PipelineConfig, RunConfig
from build_utils.constants import PipelineType, Trigger
from tsdat.config.pipeline import PipelineConfig as TsdatPipelineConfig
from build_utils.logger import configure_logger, DelayedJSONStreamHandler


# Initialize global parameters
tmp_dir = tempfile.TemporaryDirectory()
tmp_dirpath = Path(tmp_dir.name)

# This is passed to the lambda configuration via the build
pipeline_name = os.environ.get("PIPELINE_NAME")
config_id = os.environ.get("CONFIG_ID")
pipelines_config_path = os.environ.get("PIPELINES_CONFIG_PATH", "pipelines_config.yml")
pipelines_config: PipelinesConfig = PipelinesConfig(
    config_file_path=pipelines_config_path
)
pipeline_config: PipelineConfig = pipelines_config.pipelines.get(pipeline_name)
run_config: RunConfig = pipeline_config.configs.get(config_id)
s3_client = boto3.client("s3", region_name=pipelines_config.region)

logger = logging.getLogger(__name__)


def get_input_files_from_event(event) -> List[str]:
    input_files: List[str] = []

    for record in event["Records"]:
        bucket_name = record["s3"]["bucket"]["name"]
        bucket_path = record["s3"]["object"]["key"]
        local_path = download_s3_file(bucket_name, bucket_path)
        input_files.append(local_path)

    return input_files


def download_s3_file(bucket_name: str, bucket_path: str) -> str:
    local_path = tmp_dirpath / bucket_path
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path = str(local_path)

    s3_client.download_file(bucket_name, bucket_path, local_path)
    return local_path


def get_recently_modified_raw_files(pipeline, output_datastream: str) -> List[str]:
    input_files = []
    bucket_name = pipelines_config.input_bucket_name
    folder_bucket_path = run_config.input_bucket_path
    folder_bucket_path = (
        f"{folder_bucket_path}/"
        if not folder_bucket_path.endswith("/")
        else folder_bucket_path
    )

    # We need to find the last modified date for this pipeline's output datastream.
    last_modified: datetime = pipeline.storage.last_modified(output_datastream)

    # Then we need to query the input bucket/prefix for all files modified since
    # last output time.  Then we run the pipeline same as below.
    paginator = s3_client.get_paginator("list_objects_v2")
    pages = paginator.paginate(
        Bucket=pipelines_config.input_bucket_name, Prefix=folder_bucket_path
    )

    for page in pages:
        for object in page["Contents"]:
            file_bucket_path = object["Key"]
            if file_bucket_path != folder_bucket_path and (
                not last_modified or object["LastModified"] > last_modified
            ):
                logger.info(f"Adding file to input: {object['Key']}")
                input_files.append(download_s3_file(bucket_name, file_bucket_path))

    return input_files


def get_available_vap_dates(pipeline, output_datastream) -> List[str]:
    inputs = []
    # Get the input datastreams
    input_datastreams: List[str] = pipeline.parameters.datastreams

    # From storage, find the last datetime of the output datastream and any
    # input data dates that were modified since.
    last_modified: datetime = pipeline.storage.last_modified(output_datastream)
    logger.info(f"Last output date for vap = {last_modified}")
    modified_days: List[datetime] = []
    for input_datastream in input_datastreams:
        logger.info(
            f"Input datastream {input_datastream} modified after last output date."
        )
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

    return inputs


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
    os.environ["TSDAT_S3_BUCKET_NAME"] = pipelines_config.output_bucket_name

    # Logging level to use. If provided from an environment variable, it must match one
    # of the levels here: https://docs.python.org/3/library/logging.html#logging-levels
    root_logging_level = os.environ.get("ROOT_LOG_LEVEL", "WARNING").upper()
    os.environ["ROOT_LOG_LEVEL"] = root_logging_level

    logging_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    os.environ["LOG_LEVEL"] = logging_level

    # TODO: add storage classname to the pipelines config so it can be configured
    os.environ["TSDAT_STORAGE_CLASS"] = "tsdat.FileSystemS3"

    try:
        version = (
            Path(".version").read_text().strip()
        )  # Created by the Dockerfile via dunamai
    except IOError:
        version = "N/A"
    os.environ["CODE_VERSION"] = os.environ.get("CODE_VERSION", version)


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
    set_env_vars()
    configure_logger(logger)
    inputs = []
    extra_context = {}
    success = False

    try:
        logger.info(f"Running pipeline {pipeline_name} {config_id}")
        tsdat_config = TsdatPipelineConfig.from_yaml(Path(run_config.config_file_path))
        pipeline = tsdat_config.instantiate_pipeline()

        # Get the output datastream (e.g., morro.buoy_z06-lidar-10m.a1)
        output_datastream = pipeline.dataset_config.attrs.datastream

        if (
            pipeline_config.trigger == Trigger.Cron
            and pipeline_config.type == PipelineType.VAP
        ):
            inputs = get_available_vap_dates(pipeline, output_datastream)

        elif pipeline_config.type == PipelineType.Ingest:
            if pipeline_config.trigger == Trigger.Cron:
                inputs = get_recently_modified_raw_files(pipeline, output_datastream)

            else:
                inputs = get_input_files_from_event(event)

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


if __name__ == "__main__":
    event = {
        "Records": [
            {
                "s3": {
                    "bucket": {
                        "name": "ingest-buoy-dev-raw",
                    },
                    "object": {
                        "key": "lidar/morro/lidar.z06.00.20201201.000000.sta.7z",
                    },
                }
            }
        ]
    }
    lambda_handler(event, None)
