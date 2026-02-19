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
| `leaders=` | **2459247** | ~732K lines | All leader data |
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

### Notes on deprecated subspecies

Country 0 has 75+ species entries. Many are **zero-pop deprecated subspecies** — earlier evolutionary stages with fewer traits and no living pops (these survive as species_db entries but are empty). They can be identified by having a `base_ref=` pointing to the founder (569425345) and having fewer traits. Species 609 is the current founder with 38 traits.

Not all subspecies have `species_traits_evopred_count` set. The deprecated ones often lack it (variable only set when the species gained its traits through gameplay). This is irrelevant since they have 0 pops.

---

## 5. Pop Groups (`pop_groups=`)

**Location:** depth 0 at line 64992.

Pop groups are how Stellaris actually stores populations in 4.x (not individual pops). Each pop_group has a `species=N` and a floating-point `size`.

**Note:** The `pop_groups=` entries in planet blocks (depth 3) are just **arrays of IDs** pointing to these global pop_group objects. Example in a planet: `pop_groups={ 419431466 1229 2164263088 }` — these are pop_group IDs, not inline data.

For empire size calculation, it's easier to use `species_information=` in the planet blocks (see §7) which directly gives `num_pops` per species per planet.

---

## 6. Galactic Objects (`galactic_object=`)

**Location:** depth 0 at line 299792, ends before `starbase_mgr=` at line 370032.

