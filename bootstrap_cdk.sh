#!/bin/bash
#####################################################################
# Script Name:  bootstrap_cdk.sh
# Description:  Run this script to bootstrap resources needed for
#               the CDK.  You only need to run this once per account
#               and region.  This will create a CDKToolkit stack
#               which contains resources needed for the CDK deploy.
#
#####################################################################
set -e

# We need to pass a branch because our stack uses it for deployment, but we actually
# don't need it for the bootstrap.  So we can pass any value here.
export BRANCH=bootstrap
cdk bootstrap




