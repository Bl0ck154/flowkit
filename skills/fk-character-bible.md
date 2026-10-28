# Character Bible & Visual Consistency — AI Film Production

Standards and technical workflows for maintaining biometric fidelity, wardrobe coherence, signature accessories, and environmental continuity across multi-chapter AI films in Google Flow and Veo 3.

---

## 1. Core Consistency Invariants

In multi-chapter AI filmmaking (5 to 20+ episodes), the most destructive failure modes are:
1. **Facial Drift:** Subtle generational changes in jawline, eye color, facial hair, or perceived age across chapters.
2. **Wardrobe Glitching:** A character wearing battle armor spontaneously switching into court robes, or cape colors morphing between cuts.
3. **Vanishing Identifiers:** Signature scars, tattoos, family heirlooms, or eye patches disappearing between consecutive scenes.

### The Golden Production Rule:
> **"Appearance in Reference, Action in Prompt"**
> * Detailed physical appearance (facial architecture, hairstyle, bone structure, clothing fabric, color palette) **MUST** be locked into the reference image and Entity description.
> * Scene prompts **MUST NEVER** re-describe facial anatomy. Prompts must specify **ACTION, TEMPORAL KINETICS, AND IMMEDIATE EMOTION ONLY**.

---

## 2. Character Visual Anchor Sheet

Before scripting an episode, every recurring character requires an immutable Visual Anchor Sheet saved at `.omc/research/<series>_character_bible.md`:

### Specification Template:
```markdown
### [ENTITY_KEY] Character Display Name (Role-Based Alias)
* **Entity Name:** Commander_Steel (Never use real public figures — Rule 15)
* **Biometric Invariants:**
  - Perceived Age & Build: Male, 38 years old, athletic battle-hardened build, 6'1" stature.
  - Facial Structure: Sharp square jawline, high weathered cheekbones, piercing cold amber eyes.
  - Signature Identifier: Thin 3cm diagonal pale battle scar running across the left cheekbone.
  - Hair & Facial Hair: Jet-black hair tightly bound in a high topknot with an antique bronze hair pin; clean-trimmed stubble along the jawline.
* **Palette Signature (Hex Codes):**
  - Primary: Deep crimson blood (`#801818` / Crimson blood).
  - Secondary: Charcoal carbon (`#1A1A1D` / Matte black).
  - Metal: Antique unpolished bronze (`#8C6239` / Weathered bronze).
* **Signature Prop / Weapon:**
  - Double-edged bronze broadsword with an engraved dragon guard and grey stingray-skin wrapped hilt.
```

---

## 3. Wardrobe State Matrix (Costume Progression by Story Arc)

Characters cannot remain in pristine identical garments through battles, captivity, or coronation. However, wardrobe transitions must be managed through strict **Discrete States**:

| State | State Identifier | Costume & Physical Condition | Narrative Context | Associated Entity Reference |
| :--- | :--- | :--- | :--- | :--- |
| **STATE 01** | `Normal / Court` | Raw silk ceremonial robe in indigo blue, jade hair pin, pristine posture. | Imperial audience, civilian life, covert meetings. | `Commander_Steel_Court` |
| **STATE 02** | `Battle / Armor` | Black iron scale armor, bronze dragon pauldrons, heavy crimson battle cloak. | Field command, vanguard assault, night patrol. | `Commander_Steel_Armor` |
| **STATE 03** | `Wounded / Battle-worn` | Shattered shoulder plate, scorched cloak, blood-stained linen band wrapped on forehead. | Post-siege breakout, desperate retreat, duel aftermath. | `Commander_Steel_Wounded` |
| **STATE 04** | `Coronation / Triumph` | Golden embroidered imperial vestments, ceremonial dragon crown, dignified triumph. | Victory parade, enthronement, climactic resolution. | `Commander_Steel_Triumph` |

### Production Rules for Wardrobe Changes:
- When a character undergoes a major visual transformation, **create a distinct Entity Reference** (e.g., `Commander_Steel_Armor` vs. `Commander_Steel_Wounded`).
- Generate and verify dedicated reference images for each state (`POST /api/requests/batch` with `GENERATE_CHARACTER_IMAGE`).
- Bind the exact matching entity name into the scene's `character_names` array in `POST /api/scenes`.

---

## 4. Rule 15 Compliance: Real-People Bypass

Modern generative video models (Google Flow, Veo 3, Imagen 3) enforce strict automated safety filters that reject generation requests containing names of real public figures, historical leaders, or politicians.

### Safe Execution Protocol:
1. **Role-Based Aliases:**
   - ❌ **Reject:** `Napoleon_Bonaparte`, `George_Washington`, `Tran_Hung_Dao`.
   - ✅ **Approve:** `Supreme_Commander_Grand_Marshal`, `Continental_General`, `Supreme_Field_Marshal`.
2. **Pure Anatomical Descriptions (Zero Named Identity):**
   - Prompt description: *"A seasoned 13th-century military general with piercing eyes, dignified weathered facial features, high cheekbones, traditional topknot hair tied with antique bronze pin, wearing iron scale armor."*
3. **Dialogue & Narrator Isolation:**
   - Formal titles and narrative lore may appear in `narrator_text` (handled via Edge-TTS audio), but **real names must NEVER enter image or video prompts**.

---

## 5. Environmental & World Consistency

Consistency applies equally to sets, citadels, terrain, and lighting:

1. **Entity Type = `location`:** Always generate reference images in **HORIZONTAL (16:9)** orientation.
2. **Unified Lighting Signature:**
   - Lock the illumination source across the scene chain (e.g., *"lit strictly by flickering orange pitch torches and distant embers, deep chiaroscuro shadows"*).
3. **Dual Entity Ingestion in Google Flow:**
   - When posting scenes, include both the character and location in `character_names`:
     ```json
     {
       "character_names": ["Commander_Steel_Armor", "Thang_Long_Grand_Palace"]
     }
     ```
   - Flow maps both reference media IDs into `imageInputs`, anchoring the character's facial likeness simultaneously with architectural consistency.

---

## 6. Per-Project Series Manifest Engine (`scripts/series_manifest.py`)

When managing multi-chapter epics (e.g., 5 to 20+ episodes), re-creating entities or re-generating reference images causes catastrophic visual drift. FlowKit provides an automated **Per-Project Series Manifest Engine**:

- **Location:** Stored strictly per-project inside `output/<slug>/series_manifest.json`.
- **Automatic Generation:** Automatically synthesized and synchronized by FlowKit API whenever `GET /api/projects/{pid}/output-dir` or `GET /api/projects/{pid}/manifest` is accessed.

### Workflow:
1. **Auto-Generate & Sync from Active Project:**
   ```bash
   # Synchronize entities, media_ids, and episodes into output/<slug>/series_manifest.json
   python scripts/series_manifest.py sync --project-id <ORIGIN_PID>
   ```

2. **Inspect Series Manifest Overview:**
   ```bash
   python scripts/series_manifest.py show --project-dir output/<slug>
   ```

3. **Bootstrap New Episodes with Zero Ref Drift:**
   ```bash
   # Create Chapter 6, reusing existing character & location UUIDs
   python scripts/series_manifest.py bootstrap \
     --project-dir output/<slug> \
     --episode 6 \
     --title "Chương VI: Huyết Nguyệt"
   ```
   *(This automatically links all pre-existing character and location `media_id`s into the new project, completely skipping reference image generation and preserving 100% biometric consistency across seasons).*