Each galactic object = one star SYSTEM. All 784 entries have `type=star` (confirmed — no other types exist in the galaxy, including black holes and pulsars, which still use `type=star`).

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
    }
}
```

### Important: No direct owner field

Galactic object entries do NOT have an `owner=country_id` field. System ownership is determined by which country has a starbase there (via `starbase_mgr`).

### Planet IDs vs system IDs

The IDs in `planet=N` lines inside a galactic_object are planet IDs in the `planets=` section (NOT galactic_object IDs). These are different namespaces. Example: system 0 (Despad) has planets 1569–1582 and 7862. The system itself has ID 0 as a galactic_object.

### `controlled_planets` relationship

Country 0's `controlled_planets` list (see §8) contains BOTH:
- Galactic_object IDs (system IDs, 0-783) — 208 of them match for country 0
- Planet IDs from the planets section — ~1348 of them

The 208 system IDs in controlled_planets correspond to systems where country 0 has colonies (not all starbase systems). So this list CANNOT be used to count all owned systems.

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
            pop_groups= { 419431466 1229 2164263088 }  ← D3 (pop_group IDs, NOT inline data)
            pop_jobs= { 650 651 ... }   ← D3 (pop_job IDs)
            districts= { 16777853 646 647 16777674 }   ← D3 (district IDs → look up in districts= section)
            last_district_changed="district_mindlink"  ← D3
            colonize_date="2200.01.01"  ← D3
            num_sapient_pops=9616       ← D3
            final_designation="col_capital_hive"       ← D3
            ascension_tier=5            ← D3 (0-5, max = highest tier)
            stability=89.08             ← D3
            species_refs= { 609 }       ← D3 (species IDs on this planet)
            species_information=        ← D3
            {                           ← D3 (opens to D4)
                609=                    ← D4 (species ID)
                {                       ← D4 (opens to D5)
                    num_pops=9616       ← D5 ← USE THIS for pop counts per species per planet
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
| `ascension_tier=N` | int | 0–5, affects planet capacity |

### Critical: `districts=` array semantics in 4.x

In Stellaris 4.x, `districts={ 16777853 646 647 16777674 }` is a list of **district instance IDs**. Each ID references an entry in the global `districts=` section (at line 4503998). These IDs do NOT directly tell you the count — you must look up each ID in `districts=` to get its `level` (the stacked count of that district type built on this planet).

For planet 10 (home planet with ascension_tier=5):
- `16777853` → `district_hive_3`, level=5
- `646` → `district_hive_2`, level=4
- `647` → `district_hive_1`, level=3
- `16777674` → `district_mindlink`, level=15
- **Total: 5+4+3+15 = 27 district levels** on the home planet

### Critical: planet pops use `species_information`, NOT `pop_groups`

The `pop_groups=` in a planet block lists pop_group object IDs (pointers to global pop_group objects). **Do not try to parse pop_groups inline.** Use `species_information={ species_id={ num_pops=N } }` instead — it directly gives the pop count per species per planet.

---

## 8. Country Data (`country=`)

**Location:** depth 0 at line 1247753. Contains all countries (player, AI, enclaves, etc.).

### Country 0 block location

```
country=          ← D0 line 1247753
{                 ← D0 (opens to D1)
    0=            ← D1 (line 1247755 — country 0 = player)
    {             ← D1 (opens to D2)
        ...       ← D2: country 0 data fields
    }             ← back to D1
    1=            ← D1 (next country)
    ...
}
```

### Key fields inside country 0 (all at depth 2)

| Field | Approx line | Notes |
|-------|-------------|-------|
| `save_on_death=1` | 1247757 | Usually first field |
| `name= { key="Prime Empire" }` | 1247782 | Country name |
| `tech_status= { ... }` | 1247804 | Technology block — see below |
| `empire_size=1482` | ~1253879 | **Game-reported empire size** |
| `num_sapient_pops=172999` | ~1253882 | Total pops (all planets) |
| `graphical_culture="biogenesis_01"` | ~1253884 | Used to identify this country's starbases |
| `traditions= { "tr_..." }` | ~1468570 | String array of active traditions |
| `ascension_perks= { "ap_..." }` | ~1468622 | String array |
| `owned_armies= { ... }` | ~1468632 | Army ID list |
| `owned_planets= { 10 517 757 ... }` | ~1468636 | 44 colony planet IDs (integer array) |
| `restricted_systems= { ... }` | ~1468640 | 6 restricted system IDs |
| `controlled_planets= { ... }` | ~1468644 | Large mixed list (see below) |
| `edicts= { { edict="key" ... } }` | ~1468656 | Active edicts block |

### `tech_status=` format

NOT a simple array. Each technology is stored as two consecutive lines:
```
tech_status=
{
    technology="tech_maulers"   ← D3
    level=1                     ← D3
    technology="tech_weavers"   ← D3
    level=1                     ← D3
    ...
    technology="tech_psionic_theory"   ← appears at ~relative line 466 from country start
    level=1
    ...
    "tech_lost_building_methods"="64"  ← NOTE: different format for some repeatable techs!
}
```
The repeatable techs use `"tech_key"="level"` format (quoted key + numeric level). Regular techs use `technology="key"\nlevel=N` two-line format. Both need to be handled.

### `traditions=` format (depth 3 string array)

```
traditions=
{
    "tr_supremacy_adopt"
    "tr_supremacy_fleet_logistical_corps"
    ...49 entries total for country 0...
    "tr_statecraft_finish"
}
```
All traditions are quoted strings at depth 3.

### `ascension_perks=` format (same as traditions)

Country 0 has: `ap_imperial_prerogative`, `ap_enigmatic_engineering`, `ap_engineered_evolution`, `ap_behemoths`, `ap_galactic_force_projection`, `ap_galactic_wonders_utopia_and_megacorp`, `ap_master_builders`

### `owned_planets=` format (integer array at depth 3)

```
owned_planets=
{
    10 517 757 4299 6769 6280 4374 824 121 596 595 594 624 169 4965 4942
    6135 1991 7935 267 2509 791 72 3295 81 4345 4306 3518 312 7468 175
    6020 663 225 880 3977 578 249 682 899 3095 341 951 4991
}
```
44 planet IDs. These are used to filter which planets to scan for districts/pops.

### `controlled_planets=` (large mixed-namespace integer array)

Contains ~1556 IDs. These are a MIX of:
1. **Galactic object IDs** (0–783): star system objects — 208 of these for country 0
2. **Planet IDs** (large numbers): individual planet objects in owned systems

**Do not use this to count owned systems.** Only 208 of the 432 star systems appear here (only colonized systems have their star ID in this list). Use the starbase counting method instead.

### `edicts=` format (depth 4 key inside blocks)

```
edicts=
{
    {                               ← D3 (anonymous block)
        edict="crystal_focus"       ← D4
        date="-5070.07.21"         ← D4
        perpetual=yes               ← D4
        start_date="2298.05.18"    ← D4
    }
    {
        edict="fuel_gases"
        ...
    }
    ...
}
```
Active edicts for country 0 (in q2): `crystal_focus`, `fuel_gases`, `motes_kinetic`, `living_metal_construction`, `motes_armor`.

### Flags in country 0

The country flags section (inside country 0's block) contains important state:
- `bio_mutation=63621816` — flag confirming Chimeral Consciousness is active (set by event `bio.195`)
- Other biogenesis flags, event chain completion flags, etc.

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
            type="sshipyard"                  ← D3 (construction_type equivalent)
            modules= { 0=shipyard ... }       ← D3
            buildings= { 0=crew_quarters ... } ← D3
            update_flag=2048                   ← D3
            build_queue=2354                   ← D3
            station=0                          ← D3 ← CRITICAL: this is a SHIP ID (not fleet ID)
            orbitals= { 0=4294967295 ... 2=16780879 3=184552984 }  ← D3
            construction_type=starbase_shipyard ← D3 (only on developed starbases)
        }
        1=
        {
            level="starbase_level_starfortress"
            station=6                          ← ship ID 6 (not fleet 6!)
            ...
        }
        ...
    }
}
```

