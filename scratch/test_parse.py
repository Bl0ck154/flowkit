import sys
from agent.services import flow_batch as fb

# With r''' so backslashes are preserved:
raw = r''')]}'

2428
[["wrb.fr","as29s","[\"666bc47c-1fa1-4167-83cc-3088840b3146\",\"594758cc-11f5-4f92-8b3c-1213686591f4\",\"d19f6811-455b-4838-bdc2-b908aeb7bd36\",\"CAE\",null,[[1790169824,340307000],null,null,null,null,null,[null,null,[[\"test\",null,[[[\"test\"]]]]],[],1],null,null,1,\"https://flow-content.google/image/666bc47c-1fa1-4167-83cc-3088840b3146?Expires=123\",null,null,169345]]",null,null,null,"generic"]]
'''

results = fb.parse_envelope(raw)
print("Results len:", len(results))
if results:
    print("Result 0 rpcid:", results[0].rpcid)
    urls = fb.read_media_urls(results[0].data, '666bc47c-1fa1-4167-83cc-3088840b3146')
    print("Extracted image URL:", urls.image)
