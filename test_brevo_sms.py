import requests
import json

def send_test_sms():
    api_key = "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"
    phone_number = "+201066480958"
    sender = "TechDay"
    content = "Hello! This is a test SMS from Brevo API."

    url = "https://api.brevo.com/v3/transactionalSMS/sms"
    
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "api-key": api_key
    }
    
    payload = {
        "type": "transactional",
        "unicodeEnabled": True,
        "sender": sender,
        "recipient": phone_number,
        "content": content
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        print(f"Status Code: {response.status_code}")
        print(f"Response Body: {response.text}")
        
        if response.status_code in [201, 200, 202]:
            print("Successfully sent SMS!")
        else:
            print("Failed to send SMS.")
            
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    send_test_sms()
