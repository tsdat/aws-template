
FROM nikolaik/python-nodejs:python3.11-nodejs20

ARG AWS_CDK_VERSION=2.93.0

RUN npm install -g aws-cdk@${AWS_CDK_VERSION}
RUN apt update -y && apt install -y nano

COPY cdk/requirements.txt /root/requirements.txt
RUN pip install -r /root/requirements.txt

# This should be mounted to the repo in docker-compose.yml
RUN mkdir /root/cdk_app

# Set up default profile for aws cli
ENV AWS_PROFILE=tsdat

# Home dir is /root/
# Make sure to mount ~/.aws folder to /root/.aws
# Make sure to mount our cdk app to /root/cdk_app

WORKDIR /root/cdk_app

CMD ["cdk", "--version"]