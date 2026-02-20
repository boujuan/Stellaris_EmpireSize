# Stellaris Empire Size Breakdown Calculator

A Python script that parses a Stellaris 4.3 save game and calculates the exact empire size breakdown by component, annotated with every active modifier from traditions, technologies, ascension perks, governors, and planet ascension tiers.

**Accuracy: -0.1%** (1481 calculated vs 1482 game-reported on test save).

## Usage

```bash
python3 empire_size.py <save_path> [country_id]
```

Accepts a `.sav` file (ZIP archive) or a folder containing an unzipped `gamestate` file.

```bash
python3 empire_size.py saves/my_save.sav
python3 empire_size.py saves/my_save.sav 0     # explicit country ID (default: 0 = player)
python3 empire_size.py saves/q2/               # folder with gamestate
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
      16 sector capitals (planet governor, -2%/level)
      9 sector planets (sector governor, -1%/level)
      1 frontier planets (direct governor, -2%/level)
    18 planets without governor (4 in sectors, 14 frontier)
    Total pops reduction from governors: 94.39

POPULATIONS  [172,999 pops]
  Base:  172,999 × 0.005 = 865.00
  Per-species species_empire_size_mult:
    species 609:  166,826 pops  mult=-38.0%  raw= 517.16  [38 evopred traits]
    species 16777235:    3,500 pops  mult=-6.0%  raw=  17.50  [6 evopred traits, 3,500 in purge/etc]
    ...
  Raw pops (species mults only):          548.03
  After governor + ascension:             400.80
  empire_size_pops_mult = -15.0%:
    tradition: tr_domination_finish               -5.0%
    tradition: tr_synchronicity_kinship_gestalt   -5.0%
    tech: tech_psionic_theory                     -5.0%
  POPS COMPONENT: 400.80 × (1 -15.0%) = 340.7

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

CALCULATED EMPIRE SIZE:         1480.79  →  1481
GAME-REPORTED EMPIRE SIZE:      1482
DISCREPANCY:                    -1.21  (-0.1%)
═════════════════════════════════════════════════════════════════
```

## Settings

All game constants and modifier lookup tables are in the `SETTINGS` block at the top of `empire_size.py`. Update these when game rules change between patches.

### Key settings

| Setting | Default | Description |
|---------|---------|-------------|
| `EVOPRED_PER_TRAIT_MULT` | `-0.01` | EvoPred `-1%/trait` modifier. Set to `0.0` if not applicable |
| `ASCENSION_TIER_BASE_REDUCTION` | `0.05` | -5% per planet ascension tier to pops/districts/colony |
| `GOVERNOR_PLANET_RATE` | `-0.02` | Per-skill-level empire size mult for planet governors (sector capital) |
| `GOVERNOR_SECTOR_RATE` | `-0.01` | Per-skill-level empire size mult for sector governors (other planets) |
| `SYSTEM_STARBASE_LEVELS` | set of 5 | Starbase levels that count as systems (outpost through citadel) |
| `POP_CATEGORIES_NO_TRIGGERED_MODIFIERS` | set of 9 | Pop categories excluded from triggered modifiers (purge, assimilation, etc.) |
| `TRADITION_MODIFIERS` | (see file) | Maps tradition keys → empire_size modifier contributions |
| `TECH_MODIFIERS` | (see file) | Maps technology keys → empire_size modifier contributions |
| `ASCENSION_PERK_MODIFIERS` | (see file) | Maps ascension perk keys → contributions |
| `ASCENSION_EFFECT_TRADITIONS` | (see file) | Traditions giving `planetary_ascension_effect_mult` |
| `ASCENSION_EFFECT_CIVICS` | (see file) | Civics giving `planetary_ascension_effect_mult` |

## How It Works

### Save game format

Stellaris saves use the **Clausewitz PDX text format**. The script streams the `gamestate` file in 9 targeted passes:

| Pass | Section | What it extracts |
|------|---------|-----------------|
| 1 | `species_db=` | Species traits and `species_traits_evopred_count` variables |
| 2 | `country=` | Traditions, techs, perks, civics, owned planets, owned fleets, empire_size |
| 3 | `planets=` | District IDs, pop counts per species, ascension tier, governor ID per planet |
| 4 | `pop_groups=` | Per-(planet, species) pop counts split by category eligibility |
| 5 | `districts=` | Level (stacked count) for each district ID |
| 6 | `starbase_mgr=` + `ships=` | Fleet-based system count with starbase level filtering |
| 7 | `leaders=` | Skill level, class, and traits for governor leaders |
| 8 | `sectors=` | Sector capitals, system lists, and owner for sector→governor mapping |
| 9 | `galactic_object=` | Planet→system→sector chain for governor coverage |

### Empire size formula

```
# Per-planet calculation (ascension + governor applied before summing):
for each planet:
    asc_factor = 1 - tier × 0.05 × (1 + planetary_ascension_effect_mult)
    gov_pop_mult = governor_rate × governor_skill   (−0.02/level planet, −0.01/level sector)

    # Pops in triggered categories get full species_mult (trait + evopred)
    # Pops in excluded categories (purge, assimilation, etc.) get base mult (trait only)
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

### Pop category filtering

Pops in certain categories (purge, assimilation, criminal, etc.) do not receive `triggered_pop_group_modifier` effects like the EvoPred `species_empire_size_mult`. The script reads `pop_groups=` to determine each pop's category and applies triggered modifiers only to eligible pops. Static species trait modifiers (`trait_docile`, `trait_unruly`) apply to all pops regardless of category.

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
