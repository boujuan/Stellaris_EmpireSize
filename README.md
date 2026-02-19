# Stellaris Empire Size Breakdown Calculator

A Python script that parses a Stellaris 4.3 save game and calculates the exact empire size breakdown by component, annotated with every active modifier from traditions, technologies, ascension perks, governors, and planet ascension tiers.

**Accuracy: -0.2%** (1479 calculated vs 1482 game-reported on test save).

## Background

Developed to diagnose a bug in Stellaris 4.3 Cetus Open Beta (checksum `3f25`) where the **Chimeral Consciousness** authority (Evolutionary Predators + Hive Mind + Mutation tradition tree) fails to apply its `-1% Empire Size from Pops per Species Trait` bonus to any Hive Mind pop. The root cause and fix are documented in full here:

- **Bug report:** `chimeral_consciousness_growing_pains_bug.md` (Obsidian note)
- **Fix mod:** [`chimeral_consciousness_fix`](../../Mods/chimeral_consciousness_fix/) — adds the missing `triggered_pop_group_modifier` to `social_classes_triggered_modifiers_no_happiness.txt`

## Usage

```bash
python3 empire_size.py <save_folder> [country_id]
```

The save folder must contain an unzipped `gamestate` file (Stellaris saves are zipped `.sav` archives; unzip first).

```bash
# Unzip your save first
unzip "My Save.sav" -d my_save/

# Then run the calculator
python3 empire_size.py my_save/
python3 empire_size.py my_save/ 0        # explicit country ID (default: 0 = player)
```

### Example Output

```
═════════════════════════════════════════════════════════════════
 EMPIRE SIZE BREAKDOWN — Country 0: Pandora
═════════════════════════════════════════════════════════════════

PLANET ASCENSION TIERS:
    Tier 3: 1 planets  (−18.8% to pops/districts/colony)
    Tier 5: 9 planets  (−31.2% to pops/districts/colony)
    Tier 0: 34 planets  (no reduction)
  planetary_ascension_effect_mult = +25.0%:
    tradition: tr_synchronicity_finish            +25.0%

GOVERNOR EFFECTS:
    26 planets with governor coverage
    Total pops reduction from governors: 94.39

POPULATIONS  [172,999 pops]
  Base:  172,999 × 0.005 = 865.00
  Per-species species_empire_size_mult:
    species 609:  166,826 pops  mult=-38.0%  raw= 517.16  [38 evopred traits]
    ...
  Raw pops (species mults only):          546.03
  After governor + ascension:             398.80
  empire_size_pops_mult = -15.0%:
    tradition: tr_domination_finish               -5.0%
    tradition: tr_synchronicity_kinship_gestalt   -5.0%
    tech: tech_psionic_theory                     -5.0%
  POPS COMPONENT: 398.80 × (1 -15.0%) = 339.0

DISTRICTS  [777 total district levels across all owned planets]
  Base:  777 × 0.5 = 388.5
  After ascension:                        358.8
  DISTRICTS COMPONENT: 358.8 × (1 +0.0%) = 358.8

SYSTEMS  [432 owned systems]
  Starbases matched by fleet: 440  (excluded 8 orbital rings/DSCs)
  SYSTEMS COMPONENT: 367.2

COLONIES  [44 owned planets]
  Base:  44 × 20.0 = 880.0
  After ascension:                        820.0
  COLONIES COMPONENT: 820.0 × (1 -40.0%) = 492.0

CALCULATED EMPIRE SIZE:         1479.18  →  1479
GAME-REPORTED EMPIRE SIZE:      1482
DISCREPANCY:                    -2.82  (-0.2%)
═════════════════════════════════════════════════════════════════
```

## Settings

All game constants and modifier lookup tables are in the `SETTINGS` block at the top of `empire_size.py`. Update these when game rules change between patches.

### Key settings

| Setting | Default | Description |
|---------|---------|-------------|
| `EVOPRED_PER_TRAIT_MULT` | `-0.01` | EvoPred `-1%/trait` modifier. Set to `0.0` to simulate vanilla (bugged) behaviour |
| `ASCENSION_TIER_BASE_REDUCTION` | `0.05` | -5% per planet ascension tier to pops/districts/colony |
| `GOVERNOR_PLANET_RATE` | `-0.02` | Per-skill-level empire size mult for planet governors (sector capital) |
| `GOVERNOR_SECTOR_RATE` | `-0.01` | Per-skill-level empire size mult for sector governors (other planets) |
| `SYSTEM_STARBASE_LEVELS` | set of 5 | Starbase levels that count as systems (outpost through citadel) |
| `TRADITION_MODIFIERS` | (see file) | Maps tradition keys → empire_size modifier contributions |
| `TECH_MODIFIERS` | (see file) | Maps technology keys → empire_size modifier contributions |
| `ASCENSION_PERK_MODIFIERS` | (see file) | Maps ascension perk keys → contributions |
| `ASCENSION_EFFECT_TRADITIONS` | (see file) | Traditions giving `planetary_ascension_effect_mult` |
| `ASCENSION_EFFECT_CIVICS` | (see file) | Civics giving `planetary_ascension_effect_mult` |

