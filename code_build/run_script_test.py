import boto3

lambda_client = boto3.client('lambda', region_name='us-west-2')


def get_lambda(function_name) -> dict:
    """
    Gets data about a Lambda function.

    :param function_name: The name of the function.
    :return: The function data.
    """
    data = lambda_client.get_function(FunctionName=function_name)
    return data


def create_function(function_name, handler_name, iam_role, deployment_package):
    """
    Deploys a Lambda function.

    :param function_name: The name of the Lambda function.
    :param handler_name: The fully qualified name of the handler function. This
                            must include the file name and the function name.
    :param iam_role: The IAM role to use for the function.
    :param deployment_package: The deployment package that contains the function
                                code in .zip format.
    :return: The Amazon Resource Name (ARN) of the newly created function.
    """
    # LAMBDA_ROLE_ARN = "arn:aws:iam::" + ACCOUNT_NUMBER + ":role/tsdat_pipeline_lambda" 
    lambda_role_arn = ''
    
    response = lambda_client.create_function(
        FunctionName=function_name,
        Runtime='provided.al2',
        Role=lambda_role_arn,
        Handler='lambda_function.lambda_handler',
        Code={
            'ImageUri': '332883119153.dkr.ecr.us-west-2.amazonaws.com/a2e-tsdat-test:lambdafunction-4bdc10a8a50a-python3.8-v1',
        },
        Timeout=120,  
        MemorySize=1024, 
    )
    
    # Wait for create to finish
    waiter = lambda_client.get_waiter('function_active_v2')
    waiter.wait(FunctionName=function_name)
    print(f"Created function {function_name} with ARN: {response['FunctionArn']}.")
    
    return response['FunctionArn']

get_lambda('tsdat-pipeline-lambda')