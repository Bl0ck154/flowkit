import json
import urllib.request

req = urllib.request.Request(
    'http://127.0.0.1:8100/api/ext/media-url?media_id=666bc47c-1fa1-4167-83cc-3088840b3146'
)
# Wait, let's call the ext directly or fetch from main
res = urllib.request.urlopen('http://127.0.0.1:8100/api/ext/netlog')
data = json.loads(res.read().decode())
for c in data.get('captures', []):
    if 'as29s' in c.get('url', ''):
        print("as29s capture:", c['url'])
        print("f.req:", c.get('body'))
