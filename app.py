import json
from datetime import datetime, timedelta
import time
import requests

# Constants for class names and start times
SIGNUP_FOR = [
    {
        "weekday": 5, # Today is Saturday (+ 3 days = Tuesday)
        "class_name": "Just PUPA & BRZUCH",
        "class_start_time": "19:00:00"  # TUESDAY
    },
    {
        "weekday": 0, # Today is Monday (+ 3 days = Thursday)
        "class_name": "Just PUPA & BRZUCH",
        "class_start_time": "19:00:00" # THURSDAY
    },
    {  # only for tests
        "weekday": 2,  # Today is Wednesday (+ 2 days = Thursday)
        "class_name": "ZDROWY KRĘGOSŁUP I MOCNY BRZUCH",
        "class_start_time": "08:30:00"  # THURSDAY
    }
]
GYM_USERNAME="##GYM_USERNAME##"
GYM_PASSWORD="##GYM_PASSWORD##"
PUSHOVER_APP_TOKEN="##PUSHOVER_APP_TOKEN##"
PUSHOVER_USER_KEY="##PUSHOVER_USER_KEY##"
BASE_URL = "https://justgym.pl/wp-admin/admin-ajax.php"

#
def notify(message):
    # send the message to pushover service
    url = "https://api.pushover.net/1/messages.json"
    payload = {
        "token": PUSHOVER_APP_TOKEN,
        "user": PUSHOVER_USER_KEY,
        "message": message
    }
    response = requests.post(url, data=payload)
    return response

def extract_cookie(cookies, username, path):
    for cookie in cookies:
        if username in cookie and path in cookie:
            return cookie.strip()
    return None


def signup():

    # select the class name and start time based on the day of the week
    selected_class_name = None
    selected_class_start_time = None

    # select the dict based on the current day of the week. If the day is not found, nothing will be selected
    for item in SIGNUP_FOR:
        if datetime.now().weekday() == item["weekday"]:
            selected_class_name = item["class_name"]
            selected_class_start_time = item["class_start_time"]
            break

    if selected_class_name is None:
        message = 'No class found for today.'
        print(message)
        notify(message)
        return {
            'statusCode': 400,
            'body': json.dumps({'message': message})
        }

    print(f"Selected class name: {selected_class_name}")
    print(f"Selected class start time: {selected_class_start_time}")

    # Step 1: Authenticate and get the Bearer token
    auth_payload = {
        'action': 'mda_user_login',
        'log': GYM_USERNAME,
        'pwd': GYM_PASSWORD,
        'return_url': 'https://justgym.pl/klient/'
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    auth_response = requests.post(BASE_URL, data=auth_payload, headers=headers)
    auth_response.raise_for_status()
    token = auth_response.json().get("api_check", {}).get("body", {}).get("accessToken")

    if not token:
        message = 'Failed to authenticate to just gym.'
        print(message)
        notify(message)
        return {
            'statusCode': 400,
            'body': json.dumps({'message': message})
        }

    print(f"Bearer token: {token[:10]}...")

    # Extract the required cookie from the Set-Cookie header
    cookies = auth_response.headers.get('Set-Cookie', '').split(',')
    required_cookie = extract_cookie(cookies, "kondratowicz.an", "path=/wp-admin")

    # Determine the date range for the classes
    # target_date = datetime.now() + timedelta(days=3)
    target_date = datetime.now() + timedelta(days=2) # tests only

    # Set the date_from and date_to parameters
    date_from = target_date.strftime('%Y-%m-%d 00:00:00')
    date_to = target_date.strftime('%Y-%m-%d 23:59:59')

    print(f"Date from: {date_from}")
    print(f"Date to: {date_to}")

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
    classes_response = requests.post(BASE_URL, data=classes_payload, headers=classes_headers)
    classes_response.raise_for_status()
    classes_json_str = classes_response.text
    classes = json.loads(json.loads(classes_json_str)).get("results", [])

    print(f"Classes found: {len(classes)}")
    if len(classes) == 0:
        message = 'No classes found.'
        print(message)
        notify(message)
        return {
            'statusCode': 400,
            'body': json.dumps({'message': message})
        }

    # Filter classes based on the desired class names and times
    desired_classes = []
    for cls in classes:
        if cls['name'].startswith(selected_class_name) and cls['startDate'].endswith(selected_class_start_time):
            desired_classes.append(cls)

    print(f"Desired classes found: {len(desired_classes)}")

    # Ensure exactly one class is found
    if len(desired_classes) != 1:
        message = f'Expected to find exactly one class, but found {len(desired_classes)}.'
        print(message)
        notify(message)
        return {
            'statusCode': 400,
            'body': json.dumps({'message': message})
        }

    # Step 3: Sign up for the class
    cls = desired_classes[0]
    class_id = cls['classId']
    class_start = cls['startDate']
    class_end = cls['endDate']
    class_instructor = cls['instructorName']
    # Parse the datetime string
    dt_from = datetime.strptime(class_start, '%Y-%m-%dT%H:%M:%S')
    dt_to = datetime.strptime(class_end, '%Y-%m-%dT%H:%M:%S')
    # Format the date with weekday name
    date_with_weekday = dt_from.strftime('%d.%m (%A)')

    # Format the time
    time_from_str = dt_from.strftime('%H:%M')
    time_to_str = dt_to.strftime('%H:%M')


    signup_payload = {
        'action': 'mda_post_class',
        'class_id': f"{class_id}",
        'club_id': '987'
    }
    signup_headers = {
        'Authorization': f'Bearer {token}',
        'Cookie': required_cookie
    }

    retry_intervals = [30, 120, 360, 520]  # Retry intervals in seconds (30 seconds, 3 minutes)
    for interval in retry_intervals:
        signup_response = requests.post(BASE_URL, headers=signup_headers, data=signup_payload)
        signup_result = signup_response.json()
        print(f"Signup result: {signup_result}")

        if signup_result.get("status") == "ok":
            break
        else:
            print(f"Signup failed, retrying in {interval} seconds...")
            time.sleep(interval)
    else:
        message = f"Failed to sign up for class ID: {class_id} after retries."
        print(message)
        notify(message)
        return {
            'statusCode': 400,
            'body': json.dumps({'message': message})
        }

    # Check the status and position on reserve list
    if signup_result.get("status") == "ok":
        class_reservation = signup_result.get("class", {}).get("body", {}).get("classReservations", [])[0]
        position_on_reserve_list = class_reservation.get("positionOnReserveList")
        if position_on_reserve_list is None:
            signup_response_json = signup_response.json()
            message = f"Just gym: {signup_response_json['message']}. Detale:  {selected_class_name} w dniu: {date_with_weekday} {time_from_str} - {time_to_str} z {class_instructor}. class ID: {class_id}. link: https://justgym.pl/klient/zajecia-grupowe/"
        else:
            message = f"Signed up for class ID: {class_id}, but you are on the reserve list at position: {position_on_reserve_list}"
    else:
        message = f"Failed to sign up for class ID: {class_id}"

    print(message)

    # Step 4: Send the result message to SNS topic
    notify(message)

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': message,
            'class': cls
        })
    }

if __name__ == '__main__':
    signup()