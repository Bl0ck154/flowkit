# The Ultimate AI Screenplay Bible — Google Flow & Veo 3

Usage: `/fk-scriptwriter "<topic / series title>" [--episode N] [--scenes 8|12] [--lang vi|en] [--orientation HORIZONTAL|VERTICAL] [--fast]`

- **Default:** Runs the **Interactive 5-Step Director Workflow** (Section A), pausing for approval at Steps 1, 3, and 5.
- `--fast`: Bypasses user review gates to directly generate technical production scripts (still strictly enforces Section N Quality Gates).

---

## 0. Technical Truths of FlowKit (Must Never Violate)

| Technical Reality | Direct Screenplay Consequence |
| :--- | :--- |
| `POST /api/scenes` only accepts: `video_id, display_order, prompt, image_prompt, video_prompt, transition_prompt, character_names, parent_scene_id, chain_type, source`. Extra fields are **silently ignored**. | Sending `narrator_text` in the POST payload will be **lost**. You must call `PATCH /api/scenes/{sid}` with `{"narrator_text": "..."}` immediately after scene creation. |
| The server automatically injects the material `scene_prefix` (e.g., `realistic`) to the beginning of `prompt`. | Do NOT manually prepend material style prefixes into `prompt` to avoid duplicate prompt contamination. |
| `character_names` must **strictly match** project entity names (characters, locations, visual assets). | This is how reference images are routed into Google Flow `imageInputs`. Mismatched names = missing refs = facial drift and identity loss. |
| `chain_type: CONTINUATION` uses the subsequent scene image as `endImage`. On the modern Flow API, endImage triggers an immediate fatal error: `UNSUPPORTED_ON_BATCH_API`. | **Default every scene to `ROOT`.** Only use chained transitions when `FLOW_ALLOW_DEGRADED=1` is confirmed or when using compatible providers. |
| Veo 3 video clips are 8.0s; post-production applies `-ss 1` head trim → **7.0s** usable footage remaining. | All narrator mathematics (Section J) are calibrated against a 7.0s effective window. |
| Scenes are mutable via `PATCH`. | Refine prompts via `PATCH /api/scenes/{sid}`. **Never delete and recreate** (preserves generated media). |

---

## A. Interactive 5-Step Director Workflow

### Step 1 — Pitch Logline (Pause for Approval)
- If the subject is based on real historical events or public figures: execute `/fk-research` first (Rule 14).
- Present **2–3 creative angles**, each including: 1-sentence logline, genre preset (Section L), narrative tone, and the opening 3-second visual hook.

### Step 2 — Cast & World Lock
- Enumerate project entities: `character` (vertical 9:16 portrait), `location` (horizontal 16:9 landscape), and `visual_asset`.
- Lock **Lighting Signature**, **Color Palette**, and **Dialogue Language** (e.g., Vietnamese or English).
- If the project already exists: query `GET /api/projects/{pid}` to obtain exact entity names.

### Step 3 — Beat Sheet: 8–12 Beats (Pause for Approval)
One line per scene: scene archetype (Section D) · shot scale · characters present · dialogue presence · targeted emotional shift (Section I2).

### Step 4 — Technical Production Script
Author exhaustive specifications per scene: `prompt`, `video_prompt`, `narrator_text`, `character_names`, `music_cue`, `wardrobe_state`.

### Step 5 — Self-Audit & Pipeline Ingestion (Pause for Approval)
1. Run the **20-Point Quality Gate** (Section N) — output full verification scorecard; resolve any failing items.
2. Save screenplay: `.omc/research/<slug>_ep<NN>_script.json`.
3. Inquire: *"Dispatch into FlowKit pipeline immediately?"* → upon confirmation, execute Section O.

---

## B. Series Bible & Multi-Episode Arc Architecture

Before scripting Episode 1, compile a minimal Series Bible (saved at `.omc/research/<slug>_bible.md`):

- **Series Logline** (1 sentence) · **Core Theme** · **World Rules** (e.g., "Solar temperature increases 1°C every 3 days").
- **Series Clock**: Universal countdown anchor. Every episode must advance this ticking clock.
- **Visual Leitmotif**: A recurring visual motif that evolves across episodes (e.g., the sun grows progressively crimson).

### 4-Act Structure for a 10–12 Episode Series
| Act | Episodes | Narrative Function | Emotional Temperature |
| :--- | :--- | :--- | :--- |
| **Act 1 — Inciting Arc** | 1–3 | Introduce protagonists, stakes, allies, opposing force | Curiosity → Rising dread |
| **Act 2 — Escalation Arc** | 4–7 | Resource competition, betrayals, pyrrhic victories | Sustained high tension |
| **Act 3 — Darkest Night** | 8–9 | Core citadel under siege, catastrophic personal loss | Existential despair |
| **Act 4 — Climax & Resolution** | 10+ | Final confrontation, ultimate sacrifice, transformed world | Catharsis & resonance |

**Episode Transition Rule:** Scene 0 of Episode N+1 must directly address or escalate the cliffhanger of Episode N within the first 3 seconds.

---

## C. The 10 Core Screenplay Commandments

