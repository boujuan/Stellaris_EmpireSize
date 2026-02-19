# Script Development Notes

Technical notes on `empire_size.py`: architecture, parser design, bugs hit, and next steps.

---

## 1. Architecture Overview

The script does 5 sequential passes through the 65MB `gamestate` file (no pre-loading into memory):

```
Pass 1: species_db= (lines 50–30310)
    → Build {species_id: {traits, evopred_count}}

Pass 2: country= (lines 1247753–2219786)
    → Extract traditions, techs, perks, owned_planets, controlled_planets,
      empire_size, num_sapient_pops, graphical_culture

Pass 3: planets= (lines 383890–1232516)
    → For each owned planet: collect district IDs and species_information

Pass 4: districts= (lines 4503998–4599137)
    → For each district ID from pass 3: look up level value

Pass 5: ships= (lines 2459386–3191312) + starbase_mgr= (lines 370032–383890)
    → Build ship_id→culture map, then count starbases for country_culture
```

The 5 passes are in different order than sections appear in the file (starbase_mgr at ~370K is scanned after ships at ~2.4M). This means passes 3 and 5 both require scanning backwards relative to each other — no optimization is possible without two-pass pre-indexing. Runtime is acceptable (~30-60 seconds for the 65MB file on modern hardware).

---

## 2. PDX Parser (`stream_lines`)

### Core function

```python
def stream_lines(filepath):
    depth = 0
    with open(filepath, encoding='utf-8', errors='replace') as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            opens, closes = _count_braces(line)
            depth -= closes     # closing braces reduce depth BEFORE yield
            if depth < 0:
                depth = 0
            yield depth, line
            depth += opens      # opening braces increase depth AFTER yield
```

### Why this depth ordering

The rule "close before yield, open after yield" means:
- A `}` line is yielded at the depth it CLOSES TO (the outer level), not the inner level
- A `key={` line is yielded at the current depth (the outer level)
- Content inside a block starts on the NEXT line at depth+1

This makes it natural to write:
```python
if depth == 2 and line.startswith('traditions='):
    # we know the CONTENT will be at depth 3
    in_traditions = True
```

### Brace counting

```python
def _count_braces(s):
    opens = closes = 0
    in_q = False
    for c in s:
        if c == '"':
            in_q = not in_q
        elif not in_q:
            if c == '{': opens += 1
            elif c == '}': closes += 1
    return opens, closes
```

Handles braces inside quoted strings correctly. Only issue: escaped quotes `\"` inside strings could theoretically cause issues, but they don't appear in PDX format.

---

## 3. Key Parsing Challenges and Solutions

### Challenge: Section exit detection

A top-level section like `country=` opens with `country=` at depth 0, then `{` at depth 0 (opens to depth 1). The content is at depth 1+. The NEXT section (`dead_*=`) is at depth 0 again.

**Bug encountered:** The `{` that opens the country section is also at depth 0 (yielded before depth increases). So checking `if depth == 0 and in_country_section: break` would fire immediately on the `{` line, before any content is read.

**Fix:** Add `and line not in ('{', '}')` to all section-exit conditions:
```python
if depth == 0 and line not in ('{', '}'):
    break  # Left section
```

### Challenge: Country block exit

Similar issue when inside country 0's block and looking for when the next country's block starts:

```python
# WRONG: fires on the '{' that opens country 0's block
if depth <= 1 and line != '{':
    break

# CORRECT: only exit on a new country entry
if depth == 1 and line not in ('{', '}') and re.match(r'^\d+=', line):
    break
```

### Challenge: Pending blocks

PDX frequently uses the two-line pattern:
```
key=
{
    content
}
```

The `key=` line at depth D has NO braces (opens=0, closes=0). The following `{` line at depth D opens to depth D+1. Code must track that a key at depth D means the block's content is at depth D+1 on the next and subsequent lines.

The simplest approach: set a flag when `key=` is seen, and check/use that flag when processing depth D+1 lines. Reset the flag when a different depth-D key is encountered.

### Challenge: `tech_status=` dual format

Technologies have TWO formats in tech_status:

1. Normal format:
```
technology="tech_psionic_theory"
level=1
```

2. Repeatable tech format:
```
"tech_repeatable_improved_starbase_capacity"="82"
```

The script handles format 1 (building `pending_technology` when `technology="..."` is seen, then appending when `level=` follows). Format 2 (quoted key = level as single line) is NOT currently handled. Repeatable techs don't affect empire size, so this omission is acceptable.

