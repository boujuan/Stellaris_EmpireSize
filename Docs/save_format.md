# Stellaris Save Game Format Reference

Complete reference for parsing `gamestate` (the main file inside `.sav` archives).
All line numbers are approximate for `saves/q2/gamestate` (65MB, ~4.6M lines).

---

## 1. File Overview

A Stellaris save is a ZIP archive (`*.sav`). Unzip to get:
- `gamestate` — the main text file (~65MB, ~4.6M lines)
- `meta` — small metadata file (version, date, dlcs, flag, meta_planets, meta_fleets)

The `gamestate` file uses the **Clausewitz PDX text format** — a custom key-value format with nested blocks.

---

## 2. PDX Format Syntax

### 2.1 Basic rules

```pdx
key=value                    # simple assignment (int, float, string)
key="string value"           # quoted string
key={                        # block start (content on following lines)
    subkey=value
    subkey2="string"
}
key={ a b c }                # inline integer array
key={ "a" "b" "c" }         # inline string array
key=                         # pending block: { follows on next line
{
    content
}
# comment                    # ignored
```

Keys can repeat within the same block (common for arrays like `tradition` or `planet`).
All indentation uses **TABs** (1 tab per nesting level).

### 2.2 Depth tracking

The script tracks "depth" = number of currently open `{` blocks. The rule used:

1. Count `{` and `}` in each line (skipping chars inside `"..."` strings).
2. **Closing `}` decrements depth BEFORE the line is yielded.**
3. **Opening `{` increments depth AFTER the line is yielded.**

This means:
- A `key=` line at depth D opens a block that starts at depth D+1 on the NEXT line.
- A `}` line is yielded at the depth it CLOSES TO (not from).
- An inline `key={ content }` line: the `key=` is at depth D, content is also at depth D (all on one line — braces cancel out).

### 2.3 Tricky cases

**Pending block:** `key=` on one line, `{` on the next:
```
traits=       ← depth 2, opens=0, yields (2, "traits="), depth stays 2
{             ← depth 2, opens=1, yields (2, "{"), depth THEN becomes 3
    trait="…" ← depth 3
}             ← depth 3→2 (closes=1, depth becomes 2 BEFORE yield), yields (2, "}")
```

**Inline array:** `ships=\n{\n\t0 \n}`:
- `ships=` at D2, then `{` at D2 (opens to D3), then `0 ` at D3 with ship IDs.

**Entity ID encoding:** Some IDs use high-bit type prefixes:
- `16777216 = 2^24 = 0x1000000` is used as a "type prefix"
- `16777241 = 16777216 + 25` might encode "entity type 1, ID 25" (e.g. planet 25)
- These appear in `owner=` fields within fleet entries — they are NOT country IDs
- Country IDs are small integers: `0` = player, `1`, `2`, etc.
- Large numbers in `controlled_planets` like `16777238` are planet or system entities

---

## 3. Top-Level Sections

All sections at depth 0 in `gamestate` (q2 approximate line numbers):

| Section | Line | Size | Contents |
|---------|------|------|----------|
| `required_dlcs=` | 5 | small | DLC list |
| `player=` | 37 | small | Player country reference |
| `species_db=` | **50** | ~30K lines | All species definitions |
| `spy_networks=` | 30311 | medium | Spy network data |
| `espionage_assets=` | 47106 | medium | Espionage asset data |
| `vivarium_critters=` | 48356 | small | |
| `exhibits=` | 50279 | small | Grand Archive exhibits |
| `focus_cards=` | 51095 | small | |
| `patron_relations=` | 59108 | medium | Shroud patron relations |
| `nebula=` (×9) | 64807+ | small | Nebula definitions |
| `pop=` | 64989 | small | Pop objects (individual pops) |
| `pop_groups=` | **64992** | ~81K lines | Pop group objects |
| `pop_jobs=` | 146202 | ~154K lines | Pop job objects |
| `galactic_object=` | **299792** | ~70K lines | Star systems |
| `starbase_mgr=` | **370032** | ~14K lines | All starbases |
| `planets=` | **383890** | ~120K lines | All planet objects |
| `astral_rifts=` | 1232516 | ~15K lines | Astral rift data |
| `psionic_auras=` | 1247753 | tiny | |
| `country=` | **1247753** | ~972K lines | All country data |
| `dead_*=` (various) | 2219786+ | small | Dead/removed entities |
| `construction=` | 2221177 | ~186K lines | Construction queues |
| `federation=` | 2407121 | small | Federation data |
| `truce=` | 2407281 | small | |
| `trade_deal=` | 2407424 | small | |
| `leaders=` | **2407429** | ~52K lines | All leader data |
| `ships=` | **2459386** | ~732K lines | All ship objects |
| `fleet=` | **3191312** | ~570K lines | All fleet objects |
| `fleet_template=` | 3760810 | small | |
| `army=` | 3766408 | ~99K lines | Army objects |
| `deposit=` | 3865339 | ~61K lines | Deposit objects |
| `ground_combat=` | 3925936 | tiny | |
| `fired_event_ids=` | 3925963 | small | |
| `war=` | 3934464 | small | |
| `orbital_line=` | 3980594 | small | |
| `message=` | 3980710 | small | Message objects |
| `sectors=` | **4494626** | ~9K lines | Sector data |
| `districts=` | **4503998** | ~96K lines | District objects |
| `resolution=` | 4515... | small | |
| `situations=` | **4596154** | small | Situation objects |
| `council_positions=` | 4599137 | small | |
| `automation_resources=` | 4599883 | tiny | |
| `storms=` | 4599886 | small | |

