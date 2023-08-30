# Deploying Tsdat Pipelines to AWS
This repository contains the files needed to deploy your Tsdat pipelines to Amazon
Web Services (AWS).  


## Prerequisites

### **AWS Account**
In order to deploy resources to AWS, you must have an account set up and you must have
administrator priviledges on that account.  If you do not have an AWS account or you
do not have admin priviledges, then you should contact the local cloud administrator
for your organization.

### **Create an AWS CodeStar Connection to GitHub**
https://docs.aws.amazon.com/dtconsole/latest/userguide/connections-create-github.html

### **Docker**
We use a Docker container with VSCode to make setting up your development environment
a snap.  We assume users have a basic familarity with Docker containers. If you are 
new to Docker, there are many free online tutorials to get you started.

- **Windows Users:** Install Docker on wsl2 (TODO: link coming soon)
- **Mac Users:** - [Install Docker Desktop](https://docs.docker.com/desktop/install/mac-install/).

### **Visual Studio Code**
- [Install VSCode](https://code.visualstudio.com/download)
- Install the **ms-vscode-remote.vscode-remote-extensionpack** extension

## Deploying your pipelines

### **Step 1.** Check out your aws repo and your pipelines repo.

### **Step 2.** Open your aws repo in VSCode
We suggest adding your pipelines repo to your VSCode workspace and then saving the workspace so you can reuse it.

### **Step 3.** Start your cdk container & attach
Start a terminal in VSCode and run:
 ```
 docker compose build
 docker compose up -d
 ```

Then attach a VSCode window to the running container:
Attach to running container (cdk)

### **From your cdk container **
#### Edit your pipelines_config.yml file
#### Edit your aws credentials



