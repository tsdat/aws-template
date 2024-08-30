# Deploying Tsdat Pipelines to AWS

This repository contains everything needed to deploy your Tsdat pipelines to Amazon
Web Services (AWS).  The following pictures give a high level overview of the
build process and what resources are created in AWS.

![Image](./images/aws_template.png)
![Image](./images/tsdat-aws-code-build.png)
![Image](./images/tsdat-aws-functional-diagram.png)

```diff
!  NOTE: This deployment can only be run by AWS administrators, so we assume the user has
!  a basic understanding of code development, Docker containers, and the AWS cloud.
```

## Prerequisites

### **1. Create GitHub Repositories from Templates**

Make sure that you have created two new repositories in your GitHub organization from the
following template repositories:

1. <https://github.com/tsdat/pipeline-template>
2. <https://github.com/tsdat/aws-template>

```diff
!  NOTE:  If you are using an existing pipelines repository, make sure that the requirements.txt file specifies a tsdat version to `tsdat >=0.7.1`, preferably `tsdat>=0.8.5`. The AWS build will not work with earlier versions of `tsdat`.
```

If you haven't already created a pipeline repository from *pipeline-template*, do so now 
and create your pipelines. The 
[data ingest tutorial](https://tsdat.readthedocs.io/en/stable/tutorials/data_ingest/) is 
a good place to start. Clone the *aws-template* to your computer as well and add in the 
same parent folder as your pipeline repository.

If you are using WSL on Windows, make sure you run the `git clone` command from a WSL 
terminal to prevent git from converting all the file line endings to `CRLF`. If your files 
have `CRLF` line endings, it will cause the AWS pipeline to crash.

### **2. Get an AWS Account**

In order to deploy resources to AWS, you must have an account set up and you **must have
administrator privileges** on that account.  If you do not have an AWS account or you
do not have admin privileges, then you should contact the local cloud administrator
for your organization.

### **3. Create an AWS CodeStar Connection to GitHub**

<https://docs.aws.amazon.com/dtconsole/latest/userguide/connections-create-github.html#connections-create-github-console>

**Don't forget to copy the ARN of your connection to the pipelines_config.yml file.**

### **4. Install Docker**

We use a Docker container with VSCode to make setting up your development environment a 
snap.  We assume users have a basic familiarity with Docker containers. If you are new 
to Docker, there are many free online tutorials to get you started.

*NOTE: Because Docker Desktop can be flaky, especially on Windows, we recommend not using 
it. So we are providing alternative, non-Docker Desktop installation instructions for each 
platform. The Docker Desktop install is easier and requires fewer steps, so it may be fine 
for your needs, but keep in mind it may crash if you update it (requiring a full 
uninstall/reinstall, and then you lose all your container environments).  
Also, Docker Desktop requires a license.*

- **Windows Users:**
  - [Install Docker on WSL](https://tsdat.readthedocs.io/en/stable/tutorials/setup_wsl_docker/) **OR**
  - [Install Docker Desktop](https://docs.docker.com/desktop/install/windows-install/).
- **Mac Users:**
  - [Install Docker Desktop](https://docs.docker.com/desktop/install/mac-install/).  **OR**
  - [Use Docker/Colima](https://dev.to/elliotalexander/how-to-use-docker-without-docker-desktop-on-macos-217m).
- **Linux Users:**
  - [Install Docker](https://docs.docker.com/engine/install/ubuntu/). **OR**
  - [Install Docker Desktop](https://docs.docker.com/desktop/install/linux-install/).

### **Visual Studio Code**

We also recommend [installing VSCode](https://code.visualstudio.com/download) 
and using the
[ms-vscode-remote.vscode-remote-extensionpack](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.vscode-remote-extensionpack)
extension, which includes support for editing code in Docker Containers.

## Development Environment

### **1. Clone your aws repo and your pipelines repo into the same parent folder.**

```diff
!  IMPORTANT: Make sure if you are using WSL on Windows that you run the `git clone` command from a WSL terminal!
```

### **2. Open your aws-template repo in VSCode**

Open the `aws-template` repository in VSCode. You can either use the command line for 
this (i.e., `code path/to/aws-template`), or just open it using ^^File -> Open Folder^^.

```diff
!  NOTE:  If you are using WSL on Windows then you MUST open VSCode from within a WSL terminal in order for VSCode to automatically install the proper WSL interface extension.
```

Windows Users: make sure you have the WSL extension by Microsoft
    ([ms-vscode-remote.remote-wsl](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-wsl)).
    installed. Then press ++ctrl+shift+p++ and enter the command **`WSL: Reopen folder in WSL`**

### **3. Start your tsdat-cdk Docker container**

From your VSCode window, start a terminal

    Main Menu -> Terminal -> New 
    (or you can click Ctrl+`)

Then from the VSCode terminal, run:

 ```shell
docker build --platform linux/amd64 . -t tsdat-cdk
docker compose up -d
 ```

1. In our testing we found that just `docker compose up -d` works fine on our team's 
Windows, Linux, and intel MacOS systems, but the `--platform` argument was needed for 
M1/M2 MacBooks. Milage may vary.

2. If you hit an error, run
    ```shell
    docker stop tsdat-cdk
    docker rm tsdat-cdk
    ```

### **4. Attach a new VSCode window to the tsdat-cdk container**

    Type the key combination:  Ctrl-Shift-p to bring up the VSCode command palette.

    Then from the input box type: "Dev-Containers:  Attach to Running Container..." and select it

    Then choose the  tsdat-cdk  container.

This will start up a new VSCode window that is running from inside your 
tsdat-cdk container.

Troubleshooting:

1. If a new VSCode window does not appear with a terminal showing "root@tsdat-cdk" 
(it might open in Windows and not a docker container, saying docker is not installed), 
then close VSCode, open a windows prompt and run "wsl --shutdown". Reopen VSCode and 
follow the previous two steps. In the very bottom left corner of the VSCode window 
should be a blue box with the text "Container tsdat-cdk (tsdat-cdk)".

2. If the new VSCode window that pops up still isn't in the docker container, hit 
"ctrl shift P" and "Reopen folder in WSL". When VSCode warns you that docker is not 
installed in WSL, click "Install". It will install some updates and then tell you that 
docker is already installed, click "Ignore". Now close VSCode and run "wsl --shutdown". 
Try again and it should open in the docker container.

3. If the new VSCode windows that pops up tells you that tsdat/cdk no longer exists, 
go into settings and search for "Execute in WSL" to find the Dev-Containers option 
that says "Always Execute in WSL". Check that box and reload the window.

### **5. Open the provided cdk.code-workspace file**

From the VSCode window that is attached to the tsdat-cdk container:

    Main Menu -> File-> Open Workspace from File...
    In the file chooser dialog, select ```/root/aws-template/.vscode/cdk.code-workspace```

```diff
!  A box should pop up in the bottom right corner that asks if you want to install the recommended extensions.  Select "Install".
```

Once the extensions are installed, your workspace is ready!
In the Explorer, you will see two folders and a
directory structure like so:

1. :material-folder: **`aws-template/`**
    * :material-folder: *`.vscode/`*
    * :material-folder: *`.build_utils/`*
    * :material-folder: `...`
    * :material-file: *`pipelines_config.yml`*

2. :material-folder: **`.aws/`**
    * :material-file: *`config`*
    * :material-file: *`credentials`*

### **6. Edit your pipelines_config.yml file**

The top part of the `aws-template/pipelines_config.yml` contains settings related 
to the AWS-GitHub integration, where data should be pulled from & placed, and which 
AWS account should be used. Open this file and fill out the configuration options, 
using your own values as needed. This section only needs to be filled out once and 
pushed to Github once completed. AWS will use the commit saved in Github to build
the pipelines.

```yaml title="aws-template/pipelines_config.yml"

github_org: tsdat  # The name of the organization or user that cloned the 
# aws-template and pipeline-template repos.
pipelines_repo_name: pipeline-template
aws_repo_name: aws-template

account_id: "XXXXXXXXXXX" # Your AWS account ID. You can get this from the 
# AWS console: In the navigation bar at the upper right, choose your 
# username and then copy the Account ID. It should be a 12-digit number.
region: us-west-2
input_bucket_name: tsdat-input
output_bucket_name: tsdat-output
create_buckets: True  # If you have existing buckets that you would like 
# to use for your pipeline inputs and outputs, then set create_buckets: False. 
# If create_buckets is set to True and the buckets already exist, then the 
# deployment will throw an error.

github_codestar_arn: arn:aws:codestar-connections:us-west-2:...  # This is the 
# ARN of the CodeStar connection to GitHub. Check out the AWS guide for setting 
# up a CodeStar connection, then copy the ARN of your CodeStar connection here.
```

### **7. Configure your tsdat AWS profile**

From a terminal inside your VSCode window attached to the Docker, run the 
following line. You may leave this blank aside from the region. You only 
need to do this once.

```shell
aws configure --profile tsdat
AWS Access Key ID [None]: 
AWS Secret Access Key [None]: 
Default region name [None]: us-west-2
Default output format [None]: 
```

FYI: If you've already set up AWS CLI in Windows, installing in WSL will link 
to the configuration files located in the Windows location. Your credentials 
will also be linked to the ".aws" folder that should now be showing in your 
VSCode Explorer tab. You can also manually create a symbolic link using
```
sudo ln -s /mnt/c/Users/<username>/.aws .aws
```

If you want to use a different profile name than "tsdat", edit the profile name 
in the  AWS config and credentials files, as well as in 
"aws-template/Dockerfile", line 31.

Your `~/.aws/config` file should now look like this:

```txt title="~/.aws/config"
[profile tsdat]
region = us-west-2
```

### **8. Edit your aws credentials**

CDK requires that your AWS credentials be set in order to authenticate your 
CLI actions.

```diff
!  NOTE:  You must use AWS credentials file, NOT the PNNL SSO login, which is not supported by the CDK.
```

```diff
!  You will need to do this step BEFORE you deploy your stack and any time the credentials expire
!  (usually after about 12 hours).
```

From your VSCode window that is attached to the tsdat-cdk container:

- From the Explorer view, open the .aws/credentials file.
- Then go to the AWS login page `https://pnnl.awsapps.com/start`
- Then click $PROJECT_NAME -> Administrator -> Command line or programmatic access  
  (use whatever project you are admin for)
- In the section, "Option 2: Manually add a profile to your AWS credentials file 
  (Short-term credentials)"
- Click on the box to copy the text.
- Paste it in your credentials file under the [tsdat] profile (make sure to delete
the line [xxxxx _AdministratorAccess])

Your credentials file should look like this (with real values instead of the XXXX):

```txt title="~/.aws/credentials"
[tsdat]
aws_access_key_id=XXXXXXX
aws_secret_access_key=XXXXXX
aws_session_token=XXXXXX
```

Your profile should show up if you run
```bash
aws configure list
```

If it doesn't, run
```bash
export AWS_PROFILE=<profile_name>
```

### **8. Run the cdk bootstrap (Only ONCE for your AWS Account/Region!)**

Bootstrapping is the process of provisioning resources for the AWS CDK before you can 
deploy AWS CDK apps into an AWS environment. (An AWS environment is a combination of an 
AWS account and Region).

These resources include an Amazon S3 bucket for storing files and IAM roles that grant 
permissions needed to perform deployments.

The required resources are defined in an AWS CloudFormation stack, called the bootstrap 
stack, which is usually named CDKToolkit. Like any AWS CloudFormation stack, it appears 
in the AWS CloudFormation console once it has been deployed.

**Check your Cloud Formation stacks first to see if you need to deploy the bootstrap.
(e.g., <https://us-west-2.console.aws.amazon.com/cloudformation/home?region=us-west-2>)
If you see a stack named `CDKToolkit`, then you can SKIP this step.**

```shell
cd aws-template
./bootstrap_cdk.sh
```

### **9. Run the CDK build**

You can re-run this for each branch you want to deploy (e.g., dev, prod, etc.) and any time
you make changes to the stack (for example, you add a new permission to your lambda role).

```diff
!  NOTE: Most deployments will not need to change anything in the stack, but advanced users 
!  are free to customize.
```

```shell
cd aws-template
./deploy_stack.sh $BRANCH
```

(where `$BRANCH` is the branch you want to deploy (e.g., main/dev/prod))

The very first time you run `./deploy_stack.sh` for a given branch you will need to 
manually release a 
[CodePipeline](https://us-west-2.console.aws.amazon.com/codesuite/codepipeline/pipelines) 
change in AWS to get it to build the initial container images and lambda functions.

### **10. Deploying `pipeline-template` Changes**

### Adding an ingest or VAP

The steps to deploy an existing pipeline at a new site, or to deploy an entirely new 
pipeline are the same:

1. Commit and push your `pipeline-template` changes (to whichever branch you set up 
for deployment).

2. Update the `aws-template/pipelines_config.yml` file for the new pipeline.

    The second half of the `aws-template/pipelines_config.yml` file contains 
    configurations for each deployed pipeline, including the type of pipeline 
    (i.e., `Ingest` or `VAP`), the trigger (i.e., `S3` or `Cron`), and a collection 
    of configuration files for different sites that the pipeline is deployed at 
    (`configs` section).

    ```yaml title="aws-template/pipelines_config.yml"
    pipelines:
    - name: lidar  # A useful name to give the pipeline in AWS. 
      # We recommend naming this like the folder names underneath 
      # the `pipelines/` folder in the `pipeline-template` repo. 
      # E.g., if your config file is `pipelines/imu/config/pipeline_humboldt.yaml`, 
      # then `imu` would be the recommended name for it.
      type: Ingest  # The type of pipeline, either "Ingest" or "VAP"
      trigger: S3  # The type of trigger, either "S3" to trigger when 
      # a file enters the input bucket path, or "Cron" to run on a regular schedule.
      configs:
        humboldt: # Each `pipeline.yaml` config file needs to be registered 
        # so it can be deployed. This key is unique per entry.
          input_bucket_path: lidar/humboldt/  # The subpath within the input 
          # bucket that should be watched. When new files enter this bucket, 
          # the pipeline will run with those files as input.
          config_file_path: pipelines/lidar/config/pipeline_humboldt.yaml  # The 
          # path to the pipeline configuration file in the `pipeline-template` repo
        morro:
          input_bucket_path: lidar/morro/
          config_file_path: pipelines/lidar/config/pipeline_morro.yaml

    - name: lidar_vap
      type: VAP
      trigger: Cron
      schedule: Hourly  # If the "Cron" trigger is selected, then you must also 
      # specify the schedule. The schedule should be one of the following: 
      # "Hourly", "Daily", "Weekly", or "Monthly"
      configs:
        humboldt:
          config_file_path: pipelines/lidar_vap/config/pipeline.yaml
    ```

3. Commit and push these changes to Github

4. Go to the [CodePipeline UI in AWS](https://us-west-2.console.aws.amazon.com/codesuite/codepipeline/pipelines) 
    and find the CodePipeline for this project, then click 'Release Change'.

### Updating an ingest or VAP

Changes to the deployed branch(es) in the `pipeline-template` repo will be 
released automatically via the CodePipeline build process in AWS, which was 
set up to watch for branch changes during the `./deploy_stack.sh main` step.

The AWS CodePipeline build (created during the `./deploy_stack.sh main` step) 
will automatically watch for changes to your `pipeline-template` code in the 
`main` branch (or whatever branch you specified). This means that any time you 
push changes to that branch, CodePipeline will automatically update and 
re-deploy any modified ingests or VAPs.

Changes to the `aws-template` repo are not automatically released, so you'll 
have to do so manually by clicking "Release Change" in CodePipeline. If you're 
ever unsure if changes went through, even though CodePipeline automatically 
released a change, do it manually anyway.

    You've now deployed a pipeline stack to AWS and you know how to update and 
    add new pipelines on-the-fly!

## Viewing your Resources in AWS

You can use the AWS UI to view the resources that were created via the build.

### Code Pipeline

From here you can check the status of your code build to make sure it is running 
successfully.

<https://us-west-2.console.aws.amazon.com/codesuite/codepipeline/pipelines/>

### ECR Container Repository

From here you can check the status of your built images.

<https://us-west-2.console.aws.amazon.com/ecr/repositories?region=us-west-2>

### S3 Buckets

<https://s3.console.aws.amazon.com/s3/buckets?region=us-west-2>

### Lambda Functions

You can see the lambda functions that were created for each pipeline here.

<https://us-west-2.console.aws.amazon.com/lambda/home?region=us-west-2#/functions>

### Event Bridge Cron Rules

<https://us-west-2.console.aws.amazon.com/events/home?region=us-west-2#/rules>

### Cloud Formation Stack

You can see the resources that were created via the CDK deploy.  You can also delete
the stack from here to clean up those resources.  Note that any lambda functions and
Event Bridge cron rules created via the CodePipeline build are NOT part of the stack,
so these would have to be removed by hand.

<https://us-west-2.console.aws.amazon.com/cloudformation/home?region=us-west-2#/stacks?filteringText=&filteringStatus=active&viewNested=true>