---

## 4. Species Data (`species_db=`)

**Location:** depth 0 at line 50, content ends before `spy_networks=` at line 30311.

### Structure

```
species_db=           ← depth 0
{                     ← depth 0 (opens to 1)
    609=              ← depth 1 (species ID)
    {                 ← depth 1 (opens to 2)
        base_ref=570425345        ← depth 2
        name_list="HIVE1"         ← depth 2
        name=                     ← depth 2
        {                         ← depth 2 (opens to 3)
            key="Prime"           ← depth 3
            literal=yes           ← depth 3
        }                         ← back to depth 2
        plural=  { ... }          ← depth 2
        adjective= { ... }        ← depth 2
        class="FUN"               ← depth 2
        portrait="fun2"           ← depth 2
        traits=                   ← depth 2
        {                         ← depth 2 (opens to 3)
            trait="trait_organic" ← depth 3
            trait="trait_hive_mind"
            ...
        }                         ← back to depth 2
        home_planet=10            ← depth 2
        variables=                ← depth 2
        {                         ← depth 2 (opens to 3)
            species_traits_evopred_count=38  ← depth 3
        }
        gender=indeterminable     ← depth 2
    }
}
```

### Key fields at depth 2

| Field | Description |
|-------|-------------|
| `base_ref=N` | Parent species ID (subspecies point to their progenitor) |
| `name_list="..."` | Name list key |
| `class="FUN"` | Species class (FUN=fungoid, HUM=humanoid, etc.) |
| `portrait="fun2"` | Portrait key |
| `traits={}` | Block with `trait="trait_key"` entries at depth 3 |
| `variables={}` | Block with `species_traits_evopred_count=N` at depth 3 |
| `home_planet=N` | Home planet ID |
| `gender=` | `indeterminable` / `male` / `female` |

---

## 5. Pop Groups (`pop_groups=`)

**Location:** depth 0 at line 64992.

Pop groups are how Stellaris actually stores populations in 4.x (not individual pops). Each pop_group has a `species=N` and a floating-point `size`.

For empire size calculation, it's easier to use `species_information=` in the planet blocks (see §7) which directly gives `num_pops` per species per planet.

---

## 6. Galactic Objects (`galactic_object=`)

**Location:** depth 0 at line 299792, ends before `starbase_mgr=` at line 370032.

Each galactic object = one star SYSTEM.

### Structure

```
galactic_object=
{
    0=                     ← depth 1 (system ID 0–783)
    {                      ← depth 1 (opens to 2)
        coordinate= { x=… y=… origin=… randomized=yes }  ← depth 2
        type=star          ← depth 2
        name= { key="Despad" }                            ← depth 2
        planet=1569        ← depth 2 (planet ID in this system)
        planet=1570        ← depth 2 (repeating key for each body)
        ...
        star_class="sc_g"  ← depth 2
        hyperlane= { ... } ← depth 2
        sector=5           ← depth 2 (sector ID this system belongs to)
    }
}
```

### Important: No direct owner field

Galactic object entries do NOT have an `owner=country_id` field. System ownership is determined by which country has a starbase there (via `starbase_mgr` fleet-based ownership chain).

### Planet IDs vs system IDs

The IDs in `planet=N` lines inside a galactic_object are planet IDs in the `planets=` section (NOT galactic_object IDs). These are different namespaces.

### Planet→system→sector chain (Pass 8)

The script uses `galactic_object` to build a mapping: for each `planet=N` at depth 2, record which system it's in. Then using `sector=N` at depth 2, map system→sector. Combined with sector data (pass 7), this gives the full chain: planet → system → sector → local_capital → governor.

---

## 7. Planets (`planets=`)

**Location:** depth 0 at line 383890. Contains ALL planet objects (colonized and uncolonized, all countries).

