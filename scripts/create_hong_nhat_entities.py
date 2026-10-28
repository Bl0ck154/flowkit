import asyncio
from agent.api.projects import _build_character_profile
from agent.sdk.persistence.sqlite_repository import SQLiteRepository
from agent.utils.slugify import slugify

pid = '594758cc-11f5-4f92-8b3c-1213686591f4'
story = 'Ngay 22/06/2028, tham hoa Hong Nhat giang lam, mat troi doi mau do sam, nhiet do vuot 50C-68C thieu dot Ha Noi. Le Quoc Tien mang ky uc cua cai chet o Me Tri 2031 tinh day truoc do 44 ngay, cung Tran Thanh Thuy va cac nhom nguoi sinh ton bao ve ha tang ngam, doi dau Do Minh Kha va tim ra bi mat Cong Thang Long.'

entities = [
    {
        'name': 'Le Quoc Tien',
        'entity_type': 'character',
        'description': '29-year-old Vietnamese system infrastructure engineer, lean athletic build, sharp determined Asian features, short clean black hair, wearing dark charcoal tactical t-shirt and grey cargo pants, digital wrist gauge, observant survivalist gaze.',
        'voice_description': 'Calm, firm, determined Vietnamese male voice with deep analytical cadence'
    },
    {
        'name': 'Do Minh Kha',
        'entity_type': 'character',
        'description': '34-year-old Vietnamese logistics commander, tall imposing authoritative posture, slicked-back dark hair, wearing an unbuttoned black button-down shirt with rolled-up sleeves, dark trousers, distinctive matte black ring on his left ring finger, piercing cold calculated gaze.',
        'voice_description': 'Low, smooth, chillingly calm male voice with absolute authority'
    },
    {
        'name': 'Tran Thanh Thuy',
        'entity_type': 'character',
        'description': '27-year-old Vietnamese investigative journalist, smart analytical expression, hair tied back in a neat ponytail, wearing a light beige utility shirt, olive multi-pocket reporter vest, canvas shoulder bag carrying a compact camera, intelligent perceptive dark eyes.',
        'voice_description': 'Clear, articulate, sharp and perceptive Vietnamese female voice'
    },
    {
        'name': 'Nguyen Trai Avenue',
        'entity_type': 'location',
        'description': 'Wide bustling urban avenue in Hanoi during morning rush hour, elevated concrete metro tracks overhead with modern green Cat Linh - Ha Dong passenger train gliding past sleek glass skyscrapers and dense commuter traffic under a clear morning sky.'
    },
    {
        'name': 'Dai Ha Mall Heat Trap',
        'entity_type': 'location',
        'description': 'Massive modern glass shopping mall in Ha Dong district under a terrifying dark crimson sun and apocalyptic red sky, giant glass windows completely fogged with thick condensation from dark boiling interior, heat ripples warping the melting empty asphalt parking lot outside.'
    },
    {
        'name': 'Ngoc Truc Warehouse',
        'entity_type': 'location',
        'description': 'Secluded industrial concrete warehouse on Hanoi outskirts, weathered corrugated metal roof, dusty grey concrete floor with faint cracks, heavy circular dark metal floor hatch with an etched twelve-ray sun emblem hidden beneath metal shelving.'
    },
    {
        'name': 'Dried West Lake Colossus',
        'entity_type': 'location',
        'description': 'Dried-up West Lake lakebed under a scorching apocalyptic deep crimson sun and hazy red sky, cracked black mud terrain revealing gigantic ancient dark metallic curved rib structures rising from the earth like colossal dragon bones, rising hot thermal steam.'
    }
]

async def run():
    repo = SQLiteRepository()
    for ent in entities:
        profile = _build_character_profile(
            ent['name'],
            ent['description'],
            story,
            entity_type=ent['entity_type'],
            material_id='realistic'
        )
        char = await repo.create_character(
            name=ent['name'],
            slug=slugify(ent['name']),
            entity_type=ent['entity_type'],
            description=profile['description'],
            image_prompt=profile['image_prompt'],
            voice_description=ent.get('voice_description')
        )
        await repo.link_character_to_project(pid, char.id)
        print("Created and linked: " + ent['name'] + " (" + ent['entity_type'] + ") -> ID: " + str(char.id))

if __name__ == '__main__':
    asyncio.run(run())
