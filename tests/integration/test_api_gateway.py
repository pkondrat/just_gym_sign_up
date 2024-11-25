import os

import boto3
import pytest

from just_gym.app import lambda_handler

"""
Make sure env variable AWS_SAM_STACK_NAME exists with the name of the stack we are going to test. 
"""


class TestApiGateway:

    # @pytest.fixture()
    # def api_gateway_url(self):
    #     """ Get the API Gateway URL from Cloudformation Stack outputs """
    #     stack_name = os.environ.get("AWS_SAM_STACK_NAME")
    #
    #     if stack_name is None:
    #         raise ValueError('Please set the AWS_SAM_STACK_NAME environment variable to the name of your stack')
    #
    #     client = boto3.client("cloudformation")
    #
    #     try:
    #         response = client.describe_stacks(StackName=stack_name)
    #     except Exception as e:
    #         raise Exception(
    #             f"Cannot find stack {stack_name} \n" f'Please make sure a stack with the name "{stack_name}" exists'
    #         ) from e
    #
    #     stacks = response["Stacks"]
    #     stack_outputs = stacks[0]["Outputs"]
    #     api_outputs = [output for output in stack_outputs if output["OutputKey"] == "HelloWorldApi"]
    #
    #     if not api_outputs:
    #         raise KeyError(f"HelloWorldAPI not found in stack {stack_name}")
    #
    #     return api_outputs[0]["OutputValue"]  # Extract url from stack outputs

    def test_lambda_handler(self):
        event = {
          "class_name": "BRZUCH&CARDIO",
          "class_start_time": "08:00:00",
          "bypass_window_check": True
        }

        response = lambda_handler(event, None)
        assert response["statusCode"] == 200