1. **Action-Only Prompts:** Never describe facial anatomy, hair color, or body build in scene prompts. Reference images govern identity; prompts describe action only (Wardrobe state is the sole exception — Section F).
2. **3-Beat Structure in 8 Seconds:** Mandate `0-3s`, `3-6s`, `6-8s` temporal breakdown in every `video_prompt`.
3. **Narrator Mathematics:** Narrator audio must comfortably conclude within 7.0s (Section J).
4. **Show ≠ Tell:** Narration must reveal unseen context, motives, or stakes. Never redundantly narrate what is already visible on screen.
5. **Maximum 2 Named Characters per Scene:** Crowds remain blurred in the background.
6. **Camera Movement as Standalone Sentence:** Camera direction must be separated from character action sentences.
7. **No Consecutive Scale Repetition:** Never place two identical shot sizes back-to-back (Section G).
8. **Physiological Emotion:** Describe observable physiological symptoms rather than abstract adjectives (Section I).
9. **Lighting Signature Consistency:** Maintain unified lighting within identical temporal and spatial sequences.
10. **Unresolved Cliffhanger:** Every episode must end on an unanswered question or suspended threat.

---

## D. 10 Professional Cinematic Scene Archetypes

A genuine film is not a slideshow of walking figures with continuous narration. Every scene must adopt one of the following 10 archetypes, and each episode must blend **at least 5–6 distinct archetypes**:

### 1. Establishing Shot
- **Function:** Establishes geography, scale, time of day, and environmental scale. Zero or tiny character presence.
- **Framing:** Extreme Wide Shot (EWS) / Aerial / Bird's Eye.
- **Dialogue:** None. Narration + environmental audio only.
- **video_prompt Formula:**
  ```text
  0-3s: Aerial establishing shot of the mountain pass at dawn, morning fog clinging to jagged limestone peaks. 3-6s: The camera slowly descends toward an ancient stone fortress, golden sunrise light glinting off slate watchtowers. 6-8s: The camera settles on the heavy timber gates slightly ajar. Smooth crane-down movement. Lighting: soft golden dawn, volumetric morning mist. Audio: distant mountain winds, faint raven calls. Negative: subtitles, watermark, text overlay.
  ```

### 2. Dialogue Scene — Two-Shot
- **Function:** Two characters exchange vital plot information, make decisions, or enter conflict. **The backbone of cinematic storytelling.**
- **Framing:** Medium Two-Shot → Over-the-Shoulder → Reaction Close-up.
- **Dialogue:** Spoken naturally by characters inside the clip (`Character says: "..." (no subtitles)`).
- **video_prompt Formula:**
  ```text
  0-3s: Medium two-shot inside dim military tent. General Tien and Doctor Thuy sit across a rough wooden table. Tien leans forward and speaks in a low urgent tone. Tien says: "We have thirty days. No more." (no subtitles) 3-6s: Over-the-shoulder from behind Tien, camera focuses on Thuy. She listens intently, brow furrowing, then gives a slow resolute nod. Thuy says: "I will secure the medical supplies." (no subtitles) 6-8s: Close-up of Tien's face — a flicker of relief, then hardening resolve. Static locked-off shot with subtle rack focus. Lighting: warm candlelight through tent canvas, deep shadows. Audio: quiet room ambience, howling wind outside tent. Negative: subtitles, watermark, text overlay.
  ```

### 3. Dialogue Scene — Reaction Focus
- **Function:** One character speaks off-screen or from behind, while the camera fixates on the listener's internal shift.
- **Framing:** Medium → Slow push-in to Close-up on the listener.
- **video_prompt Formula:**
  ```text
  0-3s: Medium shot of Doctor Thuy speaking firmly across the table, gesturing slightly. Thuy says: "The reserves will only last two weeks." (no subtitles) 3-6s: Slow push-in to close-up of General Tien listening. His jaw tightens, eyes narrowing as he absorbs the gravity of the crisis. 6-8s: Tien looks down at the battle map, takes a slow breath, then looks back up with cold determination. Lighting: warm diffused lamp light. Audio: quiet room tone, faint distant rain. Negative: subtitles, watermark, text overlay.
  ```

### 4. Action Beat
- **Function:** Physical labor, mechanical repairs, tactical operations, or combat maneuvers.
- **Framing:** Medium Tracking / Kinetic Dynamic.
- **video_prompt Formula:**
  ```text
  0-3s: Medium tracking shot as General Tien hauls an iron reinforcement beam, sparks drifting from a brazier against the stone wall. 3-6s: He braces his shoulder against the timber barricade and hammers a heavy iron locking peg into place with a mallet. 6-8s: Tien steps back, wipes sweat from his brow, and inspects the fortified gate with a firm nod. Lateral tracking shot following the movement. Lighting: chiaroscuro — warm orange forge glow against dark stone shadows. Audio: harsh metallic clanging of hammer on iron, crackling fire. Negative: subtitles, watermark, text overlay.
  ```

### 5. Pure Reaction Shot
- **Function:** Intense close-up on a character processing shocking news, discovery, or danger. No dialogue — pure micro-expression.
- **Framing:** Close-up / Extreme Close-up.
- **video_prompt Formula:**
  ```text
  0-3s: Close-up of General Tien's face illuminated by the crimson glow of a warning signal. His pupils dilate, lips parting slightly. 3-6s: Slow push-in to extreme close-up. A bead of sweat rolls down his temple. He swallows hard. 6-8s: His eyes narrow into hardened resolve, jaw setting firmly. He exhales through his nose. Static shot with subtle handheld micro-movement. Lighting: pulsing red warning glow on one side, deep shadow on the other. Audio: low electronic drone, controlled heavy breathing. Negative: subtitles, watermark, text overlay.
  ```

