# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A single-file Python script (`empire_size.py`) that parses Stellaris 4.3 save games and calculates exact empire size breakdowns by component (pops, districts, systems, colonies), annotated with active modifiers. Built to diagnose and verify a fix for the **Chimeral Consciousness bug** where the EvoPred `-1% per trait` modifier fails to apply to Hive Mind drones.

## Running the Script

```bash
# Unzip a save first (Stellaris saves are .sav ZIP archives)
unzip "My Save.sav" -d my_save/

# Run (requires only Python 3.8+, no dependencies)
python3 empire_size.py <save_folder> [country_id]
python3 empire_size.py saves/q2/ 0    # country 0 = player (default)
```

Test saves are in `saves/q/` and `saves/q2/` (must be unzipped; gamestate files are gitignored).

## Architecture

The script is a single file with four logical sections:

1. **SETTINGS block** (lines 27–128) — All game constants, modifier lookup tables (traditions, techs, perks, edicts, civics, species traits). Update these when game rules change. The `EVOPRED_PER_TRAIT_MULT` setting toggles the bug fix simulation (set to `0.0` for vanilla bugged behavior).

2. **PDX streaming parser** (lines 135–195) — `stream_lines()` yields `(depth, line)` tuples by tracking brace depth. Critical rule: closing braces decrement depth BEFORE yield, opening braces increment AFTER yield. This means `key=` at depth D has content at depth D+1 on subsequent lines.

3. **Data extractors** (lines 202–599) — Five functions, each doing a full sequential pass through the ~65MB gamestate file:
   - Pass 1: `extract_species_data` — species traits + evopred_count from `species_db=`
   - Pass 2: `extract_country_data` — traditions, techs, perks, owned planets from `country=`
   - Pass 3: `extract_planet_data` — district IDs + pop counts per species from `planets=`
   - Pass 4: `extract_district_levels` — level (stacked count) per district from `districts=`
   - Pass 5: `count_owned_systems` — starbase count via `ships=` + `starbase_mgr=` chain

4. **Calculation + report** (lines 606–954) — Applies the empire size formula, computes discrepancies vs game-reported values, shows Growing Pains situation analysis.

## PDX Parser Pitfalls

When writing new extractors or modifying existing ones:

- **Section exit detection** must check `line not in ('{', '}')` — bare braces at the same depth as a section header will falsely trigger exits otherwise.
- **Pending blocks**: PDX uses `key=\n{` (key on one line, brace on next). The `{` line is yielded at the SAME depth as `key=`, content starts at depth+1 on the next line.
- **`tech_status`** has two formats: `technology="key"\nlevel=N` (regular) and `"tech_key"="level"` (repeatable). Only the first format is currently parsed.
- **`station=N`** in starbases is a **ship ID** (not fleet ID). Ownership is determined by `starbase.station → ship.graphical_culture → country.graphical_culture` chain.

## Empire Size Formula

```
pops     = Σ(pops × 0.005 × (1 + species_empire_size_mult)) × (1 + empire_size_pops_mult)
districts = total_levels × 0.5 × (1 + empire_size_districts_mult)
systems   = owned_systems × 1.0 × (1 + empire_size_systems_mult)
colonies  = owned_planets × 20.0 × (1 + empire_size_colonies_mult)
total     = (pops + districts + systems + colonies) × (1 + empire_size_mult)
```

`species_empire_size_mult` and `empire_size_pops_mult` are **multiplicative** with each other, not additive.

## Known Accuracy Gaps (~+14% overcount vs game)

| Component | Gap | Root Cause |
|-----------|-----|-----------|
| Pops | +123 pts | Governor `species_empire_size_mult` (`-0.02/skill/planet`) not parsed — **largest gap** |
| Districts | +30 pts | Unknown ~-7.6% source (possibly edicts/buildings) |
| Systems | +29 pts | ~34 orbital platforms included in starbase count |
| Colonies | +36 pts | Unknown ~-6.8% source |

## Adding New Modifier Sources

Add entries to the relevant dict in the SETTINGS block:
```python
TRADITION_MODIFIERS['tr_new_key'] = {'pops': -0.05}
TECH_MODIFIERS['tech_new_key'] = {'districts': -0.10}
ASCENSION_PERK_MODIFIERS['ap_new_key'] = {'colonies': -0.25}
```
Modifier type keys: `'pops'`, `'districts'`, `'systems'`, `'colonies'`, `'total'`

## Related Projects

- **Fix mod**: `~/Coding/Mods/chimeral_consciousness_fix/` — adds missing `triggered_pop_group_modifier` to `social_classes_triggered_modifiers_no_happiness.txt`
- **Stellaris install**: `~/.local/share/Steam/steamapps/common/Stellaris/` — vanilla game files for reference (`common/defines/`, `common/traditions/`, etc.)
- **Detailed docs**: `Docs/` — save format reference, formula derivations, parser design notes, development TODOs

## Game Version

Stellaris 4.3 Cetus Open Beta (checksum `3f25`). Base defines from `common/defines/00_defines.txt`.
