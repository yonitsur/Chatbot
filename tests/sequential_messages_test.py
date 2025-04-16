import requests
import threading
import time
import json
from config import UVICORN_PORT


API_URL = f"http://localhost:{UVICORN_PORT}/query"
HEADERS = {"Content-Type": "application/json"}

messages = [
    "Are there startups about wine in Chicago?",
    "Wait, I meant in NY!",
    "Actually, focus on food startups in Paris.",
]

results = {}
results_lock = threading.Lock()

def send_request(message):
    payload = json.dumps({"message": message})
    try:
        response = requests.post(API_URL, headers=HEADERS, data=payload, timeout=45)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Request failed for '{message}': {e}")
        data = {"error": f"Request failed: {e}"}
    except json.JSONDecodeError as e:
        print(f"JSON decode failed for '{message}': {e}")
        data = {"error": f"Failed to decode JSON response: {e}", "raw_text": response.text if 'response' in locals() else 'N/A'}

    with results_lock:
        results[message] = data

threads = []
print("Starting requests...")
for msg in messages:
    thread = threading.Thread(target=send_request, args=(msg,))
    threads.append(thread)
    thread.start()
    time.sleep(0.15)

print("Waiting for requests to complete...")
for thread in threads:
    thread.join()

print("\n--- Results ---")
processed_count = 0
skipped_count = 0
error_count = 0

for msg in messages:
    result = results.get(msg, {"error": "Result not found"})
    print(f"'{msg}': {result}")

    skip_message = "This message was skipped because a newer message was received."

    if "error" in result:
        error_count += 1
    elif result.get("output") == skip_message:
        skipped_count += 1
    elif "output" in result:
        processed_count += 1
    else:
        print(f"Warning: Unexpected response structure for '{msg}': {result}")
        error_count += 1


print("\n--- Summary ---")
print(f"Processed: {processed_count}")
print(f"Skipped:   {skipped_count}")
print(f"Errors:    {error_count}")

if processed_count == 1 and skipped_count == len(messages) - 1 and error_count == 0:
     print("\n>>> PASSED <<<")
else:
     print("\n>>> FAILED <<<")
     if error_count > 0:
         print("    (Check for request/response errors above)")
     if not (processed_count == 1 and skipped_count == len(messages) - 1):
         print("    (Incorrect number of processed/skipped messages)")