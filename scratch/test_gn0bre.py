import urllib.request
import json

client_uuid = "007b60d4-79aa-4a7f-8133-cc776c4daba7"
freq = f'[[["GN0Bre","[\\"{client_uuid}\\"]",null,"generic"]]]'

# call via test-direct or batch-rpc
# let's add a small endpoint or call directly
print("Testing GN0Bre with UUID:", client_uuid)
