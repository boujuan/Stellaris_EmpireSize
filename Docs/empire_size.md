# Empire Size: Formula, Modifiers, and Known Gaps

Complete reference for empire size calculation in Stellaris 4.3 Cetus Open Beta.

---

## 1. Base Defines

Source: `common/defines/00_defines.txt`

```
EMPIRE_SIZE_BASE                   = 100   # No penalty at or below this value
EMPIRE_SIZE_FLOOR                  = 50    # Empire size never treated as below this
EMPIRE_SIZE_FROM_POPS              = 0.005 # Per pop
EMPIRE_SIZE_FROM_DISTRICTS         = 0.5   # Per district level (see below)
EMPIRE_SIZE_FROM_SYSTEMS           = 1.0   # Per owned system (starbase)
EMPIRE_SIZE_FROM_COLONIES          = 20.0  # Per colonized planet
EMPIRE_SIZE_FROM_BRANCH_OFFICES    = 5.0   # Per branch office (megacorp)
EMPIRE_SIZE_TECH_COST_PENALTY      = 0.002 # Per empire size above base (for research cost)
EMPIRE_SIZE_TRADITION_COST_PENALTY = 0.002 # Per empire size above base (for tradition cost)
```

**"District level"** in 4.x: Each district instance has a `level=N` field in the save (how many of that type are built). Empire size counts `N × 0.5` per district object. Total = `Σ(all districts on all owned planets of level N) × 0.5`.

---

## 2. The Complete Formula

The formula uses per-planet calculation for ascension tier and governor effects, then applies country-wide multipliers.

```python
# Step 1: per-planet contributions
for each planet:
    # Ascension tier factor (affects pops, districts, colony — NOT systems)
    asc_factor = 1 - tier × 0.05 × (1 + planetary_ascension_effect_mult)

    # Governor pop modifier (per-skill species_empire_size_mult)
    #   Planet governor (sector capital): -0.02 × skill
    #   Sector governor (other planets):  -0.01 × skill
    gov_pop_mult = governor_rate × governor_skill

    # Per-planet pops (species mult + governor applied per pop, then ascension)
    planet_pops = Σ(pop_count × 0.005 × (1 + species_empire_size_mult + gov_pop_mult)) × asc_factor

    # Per-planet districts (ascension only)
    planet_districts = total_district_levels × 0.5 × asc_factor

    # Per-planet colony (ascension only)
    planet_colony = 1 × 20.0 × asc_factor

# Step 2: country-wide multipliers (applied to sums of all planets)
pops_component      = Σ(planet_pops)      × (1 + total_empire_size_pops_mult)
districts_component = Σ(planet_districts)  × (1 + total_empire_size_districts_mult)
colonies_component  = Σ(planet_colony)     × (1 + total_empire_size_colonies_mult)

# Step 3: systems (no per-planet ascension/governor — country-wide only)
systems_component   = owned_systems × 1.0 × (1 + total_empire_size_systems_mult)

# Step 4: global multiplier (applied to sum of all components)
subtotal = pops_component + districts_component + systems_component + colonies_component
empire_size = subtotal × (1 + total_empire_size_mult)
```

**Modifier stacking:** All modifiers of the same type (e.g., all `empire_size_pops_mult`) add together, then `(1 + sum)` is the factor.

**`species_empire_size_mult` vs `empire_size_pops_mult`:**
- `species_empire_size_mult` is applied PER POP based on that pop's species — it modifies the base contribution of each individual pop.
- `empire_size_pops_mult` is a COUNTRY-WIDE factor applied to the sum of all raw pop contributions.
- These are multiplicative with each other (not additive).

**Governor effects** are applied at the same level as `species_empire_size_mult` (per-pop, additive with species mult), then ascension tier is applied multiplicatively on top.

---

## 3. `negative_empire_size_percent` (Growing Pains)

Source: `common/script_values/00_script_values.txt`

```pdx
negative_empire_size_percent = {
    base = 0.001
    mult = trigger:empire_size
    mult = -1
    add = 1.1
    min = 0.1
    max = 1
}
```

Simplified: `max(0.1, min(1.0, 1.1 - 0.001 × empire_size))`

| Empire size | Multiplier | Effect |
|-------------|-----------|--------|
| ≤ 100 | 1.0 (max) | Full speed |
| 500 | 0.6 | 60% speed |
| 1000 | 0.1 (floor) | Minimum speed |
| 1001–∞ | 0.1 (floor) | Minimum speed |

