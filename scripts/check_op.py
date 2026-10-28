import requests
import json

res = requests.post("http://127.0.0.1:8100/api/flow/check-status", json={
    "operations": [{"operation": {"name": "2c817534-e7d9-4711-ba06-8da52e020080"}}],
    "project_id": "594758cc-11f5-4f92-8b3c-1213686591f4"
})
print("Status code:", res.status_code)
print("Response:", json.dumps(res.json(), indent=2))