### 6. Insert / Detail Shot
- **Function:** Macro shot on a crucial thematic prop: maps, hourglass, broken seal, thermometer, dagger.
- **Framing:** Macro / Extreme Close-up.
- **video_prompt Formula:**
  ```text
  0-3s: Extreme close-up of an ancient bronze sundial, shadows stretching across carved zodiac markers. 3-6s: Camera slowly racks focus to reveal a royal seal stamped in red wax on parchment behind the sundial. 6-8s: A hand enters the frame and draws an ink line across the parchment with a bamboo brush. Smooth rack focus. Lighting: harsh afternoon sun through slatted blinds. Audio: ticking of a clock, distant courtyard birds. Negative: subtitles, watermark, text overlay.
  ```

### 7. Montage Beat (Compressed Time)
- **Function:** Rapid progression of preparation, construction, marching, or tactical training.
- **Framing:** Fast cutting or multi-action pacing within a single clip.
- **video_prompt Formula:**
  ```text
  0-2s: Overhead shot of hands stacking bamboo arrows into wooden quivers. 2-4s: Medium shot of Tien tightening leather straps on an armored saddle. 4-6s: Close-up of fresh water pouring into clay jars. 6-8s: Wide shot of the fortified camp, organized and prepared as evening torches ignite. Fast montage rhythm. Lighting: warm amber dusk. Audio: rhythmic sounds of sharpening blades, pouring water, marching boots. Negative: subtitles, watermark, text overlay.
  ```

### 8. Stalking / Surveillance Shot
- **Function:** Generating covert suspense, feelings of being hunted, or espionage.
- **Framing:** Long Telephoto compressed through foreground obstruction (branches, lattice, pillars).
- **video_prompt Formula:**
  ```text
  0-3s: Long telephoto shot through carved wooden palace lattice — Lord Kha exits a pavilion, adjusting his silk collar. The lattice partially obscures the frame. 3-6s: Rack focus from the wooden screen to Kha's face. He pauses, glances sideways, and smiles coldly. 6-8s: Kha steps into a waiting carriage. The camera remains static behind the screen as the carriage pulls away. Locked-off telephoto through obstruction. Lighting: midday contrast, deep shadows beneath eaves. Audio: distant palace chatter, carriage wheels grinding on gravel. Negative: subtitles, watermark, text overlay.
  ```

### 9. Atmospheric Transition / Bridge Shot
- **Function:** Establishing time passage, twilight into darkness, weather changes. Provides narrative breathing room.
- **Framing:** Wide / Time-lapse style.
- **video_prompt Formula:**
  ```text
  0-3s: Wide static shot of the citadel exterior at dusk. The last rays of golden sunlight turn stone parapets amber. 3-6s: Shadows lengthen rapidly across the courtyard as the sun slips below the mountain crest. Citadel watch fires ignite one by one. 6-8s: Night falls — a single beacon fire casts warm light across the stone gate. Static wide shot, natural time progression. Lighting: golden hour transitioning to deep twilight. Audio: evening crickets, distant guard horn call. Negative: subtitles, watermark, text overlay.
  ```

### 10. Silent Moment (The Breathing Room)
- **Function:** Total cinematic pause. No dialogue, no narrator. Pure image, breathing, and acoustic realism.
- **Framing:** Medium or Wide, locked-off static.
- **video_prompt Formula:**
  ```text
  0-3s: Medium shot of General Tien sitting alone on a stone bench in the quiet courtyard. A single shaft of moonlight cuts across his shoulders. 3-6s: He stares at the ground. His chest rises and falls with a long, slow breath. Cold mist drifts across the flagstones. 6-8s: He lifts his gaze slowly toward the distant horizon. Locked-off static shot, zero camera movement. Lighting: single volumetric moonlight beam in darkness. Audio: near-silence — only his breathing and the distant rustle of pine needles. Negative: subtitles, watermark, text overlay.
  ```

---

## E. Multi-Language & Native Dialogue Directing

### The Core Invariant: Narration Leads, Dialogue Punctuates
In high-end cinema, dialogue and narration must never collide:
```
[1] NARRATOR TTS: Sets macroscopic context, stakes, and countdown (plays during 0-3s or before).
[2] AMBIENT AUDIO (Veo 3 Native): Continuous environmental bed (wind, rain, crackling fire).
[3] CHARACTER DIALOGUE (Veo 3 Native): Brief, sharp, localized speech embedded inside the clip.
```

### Prompt Dialogue Syntax
```text
[Character Name] says: "[Dialogue Line]" (no subtitles)
```
Examples:
- English: `Tien says: "Thirty days. No more." (no subtitles) — low urgent voice`
- Vietnamese: `Tiến nói: "Ba mươi ngày. Không hơn." (không phụ đề) — giọng trầm, dứt khoát`