**The threshold where improvement starts:** empire_size < **1100** (any value below 1100 gives multiplier > 0.1).

Growing Pains monthly progress formula (`common/situations/12_biogenesis_situations.txt`):
```pdx
monthly_progress = {
    add = 1
    modifier = { add = 2; current_situation_approach = behemoth_finale_approach_digestion }
    modifier = { add = -0.75; current_situation_approach = behemoth_finale_approach_brawn }
    modifier = { mult = value:growth_factor }
    modifier = { mult = owner.value:negative_empire_size_percent }   ← THE BLOCKER
    modifier = { owner = { is_wilderness_empire = yes }; add = 1 }
}
```

With `negative_empire_size_percent = 0.1` (empire size > 1000), monthly progress = base × growth_factor × 0.1.

---

## 4. Modifier Types Reference

| Modifier key | What it reduces | Effect on empire size number |
|---|---|---|
| `species_empire_size_mult` | Per-pop contribution (multiplicative, before country mult) | Reduces raw empire size from pops |
| `empire_size_pops_mult` | Total empire size from pops (country-wide) | Reduces empire size |
| `empire_size_districts_mult` | Total empire size from districts | Reduces empire size |
| `empire_size_systems_mult` | Total empire size from systems | Reduces empire size |
| `empire_size_colonies_mult` | Total empire size from colonies | Reduces empire size |
| `empire_size_mult` | Total empire size (global, applied last) | Reduces empire size |
| `empire_size_penalty_mult` | Cost PENALTY from empire size (tech/tradition costs) | Does NOT reduce empire size number |
| `planetary_ascension_effect_mult` | Strength of per-tier ascension reduction | Amplifies the -5%/tier planet reduction |

`empire_size_penalty_mult` was the source of confusion in the Chimeral Consciousness authority — it's a separate modifier that only affects how costly empire size is, not the raw empire size value itself.

---

## 5. All Known Modifier Sources

### 5.1 Traditions

Source: `common/traditions/*.txt`

| Tradition key | Modifier type | Value | Notes |
|---|---|---|---|
| `tr_domination_finish` | `pops` | -0.05 | |
| `tr_domination_federations_finish` | `pops` | -0.05 | Federations DLC swap of above |
| `tr_domination_federations_wilderness_finish` | `districts` | -0.05 | Wilderness+Federations swap |
| `tr_expansion_courier_network` | `systems` | -0.15 | |
| `tr_expansion_courier_network` | `colonies` | -0.15 | Same tradition, two modifiers |
| `tr_statecraft_finish` | `total` | -0.05 | Global empire_size_mult |
| `tr_synchronicity_kinship_gestalt` | `pops` | -0.05 | Gestalt-only, "Synchronized Agents" in tooltip |
| `tr_harmony_kinship` | `pops` | -0.05 | |
| `tr_harmony_kinship_shared_burdens` | `pops` | -0.05 | Shared Burdens civic swap |
| `tr_cybernetics_synaptic_sub_processing` | `districts` | -0.15 | Cybernetics tradition tree |
| `tr_nanotech_finish` | `colonies` | -0.50 | Nanotech tradition tree |
| `tr_virtuality_2` | `pops` | -0.10 | |
| `tr_virtuality_2` | `colonies` | +1.00 | Note: INCREASES colonies empire size! |

**Ascension effect traditions** (give `planetary_ascension_effect_mult`, NOT empire_size_*_mult):

| Tradition key | Value | Notes |
|---|---|---|
| `tr_synchronicity_finish` | +0.25 | Gestalt Synchronicity finisher |
| `tr_synchronicity_machine_finish` | +0.25 | Machine gestalt swap |
| `tr_harmony_finish` | +0.25 | Regular Harmony finisher |
| `tr_harmony_federations_finish` | +0.25 | Federations DLC swap |

### 5.2 Technologies

Source: `common/technology/00_soc_tech.txt`, `00_first_contact_tech.txt`

| Tech key | Modifier type | Value | Notes |
|---|---|---|---|
| `tech_psionic_theory` | `pops` | -0.05 | Social tech |
| `tech_lost_building_methods` | `districts` | -0.30 | First Contact DLC |

### 5.3 Ascension Perks

Source: `common/ascension_perks/00_ascension_perks.txt`

| Perk key | Modifier type | Value | Notes |
|---|---|---|---|
| `ap_imperial_prerogative` | `colonies` | -0.25 | Confirmed 4.3 value. Was -0.50 in earlier versions! |
| `ap_interstellar_dominion` | `systems` | -0.25 | |

