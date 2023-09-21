# Deploying Tsdat Pipelines to AWS
This repository contains the files needed to deploy your Tsdat pipelines to Amazon
Web Services (AWS).  


# Prerequisites

### **1. Create GitHub Repositories from Template**
Make sure that you have created two new repositories in your GitHub organization from the
following template repositories:
1. https://github.com/tsdat/pipeline-template
2. https://github.com/tsdat/aws-template

### **2. Get an AWS Account**
In order to deploy resources to AWS, you must have an account set up and you must have
administrator priviledges on that account.  If you do not have an AWS account or you
do not have admin priviledges, then you should contact the local cloud administrator
for your organization.

### **3. Create an AWS CodeStar Connection to GitHub**
https://docs.aws.amazon.com/dtconsole/latest/userguide/connections-create-github.html#connections-create-github-console

**Don't forget to copy the ARN of your connection to the pipelines_config.yml file.**

### **4. Install Docker**
We use a Docker container with VSCode to make setting up your development environment
a snap.  We assume users have a basic familarity with Docker containers. If you are 
new to Docker, there are many free online tutorials to get you started.

**NOTE:** Becasue Docker Desktop can be flaky, especially on Windows, we recommend not using it.
So we are providing alternative, non-Docker Desktop installation instructions for each platform.
The Docker Desktop install is easier and requires fewer steps, so it may be fine for your needs,
but keep in mind it may crash if you update it (requiring a full uninstall/reinstall, and then
you lose all your container environments).  Also, Docker Desktop requires a license.

- **Windows Users:** 
    - Install Docker on wsl2 (TODO: link coming soon) **OR**
    - [Install Docker Desktop](https://docs.docker.com/desktop/install/windows-install/).
- **Mac Users:** 
    - [Install Docker Desktop](https://docs.docker.com/desktop/install/mac-install/).  **OR**
    - [Use Docker/Colima](https://dev.to/elliotalexander/how-to-use-docker-without-docker-desktop-on-macos-217m).
- **Linux Users:** 
    - [Install Docker](https://docs.docker.com/engine/install/ubuntu/). **OR**
    - [Install Docker Desktop](https://docs.docker.com/desktop/install/linux-install/).

### **Visual Studio Code**
- [Install VSCode](https://code.visualstudio.com/download)
- Install the **ms-vscode-remote.vscode-remote-extensionpack** extension

# Deploying your pipelines

### **1. Check out your aws repo and your pipelines repo.**

### **2. Open your aws repo in VSCode**

### **3. Start your cdk container**
Start a terminal in VSCode and run:
 ```
 cd aws-template
 docker compose up -d
 ```

### **4. Attach a new VSCode window to the cdk container**
CTL-SHIFT-p
Dev-Containers:  Attach to Running Container...
Select tsdat-cdk

### **5. Open the provided cdk.code-workspace file**
From the VSCode window that is attached to the tsdat-cdk container:

* File-> Open Workspace from File...
* In the file chooser dialog, select ```/root/cdk_app/.vscode/cdk.code-workspace```

A box should pop up in the bottom right corner that asks if you want to install the 
recommended extensions.  Select **Install**.

Once the extensions are installed, your workspace is ready!  In the Explorer, you
will see two folders:

* cdk_app
* .aws

### **6. Edit your pipelines_config.yml file**
Do this from the VSCode window that is attached to the tsdat-cdk container.  Make
sure to fill out all the sections (build parameters and pipelines).

**Don't forget to copy the ARN of your CodeStar Connection** 

### **7. Configure your tsdat AWS profile (one time only)**
tsdat profile:
```
root@tsdat-cdk:~/cdk_app# aws configure --profile tsdat
AWS Access Key ID [****************X3EN]: 
AWS Secret Access Key [****************6o89]: 
Default region name [None]: us-west-2
Default output format [None]: 
```

Your ~/.aws/config file should look like this:
```
[profile tsdat]
region = us-west-2
```

### **7. Edit your aws credentials**
CDK requires that your AWS credentials be set in order to authenticate your CLI actions.

**You will need to do this BEFORE you deploy your stack.**

From your VSCode window tha tis attached to the tsdat-cdk container:
* From the Explorer view, open .aws/credentials file.  
* Then go to the AWS login page `https://pnnl.awsapps.com/start`
* Then click $PROJECT_NAME -> Administrator -> Command line or programmatic access  (use whatever project you are admin for)
* In the section, "Option 2: Manually add a profile to your AWS credentials file (Short-term credentials)",
Click on the box to copy the text.
* Paste it in  your credentials file under the [tsdat] profile (make sure to delete
the line [xxxxx _AdministratorAccess])

Your credentials file should look like this (with real values instead of the XXXX):
```
[tsdat]
aws_access_key_id=XXXXXXX
aws_secret_access_key=XXXXXX
aws_session_token=XXXXXX
```


### **8. Run the cdk bootstrap (Only need to do this the FIRST time you deploy)**
``` 
cd aws-template
cdk bootstrap
```

### **9. Run the cdk build**
You can re-run this for each branch you want to deploy (e.g., dev, prod, etc.) and any time
you make changes to the stack (for example, you add a new permission to your lambda role).

**NOTE: ** Most deployments will not need to change anything in the stack, but advanced users
are free to customize.

```
cd aws-template
./deploy_stack.sh $BRANCH   (where $BRANCH is the branch you want to deploy (e.g., dev/prod))
```
