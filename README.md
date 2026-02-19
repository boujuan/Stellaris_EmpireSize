# Stellaris Empire Size Breakdown Calculator

A Python script that parses a Stellaris 4.3 save game and calculates the exact empire size breakdown by component, annotated with every active modifier from traditions, technologies, and ascension perks.

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
 EMPIRE SIZE BREAKDOWN — Country 0: Prime Empire
═════════════════════════════════════════════════════════════════

POPULATIONS  [172,999 pops]
  Base:  172,999 × 0.005 = 865.00
  Per-species species_empire_size_mult:
    species 609: 166,826 pops  mult=-38.0%  raw=517.16  [38 evopred traits]
    ...
  empire_size_pops_mult = -15.0%:
    tradition: tr_domination_finish               -5.0%
    tradition: tr_synchronicity_kinship_gestalt   -5.0%
    tech: tech_psionic_theory                     -5.0%
  POPS COMPONENT: 464.12

DISTRICTS  [777 total district levels]
  DISTRICTS COMPONENT: 388.50

SYSTEMS  [466 starbases (incl. orbitals)]
  SYSTEMS COMPONENT: 396.10

COLONIES  [44 owned planets]
  COLONIES COMPONENT: 528.00

CALCULATED EMPIRE SIZE: 1688  (game-reported: 1482, discrepancy: +13.9%)
```

## Settings

All game constants and modifier lookup tables are in the `SETTINGS` block at the top of `empire_size.py`. Update these when game rules change between patches.

### Key settings

| Setting | Default | Description |
|---------|---------|-------------|
| `EVOPRED_PER_TRAIT_MULT` | `-0.01` | EvoPred `-1%/trait` modifier. Set to `0.0` to simulate vanilla (bugged) behaviour |
| `TRADITION_MODIFIERS` | (see file) | Maps tradition keys → empire_size modifier contributions |
| `TECH_MODIFIERS` | (see file) | Maps technology keys → empire_size modifier contributions |
| `ASCENSION_PERK_MODIFIERS` | (see file) | Maps ascension perk keys → contributions |

### Simulating vanilla (mod OFF)

```python
EVOPRED_PER_TRAIT_MULT = 0.0   # bug present: modifier never fires for hive mind drones
```

## How It Works

### Save game format

Stellaris saves use the **Clausewitz PDX text format**. The script streams the `gamestate` file in 5 targeted passes:

| Pass | Section | What it extracts |
|------|---------|-----------------|
| 1 | `species_db=` | Species traits and `species_traits_evopred_count` variables |
| 2 | `country= { N= { ... } }` | Traditions, techs, perks, edicts, owned planets, empire_size |
| 3 | `planets= { planet= { N= { ... } } }` | District IDs and pop counts per species per planet |
| 4 | `districts=` | Level (stacked count) for each district ID |
| 5 | `starbase_mgr=` + `ships=` | Starbase count via `station=ship_id` → `graphical_culture` chain |

### Empire size formula

```
pops_component    = Σ(pops × 0.005 × (1 + species_empire_size_mult)) × (1 + empire_size_pops_mult)
districts_component = total_district_levels × 0.5 × (1 + empire_size_districts_mult)
systems_component   = owned_systems × 1.0 × (1 + empire_size_systems_mult)
colonies_component  = owned_colonies × 20.0 × (1 + empire_size_colonies_mult)
empire_size = (pops + districts + systems + colonies) × (1 + empire_size_mult)
```

**District levels:** In Stellaris 4.x, each district object has a `level=N` field representing how many of that type are built. Empire size counts each level as one district.

### Known discrepancies

The script achieves ~86-90% accuracy vs game-reported values. The remaining gap comes from:

| Component | Gap | Root cause |
|-----------|-----|-----------|
| **Pops** | +~18-27% | Governor `species_empire_size_mult` (`-0.02/skill/planet`, `-0.01/skill/sector`). Not yet parsed. |
| **Districts** | +~7.6% | Unknown source — likely edicts or building modifiers not catalogued |
| **Systems** | +~8% | Starbase counter includes ~34 orbital platforms; actual owned systems ≈ count × 0.927 |
| **Colonies** | +~6.8% | Unknown source |

These gaps are reported in the output with per-component hints.

### Growing Pains situation

The script also calculates the `negative_empire_size_percent` multiplier (used by the Behemoth crisis situation's monthly progress formula) and shows how far empire size is from the threshold where progress improves:

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
└── README.md          # This file
```

## Game Version

Developed and tested against **Stellaris 4.3 Cetus Open Beta** (checksum `3f25`). Base defines sourced from `common/defines/00_defines.txt`:

- `EMPIRE_SIZE_FROM_POPS = 0.005`
- `EMPIRE_SIZE_FROM_DISTRICTS = 0.5`
- `EMPIRE_SIZE_FROM_SYSTEMS = 1.0`
- `EMPIRE_SIZE_FROM_COLONIES = 20.0`
