# Dev Docs — Stellaris Empire Size Calculator

**Game version:** 4.3 Cetus Open Beta (checksum `3f25`)
**Script:** `empire_size.py`
**Investigation date:** 2026-02-19

---

## Document Index

| File | Contents |
|------|----------|
| [`save_format.md`](save_format.md) | Complete PDX save format reference: section locations, depth rules, every relevant field |
| [`empire_size.md`](empire_size.md) | Empire size formula, all modifier sources, known discrepancies, remaining gaps |
| [`dev_notes.md`](dev_notes.md) | Script architecture, parser design, bugs hit during development, next tasks |

---

## Quick Context

This project parses `gamestate` (the main file inside a `.sav` archive) to calculate the exact empire size breakdown. The investigation was triggered by a Stellaris bug:

**The Chimeral Consciousness Bug:** The `-1% Empire Size from Pops per Species Trait` modifier for Evolutionary Predators Hive Minds never fires. It's coded in `social_classes_triggered_modifiers.txt` but Hive Mind drones exclusively include `social_classes_triggered_modifiers_no_happiness.txt`. The fix mod adds the missing block to the `_no_happiness` variant.

- **Fix mod:** `~/Coding/Mods/chimeral_consciousness_fix/`
- **Bug report:** `~/Documents/Bounotes/Modding/Stellaris/chimeral_consciousness_growing_pains_bug.md`

---

## Current Script Accuracy (q2 save, mod ON)

| Component | Game Reports | Script Calculates | Gap | Cause |
|-----------|-------------|-------------------|-----|-------|
| Pops | 341.1 | 464.1 | **+123** | Governor `species_empire_size_mult` not parsed |
| Districts | 358.8 | 388.5 | **+29.7** | Unknown ~-7.6% source |
| Systems | 367.2 | 396.1 | **+28.9** | ~34 orbital platforms overcounting |
| Colonies | 492.0 | 528.0 | **+36** | Unknown ~-6.8% source |
| **Total** | **1482** | **1688** | **+13.9%** | |

---

## Known Saves

| Save folder | Description | Game-reported empire_size |
|-------------|-------------|--------------------------|
| `saves/q/` | With fix mod ON (same game state as q2) | 1482 |
| `saves/q2/` | Same state, used as primary test | 1482 |

Both saves correspond to the same game state with the fix mod active. To test vanilla (mod OFF), set `EVOPRED_PER_TRAIT_MULT = 0.0` in SETTINGS — this gives pops_component = 735.25 vs game's 575.4 (same 159-point governor gap).

---

## Stellaris Install Path

```
~/.local/share/Steam/steamapps/common/Stellaris/
```

Key subdirs referenced throughout:
- `common/defines/00_defines.txt` — base constants
- `common/inline_scripts/pop_categories/` — triggered pop modifiers
- `common/pop_categories/` — pop category definitions
- `common/governments/authorities/` — authority definitions
- `common/traditions/` — tradition modifier definitions
- `common/technology/` — tech modifier definitions
- `common/ascension_perks/` — ascension perk definitions
- `common/static_modifiers/` — governor/static modifier definitions
- `common/situations/` — the Growing Pains situation
- `common/script_values/` — `negative_empire_size_percent` formula