### Simulating vanilla (mod OFF)

```python
EVOPRED_PER_TRAIT_MULT = 0.0   # bug present: modifier never fires for hive mind drones
```

## How It Works

### Save game format

Stellaris saves use the **Clausewitz PDX text format**. The script streams the `gamestate` file in 8 targeted passes:

| Pass | Section | What it extracts |
|------|---------|-----------------|
| 1 | `species_db=` | Species traits and `species_traits_evopred_count` variables |
| 2 | `country=` | Traditions, techs, perks, civics, owned planets, owned fleets, empire_size |
| 3 | `planets=` | District IDs, pop counts per species, ascension tier, governor ID per planet |
| 4 | `districts=` | Level (stacked count) for each district ID |
| 5 | `starbase_mgr=` + `ships=` | Fleet-based system count with starbase level filtering |
| 6 | `leaders=` | Skill level, class, and traits for governor leaders |
| 7 | `sectors=` | Sector capitals, system lists, and owner for sector→governor mapping |
| 8 | `galactic_object=` | Planet→system→sector chain for governor coverage |

### Empire size formula

```
# Per-planet calculation (ascension + governor applied before summing):
for each planet:
    asc_factor = 1 - tier × 0.05 × (1 + planetary_ascension_effect_mult)
    gov_pop_mult = governor_rate × governor_skill   (−0.02/level planet, −0.01/level sector)

    planet_pops = Σ(pops × 0.005 × (1 + species_mult + gov_pop_mult)) × asc_factor
    planet_districts = district_levels × 0.5 × asc_factor
    planet_colony = 1 × 20.0 × asc_factor

# Country-wide multipliers (applied after summing all planets):
pops_component    = Σ(planet_pops)     × (1 + empire_size_pops_mult)
districts_component = Σ(planet_districts) × (1 + empire_size_districts_mult)
systems_component   = owned_systems × 1.0 × (1 + empire_size_systems_mult)
colonies_component  = Σ(planet_colony) × (1 + empire_size_colonies_mult)

# Global multiplier:
empire_size = (pops + districts + systems + colonies) × (1 + empire_size_mult)
```

**District levels:** In Stellaris 4.x, each district object has a `level=N` field representing how many of that type are built. Empire size counts each level as one district.

### System ownership

Systems are counted via a fleet-based ownership chain: `starbase_mgr` → `station=ship_id` → ship's `fleet=fleet_id` → check fleet_id against country's `owned_fleets`. Only starbases with level in `SYSTEM_STARBASE_LEVELS` are counted (orbital rings and deep space citadels are excluded).

### Growing Pains situation

The script calculates the `negative_empire_size_percent` multiplier (used by the Behemoth crisis situation's monthly progress formula) and shows how far empire size is from the threshold where progress improves:

```
negative_empire_size_percent = max(0.1, 1.1 - 0.001 × empire_size)
Threshold for improvement: empire_size < 1100
```

## Adding New Modifier Sources

When new traditions, techs, or perks are added in a game update, add them to the relevant dict in the SETTINGS block:

```python
# In TRADITION_MODIFIERS:
'tr_new_tradition_finish': {'pops': -0.05},

# In TECH_MODIFIERS:
'tech_new_tech': {'districts': -0.10},

# In ASCENSION_PERK_MODIFIERS:
'ap_new_perk': {'colonies': -0.25},

# For planetary ascension effect mult:
# In ASCENSION_EFFECT_TRADITIONS:
'tr_new_tradition_finish': 0.25,
# In ASCENSION_EFFECT_CIVICS:
'civic_new_civic': 0.25,
```

Modifier type keys: `'pops'`, `'districts'`, `'systems'`, `'colonies'`, `'total'`

## Requirements

- Python 3.8+
- No external dependencies (stdlib only)
- Tested on Stellaris 4.3 Cetus Open Beta

## Files

```
Stellaris_EmpireSize/
├── empire_size.py     # Main script
├── CHANGELOG.md       # Version history
├── README.md          # This file
└── Docs/              # Developer documentation
    ├── index.md       # Doc index and quick context
    ├── empire_size.md # Formula, modifiers, known gaps
    ├── dev_notes.md   # Architecture and parser design
    └── save_format.md # PDX save format reference
```

## Game Version

Developed and tested against **Stellaris 4.3 Cetus Open Beta** (checksum `3f25`). Base defines sourced from `common/defines/00_defines.txt`:

- `EMPIRE_SIZE_FROM_POPS = 0.005`
- `EMPIRE_SIZE_FROM_DISTRICTS = 0.5`
- `EMPIRE_SIZE_FROM_SYSTEMS = 1.0`
- `EMPIRE_SIZE_FROM_COLONIES = 20.0`
