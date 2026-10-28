import requests
import json

res = requests.post("http://127.0.0.1:8100/api/flow/check-status", json={
    "operations": [
        {"operation": {"name": "f870145a-7ab6-4608-9643-25839dcf8a9f"}},
        {"operation": {"name": "825308bd-19c6-4171-9b58-d2e01513b639"}},
        {"operation": {"name": "c8cfd8a0-1e3f-4400-8fb9-2c146e0d8db4"}}
    ],
    "project_id": "594758cc-11f5-4f92-8b3c-1213686591f4"
})
print("Status code:", res.status_code)
print(json.dumps(res.json(), indent=2))
