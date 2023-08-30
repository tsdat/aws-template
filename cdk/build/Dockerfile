# TODO: Is there an automated process for building/publishing new containers when a new
# version of tsdat is released?
FROM public.ecr.aws/lambda/python:3.9
#ARG ECR_REPO=base/tsdat
#FROM $ECR_REPO:tsdat-0.5.2

RUN mkdir -p ingest
COPY requirements.txt .
RUN python3.9 -m pip install -r requirements.txt --target .

COPY utils utils
COPY shared shared
COPY logger.py utils/
COPY storage-extra.yaml shared/
RUN cat shared/storage-extra.yaml >> shared/storage.yaml

COPY lambda_function.py .
RUN chmod +x lambda_function.py