### Dialogue Rules:
1. **Length Cap:** Maximum **10–12 words per character per 8s clip** (Rule 12).
2. **Speaker Limit:** Maximum 2 speaking characters per scene.
3. **Delivery Direction:** Append vocal tone immediately following the quote: `— whispered urgently` or `— deep commanding baritone`.
4. **Mandatory Suffix:** Always include `(no subtitles)` or `(không phụ đề)` to prevent AI video generators from burning deformed text overlays onto the video frames.
5. **No Redundancy:** If the narrator says "They met to discuss the siege", the character must NOT say "We must discuss the siege". Dialogue expresses immediate emotional reaction and commitments.

---

## F. Wardrobe & Temporal Decay Dynamics

Reference images lock **facial identity**; clothing must be directed in prompts as **functional layers** tied to physical action:

- ✅ **Correct:** `General Tien, wearing a heavy soot-stained leather breastplate, lowers his iron visor.`
- ❌ **Incorrect:** `General Tien, a handsome Vietnamese general with sharp cheekbones and black hair.`

### Temporal Costume Progression:
| Story Stage | Wardrobe State Description |
| :--- | :--- |
| **Opening / Prologue** | `clean ceremonial robes, neat topknot, pristine fabric` |
| **Onset of Struggle** | `sleeves rolled up, light dust on shoulders, untied sash` |
| **Middle / Prolonged War** | `sweat-stained tunic, scuffed leather armor, soot on collar` |
| **Darkest Night / Climax** | `torn cloak, blood-stained linen bandage on forearm, ash-streaked face` |

---

## G. Scale Alternation & Cinematic Rhythm

Never use the same shot scale in consecutive scenes. Standard 8-Scene Rhythm:

| Scene | Archetype | Shot Framing | Kinetic Velocity | Dialogue? |
| :---: | :--- | :--- | :--- | :---: |
| 0 | Hook / Reaction | Close-up | Rapid / Urgent | Optional |
| 1 | Establishing | Extreme Wide (EWS) | Majestic / Slow | None |
| 2 | Action Beat | Medium Tracking | Kinetic / Driving | Short command |
| 3 | **Dialogue Two-Shot** | Two-Shot → OTS | Moderate / Intimate | **Mandatory** |
| 4 | Insert / Detail | Macro | Static / Tense | None |
| 5 | **Dialogue / Reaction** | Close-up → Push-in | Deep / Emotional | **Mandatory** |
| 6 | Surveillance / Threat | Telephoto through Obstruction | Simmering Tension | None |
| 7 | Cliffhanger | Wide → Slow Push-in | Accelerating Dread | Climactic line |

**The Dialogue Invariant:** Every 8-scene episode must contain **at least 2 dialogue scenes**. A video without dialogue is an automated slideshow, not cinema.

---

## H. Director of Photography (DP) Lexicon

### Camera Movements:
- `slow push-in` — Deepens internal psychological tension or realization.
- `slow pull-back` — Evokes isolation, smallness against the environment.
- `low-angle tracking` — Imparts authority, heroic determination.
- `lateral tracking` — Accelerates urgency, pursuit, race against time.
- `overhead bird-eye` — Establishes tactical layout, vulnerability.
- `rack focus from A to B` — Shifts viewer focus between foreground threat and background reaction.
- `over-the-shoulder (OTS)` — Intimate conversational framing.
- `locked-off static` — Somber gravity, quiet contemplation.
- `Dutch angle` — Disorientation, psychological unbalance.
- `subtle handheld` — Gritty documentary realism, combat tension.

### Lighting Signatures:
- `hard chiaroscuro, deep shadows` — Danger, conspiracy, moral ambiguity.
- `volumetric light beams through dust` — Fortress interiors, catacombs, temples.
- `warm golden-hour rim light` — Hope, honor, farewell.
- `flickering torchlight against wet stone` — Dungeon, night fortress defense.
- `harsh midday sun with heat shimmer` — Desolation, heat crisis, arid wasteland.
- `cold overcast diffused daylight` — Bleak realism, sorrow, military readiness.

### Optical Focal Lengths:
- `35mm natural perspective` — Grounded documentary realism.
- `85mm portrait, shallow depth of field` — Emotional character isolation.
- `telephoto lens compression` — Espionage, compressed crowds, claustrophobia.
- `wide 24mm` — Vast architectural scale or overwhelming landscape.

---

## I. Micro-Expression Physicality

AI models fail on abstract adjectives like "he looks sad". Direct precise physiological symptoms:

| Emotion | Avoid Abstract Words | Direct Physical Symptoms |
| :--- | :--- | :--- |
| **Terror** | `he is terrified` | `rapid shallow breathing, eyes darting left and right, hand gripping table edge until knuckles whiten` |
| **Resolve** | `she looks determined` | `jaw tightening firmly, gaze narrowing to a fixed point, slow decisive nod` |
| **Shock** | `he is shocked` | `sudden complete stillness, lips parting without a sound, breath held mid-inhale` |
| **Exhaustion** | `he is exhausted` | `shoulders sagging forward, spine slumping, leaning heavily against the stone wall, slow heavy blink` |
| **Suppressed Grief** | `she is sad` | `eyes glistening without tears falling, swallowing hard twice, looking away toward the window` |
| **Suspicion** | `he is suspicious` | `head tilting 15 degrees, eyes narrowing, weight shifting to back foot in a half-step retreat` |
| **Arrogance** | `he is arrogant` | `chin raised exposing throat, slow measured stride, thin smirk curling one corner of mouth` |
| **Relief** | `she is relieved` | `long slow exhale through parted lips, shoulders dropping two inches, eyes closing for three beats` |

