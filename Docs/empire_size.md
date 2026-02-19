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

```python
# Step 1: per-pop contributions (multiplicative with species_empire_size_mult)
pops_raw = Σ over all pop groups:
    pop_count × 0.005 × (1 + species_empire_size_mult_for_this_species)

# Step 2: country-wide pops multiplier (additive from all sources)
pops_component = pops_raw × (1 + total_empire_size_pops_mult)

# Step 3: district component
districts_component = total_district_levels × 0.5 × (1 + total_empire_size_districts_mult)

# Step 4: systems component
systems_component = owned_systems × 1.0 × (1 + total_empire_size_systems_mult)

# Step 5: colonies component
colonies_component = owned_colonies × 20.0 × (1 + total_empire_size_colonies_mult)

# Step 6: global multiplier (applied to sum of all components)
subtotal = pops_component + districts_component + systems_component + colonies_component
empire_size = subtotal × (1 + total_empire_size_mult)
```

**Modifier stacking:** All modifiers of the same type (e.g., all `empire_size_pops_mult`) add together, then `(1 + sum)` is the factor.

**`species_empire_size_mult` vs `empire_size_pops_mult`:**
- `species_empire_size_mult` is applied PER POP based on that pop's species — it modifies the base contribution of each individual pop.
- `empire_size_pops_mult` is a COUNTRY-WIDE factor applied to the sum of all raw pop contributions.
- These are multiplicative with each other (not additive).

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
| `species_empire_size_mult` | Per-pop contribution (multiplicative, before country mult) | ✅ Reduces raw empire size from pops |
| `empire_size_pops_mult` | Total empire size from pops (country-wide) | ✅ Reduces empire size |
| `empire_size_districts_mult` | Total empire size from districts | ✅ Reduces empire size |
| `empire_size_systems_mult` | Total empire size from systems | ✅ Reduces empire size |
| `empire_size_colonies_mult` | Total empire size from colonies | ✅ Reduces empire size |
| `empire_size_mult` | Total empire size (global, applied last) | ✅ Reduces empire size |
| `empire_size_penalty_mult` | Cost PENALTY from empire size (tech/tradition costs) | ❌ Does NOT reduce empire size number |

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

### 5.2 Technologies

Source: `common/technology/00_soc_tech.txt`, `00_first_contact_tech.txt`

| Tech key | Modifier type | Value | Notes |
|---|---|---|---|
| `tech_psionic_theory` | `pops` | -0.05 | Social tech |
| `tech_lost_building_methods` | `districts` | -0.30 | First Contact DLC |

**Note:** `tech_psionic_theory` gives `-5% empire_size_pops_mult`. Despite being called "Psionic Theory" (a research tech), it has this empire size effect. The player has it researched — confirmed in `tech_status=` block.

### 5.3 Ascension Perks

Source: `common/ascension_perks/00_ascension_perks.txt`

| Perk key | Modifier type | Value | Notes |
|---|---|---|---|
| `ap_imperial_prerogative` | `colonies` | -0.25 | Confirmed 4.3 value. Was -0.50 in earlier versions! |
| `ap_interstellar_dominion` | `systems` | -0.25 | |

**Country 0's active perks:** `ap_imperial_prerogative`, `ap_enigmatic_engineering`, `ap_engineered_evolution`, `ap_behemoths`, `ap_galactic_force_projection`, `ap_galactic_wonders_utopia_and_megacorp`, `ap_master_builders`

### 5.4 Governor Skill (NOT yet implemented in script)

Source: `common/static_modifiers/00_static_modifiers.txt`

```pdx
skill_official_planet_governor = {
    species_empire_size_mult = -0.02   # per skill level, PER PLANET
}
skill_official_sector_governor = {
    species_empire_size_mult = -0.01   # per skill level, PER SECTOR
}
```

This is applied as `species_empire_size_mult` (per-pop), meaning each pop on a governed planet has their empire size contribution reduced by `governor_skill × 0.02`.

