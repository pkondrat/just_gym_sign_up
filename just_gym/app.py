import json
import os
from datetime import datetime, timedelta

import boto3
import requests

# Constants for class names and start times
MONDAY_CLASS_NAME = "Just PUPA & BRZUCH"
MONDAY_CLASS_START_TIME = "19:00:00"
THURSDAY_CLASS_NAME = "ZUMBA"
THURSDAY_CLASS_START_TIME = "19:00:00"

# Constants for weekdays
MONDAY = 0
THURSDAY = 3
FRIDAY = 4

def send_snstopic(message):
    if os.environ.get('NOTIFY_SNS_FLAG', 'false').lower() == 'true':
        sns_client = boto3.client('sns')
        sns_topic_arn = os.environ['NOTIFY_SNS_TOPIC']
        sns_client.publish(
            TopicArn=sns_topic_arn,
            Message=message,
            Subject='Just gym sign up'
        )
    else:
        print("SNS topic notification is disabled.")

def lambda_handler(event, context):
    """Sample pure Lambda function

    Parameters
    ----------
    event: dict, required
        API Gateway Lambda Proxy Input Format

        Event doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html#api-gateway-simple-proxy-for-lambda-input-format

    context: object, required
        Lambda Context runtime methods and attributes

        Context doc: https://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html

    Returns
    ------
    API Gateway Lambda Proxy Output Format: dict

        Return doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html
    """

    base_url = "https://justgym.pl/wp-admin/admin-ajax.php"

    # select the class name and start time based on the day of the week
    selected_class_name = None
    selected_class_start_time = None
    if datetime.now().weekday() == MONDAY:
        selected_class_name = THURSDAY_CLASS_NAME
        selected_class_start_time = THURSDAY_CLASS_START_TIME
    elif datetime.now().weekday() == FRIDAY:
        selected_class_name = MONDAY_CLASS_NAME
        selected_class_start_time = MONDAY_CLASS_START_TIME

    # Get class_name, class_start_time, and bypass_window_check from event
    class_name = event.get('class_name', selected_class_name)
    class_start_time = event.get('class_start_time', selected_class_start_time)
    bypass_window_check = event.get('bypass_window_check', False)

    # Check if the function is run on Monday or Friday and within 12:00-12:30 CET period
    now = datetime.now()
    if not bypass_window_check and (now.weekday() not in [MONDAY, FRIDAY] or not (12 == now.hour and now.minute < 30)):
        message = 'This script should only run on Mondays or Fridays between 12:00 and 12:30 CET.'
        send_snstopic(message)
        return {
            'statusCode': 400,
            'body': json.dumps({'message': message})
        }

    # Step 1: Authenticate and get the Bearer token
    auth_payload = {
        'action': 'mda_user_login',
        'log': os.environ['GYM_USERNAME'],
        'pwd': os.environ['GYM_PASSWORD'],
        'return_url': 'https://justgym.pl/klient/'
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    auth_response = requests.post(base_url, data=auth_payload, headers=headers)
    auth_response.raise_for_status()
    token = auth_response.json().get("api_check", {}).get("body", {}).get("accessToken")

    # Determine the date range for the classes
    target_date = now + timedelta(days=3)

    # Set the date_from and date_to parameters
    date_from = target_date.strftime('%Y-%m-%d 00:00:00')
    date_to = target_date.strftime('%Y-%m-%d 23:59:59')



    # Step 2: Get the list of classes and their IDs
    classes_payload = {
        'action': 'ef_get_classes',
        'club_id': '987',
        'date_from': date_from,
        'date_to': date_to
    }
    classes_headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': f'Bearer {token}'
    }
    classes_response = requests.post(base_url, data=classes_payload, headers=classes_headers)
    classes_response.raise_for_status()
    classes_json_str = classes_response.text
    classes =json.loads(json.loads(classes_json_str)).get("results", [])

    # Filter classes based on the desired class names and times
    desired_classes = []
    for cls in classes:
        if cls['name'].startswith(class_name) and cls['startDate'].endswith(class_start_time):
            desired_classes.append(cls)

    # Ensure exactly one class is found
    if len(desired_classes) != 1:
        message = f'Expected to find exactly one class, but found {len(desired_classes)}.'
        send_snstopic(message)
        return {
            'statusCode': 400,
            'body': json.dumps({'message': message})
        }

    # Step 3: Sign up for the class
    cls = desired_classes[0]
    class_id = cls['classId']
    signup_payload = {
        'action': 'mda_post_class',
        'class_id': class_id,
        'club_id': '987'
    }
    signup_headers = {
        'Authorization': f'Bearer {token}'
    }
    signup_response = requests.post(base_url, headers=signup_headers, data=signup_payload)
    signup_response.raise_for_status()
    signup_result = signup_response.json()

    # Check the status and position on reserve list
    if signup_result.get("status") == "ok":
        class_reservation = signup_result.get("class", {}).get("body", {}).get("classReservations", [])[0]
        position_on_reserve_list = class_reservation.get("positionOnReserveList")
        if position_on_reserve_list is None:
            message = f"Successfully signed up for class ID: {class_id}"
        else:
            message = f"Signed up for class ID: {class_id}, but you are on the reserve list at position: {position_on_reserve_list}"
    else:
        message = f"Failed to sign up for class ID: {class_id}"

    # Step 4: Send the result message to SNS topic
    send_snstopic(message)

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': message,
            'class': cls
        })
    }