### Challenge: `station=N` in starbases is a SHIP ID

**Initial wrong assumption:** `station=N` in starbase entries is a fleet ID.

**Evidence that it's wrong:** Fleet IDs are non-sequential. Fleet 6 doesn't exist. But `station=6` appears in starbase 1.

**Discovery:** Ship IDs ARE sequential. Ship 6 exists and has `fleet=4` and `graphical_culture="humanoid_01"`. Testing `starbase.station = ship_id` → `ship.graphical_culture` correctly identifies ownership.

**Why station values skip by 6:** Station values are 0, 6, 12, 18... because each starbase station ship is 1 of every 6 ships (the other 5 in between belong to mobile fleets or other stations in that system).

### Challenge: `controlled_planets` doesn't give system count

Initial approach: use galactic_object IDs in `controlled_planets` to count owned star systems.

**Problem:** Only 208 of 432 owned systems have their galactic_object ID in `controlled_planets`. The remaining 224 systems have starbases but aren't in this list (they're non-colonized systems with outposts only, apparently).

**Solution:** Use the starbase counting method (starbase → ship → graphical_culture).

### Challenge: Planet section depth is 3, not 2

Planet section structure is `planets= { planet= { N= { content } } }`, giving content at depth 3, not depth 2 as initially assumed.

```
planets=   ← D0
{          ← D0 → D1
    planet= ← D1 (note: this wrapper key exists!)
    {       ← D1 → D2
        10= ← D2 (planet ID)
        {   ← D2 → D3
            owner=0  ← D3 (planet content)
```

If you assume planet IDs are at D1, you'll get `planet=` as the first entry, then miss all actual planet entries.

---

## 4. Data Extraction Functions

### `extract_species_data(path)`

- Scans `species_db=` block (D0 to first non-species D0 key)
- Species IDs at D1, traits at D3 (inside `traits=` at D2), evopred_count at D3 (inside `variables=` at D2)
- Tracks `section_key[depth]` dict to know which D2 block is active
- Stops when first non-brace D0 line is seen after entering species_db

### `extract_country_data(path, country_id)`

- Scans `country=` block for the target country ID
- Critical exit conditions: MUST use `line not in ('{', '}')` for D0 exit check
- `tech_status` uses pending-key approach: `technology="key"` sets `pending_technology`, then `level=` triggers append
- All major lists (traditions, perks, owned_planets, controlled_planets) use same pattern: detect `key=` at D2, set flag, collect at D3

### `extract_planet_data(path, owned_planet_ids)`

- Filters to only process owned planet IDs (fast lookup via set)
- Scans entire `planets=` section but only processes owned planets
- District IDs: simple integer array at D4 (inside `districts=` at D3)
- Pop counts: `species_information= { species_id= { num_pops=N } }` at D3/D4/D5

### `extract_district_levels(path, district_ids)`

- Scans entire `districts=` section (may be large)
- For each district in needed set, reads `level=` at D2
- Returns early when all needed IDs are found

### `count_owned_systems(path, graphical_culture)`

Two-pass approach:
1. Scan `ships=` to build `{ship_id: graphical_culture}` dict
2. Scan `starbase_mgr=` to count starbases where `station=ship_id` maps to the target culture

**Caveat:** Counts include orbital platforms (~34 extra for country 0). True system count ≈ result × 0.927.

---

## 5. Known Issues and TODOs

### TODO 1: Governor effects (HIGHEST PRIORITY)

Implement parsing of `leaders=` section to get governor skill levels and apply `species_empire_size_mult` per planet.

**What to parse:**
- In country 0's data: look for the government section or officials/councilors to find which leaders are governors for which planets
- In `leaders=` section: find each relevant leader's `skill=N`

**Data location:**
- `leaders=` section starts at line 2459247 (~732K lines)
- Leader structure: `N= { class=official skill=N ... }`
- Planet-to-governor mapping: likely in the planet's `governor=N` field (depth 3 in planet block)

