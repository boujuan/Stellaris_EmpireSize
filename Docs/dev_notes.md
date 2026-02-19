# Script Development Notes

Technical notes on `empire_size.py`: architecture, parser design, bugs hit, and remaining tasks.

---

## 1. Architecture Overview

The script does 8 sequential passes through the 65MB `gamestate` file (no pre-loading into memory):

```
Pass 1: species_db= (lines 50–30310)
    → Build {species_id: {traits, evopred_count}}

Pass 2: country= (lines 1247753–2219786)
    → Extract traditions, techs, perks, civics, owned_planets, controlled_planets,
      empire_size, num_sapient_pops, owned_fleets

Pass 3: planets= (lines 383890–1232516)
    → For each owned planet: collect district IDs, species_information,
      ascension_tier, governor leader ID

Pass 4: districts= (lines 4503998–4599137)
    → For each district ID from pass 3: look up level value

Pass 5: starbase_mgr= + ships= (lines 370032–3191312)
    → Fleet-based system count: station→ship→fleet→owned_fleets chain
      with starbase level filtering (SYSTEM_STARBASE_LEVELS)

Pass 6: leaders= (lines 2407429–2459386)
    → For governor leader IDs from pass 3: extract skill level, class, traits

Pass 7: sectors= (lines 4494626–4503998)
    → For country's sectors: local_capital, systems list, owner

Pass 8: galactic_object= (lines 299792–370032)
    → Build planet→system→sector chain for governor coverage mapping
```

Passes are not in file order (e.g., pass 8 reads galactic_object which is earlier in the file than sectors from pass 7). With OS file caching after the first pass, this is acceptable. Runtime: ~30-60 seconds total on modern hardware.

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

Handles braces inside quoted strings correctly.

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

### Challenge: `tech_status=` dual format

Technologies have TWO formats in tech_status:

1. Normal format:
```
technology="tech_psionic_theory"
level=1
```

2. Repeatable tech format:
```
"tech_lost_building_methods"="64"
```

The script handles format 1 (building `pending_technology` when `technology="..."` is seen, then appending when `level=` follows). Format 2 (quoted key = level as single line) is NOT currently handled. Repeatable techs don't affect empire size, so this omission is acceptable.

### Challenge: `station=N` in starbases is a SHIP ID

**Initial wrong assumption:** `station=N` in starbase entries is a fleet ID.

**Discovery:** Ship IDs ARE sequential. Testing `starbase.station = ship_id` → ship's `fleet=fleet_id` → check against country's `owned_fleets` correctly identifies ownership.

### Challenge: Civics extraction — if/elif chaining

When parsing `civics=` inside the `government={}` block, the entry condition (`civics=` at depth 3) and exit condition (depth <= 3, non-brace) can match on the **same line**. The `civics=` line itself is a non-brace line at depth 3, so checking both conditions in separate `if` blocks causes the flag to be set and immediately unset.

**Fix:** Use `elif` chaining so the exit condition only fires when the entry condition doesn't:
```python
if in_government and depth == 3 and line.startswith('civics='):
    in_civics_block = True
elif in_civics_block and depth == 4:
    # capture civic
elif in_civics_block and depth <= 3 and line not in ('{', '}'):
    in_civics_block = False
```

### Challenge: Sector systems — brace lines triggering exit