### Structure (depth levels from `planets=`)

```
planets=          ← D0
{                 ← D0 (opens to D1)
    planet=       ← D1 (sub-container key, no data)
    {             ← D1 (opens to D2)
        10=       ← D2 (planet ID — the home planet!)
        {         ← D2 (opens to D3)
            name= { ... }               ← D3
            planet_class="pc_hive"      ← D3
            orbit=85                    ← D3
            planet_size=18              ← D3
            owner=0                     ← D3 (country that owns it)
            original_owner=0            ← D3
            controller=0                ← D3
            pop_groups= { 419431466 1229 2164263088 }  ← D3 (pop_group IDs)
            districts= { 16777853 646 647 16777674 }   ← D3 (district IDs)
            colonize_date="2200.01.01"  ← D3
            num_sapient_pops=9616       ← D3
            ascension_tier=5            ← D3 (0-5, affects empire size)
            governor=16777547           ← D3 (leader ID, only on sector capitals)
            species_information=        ← D3
            {                           ← D3 (opens to D4)
                609=                    ← D4 (species ID)
                {                       ← D4 (opens to D5)
                    num_pops=9616       ← D5
                }
            }
            ...
        }
    }
}
```

### Key fields for empire size (all at depth 3, inside a planet block)

| Field | Type | Description |
|-------|------|-------------|
| `owner=N` | int | Country ID that owns this planet |
| `controller=N` | int | Country controlling it (usually same as owner) |
| `districts={ IDs }` | int array | District instance IDs → look up in `districts=` section for `level=` |
| `species_information={}` | block | `species_id={ num_pops=N }` at D4/D5 |
| `num_sapient_pops=N` | int | Total pops on this planet (sum check) |
| `ascension_tier=N` | int | 0–5, -5% per tier to pops/districts/colony empire size |
| `governor=N` | int | Leader ID of planet governor (only present on sector capitals) |

### District `level` semantics in 4.x

Each district instance has a `level=N` field representing how many of that type are built. Empire size counts `N × 0.5` per district object.

---

## 8. Country Data (`country=`)

**Location:** depth 0 at line 1247753. Contains all countries (player, AI, enclaves, etc.).

### Key fields inside country 0 (all at depth 2)

| Field | Approx line | Notes |
|-------|-------------|-------|
| `name= { key="Pandora" }` | 1247782 | Country name |
| `tech_status= { ... }` | 1247804 | Technology block |
| `empire_size=1482` | ~1253879 | **Game-reported empire size** |
| `num_sapient_pops=172999` | ~1253882 | Total pops (all planets) |
| `graphical_culture="biogenesis_01"` | ~1253884 | Visual culture |
| `government= { civics= { ... } }` | D2/D3/D4 | Government with civics list |
| `traditions= { "tr_..." }` | ~1468570 | String array of active traditions |
| `ascension_perks= { "ap_..." }` | ~1468622 | String array |
| `owned_planets= { 10 517 757 ... }` | ~1468636 | 44 colony planet IDs |
| `controlled_planets= { ... }` | ~1468644 | Large mixed list |
| `edicts= { { edict="key" ... } }` | ~1468656 | Active edicts block |
| `fleets_manager= { owned_fleets= { ... } }` | D2/D3/D4/D5 | Fleet ownership |

### `fleets_manager` format (for system ownership)

```
fleets_manager=
{
    owned_fleets=
    {
        {
            fleet=0            ← D5 (fleet ID)
        }
        {
            fleet=4            ← D5 (fleet ID)
        }
        ...
    }
}
```

The `owned_fleets` list contains fleet IDs at D5. These are used in pass 5 to verify system ownership: starbase → station ship → ship's fleet → check against owned_fleets.

### `government` and civics format

```
government=
{
    type="auth_bio_hive_mind_evopred"   ← D3
    civics=                              ← D3
    {                                    ← D3 (opens to D4)
        "civic_hive_natural_neural_network"  ← D4
        "civic_hive_ascensionists"           ← D4
        "civic_hive_divided_attention"       ← D4
    }
}
```

Civics are quoted strings at D4 inside the `civics={}` block.

### `tech_status=` format

Two formats:
1. Normal: `technology="tech_key"` + `level=N` on consecutive lines at D3
2. Repeatable: `"tech_key"="level"` single-line at D3

---

## 9. Starbases (`starbase_mgr=`)

**Location:** depth 0 at line 370032, ends before `planets=` at line 383890.

**Total:** 724 starbases across all countries (as of q2 save).

### Structure

