import json
import urllib.request

pid = '594758cc-11f5-4f92-8b3c-1213686591f4'

# Pre-computed image_prompts using realistic style
entities = [
    {
        'name': 'Le Quoc Tien',
        'entity_type': 'character',
        'description': 'Le Quoc Tien: 29-year-old Vietnamese system infrastructure engineer, lean athletic build, sharp determined Asian features, short clean black hair, wearing dark charcoal tactical t-shirt and grey cargo pants, digital wrist gauge, observant survivalist gaze.',
        'image_prompt': 'Single reference image of 29-year-old Vietnamese system infrastructure engineer, lean athletic build, sharp determined Asian features, short clean black hair, wearing dark charcoal tactical t-shirt and grey cargo pants, digital wrist gauge, observant survivalist gaze. Photorealistic RAW photograph, shot on Canon EOS R5, 35mm lens, natural available light, real footage. NOT 3D render, NOT CGI, NOT digital art, NOT illustration, NOT anime, NOT painting, NOT cartoon. COMPOSITION: Full body shot from head to toe, standing upright and straight (not tilted or leaning). Centered in frame with balanced composition. Front-facing view, looking directly at camera. Neutral simple background that does not distract from the subject. Proper proportions and anatomy. Character perfectly vertical, not skewed or rotated. ONE single image only, NOT a multi-panel grid or multiple views. Studio lighting, highly detailed',
        'voice_description': 'Calm, firm, determined Vietnamese male voice with deep analytical cadence'
    },
    {
        'name': 'Do Minh Kha',
        'entity_type': 'character',
        'description': 'Do Minh Kha: 34-year-old Vietnamese logistics commander, tall imposing authoritative posture, slicked-back dark hair, wearing an unbuttoned black button-down shirt with rolled-up sleeves, dark trousers, distinctive matte black ring on his left ring finger, piercing cold calculated gaze.',
        'image_prompt': 'Single reference image of 34-year-old Vietnamese logistics commander, tall imposing authoritative posture, slicked-back dark hair, wearing an unbuttoned black button-down shirt with rolled-up sleeves, dark trousers, distinctive matte black ring on his left ring finger, piercing cold calculated gaze. Photorealistic RAW photograph, shot on Canon EOS R5, 35mm lens, natural available light, real footage. NOT 3D render, NOT CGI, NOT digital art, NOT illustration, NOT anime, NOT painting, NOT cartoon. COMPOSITION: Full body shot from head to toe, standing upright and straight (not tilted or leaning). Centered in frame with balanced composition. Front-facing view, looking directly at camera. Neutral simple background that does not distract from the subject. Proper proportions and anatomy. Character perfectly vertical, not skewed or rotated. ONE single image only, NOT a multi-panel grid or multiple views. Studio lighting, highly detailed',
        'voice_description': 'Low, smooth, chillingly calm male voice with absolute authority'
    },
    {
        'name': 'Tran Thanh Thuy',
        'entity_type': 'character',
        'description': 'Tran Thanh Thuy: 27-year-old Vietnamese investigative journalist, smart analytical expression, hair tied back in a neat ponytail, wearing a light beige utility shirt, olive multi-pocket reporter vest, canvas shoulder bag carrying a compact camera, intelligent perceptive dark eyes.',
        'image_prompt': 'Single reference image of 27-year-old Vietnamese investigative journalist, smart analytical expression, hair tied back in a neat ponytail, wearing a light beige utility shirt, olive multi-pocket reporter vest, canvas shoulder bag carrying a compact camera, intelligent perceptive dark eyes. Photorealistic RAW photograph, shot on Canon EOS R5, 35mm lens, natural available light, real footage. NOT 3D render, NOT CGI, NOT digital art, NOT illustration, NOT anime, NOT painting, NOT cartoon. COMPOSITION: Full body shot from head to toe, standing upright and straight (not tilted or leaning). Centered in frame with balanced composition. Front-facing view, looking directly at camera. Neutral simple background that does not distract from the subject. Proper proportions and anatomy. Character perfectly vertical, not skewed or rotated. ONE single image only, NOT a multi-panel grid or multiple views. Studio lighting, highly detailed',
        'voice_description': 'Clear, articulate, sharp and perceptive Vietnamese female voice'
    },
    {
        'name': 'Nguyen Trai Avenue',
        'entity_type': 'location',
        'description': 'Nguyen Trai Avenue: Wide bustling urban avenue in Hanoi during morning rush hour, elevated concrete metro tracks overhead with modern green Cat Linh - Ha Dong passenger train gliding past sleek glass skyscrapers and dense commuter traffic under a clear morning sky.',
        'image_prompt': 'Single reference image of Wide bustling urban avenue in Hanoi during morning rush hour, elevated concrete metro tracks overhead with modern green Cat Linh - Ha Dong passenger train gliding past sleek glass skyscrapers and dense commuter traffic under a clear morning sky. Photorealistic RAW photograph, shot on Canon EOS R5, 35mm lens, natural available light, real footage. NOT 3D render, NOT CGI, NOT digital art, NOT illustration, NOT anime, NOT painting, NOT cartoon. COMPOSITION: Establishing shot showing the full environment. Balanced level composition with straight horizon. Clear focal point. Atmospheric and richly detailed. Show depth and spatial layout. ONE single image only, NOT a multi-panel grid or multiple views. Studio lighting, highly detailed'
    },
    {
        'name': 'Dai Ha Mall Heat Trap',
        'entity_type': 'location',
        'description': 'Dai Ha Mall Heat Trap: Massive modern glass shopping mall in Ha Dong district under a terrifying dark crimson sun and apocalyptic red sky, giant glass windows completely fogged with thick condensation from dark boiling interior, heat ripples warping the melting empty asphalt parking lot outside.',
        'image_prompt': 'Single reference image of Massive modern glass shopping mall in Ha Dong district under a terrifying dark crimson sun and apocalyptic red sky, giant glass windows completely fogged with thick condensation from dark boiling interior, heat ripples warping the melting empty asphalt parking lot outside. Photorealistic RAW photograph, shot on Canon EOS R5, 35mm lens, natural available light, real footage. NOT 3D render, NOT CGI, NOT digital art, NOT illustration, NOT anime, NOT painting, NOT cartoon. COMPOSITION: Establishing shot showing the full environment. Balanced level composition with straight horizon. Clear focal point. Atmospheric and richly detailed. Show depth and spatial layout. ONE single image only, NOT a multi-panel grid or multiple views. Studio lighting, highly detailed'
    },
    {
        'name': 'Ngoc Truc Warehouse',
        'entity_type': 'location',
        'description': 'Ngoc Truc Warehouse: Secluded industrial concrete warehouse on Hanoi outskirts, weathered corrugated metal roof, dusty grey concrete floor with faint cracks, heavy circular dark metal floor hatch with an etched twelve-ray sun emblem hidden beneath metal shelving.',
        'image_prompt': 'Single reference image of Secluded industrial concrete warehouse on Hanoi outskirts, weathered corrugated metal roof, dusty grey concrete floor with faint cracks, heavy circular dark metal floor hatch with an etched twelve-ray sun emblem hidden beneath metal shelving. Photorealistic RAW photograph, shot on Canon EOS R5, 35mm lens, natural available light, real footage. NOT 3D render, NOT CGI, NOT digital art, NOT illustration, NOT anime, NOT painting, NOT cartoon. COMPOSITION: Establishing shot showing the full environment. Balanced level composition with straight horizon. Clear focal point. Atmospheric and richly detailed. Show depth and spatial layout. ONE single image only, NOT a multi-panel grid or multiple views. Studio lighting, highly detailed'
    },
    {
        'name': 'Dried West Lake Colossus',
        'entity_type': 'location',
        'description': 'Dried West Lake Colossus: Dried-up West Lake lakebed under a scorching apocalyptic deep crimson sun and hazy red sky, cracked black mud terrain revealing gigantic ancient dark metallic curved rib structures rising from the earth like colossal dragon bones, rising hot thermal steam.',
        'image_prompt': 'Single reference image of Dried-up West Lake lakebed under a scorching apocalyptic deep crimson sun and hazy red sky, cracked black mud terrain revealing gigantic ancient dark metallic curved rib structures rising from the earth like colossal dragon bones, rising hot thermal steam. Photorealistic RAW photograph, shot on Canon EOS R5, 35mm lens, natural available light, real footage. NOT 3D render, NOT CGI, NOT digital art, NOT illustration, NOT anime, NOT painting, NOT cartoon. COMPOSITION: Establishing shot showing the full environment. Balanced level composition with straight horizon. Clear focal point. Atmospheric and richly detailed. Show depth and spatial layout. ONE single image only, NOT a multi-panel grid or multiple views. Studio lighting, highly detailed'
    }
]

created_ids = {}

for ent in entities:
    req_body = json.dumps(ent).encode('utf-8')
    req = urllib.request.Request(
        'http://127.0.0.1:8100/api/characters',
        data=req_body,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    with urllib.request.urlopen(req) as resp:
        char_data = json.loads(resp.read().decode('utf-8'))
        cid = char_data['id']
        created_ids[ent['name']] = cid
        print(f"Created Character: {ent['name']} -> {cid}")

    # Link to project
    link_req = urllib.request.Request(
        f'http://127.0.0.1:8100/api/projects/{pid}/characters/{cid}',
        data=b'{}',
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    with urllib.request.urlopen(link_req) as resp:
        print(f"Linked {ent['name']} to project {pid}")

with open('scripts/created_entities.json', 'w', encoding='utf-8') as f:
    json.dump(created_ids, f, indent=2)
print("Done all entities!")
