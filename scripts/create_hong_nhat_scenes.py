import json
import urllib.request

vid = '945ad6d4-5d79-4790-80db-1bff16ed7255'

scenes = [
    {
        'video_id': vid,
        'display_order': 0,
        'chain_type': 'ROOT',
        'character_names': ['Le Quoc Tien', 'Do Minh Kha'],
        'prompt': 'Dramatic low-angle cinematic shot in subterranean B3 basement parking at Me Tri under extreme heat. Le Quoc Tien lies on scorched concrete floor full of deep heat fractures, clutching a bleeding abdominal wound beside a torn empty water pouch and heat-warped debris. In the background, Do Minh Kha stands looming with a cold detached gaze, holding a tactical combat knife, backlit by an ominous beam of deep crimson sunlight piercing through a jagged collapsed ceiling fissure. Chiaroscuro high contrast lighting, floating soot embers, atmospheric heat distortion waves, 35mm RAW photograph.',
        'video_prompt': '0-3s: Low-angle tracking shot through heat-warped plastic debris and scorched concrete in subterranean B3 basement at Me Tri as Do Minh Kha walks slowly past motionless casualties, boots coated in red dust. 3-6s: Camera tilts down as Do Minh Kha crouches over Le Quoc Tien, who clutches a bleeding abdominal wound beside a torn empty water pouch. Do Minh Kha speaks in a hoarse parched voice "Lê Quốc Tiến, mày vốn không nên sống lâu đến thế." 6-8s: Close-up of Do Minh Kha raising a gleaming tactical knife reflecting the deep crimson sunlight bleeding through a fractured ceiling slab, then plunging the blade downward into pitch black darkness. Audio: Stifled gasping breath, slow crunching footsteps on gravel, hoarse ominous dialogue, sharp metallic blade unsheath, deep sub-bass cinematic hit. Negative: subtitles, watermark, text overlay.',
        'narrator_text': 'Tầng hầm B3 Mễ Trì, năm 2031. Dưới ánh Hồng Nhật thiêu đốt, lưỡi dao của Đỗ Minh Kha đã kết thúc ba năm sinh tồn của tôi.'
    },
    {
        'video_id': vid,
        'display_order': 1,
        'chain_type': 'ROOT',
        'character_names': ['Le Quoc Tien'],
        'prompt': 'Cinematic close-up of Le Quoc Tien jolting awake in bed, eyes wide with intense shock and cold sweat on his face. In background, a desktop setup with multiple glowing monitors and a digital clock displaying 07:13 AM. Soft morning golden sunlight streaming through half-open blinds. Photorealistic RAW photograph, Canon EOS R5, shallow depth of field.',
        'video_prompt': '0-3s: Close-up on Le Quoc Tien chest heaving as he gasps for air, jolting upright in sheer shock. 3-6s: His trembling hand grasps the smartphone, screen glowing with the date 09/05/2028. 6-8s: Camera tracks smoothly to the window showing peaceful golden morning sunlight.'
    },
    {
        'video_id': vid,
        'display_order': 2,
        'chain_type': 'ROOT',
        'character_names': ['Nguyen Trai Avenue'],
        'prompt': 'Wide establishing cinematic shot of Nguyen Trai Avenue in Hanoi during morning rush hour. The green Cat Linh - Ha Dong elevated metro train glides smoothly on elevated concrete tracks above dense streams of motorbikes and cars. Clear blue sky with gentle morning sun, modern city backdrop. RAW photograph, wide-angle 24mm, vibrant urban atmosphere.',
        'video_prompt': '0-3s: Elevated wide cinematic shot following the green metro train gliding on concrete viaducts. 3-6s: Camera cranes down toward dense streams of morning motorbike commuters on Nguyen Trai Avenue. 6-8s: Golden sunlight reflects brilliantly off modern glass skyscrapers under a blue sky.'
    },
    {
        'video_id': vid,
        'display_order': 3,
        'chain_type': 'ROOT',
        'character_names': ['Dai Ha Mall Heat Trap'],
        'prompt': 'Terrifying apocalyptic cinematic shot of Dai Ha Mall Heat Trap in Ha Dong under an eerie blood-red sky with a massive dark crimson sun. Dense crowd of panicked people inside banging frantically against fogged-up glass doors from dark steaming interiors. Heat ripples distorting the melting asphalt road outside. High contrast dramatic disaster lighting, 35mm RAW photograph.',
        'video_prompt': '0-3s: Camera pushes rapidly toward fogged glass doors as desperate hands slam against the condensation from steaming dark interiors of Dai Ha Mall Heat Trap. 3-6s: Pan up sharply to the terrifying dark crimson sun blazing in a blood-red hazy sky. 6-8s: Violent heat waves distort the melting asphalt parking lot in the foreground.'
    },
    {
        'video_id': vid,
        'display_order': 4,
        'chain_type': 'ROOT',
        'character_names': ['Le Quoc Tien', 'Ngoc Truc Warehouse'],
        'prompt': 'Atmospheric cinematic shot inside Ngoc Truc Warehouse. Le Quoc Tien shines a flashlight onto a heavy dark metal hatch embedded in the concrete floor. The circular sun emblem with twelve rays on the hatch glows with an ominous deep red bioluminescent light. Dense cold vapor rising from the metallic seams. 35mm cinematic photograph, moody volumetric shadows.',
        'video_prompt': '0-3s: Medium tracking shot of Le Quoc Tien prying aside a rusted metal shelf inside Ngoc Truc Warehouse to reveal a dark round floor hatch. 3-6s: The etched circular sun emblem on the metal hatch pulses with an ancient crimson glow. 6-8s: Freezing subterranean vapor hisses out as deep mechanical latches unlock underneath.'
    },
    {
        'video_id': vid,
        'display_order': 5,
        'chain_type': 'ROOT',
        'character_names': ['Tran Thanh Thuy', 'Do Minh Kha', 'Dried West Lake Colossus'],
        'prompt': 'Epic cinematic wide shot of Dried West Lake Colossus in Hanoi under a dark apocalyptic red sun. Cracked black mud lakebed exposes colossal ancient dark metallic ribbed structures resembling giant dragon bones protruding from the earth. Tran Thanh Thuy and Do Minh Kha stand on the distant embankment silhouetted against the colossal metallic ruins and crimson haze. Masterpiece cinematic photography, 16:9 ultra-wide, atmospheric scale.',
        'video_prompt': '0-3s: Epic sweeping drone pull-back over cracked black mud of Dried West Lake Colossus exposing colossal ancient metal ribs rising from the dry lakebed. 3-6s: Crimson sunlight reflects off the weathered metallic structures as steam rises from fissures. 6-8s: Low shot of Tran Thanh Thuy and Do Minh Kha on the distant embankment silhouetted against the colossal colossus.'
    }
]

created_scenes = []

for sc in scenes:
    req_body = json.dumps(sc).encode('utf-8')
    req = urllib.request.Request(
        'http://127.0.0.1:8100/api/scenes',
        data=req_body,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    with urllib.request.urlopen(req) as resp:
        s_data = json.loads(resp.read().decode('utf-8'))
        created_scenes.append(s_data)
        print(f"Created Scene {sc['display_order'] + 1}: {s_data['id']}")

with open('scripts/created_scenes.json', 'w', encoding='utf-8') as f:
    json.dump(created_scenes, f, indent=2)
print("Done all scenes!")
