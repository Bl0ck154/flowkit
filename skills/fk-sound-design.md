# Sound Design & Audio Mastering — AI Cinematic Soundscapes

Industry standards for multi-layer sound design, automated dynamic ducking, sub-bass rumble synthesis, and EBU R128 loudness mastering for Google Veo 3, Edge-TTS, and AI cinematic productions.

---

## 1. Principles of AI Sound Design

> *"Sound is 50 percent of the movie-going experience, and in AI cinema, sound represents 70 percent of perceived reality."* — George Lucas

When generative AI imagery occasionally exhibits synthetic artifacts, a **rich, multi-layered, and physically grounded soundscape** anchors the viewer's subconscious, convincing the brain of physical reality.

---

## 2. The 4-Layer Audio Architecture

Every professional AI cinematic scene must be constructed from four independent acoustic strata:

```
LAYER 1: NARRATOR / DIALOGUE ────► Center (Mid/Mono), Crisp clarity, High presence (+2.5dB to +3.5dB)
LAYER 2: VEO 3 FOLEY & SFX ──────► Discrete impacts, Footsteps, Clashing steel, Bowstring release
LAYER 3: AMBIENCE & ROOM TONE ──► Wind howling, Falling rain, Campfire crackle, Night cicadas
LAYER 4: SCORE & SUB-BASS DRONE ─► Orchestral themes (Suno AI), War drums, 40-60Hz tactile rumble
```

### Acoustic Balance Matrix:

| Audio Stratum | Generation Source | Role in Scene | Standard Level (Gain Factor) |
|:---|:---|:---|:---|
| **Layer 1: Voice (Dialogue & Narration)** | Edge-TTS (`NamMinhNeural` / `HoaiMyNeural`) | Story progression, emotional anchoring | `1.30 – 1.50` (+2.5dB to +3.5dB) |
| **Layer 2: Foley & SFX (Physical Action)** | Veo 3 Native Audio / SFX Library | Physical weight, combat impact | `0.60 – 0.80` (When dialogue absent) |
| **Layer 3: Ambience (World Acoustic)** | Veo 3 Background Audio / Field Recordings | Environmental scale & space | `0.20 – 0.30` (Auto-ducked during dialogue) |
| **Layer 4: Score & Sub-Bass Drone** | Suno AI (`/fk-gen-music`) & Brown noise | Emotional pulse & visceral tension | `0.35 – 0.50` (Score), `0.60` (Bumper drone) |

---

## 3. Automated Audio Ducking Invariant

The most common defect in amateur AI video compiles is **background audio or music drowning out spoken dialogue**.

### FFmpeg Sidechain Ducking Formula:
When dialogue or voice narration is active, ambient sound and background music must automatically duck by **-12dB to -15dB**:

```bash
# Mix Voice (input 1) with Ambient (input 0) applying cinema balance:
ffmpeg -y -i scene_video.mp4 -i scene_tts.wav \
  -filter_complex "[0:a]volume=0.25[bg];[1:a]volume=1.40[fg];[bg][fg]amix=inputs=2:duration=first:dropout_transition=2[aout]" \
  -map 0:v -map "[aout]" -c:v copy -c:a aac -b:a 192k output_mixed.mp4
```

---

## 4. Sub-Bass Drone Synthesis (Suspense & Chapter Bumpers)

Frequencies between **40Hz and 60Hz** bypass the auditory ear canal and vibrate directly in the chest cavity, creating visceral tension:

1. **Dramatic Triggers:**
   - Pre-ambush stillness, ticking clocks, impending royal betrayals.
   - Chapter interstitial bumpers (creating solemn, ancient reverence).
2. **FFmpeg Procedural Sub-Bass Rumble Generation:**
   ```bash
   # Synthesize 3.5s of Brown Noise filtered at 48Hz for cinematic bumper transition:
   ffmpeg -f lavfi -i "anoisesrc=c=brown:r=48000:a=0.3,lowpass=f=75,volume=0.6" -t 3.5 -c:a aac drone.m4a
   ```

---

## 5. Broadcast & YouTube Mastering (EBU R128 Loudness)

Before final distribution on YouTube (Shorts or Long-form) or streaming platforms, the master audio must comply with international broadcast loudness standards:
- **Integrated Loudness Target:** `-14.0 LUFS` (±1 LUFS) for YouTube (prevents YouTube's automated loudness penalty compressor from squashing dynamics).
- **True Peak Ceiling:** `-1.0 dBTP` (prevents digital clipping and inter-sample distortion on mobile DACs).
- **Loudness Range (LRA):** `7.0 to 10.0 LU` (maintains cinematic dynamic range between whispers and explosions).

### Mastering Command via FFmpeg:
```bash
ffmpeg -i input_master.mp4 \
  -af "loudnorm=I=-14:LRA=7:TP=-1.0" \
  -c:v copy -c:a aac -b:a 256k final_master_mastered.mp4
```

---

## 6. Procedural Foley & SFX Layering (`scripts/sfx_layering.py`)

When scene actions feature intense physical beats (blade combat, heavy strikes, detonations, underground tremors), FlowKit's automated sound design engine scans the `prompt` or `video_prompt` to synthesize and layer synchronized sound effects:

### Supported SFX Categories & Triggers:
- **`metal_clash`** (Keywords: `knife`, `blade`, `sword`, `dao`, `kiếm`, `chém`, `steel`): Metallic blade impact with high-frequency shimmer.
- **`heavy_impact`** (Keywords: `strike`, `slam`, `punch`, `đấm`, `va chạm`, `ngã gục`): Low-end punch with 65Hz transient thud.
- **`explosion_blast`** (Keywords: `explosion`, `blast`, `nổ`, `bomb`, `shockwave`, `lựu đạn`): Deep detonation rumble with brown noise decay.
- **`underground_drone`** (Keywords: `tầng hầm`, `b3`, `cống ngầm`, `underground`, `tunnel`): 45Hz subterranean room tone.
- **`alarm_siren`** (Keywords: `báo động`, `siren`, `alarm`, `klaxon`, `còi báo`): Modulated tactical warning siren.
- **`heartbeat_tension`** (Keywords: `tim đập`, `tension`, `gasping`, `thở dốc`, `hồi hộp`): 60 BPM physiological heartbeat pulse.

### Automated Layering Command:
```bash
python scripts/sfx_layering.py \
  --input-video path/to/scene.mp4 \
  --prompt "0-3s: Tactical knife blade clash. 3-6s: Heavy strike against concrete." \
  --output path/to/scene_with_sfx.mp4 \
  --volume 0.6
```
*(Studio sample overrides can be added to `assets/sfx/<category>/` for custom studio WAV assets).*