### CRITICAL: `station=N` is a SHIP ID, not a fleet ID

This was the key discovery for starbase ownership. Fleet IDs in the save are NOT sequential (they use type-prefix encoding and skip many values). Ship IDs ARE sequential starting from 0.

For example:
- Starbase 0: `station=0` → ship 0 → `graphical_culture="biogenesis_01"` → country 0's starbase
- Starbase 1: `station=6` → ship 6 → `graphical_culture="humanoid_01"` → another country's starbase
- Starbase 2: `station=12` → ship 12 → `graphical_culture="plantoid_01"` → yet another country

The station values increment by 6 (0, 6, 12, 18...) because each starbase system has exactly one ship entry (the station ship). They're every 6th ship because in between are other ship types from non-station fleets.

### Orbital platforms

Some starbases are **orbital platforms** (secondary stations in the same system). They appear in the `orbitals={}` block of a main starbase (non-4294967295 values). Orbitals add ~34 extra starbases to the country 0 count, giving 466 vs the correct 432 systems.

Orbital IDs in the `orbitals={}` block use entity-encoded IDs (like `16780879 = 16777216 + 3663`). These do NOT directly map to starbase IDs, making it hard to exclude them programmatically without a cross-reference.

**Practical workaround:** Use count × 0.926 as approximation, or accept the ~8% overcount.

---

## 10. Ships (`ships=`)

**Location:** depth 0 at line 2459386.

**Total:** 7301 ships across all entities, 6334 have `graphical_culture`.

### Structure

```
ships=
{
    0=             ← D1 (ship ID)
    {
        fleet=0                         ← D2 (fleet this ship belongs to)
        name= { key="STARBASE_STATION_NAME_FORMAT_NON_PRIMARY" ... }  ← D2
        reserve=0                       ← D2
        ship_design_implementation= { design=268435591 ... }  ← D2
        graphical_culture="biogenesis_01"  ← D2 ← identifies owning country
        section= { ... }                ← D2
        ...
    }
    6=
    {
        fleet=4
        graphical_culture="humanoid_01"
        ...
    }
    ...
}
```

### Using `graphical_culture` for ownership