### 5.4 Governor Skill

Source: `common/static_modifiers/00_static_modifiers.txt`

**Implemented in script.** Applied as per-pop `species_empire_size_mult` on each governed planet.

| Modifier | Rate | Applied when |
|----------|------|-------------|
| `skill_X_planet_governor` | `-0.02 × skill` per pop | Planet is the sector capital (direct governor) |
| `skill_X_sector_governor` | `-0.01 × skill` per pop | Planet is in sector but not capital |

All governor classes (official, commander, scientist) provide this rate. They do NOT stack — each planet gets ONE rate based on its relationship to the governor.

Effective skill = `level + bonus_skill_level` (from `leaders=` section).

**Implementation:** The script builds a planet→system→sector→governor chain across passes 3, 6, 7, and 8 to determine each planet's governor and rate. For the q2 save: 26 of 44 planets have governor coverage, reducing pops by ~94 points.

### 5.5 Planet Ascension Tiers

Source: `common/planet_classes/` (designation modifiers)

**Implemented in script.** Each planet has an `ascension_tier` (0-5). Per tier: `-5%` to pops, districts, AND colony empire size from that planet. No effect on systems.

Modified by `planetary_ascension_effect_mult` (additive from traditions/civics):
```
ascension_factor = 1 - tier × 0.05 × (1 + effect_mult)
```

Example: Tier 5 with +0.25 effect_mult = `1 - 5 × 0.05 × 1.25 = 0.6875` → **-31.2%** reduction.

**Ascension effect civics** (give `planetary_ascension_effect_mult`):

| Civic key | Value |
|---|---|
| `civic_ascensionists` | +0.25 |
| `civic_hive_ascensionists` | +0.25 |
| `civic_machine_ascensionists` | +0.25 |
| `civic_corporate_ascensionists` | +0.25 |

### 5.6 Species Traits

Source: `common/traits/04_species_traits.txt`, `02_species_traits_basic_characteristics.txt`

These give `species_empire_size_mult` at the species level (per pop):

| Trait | Value |
|-------|-------|
| `trait_docile` | -0.10 |
| `trait_unruly` | +0.10 |
| `trait_cave_dweller` | +0.10 |
| `trait_robot_cave_dweller` | +0.10 |