When parsing `systems={}` inside a sector block, the `{` on its own line after `systems=` would trigger the exit condition (`depth <= 2, non-brace`... except `{` wasn't excluded). Same pattern for galactic_object planet blocks.

**Fix:** Add `and line not in ('{', '}')` to all sub-block exit conditions.

### Challenge: Leader finalize — premature save on `{`

After matching a leader ID like `16777547=` at depth 1 and setting `current_id`, the next line `{` (also at depth 1 before opens) triggered the finalize-and-save block, storing the leader with all-zero fields before any depth 2 data was captured.

**Fix:** Check `line not in ('{', '}')` in the depth 1 finalize block, and add `if depth <= 1: continue` to skip brace lines.

### Challenge: Galactic object planets — not a sub-block

Planets in `galactic_object` are individual `planet=<id>` entries at depth 2, NOT a sub-block with IDs at depth 3. The format is simply:
```
planet=1569
planet=1570
```

**Fix:** Capture `planet=(\d+)` at depth 2 directly instead of looking for a block.

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
- **Civics:** Parsed from `government={civics={...}}` at D3/D4 with `elif` chaining (see §3)
- **Owned fleets:** Parsed from `fleets_manager={owned_fleets={{fleet=N}...}}` block, fleet IDs at D5

### `extract_planet_data(path, owned_planet_ids)`

- Filters to only process owned planet IDs (fast lookup via set)
- Scans entire `planets=` section but only processes owned planets
- District IDs: simple integer array at D4 (inside `districts=` at D3)
- Pop counts: `species_information= { species_id= { num_pops=N } }` at D3/D4/D5
- **Ascension tier:** `ascension_tier=N` at D3 (default 0)
- **Governor:** `governor=<leader_id>` at D3 (only on sector capital planets)

### `extract_district_levels(path, district_ids)`

- Scans entire `districts=` section (may be large)
- For each district in needed set, reads `level=` at D2
- Returns early when all needed IDs are found

### `count_owned_systems(path, owned_fleet_ids)`

Fleet-based ownership approach:
1. Scan `ships=` to build `{ship_id: fleet_id}` dict
2. Scan `starbase_mgr=` to count starbases where:
   - `level` is in `SYSTEM_STARBASE_LEVELS` (outpost/starport/starhold/starfortress/citadel)
   - `station=ship_id` → ship's `fleet=fleet_id` → fleet_id is in `owned_fleet_ids`
3. Returns tuple: `(system_count, total_matched, excluded_count)`

Non-system starbases (orbital rings, deep space citadels) are excluded by level filtering. Other countries' starbases are excluded by fleet ownership check.

### `extract_leader_data(path, leader_ids)`

- Scans `leaders=` section for specified leader IDs
- For each leader: extracts `level`, `bonus_skill_level`, `class`, `traits` at D2
- Returns `{leader_id: {'skill': level + bonus_skill_level, 'class': str, 'traits': [str]}}`
- Key: finalize logic runs on depth 1 non-brace lines only (see §3)

### `extract_sector_data(path, country_id)`

- Scans `sectors=` section for sectors with `owner=<country_id>`
- For each sector: captures `local_capital=<planet_id>` and `systems={...}` at D2
- Returns `{sector_id: {'local_capital': planet_id, 'systems': [int]}}`

### `build_planet_to_sector_map(path, sector_data)`

- Scans `galactic_object=` section to build planet→system mapping
- Combines with sector_data (system→sector mapping) to build full chain:
  planet → system → sector → local_capital → is_sector_capital? → sector_governor
- Returns `{planet_id: {'sector_id': int, 'is_sector_capital': bool, 'sector_governor': int|None}}`
- The sector_governor comes from the capital planet's `governor=` field

---

## 5. Known Issues and Remaining TODOs

### RESOLVED: Governor effects

Implemented in v0.2. Per-planet governor skill effects via planet→sector→governor chain. Result: pops gap reduced from +123 to -2.1.

### RESOLVED: Orbital platforms / system overcount

Implemented in v0.2. Two fixes:
1. **Starbase level filtering** — only count levels in `SYSTEM_STARBASE_LEVELS`, excluding orbital rings and deep space citadels (-8 systems)
2. **Fleet-based ownership** — ship→fleet→owned_fleets chain instead of graphical_culture matching (-26 systems from other countries)

### RESOLVED: District and colony -7.6%/-6.8% gaps

Both explained by planet ascension tiers. Tier 5 planets with +25% effect_mult give -31.2% reduction. Applied per-planet in v0.2.

### TODO 1: Councilor skill effects

Council positions provide per-skill modifiers to empire size (e.g., Machine Intelligence ruler might give -3%/level pops). Not yet parsed. May explain the remaining -2.1 pops gap.

### TODO 2: Governor traits

`GOVERNOR_TRAIT_MODIFIERS` is defined in SETTINGS but not yet applied. Example: `leader_trait_urbanist` gives -50% districts on governed planet, -25% on sector planets.

### TODO 3: Handle repeatable tech format

Currently misses techs in `"tech_key"="level"` format (repeatable techs). Doesn't affect empire size currently but should be fixed for completeness.

### TODO 4: Sector coverage gap

15 of 44 planets are unmapped to sectors (galactic_object scan finds 29/44). These unmapped planets get no governor reduction. Likely an issue with the system→sector mapping for planets in systems that aren't in any sector's system list.

---

## 6. Performance Notes

### File size

`gamestate` for q2: ~65MB, ~4.6M lines. Each pass reads the entire file sequentially. With OS file caching (after first read), subsequent passes are fast.

Typical runtime: 30-60 seconds total for 8 passes on a modern SSD.

### Optimization opportunities

1. **Pre-indexing:** First pass could record byte offsets of major section starts, allowing random-access seeking in subsequent passes. Not implemented — acceptable performance without it.

2. **Single-pass alternative:** A single-pass state machine could extract all data simultaneously, but the code complexity would be much higher.

3. **Memory:** The `ship_fleet` dict from pass 5 holds ship→fleet mappings. The `planet_data` dict (44 planets × their districts + pops) is small. Leader and sector data are also small.

### Encoding

PDX files use `errors='replace'` in file open — some binary/UTF8 edge cases exist in PDX format (especially in player-entered names). This prevents crashes at the cost of potentially garbling rare character sequences.

---

## 7. Modifier Interaction: species_empire_size_mult vs empire_size_pops_mult

These two modifier types interact multiplicatively, NOT additively:

```python
# CORRECT (multiplicative):
pops_component = Σ(pops × base × (1 + species_mult + gov_mult)) × asc_factor × (1 + pops_mult)

# WRONG (additive would be):
pops_component = Σ(pops × base × (1 + species_mult + pops_mult))
```

Governor effects are additive with species_mult (both are per-pop), then ascension tier is multiplicative on the per-planet sum, then country-wide pops_mult is multiplicative on the total.

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

---

## 11. Useful File Locations for Future Investigation

### For councilor effects (TODO 1)

```
common/council_positions/*.txt
    → Check council position modifiers for empire size effects per skill level
```

### For governor traits (TODO 2)

```
common/static_modifiers/00_static_modifiers.txt
    → leader_trait_urbanist: planet_districts_empire_size_mult
common/traits/50_leader_traits.txt
    → Leader trait definitions and their modifier keys
```
