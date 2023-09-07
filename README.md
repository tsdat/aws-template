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
Do this from the VSCode window that is attached to the tsdat-cdk container.

**Don't forget to copy the ARN of your CodeStar Connection** 

### **7. Configure your AWS profiles (one time only)**
tsdat profile:
```
root@tsdat-cdk:~/cdk_app# aws configure --profile tsdat
AWS Access Key ID [****************X3EN]: 
AWS Secret Access Key [****************6o89]: 
Default region name [None]: us-west-2
Default output format [None]: 
```

tsdat sso profile:
```
root@tsdat-cdk:~/cdk_app# aws configure sso --profile tsdat
SSO session name (Recommended): tsdat
SSO start URL [None]: https://pnnl.awsapps.com/start
SSO region [None]: us-west-2
SSO registration scopes [sso:account:access]:
Attempting to automatically open the SSO authorization page in your default browser.
If the browser does not open or you wish to use a different device to authorize this request, open the following URL:

https://device.sso.us-west-2.amazonaws.com/

Then enter the code:

NCGP-GDLD
There are 4 AWS accounts available to you.
Using the account ID 332883119153
There are 2 roles available to you.
Using the role name "AdministratorAccess"
CLI default client Region [us-west-2]:
CLI default output format [None]:

To use this profile, specify the profile name using --profile, as shown:

aws s3 ls --profile tsdat
```

Your ~/.aws/config file should look like this:
```
[profile tsdat]
region = us-west-2
sso_session = tsdat
sso_account_id = xxxxxxxxxxx
sso_role_name = AdministratorAccess
[sso-session tsdat]
sso_start_url = https://pnnl.awsapps.com/start
sso_region = us-west-2
sso_registration_scopes = sso:account:access
```

### **7. Edit your aws credentials**
CDK requires that your AWS credentials be set in order to authenticate your CLI actions.
From your VSCode window tha tis attached to the tsdat-cdk container

From the VSCode Explorer, open .aws/credentials file

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
