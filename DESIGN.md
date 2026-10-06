# Starfall Research Site: design + contracts

Expansion for the user's Gravity Gun mod (Skyrim SE). **Never modify anything under /home/claude/GravityGun.**

## Plugins (load order)
1. `StarfallCreatures.esp`: zombies, headcrabs, factions, leveled lists. Master: Skyrim.esm only.
2. `StarfallSite.esp`: crater worldspace, facility interior, scientists, guards, dialogue, quest, notes.
   Masters: Skyrim.esm, GravityGun.esp, StarfallCreatures.esp.
3. `StarfallSite.dll` (SKSE, CommonLibSSE-NG): world spawner, headcrab pounce, NPC-to-NPC chatter,
   dialogue actions (quest stages, items). Reads its data tables from JSON written by the ESP generator:
   `SKSE/Plugins/StarfallSite/forms.json` (+ `StarfallSite.ini` for tuning).

## Lore (short)
A year ago a star fell in the mountains east of Riverwood. Its crystalline core (the "Energy Crystals"
the player already hunts in Embershard) is anomalous: it stores zero-point energy. The **Lambda Directorate**
(scholars and engineers from somewhere far beyond Tamriel; they are vague about "back home") came through
a resonance rift and built **Starfall Research Site** inside the crater. They built the Zero-Point Field
Manipulator (the player's Gravity Gun). One prototype went missing: a frightened junior researcher
smuggled it out and hid it in Riverwood (Alvor's house), which is where the player found it.
Crystal-resonance experiments in the Test Chamber tore micro-rifts into a hostile border world they call
**the Hollow**. Things came through: headcrabs. A headcrab latched onto a person makes a zombie.
"Incident Seven" was a containment failure in Containment Wing B; specimens escaped into Skyrim.
Wuunferth in Windhelm developed Energy Trap from Directorate notes he bought (light mention only).
The facility still operates, guarded, strained, divided over whether to continue.

## Characters
| EDID | Name | Head | Role | Personality | Voice type EDID |
|---|---|---|---|---|---|
| SFKast | Dr. Aurelius Kast | einstein | Site Director / lead researcher | brilliant, dry wit, proud, secretive, downplays the breach | SFVoiceKast |
| SFHale | Dr. Marcus Hale | luther | Senior scientist, runs the Test Chamber, built the ZPF Manipulator | enthusiastic, brash, thrill-seeking, loves "his" gun | SFVoiceHale |
| SFRusk | Dr. Emil Rusk | walter | Medical researcher (xenobiology, parasitism) | cautious, increasingly frightened, conscience of the site | SFVoiceRusk |
| SFVenn | Tobias Venn | slick | Chief engineer (resonance array, generators) | sarcastic, pragmatic, complains about Skyrim's lack of tools | SFVoiceVenn |
| SFPell | Jory Pell | walter | Junior researcher | nervous, overworked, jumpy | SFVoiceJunior1 |
| SFHolt | Brennic Holt | slick | Junior researcher | cocky, ambitious, wants Hale's job | SFVoiceJunior2 |
| SFMire | Ollan Mire | luther | Junior researcher | quiet, homesick, fond of the locals and Nord books | SFVoiceJunior3 |
| SFMoran | Captain Dace Moran | combine_warden | Head of security | gruff, distrusts scientists, protective of his officers | SFVoiceMoran |
| SFGuard* | Security Officer | combine | guards (9) | mixed: bored, nervous, sardonic | SFVoiceGuardA / SFVoiceGuardB |

## Quest: "Anomalous Materials" (EDID SFQuestMain), optional, never touches the existing Gravity Gun quest
- 10 Speak with Director Kast (set on first entering the site).
- 20 Kast sends you to Dr. Hale; Hale asks for 3 Energy Crystals (GravityGun.esp form 0x806). Hand-in removes 3.
- 30 Dr. Rusk asks you to recover his research journal from sealed Containment Wing B; he gives the Wing B keycard.
- 40 Return the journal to Rusk (removes it). He reveals the truth about Incident Seven.
- 50 Confront Kast (dialogue). Reward: Directorate Clearance (Hale becomes a vendor of Energy Crystals; armory chest unlocked).
- 100 Complete.

## DLL data contract: SKSE/Plugins/StarfallSite/forms.json
```json
{
  "spawner": {
    "plugin": "StarfallCreatures.esp",
    "groups": [ {"name": "headcrabs_small", "lvln": "0x80A", "min": 1, "max": 3, "weight": 4, "minLevel": 1, "interior": true, "exterior": true}, ... ],
    "canister": {"plugin": "StarfallSite.esp", "static": "0x9xx"}
  },
  "headcrabKeyword": {"plugin": "StarfallCreatures.esp", "id": "0x801"},
  "zombieKeyword": {"plugin": "StarfallCreatures.esp", "id": "0x802"},
  "siteWorldspace": {"plugin": "StarfallSite.esp", "id": "0x..."},
  "siteCells": [ {"plugin": "StarfallSite.esp", "id": "0x..."} ],
  "actors": { "SFKast": {"plugin": "StarfallSite.esp", "id": "0x..."}, ... },
  "conversations": [
    {"a": "SFKast", "b": "SFHale", "lines": [ {"who": "a", "topic": "0x..."}, {"who": "b", "topic": "0x..."} ],
     "minStage": 0, "maxStage": 1000, "weight": 1}
  ],
  "infoActions": [ {"info": "0x...", "setStage": 20, "removeItem": {"plugin": "GravityGun.esp", "id": "0x806", "count": 3},
                    "addItem": {...}, "objectiveDisplayed": [20], "objectiveCompleted": [10]} ],
  "quest": {"plugin": "StarfallSite.esp", "id": "0x..."}
}
```

## Asset paths
- meshes/StarfallSite/{creatures,guards,scientists,props,kit}/...
- textures/StarfallSite/{creatures,guards,scientists,props,kit}/...
- Sound/Voice/StarfallSite.esp/<VoiceTypeEDID>/<file>.fuz|.wav (see VOICE.md + voice_manifest.csv)
