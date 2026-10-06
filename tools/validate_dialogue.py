"""Validate dialogue/dialogue.json and dialogue/quest_text.json for the Starfall Research Site expansion."""
import json, re, sys
from collections import Counter, defaultdict

D = "/home/claude/Facility/dialogue/"
EMOS = {"Neutral", "Anger", "Disgust", "Fear", "Sad", "Happy", "Surprise", "Puzzled"}
CTYPES = {"Attack", "Hit", "Flee", "LostToCombat", "Death", "Murder", "AlertIdle", "AlertToCombat", "CombatToNormal",
          "CombatToLost", "NormalToAlert", "DetectFriendDie"}
ACTS = {"setStage", "removeCrystals", "giveKeycard", "removeJournal", "objectiveDisplayed", "objectiveCompleted", "openVendor"}
COND_RE = re.compile(r"^(stage(<|>=|==)\d+|hasGravityGun|noGravityGun|crystals>=3|hasJournal|hasKeycard|night|day)$")
BANNED = ["earth", "black mesa", "freeman", "combine", "half-life", "half life", "valve"]

errs, warns = [], []
raw = open(D + "dialogue.json", encoding="utf-8").read() + open(D + "quest_text.json", encoding="utf-8").read()
for ch in ("—", "–"):
    if ch in raw:
        errs.append("dash U+%04X found" % ord(ch))
for b in BANNED:
    if re.search(r"\b%s\b" % re.escape(b), raw.lower()):
        errs.append("banned term: " + b)

d = json.load(open(D + "dialogue.json", encoding="utf-8"))
q = json.load(open(D + "quest_text.json", encoding="utf-8"))
SP = set(d["speakers"])
ids = Counter()
voiced = []  # (category, speaker, text)
wc = lambda t: len(t.split())


def line(cat, spk, o, need):
    for k in need:
        if k not in o:
            errs.append("%s missing %s: %s" % (cat, k, o.get("id")))
    ids[o["id"]] += 1
    if o["emotion"] not in EMOS:
        errs.append("bad emotion " + o["id"])
    n = wc(o["text"])
    if n < 1 or n > 30:
        errs.append("word count %d: %s" % (n, o["id"]))
    voiced.append((cat, spk, o["text"]))


def conds(o):
    for c in o.get("cond", []):
        if not COND_RE.match(c):
            errs.append("bad cond %r in %s" % (c, o["id"]))


for cat, need in (("greetings", ["id", "speaker", "cond", "emotion", "text"]),
                  ("idle", ["id", "speaker", "cond", "emotion", "text"]),
                  ("combat", ["id", "speaker", "type", "cond", "emotion", "text"])):
    for o in d[cat]:
        if o["speaker"] not in SP:
            errs.append("unknown speaker " + o["id"])
        if cat == "combat" and o["type"] not in CTYPES:
            errs.append("bad combat type " + o["id"])
        conds(o)
        line(cat, o["speaker"], o, need)

for c in d["conversations"]:
    ids[c["id"]] += 1
    for k in ("a", "b"):
        if c[k] not in SP:
            errs.append("unknown speaker in " + c["id"])
    if not 2 <= len(c["lines"]) <= 6:
        errs.append("conversation length " + c["id"])
    for l in c["lines"]:
        if l["who"] not in ("a", "b"):
            errs.append("bad who " + l["id"])
        line("conversations", c[l["who"]], l, ["who", "id", "emotion", "text"])


def topic(t, depth=0):
    for k in ("id", "speaker", "prompt", "cond", "once", "responses", "actions", "children"):
        if k not in t:
            errs.append("topic missing %s: %s" % (k, t.get("id")))
    ids[t["id"]] += 1
    if t["speaker"] not in SP:
        errs.append("unknown speaker " + t["id"])
    if wc(t["prompt"]) > 10:
        errs.append("prompt too long " + t["id"])
    if not 1 <= len(t["responses"]) <= 3:
        errs.append("response count " + t["id"])
    bad = set(t["actions"]) - ACTS
    if bad:
        errs.append("bad action keys %s in %s" % (bad, t["id"]))
    conds(t)
    for r in t["responses"]:
        line("topics", t["speaker"], r, ["id", "emotion", "text"])
    for ch in t["children"]:
        topic(ch, depth + 1)


for t in d["topics"]:
    topic(t)

dups = [i for i, n in ids.items() if n > 1]
if dups:
    errs.append("duplicate ids: %s" % dups)
texts = Counter(v[2].lower() for v in voiced)
for t, n in texts.items():
    if n > 1:
        warns.append("duplicate text: " + t)

# quest_text checks
for k in ("10", "20", "30", "40", "50"):
    if k not in q["stages"]:
        errs.append("missing stage text " + k)
for k in ("10", "20", "30", "40"):
    if k not in q["objectives"]:
        errs.append("missing objective " + k)
jw = wc(q["items"]["journal"]["text"])
if not 250 <= jw <= 400:
    errs.append("journal words %d" % jw)
if not 10 <= len(q["notes"]) <= 14:
    errs.append("note count %d" % len(q["notes"]))
for n in q["notes"]:
    w = wc(n["text"])
    if not 60 <= w <= 250:
        errs.append("note %s words %d" % (n["id"], w))
nid = Counter(n["id"] for n in q["notes"])
if any(v > 1 for v in nid.values()):
    errs.append("duplicate note ids")

# report
per_cat = Counter(v[0] for v in voiced)
per_spk = defaultdict(Counter)
for cat, spk, _ in voiced:
    per_spk[spk][cat] += 1
in_range = sum(1 for v in voiced if 4 <= wc(v[2]) <= 18)
print("per category:", dict(per_cat))
print("conversations:", len(d["conversations"]), " topics (incl. children):",
      sum(1 for i in ids if i.startswith("tp_") and not re.search(r"_r\d+$", i)))
for s in d["speakers"]:
    print("  %-8s %s total=%d" % (s, dict(per_spk[s]), sum(per_spk[s].values())))
print("voiced lines total:", len(voiced), " lines with 4-18 words: %d (%.0f%%)" % (in_range, 100.0 * in_range / len(voiced)))
print("max words:", max(wc(v[2]) for v in voiced), " journal words:", jw,
      " notes:", len(q["notes"]), [wc(n["text"]) for n in q["notes"]])
for w in warns:
    print("WARN", w)
for e in errs:
    print("ERROR", e)
print("OK" if not errs else "FAILED")
sys.exit(1 if errs else 0)
