import requests

resp = requests.get("http://127.0.0.1:8100/api/ext/find-actions")
print(resp.json())
