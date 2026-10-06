# Adding voice lines

Every spoken line in the expansion is listed in **`voice_manifest.csv`**, 503 rows in all. Columns:

| column | meaning |
|---|---|
| folder | where the file goes inside your mod's Data folder |
| file | exact file name (`.fuz`; see formats below) |
| voice_type | which voice it is (one per character, two shared guard voices) |
| speaker | the character |
| category | greeting, idle, combat:&lt;type&gt;, conversation, topic, gate |
| emotion | Neutral / Anger / Fear / Happy / Sad / Surprise / Puzzled / Disgust (handy as a TTS style hint) |
| text | the line |
| line_id | stable id from `dialogue/dialogue.json` |

Example row:
```
Sound\Voice\StarfallSite.esp\SFVoiceKast\  SFDialogue_SFHello_00000AB9_1.fuz  SFVoiceKast  SFKast  greeting  Neutral  "Mind the cables..."
```

## Voices

| voice_type | who | lines |
|---|---|---|
| SFVoiceKast | Director Aurelius Kast (old, dry, proud) | 62 |
| SFVoiceHale | Dr. Marcus Hale (brash, excited) | 56 |
| SFVoiceRusk | Dr. Emil Rusk (careful, frightened) | 52 |
| SFVoiceVenn | Tobias Venn (sarcastic engineer) | 44 |
| SFVoiceJunior1 | Jory Pell (nervous junior) | 33 |
| SFVoiceJunior2 | Brennic Holt (cocky junior) | 31 |
| SFVoiceJunior3 | Ollan Mire (quiet, homesick junior) | 34 |
| SFVoiceMoran | Captain Dace Moran (gruff security chief) | 60 |
| SFVoiceGuardA | Security officer voice A (also the gate sentry) | 69 |
| SFVoiceGuardB | Security officer voice B | 62 |

## Formats

- **.fuz** (audio plus lip sync) is the standard. xVASynth can export straight to .fuz, and Yakitori Audio Converter / Unfuzer convert .wav to .xwm/.fuz.
- **.xwm** without lip data also works; just change the extension in the file name.
- **.wav:** many mod authors play loose .wav voice files fine in Skyrim SE. If a .wav line stays silent on your setup, convert it to .xwm.
- **Lip sync** doesn't matter much here: everyone wears a helmet or an HL head mesh that doesn't animate.

## Rules

- The file name is fixed by the line's internal ID. Don't rename files. If you regenerate the plugin, re-read the manifest, because the IDs can change when lines are added or removed.
- Lines with no audio file still show their subtitle for a few seconds, so missing files never break anything.
- To change a line's text, edit `dialogue/dialogue.json` and rerun `tools/build_site.py`. That rewrites the plugin and the manifest.
