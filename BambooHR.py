import requests
import json
from datetime import date
import base64
import xml.etree.ElementTree as ET

# Function to base64 encode the API key, in other case, it will not send the request.


def encode_api_key(api_key):
    api_key_bytes = f"{api_key}:".encode('utf-8')
    encoded_api_key = base64.b64encode(api_key_bytes).decode('utf-8')
    return encoded_api_key

# Get Time Off Requests from BambooHR API  // https://documentation.bamboohr.com/reference/time-off-get-time-off-requests-1

# Replace "YOUR_API_KEY" with your actual API Key generated from BambooHR.

api_key = "YOUR_API_KEY"
encoded_api_key = encode_api_key(api_key)

# Replace "YOUR_COMPANY_DOMAIN_IN_BAMBOOHR" with your actual company domain in BambooHR.

companyDomain = 'YOUR_COMPANY_DOMAIN_IN_BAMBOOHR'

today_date = date.today().strftime('%Y-%m-%d')
url_requests = f"https://api.bamboohr.com/api/gateway.php/{companyDomain}/v1/time_off/requests/?start={today_date}&end={today_date}"
headers_requests = {"Authorization": f"Basic {encoded_api_key}"}
response_requests = requests.get(url_requests, headers=headers_requests)

if response_requests.status_code == 200:
    print("Get Time Off Request is successful!")

    # Some of the requests may not be approved. For correct information, we need to parse the XML response for approved requests.
    root_requests = ET.fromstring(response_requests.text)

    # Create a dictionary to store approved requests grouped by vacation type
    approved_requests_by_type = {}

    # Iterate through each request
    for request_elem in root_requests.findall('.//request[status="approved"]'):
        employee_id = request_elem.find('employee').attrib['id']
        employee_name = request_elem.find('employee').text
        start_date = request_elem.find('start').text
        end_date = request_elem.find('end').text
        vacation_type = request_elem.find('type').text

        # Add information to the dictionary grouped by vacation type
        if vacation_type not in approved_requests_by_type:
            approved_requests_by_type[vacation_type] = []

        approved_requests_by_type[vacation_type].append({
            'employee_id': employee_id,
            'employee_name': employee_name,
            'start_date': start_date,
            'end_date': end_date,
            'vacation_type': vacation_type
        })

else:
    print(f"Request for approved requests failed with status code {response_requests.status_code}.")
    print(response_requests.text)
    approved_requests_by_type = {}

# Get Employees from BambooHR API // https://documentation.bamboohr.com/reference/get-employee
url_employees = f"https://api.bamboohr.com/api/gateway.php/{companyDomain}/v1/employees/directory"
headers_employees = {
    "accept": "application/xml",
    "authorization": f"Basic {encoded_api_key}"
}

# Initialize employee_jobs with an empty dictionary
employee_jobs = {}

try:
    response_employees = requests.get(url_employees, headers=headers_employees)
    response_employees.raise_for_status()  # Raise an HTTPError for bad responses

    # Parse the XML response for employee job titles
    root_employees = ET.fromstring(response_employees.text)

    # Iterate through each 'employee' element. We need to compare employee IDs to add the correct job titles. However, if an employee is disabled, the request still appears in "Get Time Off Request," but in "Get Employees," we could not find the employee's ID. So our code will not add this employee in JSON.
    for employee_elem in root_employees.findall('.//employee'):
        employee_id = employee_elem.get('id')
        job_title_elem = employee_elem.find('.//field[@id="jobTitle"]')
        job_title = job_title_elem.text if job_title_elem is not None else "Job Title Not Found"

        # Add information to the dictionary
        employee_jobs[employee_id] = job_title

    print("Get Employee Request is successful!")

except requests.exceptions.RequestException as e:
    print(f"Request for employee job titles failed. Error: {e}")
    # You may choose to exit or handle the error as appropriate
    employee_jobs = {}

# Write the updated approved_requests to the JSON file
filtered_requests = [
    {
        'employee_id': request['employee_id'],
        'employee_name': request['employee_name'],
        'start_date': request['start_date'],
        'end_date': request['end_date'],
        'vacation_type': request['vacation_type'],
        'job_title': employee_jobs.get(request['employee_id'])
    }
    for vacation_type, requests_list in approved_requests_by_type.items()
    for request in requests_list
    if employee_jobs.get(request['employee_id']) is not None
]

# Check if the JSON file writing was successful
try:
    with open('output.json', 'w') as json_file:
        json.dump(filtered_requests, json_file, indent=2)
    print("JSON file written successfully!")
except Exception as e:
    print(f"Failed to write JSON file. Error: {e}")

# Replace "YOUR_WEBHOOK_URL" with your actual Slack webhook URL.
webhook_url = 'YOUR_WEBHOOK_URL'

# Format the message using information from the filtered_requests
formatted_message = ""

current_vacation_type = None

for entry in filtered_requests:
    if entry['vacation_type'] != current_vacation_type:
        # Start a new group with the vacation type as the header
        current_vacation_type = entry['vacation_type']
        formatted_message += f"*On {current_vacation_type}*\n"  # Use asterisks for bold in Slack

    formatted_message += f"{entry['employee_name']} ({entry['job_title']})\n"
    formatted_message += f"From: {entry['start_date']}  To: {entry['end_date']}\n\n"

# Send the formatted message to Slack
payload = {
    'text': formatted_message
}

headers = {
    'Content-Type': 'application/json'
}

response_slack = requests.post(webhook_url, data=json.dumps(payload), headers=headers)

# Check if the message was sent to Slack successfully
if response_slack.status_code == 200:
    print("Message sent to Slack successfully")
else:
    print(f"Failed to send message to Slack. Error: {response_slack.text}")