---

## I2. The 8-Second Micro-Emotional Arc (A → B Progression)

Every scene **MUST** exhibit an internal emotional transformation. A character begins at State A and arrives at State B:

```
Beat 1 (0-3s): STATE A — Initial baseline emotion
Beat 2 (3-6s): THE CATALYST — Visual, acoustic, or physical shift that fractures the baseline
Beat 3 (6-8s): STATE B — New, irreversible emotional resolution
```

### 15 Extended Physiological Expression States:
1. **Calm → Terror:** Eyes gazing calmly → Pupils dilate widely, lips part trembling → Face goes pale, steps backward.
2. **Skepticism → Bitter Realization:** Brows slightly furrowed → Pupils freeze, jaw muscle twitches → Slow shake of head, glistening eyes.
3. **Despair → Desperate Resolve:** Head lowered in defeat → Slowly lifts chin through disheveled hair → Jaw sets, fists clench white, eyes blaze.
4. **Confidence → Sudden Collapse:** Smug half-smile → Smile vanishes instantly, brow contorts → Stares blankly downward, hands tremble.
5. **Fear → Rising Courage:** Body shaking, darting eyes → Closes eyes, takes one deep breath → Opens eyes locked on the enemy, stands tall.
6. **Rage → Cold Cruelty:** Veins bulging on neck, panting → Breath abruptly slows, facial muscles relax into blankness → Eyes turn icy, cold smirk forms.
7. **Physical Pain → Iron Will:** Grimacing from wound, biting lower lip → Sharp hiss through teeth, sweating profusely → Forces eyes open, stance solidifies.
8. **Vigilance → Moving Relief:** Hand clenched on sword hilt, scanning shadows → Grip slowly relaxes, shoulders drop → Soft exhale, gaze softens warmly.
9. **Pride → Humiliated Rage:** Chin high, disdainful stare → Lowers head, ears flushing red → Clenches fists until veins stand out.
10. **Remorse → Redemption Resolve:** Staring down at trembling hands in self-blame → Looks up toward the horizon → Expression turns steely, gives a decisive nod.
11. **Confusion → Sudden Epiphany:** Eyes scanning documents frantically → Pupils freeze, light sparks in eyes → Gentle smile forms as puzzle clicks.
12. **Isolation → Found Solidarity:** Vacant stare in the crowd → Catches comrade's loyal gaze → Subtle nod, warmth returns to weathered face.
13. **Agony → Manic Defiance:** Tears streaming down, head in hands → Broken laughter escapes lips → Eyes widen with wild defiance.
14. **Melancholy → Peaceful Acceptance:** Heavy weary eyes, downturned mouth → Closes eyes into the passing breeze → Gentle half-smile, total tranquility.
15. **Casual Watch → Maximum Alertness:** Scanning darkness lazily → Ear twitches slightly, pupils snap toward shadows → Lowers center of gravity silently.

---

## I3. 8 Cinematic Action Archetypes

### 1. Melee Duel / Clashing Blades
- **AI Safety Rule:** Avoid impaling weapons through bodies. Describe weapon trajectory and explosive spark impacts on shields/guards.
- **video_prompt:**
  ```text
  0-3s: Two warriors lower their combat stances, bronze swords raised to shoulder height, eyes locked across drifting ash. 3-6s: The left warrior lunges forward in a powerful diagonal slash; his blade collides violently with his opponent's iron shield, discharging brilliant orange sparks. Camera tracks the kinetic slash. 6-8s: Both warriors lock blades in a rigid contest of brute strength, muscles straining, hot breath steaming in the cold night air. Audio: Clashing steel, sizzling sparks, heavy war grunts. Negative: subtitles, watermark, text overlay.
  ```

### 2. High-Speed Pursuit
- **AI Safety Rule:** Never run directly into the camera lens. Track diagonally or laterally.
- **video_prompt:**
  ```text
  0-3s: A courier gallops at full sprint along a muddy forest road, black cloak fluttering in the storm. 3-6s: Three mounted pursuers surge into frame behind him, arrows whistling past and striking the earth. The camera tracks laterally alongside the galloping steeds. 6-8s: The courier jerks the reins, veering sharply through a narrow rocky ravine, mud spraying across the lower frame. Audio: Thundering rhythmic hooves, whistling arrows, panicked horse whinny. Negative: subtitles, watermark, text overlay.
  ```

### 3. Dodge & Counter-Strike
- **AI Safety Rule:** Duck or sidestep; avoid 360-degree midair flips.
- **video_prompt:**
  ```text
  0-3s: The general stands in a balanced guard stance, watching an enemy spear thrust incoming. 3-6s: As the spear tip nears, he ducks low to the left, pivoting his wrist to strike the spear shaft upward with his broadsword hilt. The camera pushes in on the deflection. 6-8s: The spear deflects wide; the general straightens into an imposing counter stance. Audio: Whistling spear air rush, dull timber crack, clatter of weapon. Negative: subtitles, watermark, text overlay.
  ```

