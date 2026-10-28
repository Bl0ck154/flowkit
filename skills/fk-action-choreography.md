# Action Choreography — AI Cinematic Combat & Motion Direction

Technical manual for choreographing physics-safe action sequences, duels, and epic battle dynamics optimized specifically for generative AI video models (Google Veo 3, Flow, Sora). Eliminates anatomical morphing, limb fusion, and weapon clipping.

---

## 1. Physical Principles of Generative AI Video

Unlike traditional 3D CGI or live-action stunt work, generative AI video possesses no underlying skeletal rig, collision meshes, or Newtonian physics simulation. The model predicts sequential pixel manifolds based on training probabilities.

### High-Risk Deformation Traps:
- **360-Degree Continuous Spins:** The model fails to maintain simultaneous dorsal and ventral memory, frequently rendering a second face on the back of the head.
- **Direct Head-On Sprints Toward Camera:** Rapid focal scale expansion distorts biometric proportions and liquefies facial features.
- **Intricate Physical Grappling:** Close-contact wrestling blends skin textures, generating fused limbs, three-armed mutants, or rubbery appendages.
- **Deep Penetration Wounds (Impaling):** Triggers safety moderation filters or results in rubberized, bending weapons.

### Strengths to Maximize:
- **Unidirectional Trajectories:** Clean linear, diagonal, or arc-based kinetic paths.
- **Environmental Momentum:** Billowing cloaks, turbulent hair, kicking dust clouds, sparks flying from steel collisions.
- **Camera-Assisted Kinetic Energy:** Dynamic tracking and push-ins synchronized to the blow to amplify visual force without complex character movement.

---

## 2. The 3-Phase Motion Invariant

Every 8-second Veo 3 video clip (yielding 7.0 seconds of pristine footage after a 1.0s head trim) must be structured into three distinct temporal phases:

```
[0–3s: PREPARATION & KINETIC TENSION] ──► [3–6s: KINETIC STRIKE & TRAJECTORY] ──► [6–8s: RECOIL & ANCHOR POSE]
(Stance, grip, eye lock, coiled potential)   (Unidirectional release, camera assist)   (Follow-through, sparks, dust settle)
```

### Phase 1 (0–3s) — Preparation & Kinetic Tension
- **Objective:** Establish physical balance, lower the center of gravity, lock eye contact onto the target.
- **Safe Prompt Verbs:** `lowers stance into a firm combat crouch`, `tightens white-knuckled grip on the sword hilt`, `draws heavy recurve bowstring backward smoothly to the cheekbone`.
- **Camera Dynamic:** Slow deliberate dolly-in or static locked-off shot to build coiled tension.

### Phase 2 (3–6s) — Kinetic Strike & Spatial Trajectory
- **Objective:** Execute the primary strike along a **single distinct vector**.
- **Golden Rule:** Describe weapon trajectory and environmental impact, NEVER soft-tissue penetration.
- **Safe Prompt Verbs:** `lunges forward in a powerful diagonal downward slash`, `sweeps the iron spear across in a broad horizontal crescent arc`, `releases the arrow which streaks forward leaving an air ripple`.
- **Camera Dynamic:** Camera rapidly tracking alongside the strike to amplify velocity.

### Phase 3 (6–8s) — Recoil, Anchor Pose & Resolution
- **Objective:** Settle into an anchor freeze-pose, absorbing recoil and displaying exertion.
- **Safe Prompt Verbs:** `skids to a firm halt kicking up dry dust`, `holds the defensive parry lock as orange sparks scatter`, `chest heaves with controlled breaths, fierce glare locked on opponent`.
- **Environmental Aftermath:** Cloaks settle, kicked-up gravel rolls to a stop, rising smoke clears.

---

## 3. Physics-Safe Action Vocabulary vs. Deformation Traps

