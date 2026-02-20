# Changelog

## v1.1 — Pop Category Filtering & .sav Support (2026-02-20)

Improved accuracy from **-0.2%** to **-0.1%** and added direct `.sav` file support.

### New Features

- **Direct .sav file support**: Accepts `.sav` ZIP archives directly — no manual unzipping required. Also accepts folders with an unzipped `gamestate` file as before.
- **Pop category filtering**: New pass reads `pop_groups=` to determine each pop's category (drone, purge, assimilation, etc.). Triggered modifiers like EvoPred `species_empire_size_mult` are only applied to pops in eligible categories. Pops in purge/assimilation/criminal/etc. categories are correctly excluded. Static species trait modifiers (`trait_docile`, `trait_unruly`) still apply to all pops.
- **Detailed governor reporting**: Per-governor skill breakdown showing level + bonus = effective skill, planet coverage type (sector capital / sector / frontier), and planets without governor coverage.
- **Full sector mapping**: All owned planets are now mapped including frontier systems (not assigned to any sector). Previously 15/44 planets were unreported.

### Architecture Changes

- **9-pass parser** (was 8): added `pop_groups=` pass for pop category data
- **Split species multipliers**: `calculate_active_modifiers` returns both `species_mults` (full: trait + evopred) and `species_base_mults` (trait-only) so `calculate_breakdown` can apply the correct mult per pop category
- **`main()` refactored** into `main()` (input handling + cleanup) and `_run_analysis()` (9-pass analysis) to support temp directory cleanup for .sav extraction
- **Leader data enriched**: `extract_leader_data()` returns separate `level` and `bonus` fields alongside the `skill` sum

### New SETTINGS

| Constant | Description |
|----------|-------------|
| `POP_CATEGORIES_NO_TRIGGERED_MODIFIERS` | Pop categories excluded from triggered modifiers (purge, assimilation, criminal, etc.) |

### Results (q2 save)

| Component | v0.2 | v1.1 | Game | v1.1 Error |
|-----------|------|------|------|------------|
| Pops | 339.0 | 340.7 | 341.1 | -0.1% |
| Districts | 358.8 | 358.8 | 358.8 | exact |
| Systems | 367.2 | 367.2 | 367.2 | exact |
| Colonies | 492.0 | 492.0 | 492.0 | exact |
| **Total** | **1479** | **1481** | **1482** | **-0.1%** |

---

## v0.2 — Per-Planet Accuracy Update (2026-02-19)

Reduced discrepancy from **+13.9%** to **-0.2%** vs game-reported empire size (1479 calculated vs 1482 game-reported).

### New Mechanics Implemented

- **Planet ascension tiers**: -5% per tier × (1 + `planetary_ascension_effect_mult`) applied per-planet to pops, districts, and colony size. Sources: Harmony/Synchronicity finishers (+25%), Ascensionists civic (+25%).
- **Governor skill effects**: Per-planet `species_empire_size_mult` from governor skill level. Planet governor (sector capital): -2%/level. Sector governor (other planets): -1%/level. Requires parsing leaders, sectors, and galactic objects to build the planet→sector→governor chain.
- **Fleet-based system ownership**: Replaced the `graphical_culture` heuristic (which matched all countries sharing the same culture) with a ship→fleet→`owned_fleets` ownership chain. Eliminated 26-system overcount.
- **Starbase level filtering**: Only count `SYSTEM_STARBASE_LEVELS` (outpost through citadel), excluding orbital rings and deep space citadels. Eliminated 8-system overcount.

### Architecture Changes

- **8-pass parser** (was 5): species → country → planets → districts → systems → leaders → sectors → galactic objects
- **Per-planet calculation**: Ascension tier and governor modifiers are applied per-planet before summing, then country-wide multipliers are applied to the sum. Previously all calculation was global.
- **New extraction functions**: `extract_leader_data()`, `extract_sector_data()`, `build_planet_to_sector_map()`
- **Enhanced extractions**: `extract_country_data()` now parses civics and `owned_fleets`. `extract_planet_data()` now captures `ascension_tier` and `governor` fields.

### Results (q2 save)

| Component | v0.1 | v0.2 | Game | v0.2 Error |
|-----------|------|------|------|------------|
| Pops | 464.1 | 339.0 | 341.1 | -0.6% |
| Districts | 388.5 | 358.8 | 358.8 | exact |
| Systems | 396.1 | 367.2 | 367.2 | exact |
| Colonies | 528.0 | 492.0 | 492.0 | exact |
| **Total** | **1688** | **1479** | **1482** | **-0.2%** |

### New SETTINGS

| Constant | Value | Description |
|----------|-------|-------------|
| `ASCENSION_TIER_BASE_REDUCTION` | `0.05` | -5% per ascension tier |
| `ASCENSION_EFFECT_TRADITIONS` | dict | Traditions giving `planetary_ascension_effect_mult` |
| `ASCENSION_EFFECT_CIVICS` | dict | Civics giving `planetary_ascension_effect_mult` |
| `GOVERNOR_PLANET_RATE` | `-0.02` | Per-skill empire size mult for planet governors |
| `GOVERNOR_SECTOR_RATE` | `-0.01` | Per-skill empire size mult for sector governors |
| `SYSTEM_STARBASE_LEVELS` | set | Starbase levels that count as systems |
| `GOVERNOR_TRAIT_MODIFIERS` | dict | Per-trait governor modifiers (placeholder) |

---

## v0.1 — Initial Release (2026-02-19)

First working version. 5-pass parser achieving ~86% accuracy.

- Parses species traits, country data, planets, districts, and systems
- Applies species_empire_size_mult (including EvoPred), empire_size_pops/districts/systems/colonies_mult, and global empire_size_mult
- Configurable SETTINGS block for traditions, technologies, ascension perks, and edict modifiers