Each ship has a `graphical_culture` matching the country that built it. For starbase ships:
- `"biogenesis_01"` = country 0 (the player's Hive Mind / biogenesis empire)
- `"biogenesis_01_fallen_empire"` = a different fallen empire with biogenesis culture (NOT country 0)

To count country 0's starbases: `starbase.station=N` → look up ship N → check `ship.graphical_culture == "biogenesis_01"`.

### Ship culture counts (q2 save)

From scanning all ships:
| Culture | Count |
|---------|-------|
| biogenesis_01 | 1358 |
| biogenesis_01_fallen_empire | 741 |
| humanoid_01 | 713 |
| avian_01 | 510 |
| ... | ... |

---

## 11. Fleets (`fleet=`)

**Location:** depth 0 at line 3191312.

**Total:** 3677 fleet objects. Fleet IDs are NOT sequential — they use type-prefix encoding, so fleet 5 might not exist while fleet 50331653 does.

### Structure

```
fleet=
{
    0=             ← D1 (fleet ID)
    {
        name= { key="shipclass_starbase_name" ... }  ← D2 (starbase fleet identifier)
        ships= { 0 }        ← D2-D3 (ship IDs in this fleet)
        combat= { ... }     ← D2
        fleet_stats= { ... }  ← D2
        station=yes          ← D2 (marks this as a station/starbase fleet)
        orbital_station=yes  ← D2
        hit_points=219572    ← D2
        ...
    }
    ...
}
```

### Fleet ownership gotcha

Fleet entries DO have an `owner=` field, but it is NOT a country ID. The value is an **entity-encoded ID** such as `owner=16777241 = 16777216 + 25`. This appears to encode "planet entity 25" (or similar), not "country 25". Regular country IDs (0, 1, 2...) do NOT appear in fleet `owner=` fields.

**Do NOT use fleet `owner=` to determine which country owns a starbase.** Use the starbase → ship → graphical_culture chain instead.

### Identifying starbase fleets

Starbase fleets have:
- `station=yes` at depth 2
- `orbital_station=yes` at depth 2
- Name key `"shipclass_starbase_name"` at depth 3 (inside `name={}`)

However, `station=yes` also appears on other non-starbase station types (orbital science labs, listening posts, etc.), so there are 3162 "station fleets" even though there are only 724 starbases.

---

## 12. Districts (`districts=`)

**Location:** depth 0 at line 4503998 (NOT inside planets= — it's a separate top-level section).

**Total:** Contains ALL district objects for the ENTIRE game.

### Structure

```
districts=
{
    16777216=       ← D1 (district instance ID — NOT sequential from 0)
    {
        zones= { 548 }              ← D2 (zone IDs within this district)
        type="district_generator"   ← D2
        level=3                     ← D2 ← STACKED COUNT (how many of this type built)
    }
    2=              ← D1 (note: IDs are non-sequential, mixed large and small values)
    {
        zones= { 2 98 99 }
        type="district_hive_1"
        level=5
    }
    ...
}
```

### District `level` semantics

In Stellaris 4.x with the zone system:
- Each planet has a few district TYPE STACKS (one entry per district type)
- `level=N` = how many of that type are built = contributes N × `EMPIRE_SIZE_FROM_DISTRICTS` (0.5) to empire size
- The `zones={}` block lists the zone instances within the district (each zone slot has a building or is empty)
- IDs in the `zones` array are NOT useful for empire size calculation

### Example: Home planet 10's districts

| District ID | Type | Level | Empire size contribution |
|-------------|------|-------|--------------------------|
| 16777853 | district_hive_3 | 5 | 2.5 |
| 646 | district_hive_2 | 4 | 2.0 |
| 647 | district_hive_1 | 3 | 1.5 |
| 16777674 | district_mindlink | 15 | 7.5 |
| **Total** | | **27** | **13.5** |

The grand total across all 44 owned planets = **777 district levels** (verified against game tooltip).

### Parsing note

District IDs from planet's `districts={}` array are a mix of small integers (like 646) and large integers (like 16777853). There are NO sequential IDs — you must scan the whole `districts=` section to build a lookup `id → level`. The section is large (~96K lines) so searching by ID for each district is O(n×m) without a pre-built index. Build the full `{id: level}` dict once, then look up.

---

## 13. Situations (`situations=`)

**Location:** depth 0 at line 4596154.

The Growing Pains situation (`behemoth_finale_situation`) is in this section:

```
situations=
{
    ...
    {                                         ← anonymous block
        country=0
        target= { type=country id=0 ... }
        type="behemoth_finale_situation"
        progress=219.33                       ← CURRENT PROGRESS
        last_month_progress=1.965             ← LAST MONTH GAIN
        approach="behemoth_finale_approach_digestion"
        stage_durations= { ... }
    }
}
```

### Stage thresholds

| Stage | Progress Range | Event on Enter |
|-------|---------------|----------------|
| 1 | 0 → 80 | `biocrisis.210` |
| 2 | 80 → 180 | `biocrisis.215` |
| 3 | 180 → 300 | `biocrisis.220` |
| 4 | 300 → 440 | `biocrisis.225` |
| 5 | 440 → 600 | `biocrisis.230` |
| 6 | 600 → 780 | `biocrisis.235` |
| 7 | 780 → 980 | `biocrisis.240` |
| 8 | 980 → 1200 | `biocrisis.245` |
| Final | 1200 | `biocrisis.250` (superweapon) |

---

## 14. Leaders (`leaders=`)

**Location:** depth 0 at line 2459247. Contains ALL leader objects.

**Relevant for:** Governor `species_empire_size_mult` — the biggest unresolved gap in the script. Each planet governor contributes `-0.02 × skill_level` as `species_empire_size_mult` to all pops on their planet.

### How to parse governor effects (NOT YET IMPLEMENTED)

1. In `country=` block for country 0, find the government/officials data to identify which leaders are governors
2. In `leaders=` section, find each leader by ID and read their `skill=N` level
3. For each planet: look up the governor's skill, compute `-0.02 × skill` (planet) or `-0.01 × skill` (sector)
4. Apply this as additional `species_empire_size_mult` on top of evopred modifier, for all pops on that planet

This is the primary missing piece (~-17% to -22% of pops component).

Governor modifier source: `common/static_modifiers/00_static_modifiers.txt`
```pdx
skill_official_planet_governor = {
    species_empire_size_mult = -0.02    # per skill level
}
skill_official_sector_governor = {
    species_empire_size_mult = -0.01    # per skill level
}
```