A level-8 planet governor = `-0.16 species_empire_size_mult` for all pops on that planet. With 44 colonized planets and high-level governors, total effect could be `-17%` to `-22%` on pops component.

**This is the largest unresolved source of discrepancy** (+123 points overcount in pops).

To implement: parse `leaders=` section for planet governor leaders, read their skill levels, weight by pops on each governed planet.

### 5.5 Species Traits

Source: `common/traits/04_species_traits.txt`, `02_species_traits_basic_characteristics.txt`

These give `species_empire_size_mult` at the species level (per pop):

| Trait | Value |
|-------|-------|
| `trait_docile` | -0.10 |
| `trait_unruly` | +0.10 |
| `trait_cave_dweller` | +0.10 |
| `trait_robot_cave_dweller` | +0.10 |

Species 609 (country 0's main species) has none of these — its `species_empire_size_mult` is entirely from the evopred fix mod.

### 5.6 The EvoPred Fix Modifier

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

Effect: `species_empire_size_mult = -0.01 × species_traits_evopred_count` applied to all pops whose species has the `species_traits_evopred_count` variable set and whose owner is an EvoPred + Mutation empire.

For species 609 with 38 traits: `species_empire_size_mult = -0.38`.

### 5.7 Authority Modifiers

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

### species_empire_size_mult (per species, from mod + traits)
| Species | Evopred count | Trait mult | Net mult |
|---------|--------------|-----------|----------|
| 609 (Prime, 166826 pops) | 38 | 0 | **-38.0%** |
| 16777235 (Sejethari, 3500 pops) | 6 | 0 | -6.0% |
| 16777233 (Keerim, 1123 pops) | 8 | 0 | -8.0% |
| 16777229 (Cydran, 898 pops) | 6 | 0 | -6.0% |
| 28 (Thorquell, 652 pops) | 7 | 0 | -7.0% |

The alien pops (species 16777235, 16777233, 16777229, 28) are being purged. They have `species_traits_evopred_count` set because they likely come from another EvoPred empire in the galaxy (the variable was set when their empire processed them). With our fix mod, these also benefit from the reduction.

---

## 7. Component Breakdown Verification (q2 save)

### Game tooltip (with fix mod ON):

| Component | Game | Script | Diff | Diff % |
|-----------|------|--------|------|--------|
| Pops | 341.1 | 464.1 | +123.0 | +36.1% |
| Districts | 358.8 | 388.5 | +29.7 | +8.3% |
| Systems | 367.2 | 396.1 | +28.9 | +7.9% |
| Colonies | 492.0 | 528.0 | +36.0 | +7.3% |
| **Subtotal** | **1559.1** | **1776.7** | +217.6 | +13.9% |
| After ×0.95 | **1481.1** | **1688.0** | +206.9 | +13.9% |

### What game tooltip shows for pops modifiers

The game's empire size tooltip (from in-game UI) only shows:
- Domination Traditions finished: -5%
- Synchronized Agents: -5%
- Psionic Theory: -5%

But the calculated pops component (341.1) implies an effective total multiplier of ~-37.5% on raw pops — far more than the -15% visible in the tooltip. The game tooltip likely doesn't show governor effects as they're calculated differently (per-planet, not as country modifiers).

### Mod effect verification

With mod OFF (EVOPRED_PER_TRAIT_MULT = 0.0):
- pops_raw = 864.995 (all species mult = 0)
- pops_component = 864.995 × 0.85 = 735.25
- Game-reported pops component = 575.4

With mod ON:
- pops_raw = 546.03 (species 609 at -38%, others at their evopred mult)
- pops_component = 546.03 × 0.85 = 464.12
- Game-reported pops component = 341.1

Difference in pops_raw: 864.995 - 546.03 = **318.97** (effect of mod on raw pops)
Difference in pops_component: 735.25 - 464.12 = **271.13** (after -15% pops_mult)
Difference in final empire size (× 0.95): **257.6**

This confirms the mod works — removing 38% from 96.6% of pops.

---

## 8. Unresolved Discrepancies

### 8.1 Pops: +123 points overcount

**Cause:** Governor `species_empire_size_mult` not implemented.

**Calculation:** The pops_component gap of 123 / 464 = 26.5% overcount. Working backwards:
- Without mod (game=575.4 vs script=735.25): gap/script = 159.85/735.25 = 21.7%
- With mod (game=341.1 vs script=464.12): gap/script = 123/464 = 26.5%

The governor effect is applied PER POP on each planet, so it interacts multiplicatively with `species_empire_size_mult`. That's why the percentage differs between the two scenarios (governor's absolute contribution is the same but the fraction of the script's output varies).

**To fix:** Parse `leaders=` section, find each planet's governor, apply `-0.02 × skill_level` as `species_empire_size_mult` to all pops on that planet.

### 8.2 Districts: +29.7 points overcount

**Cause:** Unknown source of `-7.64% empire_size_districts_mult`.

Working backwards: 358.8 / (777 × 0.5) = 0.9236 → -7.64% on districts base.

**Possible sources to investigate:**
- Planet-level building modifiers (some buildings might reduce district empire size contribution)
- Edicts (country 0 has `crystal_focus`, `fuel_gases`, `motes_kinetic`, `living_metal_construction`, `motes_armor` — check if any affect districts)
- `tr_domination_imperious_architecture` for Hive Minds activates as `tr_domination_synaptic_extensions` — check its inline script in capital buildings: `common/inline_scripts/buildings/on_all_capital_buildings.txt`

### 8.3 Systems: +28.9 points overcount

**Cause:** Script counts 466 starbases (via ship culture), game shows 432 systems.

Difference: 34 orbital platforms. Each contributes `1.0 × (1 - 0.15) × (1 - 0.05) = 0.807` to empire size.
34 × 0.807 = 27.4 ≈ 28.9 points.

**To fix:** Identify orbital platforms and exclude them. Hard to do programmatically since orbital IDs in the `orbitals={}` block use entity encoding. Options:
1. Apply a correction factor (×432/466 ≈ ×0.927)
2. Cross-reference orbital IDs by scanning all `orbitals={}` blocks and collecting non-null entries

### 8.4 Colonies: +36 points overcount

**Cause:** Unknown source of approximately `-6.82% empire_size_colonies_mult`.

Working backwards: 492 / (44 × 20 × 0.85 × 0.75) = 492/561 = 0.877... but that doesn't work out simply. Actually:
44 × 20 = 880, script gives 880 × 0.60 = 528 (using -40% = -0.15 - 0.25). Game gives 492. 492/880 = 0.5591. 528/880 = 0.60. So there's another -4.1% additive reduction.

**Possible sources:**
- `ap_interstellar_dominion` gives `empire_size_systems_mult = -0.25` — already checked, not colonies
- There might be an edict or building providing additional colony reduction
- Could be a different value for `ap_imperial_prerogative` (maybe it's actually -0.30 not -0.25 in 4.3?)

---

## 9. What the Chimeral Consciousness Bug Caused

Without the fix mod:
- pops_component = 735.25 (vs 464.12 with fix)
- systems = same, districts = same, colonies = same
- Total empire size ≈ 1704

With the fix mod (where we are now):
- pops_component = 464.12
- Total empire size ≈ 1482

The -38% reduction on species 609 (96.6% of pops) saves 271 points in pops_component before the global -5% multiplier = 257 points in final empire size.

Despite this improvement:
- `negative_empire_size_percent` = 0.1 for BOTH 1704 and 1482 (floor at empire_size ≥ 1000)
- Growing Pains progress rate is the same (1.965/month) because the floor is at the same value
- Need empire_size < 1000 for any visible improvement; current gap is ~481 points