### 4. Precision Archery
- **AI Safety Rule:** Structure as pull -> release shockwave -> trajectory pan.
- **video_prompt:**
  ```text
  0-3s: The archer stands steady upon the battlement, drawing the heavy recurve bowstring back to her jawline in the rain. 3-6s: She releases; the bowstring snaps forward and the iron arrow streaks diagonally through the mist. The camera pans rapidly with the arrow trajectory. 6-8s: The arrow strikes the enemy signal banner in the distance, tearing it down; the archer lowers her bow with a calm exhale. Audio: Crisp bowstring snap, piercing arrow whistle, distant timber crash. Negative: subtitles, watermark, text overlay.
  ```

### 5. Stealth Ambush
- **AI Safety Rule:** Emerge from natural shadow/cover; avoid teleportation artifacts.
- **video_prompt:**
  ```text
  0-3s: A patrol unit carrying torches marches cautiously through a silent canyon pass, firelight dancing on rock walls. 3-6s: From dark tree branches above, cloaked scouts drop down silently, blades drawn to block the path. Low-angle camera looking up dramatically. 6-8s: A dropped torch hisses into a puddle and extinguishes in smoke; the scouts form an unbroken perimeter in the moonlight. Audio: Rustling leaves, taut rope snap, hissing fire extinguishing, unison steel unsheathing. Negative: subtitles, watermark, text overlay.
  ```

### 6. Breaching / Gate Breakout
- **AI Safety Rule:** Direct kinetic impact against timber/iron; use dust and debris shockwaves.
- **video_prompt:**
  ```text
  0-3s: The lead warrior locks his heavy bronze shield against his shoulder, driving all momentum forward. 3-6s: He smashes into the reinforced timber palace doors, splintering wood and sending dust billowing across the frame. Subtle camera shake on impact. 6-8s: The doors burst open, morning sunlight flooding inward to silhouette the warrior raising his sword to lead the charge. Audio: War cry, splintering timber crash, iron impact boom. Negative: subtitles, watermark, text overlay.
  ```

### 7. Desperate Shield Wall Stand
- **AI Safety Rule:** Anchor firm poses; express resilience under pressure.
- **video_prompt:**
  ```text
  0-3s: Shield-bearers drop to one knee, interlocking large bronze shields into a solid barricade before incoming fire arrows. 3-6s: A barrage of flaming arrows thuds heavily into the shields, smoking under the impact, but the wall holds firm. Low-angle heroic perspective. 6-8s: Smoke curls off the scorched shields; the commander raps his sword pommel three times against bronze to rally the ranks. Audio: Raining arrow impacts on metal, crackling flames, three crisp steel strikes. Negative: subtitles, watermark, text overlay.
  ```

### 8. Tense Standoff / Eye-to-Eye
- **AI Safety Rule:** Minimal physical body movement; concentrate energy into eyes, breathing, and 180-degree arc camera orbit.
- **video_prompt:**
  ```text
  0-3s: Medium two-shot of two rival commanders facing each other three paces apart on an ancient wooden bridge, wind whipping their robes. 3-6s: The camera executes a slow 180-degree arc shot around them. Neither moves; their eyes burn with locked hatred as one hand rests upon his sword hilt. 6-8s: Close-up of a bead of sweat rolling down the jawline; a thumb subtly clicks the sword guard upward from the scabbard. Audio: Creaking wooden bridge, distant wind chime, dry throat swallow, metallic click. Negative: subtitles, watermark, text overlay.
  ```

---

## I4. The Suspense & Tension Toolkit (6 Master Techniques)

True suspense is generated through **information withholding** and **impending dread**, not cheap jump scares:

### 1. The Ticking Clock
- **Principle:** Audience watches a physical deadline expire (candle melting toward gunpowder, sun sinking below the horizon).
- `video_prompt`: Macro close-up of a red candle melting onto a war table, hot wax pooling toward the edge of an envelope dusted with sulfur. Camera slowly dollies forward.
- `narrator_text`: Thirty seconds remain. If unopened, the cipher will consume itself in flames.
- `Audio`: Rhythmic dripping of wax like a clock pendulum, shallow choked breathing.

### 2. The Blind Spot / Negative Space
- **Principle:** Character framed on the extreme third, leaving an expansive, pitch-black void behind them.
- `video_prompt`: Close-up of general cleaning his sword by candlelight on screen-left. The right two-thirds is a pitch-black corridor behind him. A faint shadow drifts in the deep darkness.
- `narrator_text`: In the shadows of the imperial court, the deadliest blade always strikes from behind.
- `Audio`: Cloth wiping across cold steel, faint padding footsteps on distant floorboards.

### 3. The Delayed Reveal
- **Principle:** Character witnesses a horrific sight first, face contorting, while concealing the source from the viewer until the 6th second.
- `video_prompt`: 0-3s: Close-up of a sentry peering through a wooden shutter, eyes widening in sheer disbelief, jaw trembling. 3-6s: Camera slowly tracks over the sentry's shoulder. 6-8s: The river below is revealed, covered with thousands of silent enemy warships emerging from the mist.
- `narrator_text`: When the shutter opened, all hope for a peaceful night dissolved into the mist.
- `Audio`: Creaking shutter hinge, pounding heartbeat, then thundering roar of a thousand oars churning water.

### 4. Sonic Isolation / The Sensory Cutout
- **Principle:** Abruptly eliminate all musical score, isolating a single surreal sound to heighten visceral tension.
- `video_prompt`: Close-up in slow motion of the archer taking aim amidst a chaotic battlefield. His focus is absolute; a single raindrop strikes his eyelid, causing a micro-blink.
- `narrator_text`: Amidst ten thousand clashing blades, time freezes before the arrow of destiny.
- `Audio`: Total muting of battle noise; only a slow 40 BPM heartbeat and deep breath intake.