Species 609 (country 0's main species) has none of these — its `species_empire_size_mult` is entirely from the evopred fix mod.

### 5.7 The EvoPred Fix Modifier

Source (our mod): `chimeral_consciousness_fix/common/inline_scripts/pop_categories/social_classes_triggered_modifiers_no_happiness.txt`

```pdx
triggered_pop_group_modifier = {
    potential = {
        exists = owner
        owner = {
            has_origin = origin_evolutionary_predators
            is_mutation_authority = yes    # = has_country_flag = bio_mutation
        }
        species = {
            is_variable_set = species_traits_evopred_count
        }
    }
    key = origin_evolutionary_predators
    species_empire_size_mult = -0.01
    mult = species.species_traits_evopred_count
}
```

Effect: `species_empire_size_mult = -0.01 × species_traits_evopred_count` applied to all pops whose species has the variable set and whose owner is an EvoPred + Mutation empire.

For species 609 with 38 traits: `species_empire_size_mult = -0.38`.

### 5.8 Authority Modifiers

Country 0's authority (`auth_bio_hive_mind_evopred` advanced swap):
- `empire_size_penalty_mult = -0.20` — COST PENALTY only, does NOT reduce empire size
- `pop_cat_purge_bonus_workforce_mult = 0.5`

Base `auth_hive_mind` (replaced by the swap via `inherit_effects = no`):
- `empire_size_penalty_mult = -0.25` — also cost penalty only

**Neither reduces actual empire size.** This was a source of confusion; `empire_size_penalty_mult` is intentional (secondary benefit), not a bug.

---

## 6. Country 0 Active Modifiers (q2 save)

### empire_size_pops_mult total: -15%
| Source | Value |
|--------|-------|
| tr_domination_finish | -5.0% |
| tr_synchronicity_kinship_gestalt | -5.0% |
| tech_psionic_theory | -5.0% |
| **Total** | **-15.0%** |

### empire_size_districts_mult total: 0%
| Source | Value |
|--------|-------|
| (none found) | 0% |

### empire_size_systems_mult total: -15%
| Source | Value |
|--------|-------|
| tr_expansion_courier_network | -15.0% |

### empire_size_colonies_mult total: -40%
| Source | Value |
|--------|-------|
| tr_expansion_courier_network | -15.0% |
| ap_imperial_prerogative | -25.0% |

### empire_size_mult total: -5%
| Source | Value |
|--------|-------|
| tr_statecraft_finish | -5.0% |

### planetary_ascension_effect_mult total: +25%
| Source | Value |
|--------|-------|
| tr_synchronicity_finish | +25.0% |

### species_empire_size_mult (per species, from mod + traits)
| Species | Evopred count | Trait mult | Net mult |
|---------|--------------|-----------|----------|
| 609 (Prime, 166826 pops) | 38 | 0 | **-38.0%** |
| 16777235 (Sejethari, 3500 pops) | 6 | 0 | -6.0% |
| 16777233 (Keerim, 1123 pops) | 8 | 0 | -8.0% |
| 16777229 (Cydran, 898 pops) | 6 | 0 | -6.0% |
| 28 (Thorquell, 652 pops) | 7 | 0 | -7.0% |

---

## 7. Component Breakdown Verification (q2 save)

### Game tooltip vs script (with fix mod ON):

| Component | Game | Script | Diff | Diff % |
|-----------|------|--------|------|--------|
| Pops | 341.1 | 339.0 | -2.1 | -0.6% |
| Districts | 358.8 | 358.8 | 0.0 | exact |
| Systems | 367.2 | 367.2 | 0.0 | exact |
| Colonies | 492.0 | 492.0 | 0.0 | exact |
| **Subtotal** | **1559.1** | **1557.0** | -2.1 | -0.1% |
| After ×0.95 | **1482** | **1479** | -2.8 | -0.2% |

### What resolved each component gap

| Component | v0.1 Gap | Fix | v0.2 Gap |
|-----------|----------|-----|----------|
| Pops (+123) | Governor effects + ascension tier not applied | Per-planet governor skill mult + ascension factor | -2.1 |
| Districts (+29.7) | Ascension tier not applied | Per-planet ascension factor | 0.0 |
| Systems (+28.9) | graphical_culture matched other countries; orbital rings/DSCs counted | Fleet ownership chain + starbase level filtering | 0.0 |
| Colonies (+36) | Ascension tier not applied | Per-planet ascension factor | 0.0 |

---

## 8. Remaining Discrepancies

### 8.1 Pops: -2.1 points undercount

The remaining -0.6% gap in pops is small and likely from one or more of:

- **Councilor skill effects** — council positions provide per-skill modifiers (e.g., Machine Intelligence ruler: -3%/level pops). Not yet parsed.
- **Governor traits** — e.g., `leader_trait_urbanist` gives -50% districts on governed planet (partially catalogued in `GOVERNOR_TRAIT_MODIFIERS` but not applied).
- **Dynamic event modifiers** — biogenesis event chain modifiers (e.g., `optimized_workforce`).
- **Federation perks** — `ascension_shared_1` gives +0.20 `planetary_ascension_effect_mult`.
- **Sector governor coverage gap** — 15 of 44 planets unmapped to sectors (likely uncolonized system mapping issues). These planets get no governor reduction, which may slightly overcount rather than undercount.

### 8.2 Systems: resolved

Previously +28.9 overcount. Fixed by:
1. **Fleet-based ownership** (ship→fleet→owned_fleets chain) instead of graphical_culture matching — eliminated 26 false matches from other countries sharing "biogenesis_01" culture.
2. **Starbase level filtering** — excluded 8 orbital rings and deep space citadels via `SYSTEM_STARBASE_LEVELS`.

### 8.3 Districts and Colonies: resolved

Both resolved by planet ascension tier implementation. The "unknown -7.6% districts source" and "unknown -6.8% colonies source" from v0.1 were both explained by ascension tier reductions on the 10 planets at tier 3-5.

---

## 9. What the Chimeral Consciousness Bug Caused

Without the fix mod:
- pops_component = 735.25 (vs 339.0 with fix + governors + ascension)
- systems = same, districts = same, colonies = same
- Total empire size ~1704

With the fix mod (where we are now):
- pops_component = 339.0
- Total empire size ~1479

Despite this improvement:
- `negative_empire_size_percent` = 0.1 for BOTH 1704 and 1479 (floor at empire_size >= 1000)
- Growing Pains progress rate is the same (1.965/month) because the floor is at the same value
- Need empire_size < 1000 for any visible improvement; current gap is ~479 points
