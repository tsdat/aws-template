
FROM nikolaik/python-nodejs:python3.11-nodejs20

ARG AWS_CDK_VERSION=2.93.0

RUN npm install -g aws-cdk@${AWS_CDK_VERSION}
RUN apt update -y && apt install -y nano

COPY requirements.txt /root/requirements.txt
RUN pip install -r /root/requirements.txt

# Install the aws cli
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "/root/awscliv2.zip"
RUN unzip /root/awscliv2.zip -d /root
RUN /root/aws/install

# AWS cli help doesn't work out of the box, so we have to add these 2 additional libs
RUN apt-get install groff less -y

# Also need to install the session manager plugin
RUN curl "https://s3.amazonaws.com/session-manager-downloads/plugin/latest/ubuntu_64bit/session-manager-plugin.deb" -o "/root/session-manager-plugin.deb"
RUN dpkg -i /root/session-manager-plugin.deb

# Add the jq library for parsing aws cli output
RUN apt-get install jq -y

# This should be mounted to the repo in docker-compose.yml
RUN mkdir /root/aws-template

# Set up default profile for aws cli
ENV AWS_PROFILE=tsdat

# Home dir is /root/
# Make sure to mount ~/.aws folder to /root/.aws
# Make sure to mount our cdk app to /root/aws-template

WORKDIR /root/aws-template