**Parsing approach:**
1. In pass 3 (planet data), also extract `governor=N` field (leader ID for the planet's governor)
2. New pass: scan `leaders=` to build `{leader_id: skill_level}` dict for all official-class leaders
3. In calculation: for each owned planet, compute `governor_mult = -0.02 × skill` and apply to all pops on that planet

**Expected gain:** Will close the +123 point pops discrepancy.

### TODO 2: Identify orbital platforms

Better system count by excluding orbitals from starbase count.

**Approach A (scan orbitals blocks):**
1. In pass 5, when scanning `starbase_mgr=`, collect all non-null orbital IDs from `orbitals={}` blocks
2. These are entity-encoded IDs (like `16780879`). Need to figure out encoding to map back to starbase IDs.
3. Entity encoding: `16777216 = 2^24`. Values like `16780879 = 16777216 + 3663` might mean starbase type 1, index 3663. Needs verification.

**Approach B (correction factor):**
Use `min(count, round(count × 0.927))` as an approximation. The ratio 432/466 = 0.927 is specific to this save state; it might vary.

### TODO 3: Identify -7.6% districts source

Unknown source of `empire_size_districts_mult` giving -7.64%.

**Places to investigate:**
- `common/edicts/*.txt` — active edicts: `crystal_focus`, `fuel_gases`, `motes_kinetic`, `living_metal_construction`, `motes_armor`
- `common/inline_scripts/buildings/on_all_capital_buildings.txt` — the Synaptic Extensions capital building (hive mind swap of tr_domination_imperious_architecture) might have district modifiers
- `common/buildings/` — any building with `empire_size_districts_mult`
- `common/governments/civics/02_gestalt_civics.txt` — Devouring Swarm civic modifiers (might have been missed)

### TODO 4: Identify -6.8% colonies source

Unknown source giving additional colonies reduction beyond -40% (Courier Network -15% + Imperial Prerogative -25%).

**Calculate expected vs actual:**
- Expected with known mods: `44 × 20 × 0.85 × 0.75 = 561`
- Game shows: 492
- Ratio: 492/561 = 0.877 → additional -12.3% on top of already-applied mods?

Wait — let me reconsider. The mods are ADDITIVE:
- -0.15 + -0.25 = -0.40
- `44 × 20 × (1 - 0.40) = 528`
- Game shows 492
- 492/528 = 0.932 → additional **-6.8%** additive reduction

**Possible sources:**
- `ap_imperial_prerogative` might actually be -0.30 not -0.25 in 4.3
- Some tradition may give additional -5% colonies for specific government types
- Check `02_gestalt_civics.txt` Devouring Swarm swap for any colonies modifier

### TODO 5: Handle repeatable tech format

Currently misses techs in `"tech_key"="level"` format (repeatable techs). Doesn't affect empire size currently but should be fixed for completeness.

---

## 6. Performance Notes

### File size

`gamestate` for q2: ~65MB, ~4.6M lines. Each pass reads the entire file sequentially. With OS file caching (after first read), subsequent passes are fast.

Typical runtime: 60-120 seconds total for 5 passes on a modern SSD (dominated by the `ships=` section parsing in pass 5, which is 732K lines).

### Optimization opportunities

1. **Pre-indexing:** First pass could record byte offsets of major section starts, allowing random-access seeking in subsequent passes. Not implemented — acceptable performance without it.

2. **Single-pass alternative:** A single-pass state machine could extract all data simultaneously, but the code complexity would be much higher.

3. **Memory:** The `ship_culture` dict from pass 5 holds up to 7301 entries — negligible memory. The `planet_data` dict (44 planets × their districts + pops) is also small.

### Encoding

PDX files use `errors='replace'` in file open — some binary/UTF8 edge cases exist in PDX format (especially in player-entered names). This prevents crashes at the cost of potentially garbling rare character sequences.

---

## 7. Modifier Interaction: species_empire_size_mult vs empire_size_pops_mult

These two modifier types interact multiplicatively, NOT additively:

```python
# CORRECT (multiplicative):
pops_component = Σ(pops × base × (1 + species_mult)) × (1 + pops_mult)

# WRONG (additive would be):
pops_component = Σ(pops × base × (1 + species_mult + pops_mult))
```

Verification from data:
- Without mod: `pops_raw = 865.0`, `pops_component = 865 × 0.85 = 735.25`
- With mod (species 609 at -38%): `pops_raw = 546.03`, `pops_component = 546.03 × 0.85 = 464.12`

The `empire_size_pops_mult` (-15%) is applied to the WHOLE sum of raw pop contributions, after per-species effects have already reduced individual contributions.

---

## 8. The Chimeral Consciousness Bug: Full Analysis

### Root cause

`social_classes_triggered_modifiers.txt` (lines 154-168) contains a `triggered_pop_group_modifier` applying `species_empire_size_mult = -0.01 × species_traits_evopred_count`. This file is included by REGULAR pop categories (workers, specialists, rulers) but NOT by gestalt drone pop categories.

Gestalt drone categories (`common/pop_categories/01_gestalt_drones.txt`) ONLY include:
```pdx
inline_script = "pop_categories/social_classes_triggered_modifiers_no_happiness"
```

This `_no_happiness` variant was missing the evopred modifier. Since all Hive Mind pops are drones, the modifier NEVER fires.

### Fix

Added the modifier block to the `_no_happiness` file. The fix mod:
- Location: `~/Coding/Mods/chimeral_consciousness_fix/`
- Deployed (symlinked) to: `~/.local/share/Paradox Interactive/Stellaris/mod/`
- **FIOS/LIOS behavior for inline_scripts:** DUPL (duplicates) — must replace entire file

### Wiki FIOS/LIOS table for `inline_scripts`

From the official wiki: `inline_scripts` are **DUPL** — "Only works when the file is fully replaced in my experience." This means our mod correctly provides the complete vanilla content + our fix.

### Related authority bug

The Chimeral Consciousness authority (`auth_bio_hive_mind_evopred`) uses `empire_size_penalty_mult = -0.20`. This is NOT a bug — it's an intentional secondary benefit (reduces tech/tradition cost penalty from empire size). The per-trait reduction is the primary mechanic (fixed by our mod) and the -20% penalty reduction is a separate, working bonus.

### `is_mutation_authority` trigger

```pdx
is_mutation_authority = {
    has_country_flag = bio_mutation
}
```

The `bio_mutation` flag is set by event `bio.195` (Hive Mind path) when `tr_mutation_finish` tradition is adopted. Confirmed present in country 0's flags in both saves.

### `species_traits_evopred_count` variable

Set per-species by `set_species_traits_evopred_count_variable` scripted effect, which calculates it from `num_traits` on the species. The founder species (609) has count=38, matching the 38 traits listed in its definition.

---

## 9. Mod Deployment Notes

### File structure

```
~/Coding/Mods/chimeral_consciousness_fix/            ← dev source
    descriptor.mod
    common/inline_scripts/pop_categories/
        social_classes_triggered_modifiers_no_happiness.txt

~/Coding/Mods/chimeral_consciousness_fix.mod         ← launcher descriptor (points to dev location)
    path="/home/boujuan/Coding/Mods/chimeral_consciousness_fix"

~/.local/share/Paradox Interactive/Stellaris/mod/
    chimeral_consciousness_fix -> (symlink to dev location above)
    chimeral_consciousness_fix.mod (copy of .mod file)
```

### Updating the mod after a game patch

1. Check if vanilla `social_classes_triggered_modifiers_no_happiness.txt` changed
2. If changed: copy new vanilla content into our mod's version, keep the evopred block appended
3. Update `supported_version="v4.X.*"` in both `descriptor.mod` and `chimeral_consciousness_fix.mod`

---

## 10. Console Workarounds (for the Growing Pains bug)

To bypass the stuck Growing Pains situation without fixing empire size:

```
# Select the Growing Pains situation first, then:
effect add_situation_progress = 100    # Add 100 progress
effect add_situation_progress = 1200   # Complete entire situation
```

Stage events (from `common/situations/12_biogenesis_situations.txt`):
- Stage 1 → 2 (at 80): `event biocrisis.210`
- Stage 2 → 3 (at 180): `event biocrisis.215`
- Stage 3 → 4 (at 300): `event biocrisis.220`
- etc. (multiples of 5 up to biocrisis.250 for final)

---

## 11. Useful File Locations for Future Investigation

### For governor effects (TODO 1)

```
common/static_modifiers/00_static_modifiers.txt
    skill_official_planet_governor → species_empire_size_mult = -0.02
    skill_official_sector_governor → species_empire_size_mult = -0.01
    (also: skill_commander_*, skill_scientist_* variants for governors)
```

### For district -7.6% gap (TODO 3)

```
common/inline_scripts/buildings/on_all_capital_buildings.txt
    → Check hive mind capital building effects
common/edicts/*.txt
    → crystal_focus, fuel_gases, motes_kinetic, living_metal_construction, motes_armor
common/static_modifiers/00_static_modifiers.txt
    → empire_size_districts_mult occurrences
```

### For colonies -6.8% gap (TODO 4)

```
common/ascension_perks/00_ascension_perks.txt
    → Verify ap_imperial_prerogative value in 4.3 (line ~1472)
common/governments/civics/02_gestalt_civics.txt
    → Check Devouring Swarm swap_type section (lines 277+)
```
