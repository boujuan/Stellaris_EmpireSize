# Changelog

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

### Results (q2 save, mod ON)

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

### Remaining Gap

The -0.2% residual (-2.82 points) in pops is likely from councilor skill effects or minor modifiers not yet catalogued.

---

## v0.1 — Initial Release (2026-02-19)

First working version. 5-pass parser achieving ~86% accuracy.

- Parses species traits, country data, planets, districts, and systems
- Applies species_empire_size_mult (including EvoPred fix mod), empire_size_pops/districts/systems/colonies_mult, and global empire_size_mult
- Configurable SETTINGS block for traditions, technologies, ascension perks, and edict modifiers
- Reports Growing Pains situation progress multiplier
