import logging
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

import boto3

from build_utils.logger import DelayedJSONStreamHandler, configure_logger

# Set up logging: note that this needs to be done before the PipelinesConfig import
# because we want to remove
logger = logging.getLogger(__name__)
configure_logger(logger)

from build_utils.pipelines_config import PipelinesConfig  # noqa: E402

# Initialize global parameters
TMP_DIR = tempfile.TemporaryDirectory()
TMP_DIRPATH = Path(TMP_DIR.name)

# This is passed to the lambda configuration via the build
PIPELINE_NAME = os.environ["PIPELINE_NAME"]
CONFIG_ID = os.environ["CONFIG_ID"]
PIPELINES_CONFIG_PATH = os.environ.get("PIPELINES_CONFIG_PATH", "pipelines_config.yml")

PIPELINES_CONFIG = PipelinesConfig(config_file_path=PIPELINES_CONFIG_PATH)
PIPELINE_CONFIG = PIPELINES_CONFIG.pipelines[PIPELINE_NAME]
RUN_CONFIG = PIPELINE_CONFIG.configs[CONFIG_ID]
S3_CLIENT = boto3.client("s3", region_name=PIPELINES_CONFIG.region)


def get_input_files_from_event(event) -> List[str]:
    input_files: List[str] = []

    for record in event["Records"]:
        bucket_name = record["s3"]["bucket"]["name"]
        bucket_path = record["s3"]["object"]["key"]
        local_path = download_s3_file(bucket_name, bucket_path)
        input_files.append(local_path)

    return input_files


def download_s3_file(bucket_name: str, bucket_path: str) -> str:
    local_path = TMP_DIRPATH / bucket_path
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path_str = str(local_path)

    S3_CLIENT.download_file(bucket_name, bucket_path, local_path_str)
    return local_path_str


def get_recently_modified_raw_files(pipeline, output_datastream: str) -> List[str]:
    input_files = []
    bucket_name = PIPELINES_CONFIG.input_bucket_name
    folder_bucket_path = RUN_CONFIG.input_bucket_path
    folder_bucket_path = (
        f"{folder_bucket_path}/"
        if not folder_bucket_path.endswith("/")
        else folder_bucket_path
    )

    # We need to find the last modified date for this pipeline's output datastream.
    last_modified: datetime = pipeline.storage.last_modified(output_datastream)

    # Then we need to query the input bucket/prefix for all files modified since
    # last output time.  Then we run the pipeline same as below.
    paginator = S3_CLIENT.get_paginator("list_objects_v2")
    pages = paginator.paginate(
        Bucket=PIPELINES_CONFIG.input_bucket_name, Prefix=folder_bucket_path
    )

    for page in pages:
        for object in page["Contents"]:
            file_bucket_path = object["Key"]  # type: ignore
            file_last_modified = object["LastModified"]  # type: ignore
            if file_bucket_path != folder_bucket_path and (
                not last_modified or file_last_modified > last_modified
            ):
                logger.info(f"Adding file to input: {object['Key']}")  # type: ignore
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
        logger.info("No new input files available to run!")

    else:
        # If new files were found, we'll just run the last specified time noted.
        # Previous times will need to be rerun locally.

        # Start from previous X, at midnight UTC.
        cron_schedule = PIPELINE_CONFIG.schedule
        if cron_schedule=="Hourly":
            td = timedelta(hours=1)
        elif cron_schedule=="Daily":
            td = timedelta(days=1)
        elif cron_schedule=="Weekly":
            td = timedelta(days=7)
        elif cron_schedule=="Monthly":
            td = timedelta(weeks=4)

        modified_days: datetime = datetime.now(timezone.utc) - td
        start_day = round_time_to_midnight(modified_days)
        end_day = round_time_to_midnight(modified_days) + td

        # Start and end dates for the pipeline need to be strings in this
        # format: 20230101
        start_day_str = start_day.strftime("%Y%m%d")
        end_day_str = end_day.strftime("%Y%m%d")
        inputs = [start_day_str, end_day_str]

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
    os.environ["TSDAT_S3_BUCKET_NAME"] = PIPELINES_CONFIG.output_bucket_name

    # Logging level to use. If provided from an environment variable, it must match one
    # of the levels here: https://docs.python.org/3/library/logging.html#logging-levels
    root_logging_level = os.environ.get("ROOT_LOG_LEVEL", "WARNING").upper()
    os.environ["ROOT_LOG_LEVEL"] = root_logging_level

    logging_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    os.environ["LOG_LEVEL"] = logging_level

    # TODO: add storage classname to the pipelines config so it can be configured
    os.environ["TSDAT_STORAGE_CLASS"] = "tsdat.FileSystemS3"

    try:
        # Created by the Dockerfile via dunamai
        version = Path(".version").read_text().strip()
    except IOError:
        version = "N/A"
    os.environ["CODE_VERSION"] = os.environ.get("CODE_VERSION", version)


def get_next_day(date: datetime) -> datetime:
    """
    Get the datetime for one day after the given date.

    Args:
        date (datetime):

    Returns:
        datetime:  datetime for one day after date or None if date is None
    """
    return date + timedelta(days=1)


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
    from tsdat.config.pipeline import PipelineConfig as TsdatPipelineConfig

    from build_utils.constants import PipelineType, Trigger

    set_env_vars()
    inputs = []
    extra_context = {}
    success = False

    try:
        logger.info(f"Running pipeline {PIPELINE_NAME} {CONFIG_ID}")
        tsdat_config = TsdatPipelineConfig.from_yaml(Path(RUN_CONFIG.config_file_path))
        pipeline = tsdat_config.instantiate_pipeline()

        # Get the output datastream (e.g., morro.buoy_z06-lidar-10m.a1)
        output_datastream = pipeline.dataset_config.attrs.datastream

        if (
            PIPELINE_CONFIG.trigger == Trigger.Cron
            and PIPELINE_CONFIG.type == PipelineType.VAP
        ):
            inputs = get_available_vap_dates(pipeline, output_datastream)

        elif PIPELINE_CONFIG.type == PipelineType.Ingest:
            if PIPELINE_CONFIG.trigger == Trigger.Cron:
                inputs = get_recently_modified_raw_files(pipeline, output_datastream)

            else:
                inputs = get_input_files_from_event(event)

            assert len(inputs) >= 1, "No input files found!"

        if len(inputs) > 0:
            logger.info(f"Running with inputs: {inputs}")
            pipeline.run(inputs)

        success = True

    except BaseException:
        logger.exception("Failed to run the pipeline.")

    finally:
        extra_context = {
            "success": success,
            "inputs": inputs,
            "code_version": os.environ.get("CODE_VERSION", ""),
            "event": event,
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