### 5. The Deceptive Calm
- **Principle:** Unnerving stillness that contrasts with imminent annihilation.
- `video_prompt`: Mirror-flat morning lake surface; a water lily sways gently in the breeze. Suddenly, concentric ripples erupt across the surface, vibrating with increasing violence from underground tremors.
- `narrator_text`: The lake remains terrifyingly still... Herald of the catastrophe gathering beneath the earth.
- `Audio`: Solitary bird chirp abruptly silenced by deep subterranean rumble, water sloshing.

### 6. Time Dilation on Edge
- **Principle:** Deconstruct a 1-second real-world crisis into a full 8-second cinematic struggle.
- `video_prompt`: 0-3s: Bloodied hand of a guardsman reaches out in desperation toward a falling battle standard. 3-6s: Fingers brush against the silk banner by millimeters; macro camera captures fabric sliding across knuckles. 6-8s: He strains forward another half-inch, gripping the wooden pole right before it hits the ground.
- `narrator_text`: A single fraction of an inch decided the fate of the entire army.
- `Audio`: Slow-motion fluttering silk, teeth grinding in agony, decisive timber snap as hand grips wood.

---

## J. Narrator Mathematics (The 7.0s Usable Window)

Veo 3 produces an 8.0s clip. Post-production trims the first 1.0s (`-ss 1`) to eliminate model initialization freezes. Usable footage = **7.0 seconds**.

### Exact Word Count Constraints (Hard Maximum):
| Language | Max Words | Target Duration | Speed Rate | Structural Rules |
| :--- | :---: | :---: | :---: | :--- |
| **Vietnamese** | **18–22** | ~6.0s – 6.5s | 1.1x | Tonal diacritics slow TTS. 2 punchy clauses separated by `—`. |
| **English** | **20–24** | ~6.0s – 6.5s | 1.0x | Active verbs, zero filler adjectives. |
| **Scenes with Dialogue** | **12–16** | ~4.0s – 4.5s | 1.1x | Narration must finish BEFORE characters begin speaking. |

**The Golden Rule:** A narrator must NEVER narrate what is already obvious on screen. Narration reveals *lore, motivation, consequences, and the ticking clock*.

---

## K. Anti-Artifact Playbook

| AI Vulnerability | Problematic Prompting | Physics-Safe Prompting |
| :--- | :--- | :--- |
| **Finger Dexterity** | Typing passcodes, interlinking fingers | Pressing flat palm, shifting lever, turning wheel, wearing gauntlets |
| **Text & Numbers** | Close-ups of readable screens or paper | Graphical symbols: glowing runes, flashing red signal, wax seal |
| **180° Head Turn** | Character turning from back to front | Split into 2 separate scenes; cut directly to front close-up |
| **Feet Slipping** | Floating walk cycle without contact | Specify surface traction: `boots striking wet concrete firmly` |
| **Mid-Clip Costume Change** | Character taking off coat or backpack | Garments must be fully worn from Frame 0 |
| **Body Merging** | Intimate grappling or tight hugs | Maintain distance: `standing an arm's length apart` |
| **Physical Impossibility** | Superhuman leaps, car crashes | Shoot the aftermath: dust billowing, camera shaking, debris settling |
| **Action Overload** | 5 actions crammed into 8s | Strictly 1 primary kinetic action per temporal beat |

---

## L. Genre Presets

| Genre | Color Palette Signature | Characteristic Keywords | Signature Hook |
| :--- | :--- | :--- | :--- |
| **Post-Apocalypse / Survival** | Burnt amber, dust grey | rust, corrugated iron, sandstorm, gas mask | Thermometer spikes past fatal threshold |
| **Revenge / Modern Noir** | Charcoal black, cold glass reflections | penthouse window, tailored suit, rain slick | Old scar throbs with memory |
| **Historical War / Epic** | Muted bronze, crimson, ash | iron scale armor, war drums, banner, torches | Ominous battle horn echoes in fog |
| **Cyberpunk / Sci-Fi** | Deep cyan, neon magenta | airlock steam, zero-g debris, biometric HUD | Pressure seal breach alarm |
| **Dark Fantasy** | Midnight violet, torch orange | ancient runes, misty bog, iron talismans | Relic emits sudden shockwave |

---

## L2. Safety Filter Ladder (Real-People Bypass)

If a prompt trips safety moderation, descend this ladder systematically:
1. **Camera Angle Shift:** Reposition camera behind the character or in a 3/4 profile.
2. **Remove Names from Prompt:** Retain entity in `character_names`, but remove specific aliases from the `video_prompt` text (use "the commander").
3. **Drop Reference Dependency:** Remove `character_names` for that single scene, relying on prompt physical descriptors.
4. **Keyword Sanitation:** Substitute flagged terms: `confidential/classified` → `parchment/scroll`; `weapon/rifle` → `iron gear`; `blood/kill` → `confrontation`. Never include minors.

---

## M. Audio & Musical Score Architecture