```
starbase_mgr=
{
    starbases=         ← D1 (only sub-key)
    {
        0=             ← D2 (starbase ID)
        {
            level="starbase_level_citadel"    ← D3
            station=0                          ← D3 ← SHIP ID (not fleet ID)
            modules= { ... }                  ← D3
            buildings= { ... }                ← D3
            orbitals= { ... }                 ← D3
            ...
        }
    }
}
```

### System counting via fleet ownership (implemented)

The script uses a fleet-based ownership chain:
1. Capture `station=N` (ship ID) and `level="..."` per starbase
2. Look up ship N → get its `fleet=M`
3. Check if fleet M is in the country's `owned_fleets`
4. Only count if `level` is in `SYSTEM_STARBASE_LEVELS`

This correctly excludes:
- **Orbital rings** (`starbase_level_orbital_ring`) — 4 in q2 save
- **Deep space citadels** (`starbase_level_deep_space_citadel`) — 4 in q2 save
- **Other countries' starbases** — eliminated by fleet ownership check

### SYSTEM_STARBASE_LEVELS

```python
{
    'starbase_level_outpost',
    'starbase_level_starport',
    'starbase_level_starhold',
    'starbase_level_starfortress',
    'starbase_level_citadel',
}
```

---

## 10. Ships (`ships=`)

**Location:** depth 0 at line 2459386.

### Structure

```
ships=
{
    0=             ← D1 (ship ID)
    {
        fleet=0                         ← D2 (fleet this ship belongs to)
        graphical_culture="biogenesis_01"  ← D2
        ...
    }
}
```

### Fleet-based ownership (replaces graphical_culture heuristic)

The v0.1 approach used `graphical_culture` to match ships to countries. This failed because multiple countries can share the same culture (e.g., "biogenesis_01" matched 1358 ships across multiple countries).

The v0.2 approach uses `fleet=N` per ship, then checks if that fleet is in the country's `owned_fleets`. This gives exact ownership.

---

## 11. Fleets (`fleet=`)

**Location:** depth 0 at line 3191312.

Fleet IDs are NOT sequential — they use type-prefix encoding.

### Fleet ownership

Fleet entries have an `owner=` field, but it is NOT a country ID (it's an entity-encoded ID). **Do NOT use fleet `owner=` to determine which country owns a starbase.** Use the country's `fleets_manager → owned_fleets` list instead.

---

## 12. Districts (`districts=`)

**Location:** depth 0 at line 4503998 (NOT inside planets= — it's a separate top-level section).

### Structure

```
districts=
{
    16777216=       ← D1 (district instance ID)
    {
        zones= { 548 }              ← D2
        type="district_generator"   ← D2
        level=3                     ← D2 ← STACKED COUNT
    }
}
```

`level=N` = how many of that type are built = contributes N × 0.5 to empire size.

---

## 13. Situations (`situations=`)

**Location:** depth 0 at line 4596154.

The Growing Pains situation (`behemoth_finale_situation`) is in this section.

---

## 14. Leaders (`leaders=`)

**Location:** depth 0 at line 2407429. Contains ALL leader objects.

### Structure

```
leaders=
{
    16777547=        ← D1 (leader ID)
    {
        level=7                    ← D2
        bonus_skill_level=0        ← D2
        class="official"           ← D2
        traits="leader_trait_adaptable"  ← D2 (repeating key)
        traits="leader_trait_urbanist"   ← D2
        ...
    }
}
```

### Key fields at depth 2

| Field | Description |
|-------|-------------|
| `level=N` | Base skill level |
| `bonus_skill_level=N` | Additional skill levels (from traits, etc.) |
| `class="..."` | `official`, `commander`, `scientist` |
| `traits="..."` | Repeating key, one per trait |

### Governor skill calculation

Effective skill = `level + bonus_skill_level`.

Each planet's governor is identified by the `governor=<leader_id>` field in the planet block (§7). Only sector capital planets have this field. Other planets in the sector receive the sector governor rate (-0.01/level instead of -0.02/level).

---

## 15. Sectors (`sectors=`)

**Location:** depth 0 at line 4494626.

### Structure

```
sectors=
{
    5=              ← D1 (sector ID)
    {
        owner=0                 ← D2 (country ID)
        local_capital=10        ← D2 (planet ID of sector capital)
        systems=                ← D2
        {                       ← D2 (opens to D3)
            0                   ← D3 (system IDs)
            1
            2
            ...
        }
    }
}
```

### Key fields at depth 2

| Field | Description |
|-------|-------------|
| `owner=N` | Country ID that owns this sector |
| `local_capital=N` | Planet ID of sector capital (has `governor=` field) |
| `systems={...}` | List of galactic_object (system) IDs in this sector |

The sector data links systems to their sector, which links to the sector capital, which links to the governor via the planet's `governor=` field.