| Combat Archetype | ❌ High-Risk Triggers (Causes Morphing) | ✅ Physics-Safe Vocabulary (Clean 100% Render) |
| :--- | :--- | :--- |
| **Swords / Blades** | `stabs sword through enemy chest, blood splatters` | `delivers a decisive diagonal downward slash, blade clashing against raised iron shield in an explosive burst of orange sparks` |
| **Spears / Polearms** | `twirls spear rapidly spinning 10 times in air` | `thrusts the heavy spear forward in an explosive straight line, then retracts immediately into a solid defensive guard` |
| **Archery / Snipers** | `rapidly shoots 10 arrows in 2 seconds` | `smoothly pulls bowstring taut to jawline, exhales, and looses a single heavy war arrow that streaks through smoke` |
| **Dodges & Evasions** | `does a backflip somersault in midair` | `ducks low beneath the sweeping blade, sidestepping swiftly to screen-left with defensive guard raised` |
| **Cavalry / Horseback** | `horse leaps directly over camera lens` | `gallops hard diagonally across the frame from mid-ground to foreground, hooves churning up wet mud` |
| **Unarmed Melee** | `grapples and rolls on the floor wrestling` | `drives a heavy iron-gauntleted punch forward, deflecting the incoming blow with a solid forearm block` |

---

## 4. Master Battle Sequence Templates

### Template 1: Melee Duel (Clashing Steel)
```text
[0-3s] Medium shot: The commander lowers his combat stance, drawing his bronze blade in a deliberate arc as hot torch embers drift past.
[3-6s] He explodes forward in a decisive diagonal slash; his blade collides violently with his opponent's raised iron buckler, discharging a brilliant shower of orange sparks. The camera rapidly dollies forward to accentuate the impact.
[6-8s] Both warriors lock blades in a rigid contest of physical will, muscles straining, breath pluming in the freezing mountain air.
Audio: Resonant clatter of striking metal, sizzle of flying sparks, heavy guttural war grunt.
Negative: subtitles, captions, watermark, text overlay, extra limbs, distorted hands.
```

### Template 2: Precision Archery Sequence
```text
[0-3s] Medium close-up: The archer stands resolute upon the wind-swept battlements, drawing the heavy horn bowstring back to her jawline with frozen focus amidst heavy snowfall.
[3-6s] She looses the arrow; the bowstring snaps forward with a sharp vibration, and the iron bodkin arrow streaks diagonally across the snowy sky. The camera smoothly pans alongside the arrow's flight path.
[6-8s] She lowers her bow into a ready stance, eyes tracking the distant impact beyond the palisade, her fur-lined cloak whipping violently in the gale.
Audio: Crisp snap of bowstring vibration, whistling air rush of speeding arrow, distant heavy thud into wood.
Negative: subtitles, captions, watermark, text overlay, extra fingers.
```

### Template 3: Armored Cavalry Charge
```text
[0-3s] Wide shot: The armored cavalry vanguard holds formation momentarily at the crest of the grassy hill, war steeds stamping restless hooves into rising morning mist.
[3-6s] The riders surge downhill simultaneously in a thunderous charge, iron lances leveled horizontally, moving diagonally from upper-left to lower-right. The camera tracks smoothly alongside the galloping horses.
[6-8s] Mud and clods of earth erupt violently beneath pounding hooves, silk battle banners fluttering furiously overhead as the charge reaches full momentum.
Audio: Massive rhythmic thunder of hundreds of galloping hooves, clanking bronze armor plates, distant war horn call.
Negative: subtitles, captions, watermark, text overlay, distorted legs.
```

### Template 4: Fortress Gate Siege & Shield Wall
```text
[0-3s] Low-angle shot: Soldiers brace their heavy bronze tower shields together into an unbroken wall, locking shoulders against the reinforced timber frame.
[3-6s] A volley of flaming arrows rains down from the dark sky, striking the shield wall in explosive bursts of sparks and splintering wood. The camera remains locked in a low-angle heroic perspective.
[6-8s] The soldiers hold their ground without flinching, smoke curling off the charred bronze shield faces as the commander raises his sword to signal the counter-assault.
Audio: Thundering impact of flaming arrows on metal and timber, hissing fire extinguished on wet wood, resolute soldier battle cry.
Negative: subtitles, captions, watermark, text overlay, blurry faces.
```