### Audio Tags in `video_prompt`:
- `Audio:` Background acoustic bed (wind howling, rain on canvas, engine idle).
- `SFX:` Discrete synchronized impacts (steel clashing, bolt locking, glass shattering).
- `Dialogue:` Native speech formatted as `Character says: "..." (no subtitles)`.
- **Mandatory Negative Tag:** `Negative: subtitles, captions, watermark, text overlay.`

### `music_cue` (Stored in screenplay JSON metadata, never sent to generation API):
- **Hook:** `low analog drone, ticking pulse, 60 BPM`
- **Escalation:** `industrial percussion, driving bass, 90 BPM`
- **Dialogue:** `sparse piano over warm ambient pad, breathing room`
- **Dread / Threat:** `dissonant low strings, sub-bass swells`
- **Cliffhanger:** `crescendo to a massive hit, then abrupt absolute silence`

---

## N. Quality Gate — 20 Production Checkpoints

Every scene script must pass this 20-point audit before generation:

| # | Checkpoint | Pass Criteria |
| :-: | :--- | :--- |
| 1 | Action-Only Prompt | Zero descriptions of face/hair/body in prompts |
| 2 | Wardrobe Progression | Costume changes justified and recorded in `wardrobe_state` |
| 3 | 3-Beat Pacing | Every `video_prompt` contains `0-3s`, `3-6s`, `6-8s` |
| 4 | Prompt Word Count | 100–150 words per prompt, containing lighting + audio tags |
| 5 | Narrator Word Count | 18–22 words (12–16 words for scenes with dialogue) |
| 6 | Show ≠ Tell | Narration does not redundantly describe on-screen actions |
| 7 | Character Limit | Maximum 2 named characters per scene |
| 8 | Entity Integrity | `character_names` strictly matches project database entities |
| 9 | Scale Alternation | No two consecutive scenes share the same framing scale |
| 10 | Standalone Camera | Camera motion written as a dedicated separate sentence |
| 11 | Physiological Emotion | Emotions described via physiological cues, not abstract adjectives |
| 12 | Anti-Artifact Rules | Free of finger micro-actions, text, 180° turns, mid-clip costume swaps |
| 13 | Lighting Consistency | Unified lighting signature across same-location scenes |
| 14 | Safety Compliance | Role-based aliases only; zero public figure names or flagged terms |
| 15 | 3-Second Hook | Scene 0 presents immediate visual conflict in the opening frame |
| 16 | Cliffhanger | Final scene leaves a suspended, unanswered narrative threat |
| 17 | Fact-Check Verification | Historical/factual data verified via research notes |
| 18 | Chain Type Standard | Defaulted to `ROOT` |
| 19 | Dialogue Presence | Minimum 2 dialogue scenes per 8-scene episode |
| 20 | Subtitle Suppression | All dialogue includes `(no subtitles)` suffix |

---

## O. Production Output & Pipeline Execution

### O.1 Screenplay JSON Schema
Save at `.omc/research/<slug>_ep<NN>_script.json`:
```json
{
  "series": "Hong Nhat Thang Long",
  "episode": 2,
  "title": "Race Against Time",
  "orientation": "HORIZONTAL",
  "lighting_signature": "volumetric light through dust (indoor); harsh midday sun (outdoor)",
  "scenes": [
    {
      "display_order": 0,
      "scene_type": "reaction_hook",
      "beat": "hook",
      "framing": "close-up",
      "chain_type": "ROOT",
      "character_names": ["Commander_Tien"],
      "has_dialogue": false,
      "wardrobe_state": "sleeves rolled up, light dust on shoulders",
      "prompt": "Close-up inside dim warehouse. Commander Tien stares at a pulsing red warning display, face half-lit by crimson glow. 35mm lens, shallow depth of field.",
      "video_prompt": "0-3s: Close-up of Commander Tien's face illuminated by pulsing red warning light. His eyes widen, lips parting slightly. 3-6s: Slow push-in to extreme close-up. Sweat on his brow catches the red light. He swallows hard. 6-8s: His jaw sets firmly, eyes narrowing with resolve. He exhales through his nose. Static shot with subtle handheld shake. Lighting: pulsing red on one side, deep shadow on the other. Audio: low electronic alarm pulse, controlled breathing. Negative: subtitles, watermark, text overlay.",
      "narrator_text": "The solar radiation warning flashes across the forecast terminal. The countdown stands at exactly thirty days.",
      "music_cue": "low analog drone, ticking pulse, 60 BPM"
    }
  ]
}
```

### O.2 Pipeline Ingestion Protocol
1. Verify daemon: `curl -s http://127.0.0.1:8100/health` → `{"extension_connected": true}`.
2. Create video entry: `POST /api/videos` with `project_id`, `title`, `orientation`.
3. Create scenes: `POST /api/scenes` (only approved schema fields).
4. Patch narration: `PATCH /api/scenes/{sid}` with `{"narrator_text": "..."}`.
5. Batch generation execution:
   - Reference images: `POST /api/requests/batch` with `GENERATE_CHARACTER_IMAGE`.
   - Scene start images: `POST /api/requests/batch` with `GENERATE_IMAGE`.
   - Veo 3 video clips: `POST /api/requests/batch` with `GENERATE_VIDEO`.
   - AI Vision review: `POST /api/videos/{vid}/review?mode=light`.
   - TTS narration: `POST /api/tts/generate` (Edge-TTS or OmniVoice).
   - Final concatenation & audio mastering: `/fk-concat-fit-narrator`.
