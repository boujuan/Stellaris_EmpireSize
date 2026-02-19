#!/usr/bin/env python3
"""
Stellaris Empire Size Breakdown Calculator v1.0

Parses a Stellaris 4.3 save game and calculates exact empire size contributions
by component (pops, districts, systems, colonies), annotated with which modifiers
are active. Reports discrepancies vs game-reported value to reveal missing sources.

Usage:
    python3 empire_size.py <save_folder> [country_id]

Examples:
    python3 empire_size.py /home/boujuan/Desktop/q/q2
    python3 empire_size.py /home/boujuan/Desktop/q/q 0
"""

import sys
import re
from pathlib import Path
from collections import defaultdict

# ================================================================
# SETTINGS — Update this section when game rules change
# Game version: Stellaris 4.3 Cetus Open Beta (checksum 3f25)
# ================================================================

DEFAULT_COUNTRY_ID = 0

# Base empire size contributions (from common/defines/00_defines.txt)
BASE = {
    'pops':      0.005,   # EMPIRE_SIZE_FROM_POPS per pop
    'districts': 0.5,     # EMPIRE_SIZE_FROM_DISTRICTS per district level
    'systems':   1.0,     # EMPIRE_SIZE_FROM_SYSTEMS per owned system (any starbase)
    'colonies':  20.0,    # EMPIRE_SIZE_FROM_COLONIES per colony planet
}

# Evolutionary Predators -1% empire size per trait
# Applied as species_empire_size_mult via triggered_pop_group_modifier
# when Chimeral Consciousness Fix mod is loaded.
# Set to 0.0 to simulate vanilla (bug: modifier absent for hive mind drones).
EVOPRED_PER_TRAIT_MULT = -0.01   # -1% per species_traits_evopred_count

# Species traits → species_empire_size_mult (multiplicative per pop, before country pops mult)
# Source: common/traits/04_species_traits.txt, 02_species_traits_basic_characteristics.txt
TRAIT_SPECIES_EMPIRE_SIZE_MULT = {
    'trait_docile':            -0.10,   # Organic positive (+2 cost)
    'trait_unruly':             0.10,   # Organic negative (-2 cost)
    'trait_cave_dweller':       0.10,   # Lithoid/organic
    'trait_robot_cave_dweller': 0.10,   # Robotic
    # Cyborg traits have dynamic modifiers (not simple mult) — handled separately if needed
}

# Traditions → empire_size modifier contributions
# Key: exact tradition key as stored in save's traditions=[] array
# Value: dict mapping modifier type to value
#   Types: 'pops'      = empire_size_pops_mult
#          'districts' = empire_size_districts_mult
#          'systems'   = empire_size_systems_mult
#          'colonies'  = empire_size_colonies_mult
#          'total'     = empire_size_mult (global, applied after all components summed)
# Source: common/traditions/*.txt
TRADITION_MODIFIERS = {
    # Domination tree
    'tr_domination_finish':                        {'pops': -0.05},
    'tr_domination_federations_finish':            {'pops': -0.05},   # Federations DLC swap
    'tr_domination_federations_wilderness_finish': {'districts': -0.05},  # Wilderness+Federations
    # Expansion tree
    'tr_expansion_courier_network':                {'systems': -0.15, 'colonies': -0.15},
    # Statecraft tree
    'tr_statecraft_finish':                        {'total': -0.05},
    # Synchronicity tree (gestalt)
    'tr_synchronicity_kinship_gestalt':            {'pops': -0.05},   # = "Synchronized Agents"
    # Harmony tree
    'tr_harmony_kinship':                          {'pops': -0.05},
    'tr_harmony_kinship_shared_burdens':           {'pops': -0.05},   # Shared Burdens civic swap
    # Cybernetics tree
    'tr_cybernetics_synaptic_sub_processing':      {'districts': -0.15},
    # Nanotech tree
    'tr_nanotech_finish':                          {'colonies': -0.50},
    # Virtuality tree
    'tr_virtuality_2':                             {'pops': -0.10, 'colonies': 1.00},
}

# Technologies → empire_size modifier contributions
# Key: exact technology key as stored in save's tech_status block
# Source: common/technology/*.txt
TECH_MODIFIERS = {
    'tech_psionic_theory':        {'pops': -0.05},    # Social tech; psionic unlocks
    'tech_lost_building_methods': {'districts': -0.30},  # First Contact DLC
}

# Ascension Perks → empire_size modifier contributions
# Source: common/ascension_perks/00_ascension_perks.txt
ASCENSION_PERK_MODIFIERS = {
    'ap_imperial_prerogative': {'colonies': -0.25},   # Confirmed 4.3 value (was -0.50 pre-4.3)
    'ap_interstellar_dominion':{'systems':  -0.25},
}

# Edicts → empire_size modifier contributions
# Key: edict key as stored in save's edicts block
EDICT_MODIFIERS = {
    # Example: 'edict_name': {'pops': -0.05}
    # Add entries here if active edicts affect empire size
}

# Policies → empire_size modifier contributions
# Key: active policy option key
POLICY_MODIFIERS = {
    # Example: 'policy_option_key': {'pops': -0.05}
}

# Civics → empire_size modifier contributions
CIVIC_MODIFIERS = {
    # Example: 'civic_key': {'pops': -0.10}
}

# Planet Ascension Tier — reduces pops, districts, AND colony from that planet.
# Each tier: -5% base, scaled by (1 + planetary_ascension_effect_mult).
# Source: wiki Designation.md, verified in save (ascension_tier=N at depth 3).
ASCENSION_TIER_BASE_REDUCTION = 0.05   # per tier

# Sources of planetary_ascension_effect_mult (from traditions)
ASCENSION_EFFECT_TRADITIONS = {
    'tr_synchronicity_finish':        0.25,  # Hive gestalt
    'tr_synchronicity_machine_finish':0.25,  # Machine gestalt swap
    'tr_harmony_finish':              0.25,  # Regular empires
    'tr_harmony_federations_finish':  0.25,  # Federations DLC swap
}

# Sources of planetary_ascension_effect_mult (from civics)
ASCENSION_EFFECT_CIVICS = {
    'civic_ascensionists':            0.25,  # Regular
    'civic_hive_ascensionists':       0.25,  # Hive gestalt
    'civic_machine_ascensionists':    0.25,  # Machine gestalt
    'civic_corporate_ascensionists':  0.25,  # Corporate
}

# Governor skill effects on pops (species_empire_size_mult per skill level)
# Source: common/static_modifiers/00_static_modifiers.txt lines 1305-1377
# All governor classes (official, commander, scientist) use the same rates.
# Planet and sector effects do NOT stack — each planet gets one rate.
GOVERNOR_PLANET_RATE = -0.02   # Sector capital: direct planet governor
GOVERNOR_SECTOR_RATE = -0.01   # Other sector planets: sector governor

# Starbase levels that count as systems for empire size.
# Orbital rings and deep space citadels are excluded.
# Source: common/starbase_levels/
SYSTEM_STARBASE_LEVELS = {
    'starbase_level_outpost',
    'starbase_level_starport',
    'starbase_level_starhold',
    'starbase_level_starfortress',
    'starbase_level_citadel',
}

# Governor trait modifiers (per-planet empire size effects)
# Source: common/traits/00_governor_traits.txt
GOVERNOR_TRAIT_MODIFIERS = {
    'leader_trait_urbanist': {
        'planet': {'districts': -0.50},
        'sector': {'districts': -0.25},
    },
}

# ================================================================
# END SETTINGS
# ================================================================


# ================================================================
# PDX STREAMING PARSER
# ================================================================

def _count_braces(s):
    """Count unquoted { and } in a string. Returns (opens, closes)."""
    opens = closes = 0
    in_q = False
    for c in s:
        if c == '"':
            in_q = not in_q
        elif not in_q:
            if c == '{':
                opens += 1
            elif c == '}':
                closes += 1
    return opens, closes


def stream_lines(filepath):
    """
    Yield (depth, line) for each non-empty, non-comment line.
    depth = number of enclosing blocks at the start of this line.
    Closing braces reduce depth BEFORE the line is yielded.
    Opening braces increase depth AFTER the line is yielded.
    """
    depth = 0
    with open(filepath, encoding='utf-8', errors='replace') as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            opens, closes = _count_braces(line)
            depth -= closes
            if depth < 0:
                depth = 0
            yield depth, line
            depth += opens


def extract_string_array(lines_iter, entry_depth):
    """
    Collect quoted strings from an array block at entry_depth+1.
    Returns list of strings. Consumes lines until we return to entry_depth.
    """
    result = []
    for depth, line in lines_iter:
        if depth <= entry_depth:
            break
        m = re.match(r'^"([^"]+)"$', line)
        if m:
            result.append(m.group(1))
    return result


def extract_int_array(lines_iter, entry_depth):
    """Collect space-separated integers from an array block."""
    result = []
    for depth, line in lines_iter:
        if depth <= entry_depth:
            break
        # Lines like "1 2 3 4 5" or single integers
        nums = re.findall(r'\b(\d+)\b', line)
        result.extend(int(n) for n in nums)
    return result


# ================================================================
# SAVE GAME DATA EXTRACTORS
# ================================================================

def extract_species_data(gamestate_path):
    """
    Extract species traits and evopred_count from species_db= section.
    Returns: {species_id: {'traits': [str], 'evopred_count': int}}
    """
    species = {}
    in_db = False
    db_depth = None
    current_id = None
    sp_depth = None
    section_key = {}  # depth -> current key at that depth

    gen = stream_lines(gamestate_path)
    for depth, line in gen:
        if not in_db:
            if depth == 0 and re.match(r'^species_db=', line):
                in_db = True
                db_depth = 0
            continue

        # Exit species_db when we return to depth 0 with a new key
        if depth == 0 and in_db and not re.match(r'^[{}]', line):
            break

        # Depth 1: species ID entries like "609="
        if depth == 1:
            m = re.match(r'^(\d+)=', line)
            if m:
                current_id = int(m.group(1))
                species[current_id] = {'traits': [], 'evopred_count': 0}
                sp_depth = 1
                section_key = {}
            continue

        if current_id is None:
            continue

        # Track section keys at depth 2 (traits=, variables=, etc.)
        if depth == 2:
            m = re.match(r'^(\w+)=', line)
            if m:
                section_key[2] = m.group(1)

        # Collect traits at depth 3 when in traits= block
        if depth == 3 and section_key.get(2) == 'traits':
            m = re.match(r'^trait="([^"]+)"', line)
            if m:
                species[current_id]['traits'].append(m.group(1))

        # Collect evopred_count at depth 3 when in variables= block
        if depth == 3 and section_key.get(2) == 'variables':
            m = re.match(r'^species_traits_evopred_count=(\d+)', line)
            if m:
                species[current_id]['evopred_count'] = int(m.group(1))

    return species


def extract_country_data(gamestate_path, country_id):
    """
    Extract traditions, technologies, ascension perks, edicts, owned planets,
    and empire_size for the specified country.
    Returns dict with all extracted data.
    """
    data = {
        'traditions': [],
        'technologies': [],
        'ascension_perks': [],
        'edicts': [],
        'civics': [],
        'owned_planets': [],
        'controlled_planets': [],
        'owned_fleets': [],
        'empire_size': None,
        'num_sapient_pops': None,
        'name': str(country_id),
        'graphical_culture': None,
    }

    in_country_section = False
    in_target_country = False
    country_section_depth = None
    target_depth = None
    current_subsection = None
    sub_depth = None
    in_tech_status = False
    tech_status_depth = None
    pending_technology = None
    in_government = False
    in_civics_block = False
    in_fleets_manager = False
    in_owned_fleets = False

    for depth, line in stream_lines(gamestate_path):
        # Find country= section
        if not in_country_section:
            if depth == 0 and re.match(r'^country=', line):
                in_country_section = True
                country_section_depth = 0
            continue

        # Find target country ID block at depth 1
        if not in_target_country:
            if depth == 0 and in_country_section and line not in ('{', '}'):
                break  # Left country section (new top-level key)
            if depth == 1 and re.match(rf'^{country_id}=', line):
                in_target_country = True
                target_depth = 1
            continue

        # Exit target country block when we see the NEXT country entry at depth 1
        if depth == 1 and line not in ('{', '}') and re.match(r'^\d+=', line):
            break  # Found next country's block

        # tech_status= block: collect technology="key" pairs
        if depth == 2 and re.match(r'^tech_status=', line):
            in_tech_status = True
            tech_status_depth = 2
            continue

        if in_tech_status:
            if depth <= tech_status_depth and line not in ('{', '}'):
                in_tech_status = False
                pending_technology = None
            elif depth == 3:
                m = re.match(r'^technology="([^"]+)"', line)
                if m:
                    pending_technology = m.group(1)
                elif re.match(r'^level=', line) and pending_technology:
                    data['technologies'].append(pending_technology)
                    pending_technology = None

        # graphical_culture=
        if depth == 2:
            m = re.match(r'^graphical_culture="([^"]+)"', line)
            if m and data['graphical_culture'] is None:
                data['graphical_culture'] = m.group(1)

        # empire_size=
        if depth == 2:
            m = re.match(r'^empire_size=(\d+)', line)
            if m and data['empire_size'] is None:
                data['empire_size'] = int(m.group(1))

        # num_sapient_pops=
        if depth == 2:
            m = re.match(r'^num_sapient_pops=(\d+)', line)
            if m and data['num_sapient_pops'] is None:
                data['num_sapient_pops'] = int(m.group(1))

        # name= (country name)
        if depth == 2 and re.match(r'^name=', line):
            current_subsection = 'name'
            sub_depth = 2

        if depth == 3 and current_subsection == 'name':
            m = re.match(r'^key="([^"]+)"', line)
            if m:
                data['name'] = m.group(1)

        # traditions= block: collect quoted tradition keys
        if depth == 2 and re.match(r'^traditions=', line):
            current_subsection = 'traditions'
            sub_depth = 2
            continue

        if current_subsection == 'traditions' and depth == 3:
            m = re.match(r'^"([^"]+)"$', line)
            if m:
                data['traditions'].append(m.group(1))
        elif current_subsection == 'traditions' and depth <= sub_depth and line not in ('{', '}'):
            current_subsection = None

        # ascension_perks= block
        if depth == 2 and re.match(r'^ascension_perks=', line):
            current_subsection = 'ascension_perks'
            sub_depth = 2
            continue

        if current_subsection == 'ascension_perks' and depth == 3:
            m = re.match(r'^"([^"]+)"$', line)
            if m:
                data['ascension_perks'].append(m.group(1))
        elif current_subsection == 'ascension_perks' and depth <= sub_depth and line not in ('{', '}'):
            current_subsection = None

        # owned_planets= block: integer array
        if depth == 2 and re.match(r'^owned_planets=', line):
            current_subsection = 'owned_planets'
            sub_depth = 2
            continue

        if current_subsection == 'owned_planets' and depth == 3:
            nums = re.findall(r'\b(\d+)\b', line)
            data['owned_planets'].extend(int(n) for n in nums)
        elif current_subsection == 'owned_planets' and depth <= sub_depth and line not in ('{', '}'):
            current_subsection = None

        # controlled_planets= block: integer array (includes stars for owned systems)
        if depth == 2 and re.match(r'^controlled_planets=', line):
            current_subsection = 'controlled_planets'
            sub_depth = 2
            continue

        if current_subsection == 'controlled_planets' and depth == 3:
            nums = re.findall(r'\b(\d+)\b', line)
            data['controlled_planets'].extend(int(n) for n in nums)
        elif current_subsection == 'controlled_planets' and depth <= sub_depth and line not in ('{', '}'):
            current_subsection = None

        # edicts= block
        if depth == 2 and re.match(r'^edicts=', line):
            current_subsection = 'edicts'
            sub_depth = 2
            continue

        if current_subsection == 'edicts' and depth == 4:
            m = re.match(r'^edict="([^"]+)"', line)
            if m:
                data['edicts'].append(m.group(1))

        # government= { civics= { ... } } block for civic keys
        if depth == 2 and re.match(r'^government=', line):
            in_government = True
        if in_government and depth == 3 and re.match(r'^civics=', line):
            in_civics_block = True
        elif in_civics_block and depth == 4:
            m = re.match(r'^"([^"]+)"$', line)
            if m:
                data['civics'].append(m.group(1))
        elif in_civics_block and depth <= 3 and line not in ('{', '}'):
            in_civics_block = False
        if in_government and depth <= 2 and line not in ('{', '}') and not re.match(r'^government=', line):
            in_government = False

        # fleets_manager= { owned_fleets= { { fleet=N } ... } }
        if depth == 2 and re.match(r'^fleets_manager=', line):
            in_fleets_manager = True
        elif in_fleets_manager and depth == 3 and re.match(r'^owned_fleets=', line):
            in_owned_fleets = True
        elif in_owned_fleets and depth == 5:
            m = re.match(r'^fleet=(\d+)', line)
            if m:
                data['owned_fleets'].append(int(m.group(1)))
        elif in_owned_fleets and depth <= 3 and line not in ('{', '}'):
            in_owned_fleets = False
        if in_fleets_manager and depth <= 2 and line not in ('{', '}') and not re.match(r'^fleets_manager=', line):
            in_fleets_manager = False

    return data


def extract_planet_data(gamestate_path, owned_planet_ids):
    """
    For each owned planet, extract:
      - district IDs (from districts={...} array)
      - pops per species (from species_information={N={num_pops=X}})
      - ascension_tier (int, default 0)
      - governor leader ID (int or None)
    Returns: {planet_id: {'district_ids': [int], 'species_pops': {species_id: int},
              'ascension_tier': int, 'governor': int|None}}
    """
    owned_set = set(owned_planet_ids)
    planet_data = {pid: {'district_ids': [], 'species_pops': {},
                         'ascension_tier': 0, 'governor': None}
                   for pid in owned_set}

    in_planets = False
    current_planet_id = None
    current_subsection = None
    sub_depth = None
    current_species_id = None

    # Planet section structure (depths from stream_lines):
    #  D0: planets=  D0: {
    #  D1: planet=   D1: {
    #  D2: 0=        D2: {       <- planet ID
    #  D3: owner=, districts=, species_information=, ...  <- planet content
    #  D4: content of those sub-blocks
    #  D5: content of species_information sub-blocks

    for depth, line in stream_lines(gamestate_path):
        if not in_planets:
            if depth == 0 and re.match(r'^planets=', line):
                in_planets = True
            continue

        # Exit planets section on a new depth-0 key (not a brace)
        if depth == 0 and line not in ('{', '}'):
            break

        # Planet ID entries at depth 2 (inside planets= { planet= { ... })
        if depth == 2 and re.match(r'^\d+=', line):
            m = re.match(r'^(\d+)=', line)
            pid = int(m.group(1))
            current_planet_id = pid if pid in owned_set else None
            current_subsection = None
            current_species_id = None
            continue

        if current_planet_id is None:
            continue

        pd = planet_data[current_planet_id]

        # ascension_tier= at depth 3
        if depth == 3:
            m = re.match(r'^ascension_tier=(\d+)', line)
            if m:
                pd['ascension_tier'] = int(m.group(1))
                continue

        # governor= at depth 3
        if depth == 3:
            m = re.match(r'^governor=(\d+)', line)
            if m:
                pd['governor'] = int(m.group(1))
                continue

        # districts= array at depth 3
        if depth == 3 and re.match(r'^districts=', line):
            current_subsection = 'districts'
            sub_depth = 3
            continue

        if current_subsection == 'districts' and depth == 4:
            nums = re.findall(r'\b(\d+)\b', line)
            pd['district_ids'].extend(int(n) for n in nums)
        elif current_subsection == 'districts' and depth <= sub_depth and line not in ('{', '}'):
            current_subsection = None

        # species_information= block at depth 3
        if depth == 3 and re.match(r'^species_information=', line):
            current_subsection = 'species_info'
            sub_depth = 3
            current_species_id = None
            continue

        if current_subsection == 'species_info':
            if depth == 4 and re.match(r'^\d+=', line):
                m = re.match(r'^(\d+)=', line)
                current_species_id = int(m.group(1))
            elif depth == 5 and current_species_id is not None:
                m = re.match(r'^num_pops=(\d+)', line)
                if m:
                    pd['species_pops'][current_species_id] = \
                        pd['species_pops'].get(current_species_id, 0) + int(m.group(1))
            elif depth <= sub_depth and line not in ('{', '}'):
                current_subsection = None
                current_species_id = None

    return planet_data


def extract_district_levels(gamestate_path, district_ids):
    """
    Look up the level= field for each district ID in the global districts= section.
    Returns: {district_id: level}
    Each district in 4.3 has type= and level= (level = how many of that type are built).
    """
    needed = set(district_ids)
    levels = {}
    in_districts = False
    current_did = None

    # districts= section structure:
    #  D0: districts=  D0: {
    #  D1: DISTRICT_ID=   D1: {
    #  D2: type="...", level=N, zones={...}

    for depth, line in stream_lines(gamestate_path):
        if not in_districts:
            if depth == 0 and re.match(r'^districts=', line):
                in_districts = True
            continue

        if depth == 0 and line not in ('{', '}'):
            break  # Left districts section

        if depth == 1 and re.match(r'^\d+=', line):
            m = re.match(r'^(\d+)=', line)
            current_did = int(m.group(1))
            continue

        if depth == 2 and current_did in needed:
            m = re.match(r'^level=(\d+)', line)
            if m:
                levels[current_did] = int(m.group(1))

        if len(levels) == len(needed):
            break

    return levels


def count_owned_systems(gamestate_path, owned_fleet_ids):
    """
    Count systems owned by this country using the starbase_mgr section.
    Only counts starbases with levels in SYSTEM_STARBASE_LEVELS (excludes
    orbital rings, deep space citadels, and other special starbases).
    Ownership verified via station ship fleet membership.

    Returns: (system_count, total_starbases_matched, excluded_count)
    """
    owned_fleets = set(owned_fleet_ids)

    # Build ship_id -> fleet_id from the ships section
    ship_fleet = {}
    in_ships = False
    ship_id = None

    for depth, line in stream_lines(gamestate_path):
        if not in_ships:
            if depth == 0 and re.match(r'^ships=', line):
                in_ships = True
            continue
        if depth == 0 and line not in ('{', '}'):
            break
        if depth == 1 and line not in ('{', '}'):
            m = re.match(r'^(\d+)=', line)
            if m:
                ship_id = int(m.group(1))
        if depth == 2 and ship_id is not None:
            m = re.match(r'^fleet=(\d+)', line)
            if m:
                ship_fleet[ship_id] = int(m.group(1))

    # Count starbases whose station ship is in one of our fleets
    system_count = 0
    total_matched = 0
    excluded = 0
    in_sm = False
    sb_id = None
    sb_level = None
    sb_station = None

    for depth, line in stream_lines(gamestate_path):
        if not in_sm:
            if depth == 0 and re.match(r'^starbase_mgr=', line):
                in_sm = True
            continue
        if depth == 0 and line not in ('{', '}'):
            break
        if depth == 2 and line not in ('{', '}'):
            m = re.match(r'^(\d+)=', line)
            if m:
                # Process previous starbase if complete
                if sb_station is not None and sb_level is not None:
                    fleet_id = ship_fleet.get(sb_station)
                    if fleet_id is not None and fleet_id in owned_fleets:
                        total_matched += 1
                        if sb_level in SYSTEM_STARBASE_LEVELS:
                            system_count += 1
                        else:
                            excluded += 1
                sb_id = int(m.group(1))
                sb_level = None
                sb_station = None
        if depth == 3 and sb_id is not None:
            m = re.match(r'^level="([^"]+)"', line)
            if m:
                sb_level = m.group(1)
            m = re.match(r'^station=(\d+)', line)
            if m:
                sb_station = int(m.group(1))

    # Process last starbase
    if sb_station is not None and sb_level is not None:
        fleet_id = ship_fleet.get(sb_station)
        if fleet_id is not None and fleet_id in owned_fleets:
            total_matched += 1
            if sb_level in SYSTEM_STARBASE_LEVELS:
                system_count += 1
            else:
                excluded += 1

    return system_count, total_matched, excluded


def extract_leader_data(gamestate_path, leader_ids):
    """
    Extract skill levels, class, and traits for specified leaders.
    Pass 6: iterates the leaders= section.
    Returns: {leader_id: {'skill': int, 'class': str, 'traits': [str]}}
    """
    needed = set(leader_ids)
    if not needed:
        return {}

    leaders = {}
    in_leaders = False
    current_id = None
    current_data = None

    for depth, line in stream_lines(gamestate_path):
        if not in_leaders:
            if depth == 0 and re.match(r'^leaders=', line):
                in_leaders = True
            continue
        if depth == 0 and line not in ('{', '}'):
            break

        if depth == 1 and line not in ('{', '}'):
            # New leader ID entry — finalize previous leader if any
            if current_id is not None and current_data is not None:
                current_data['skill'] = current_data['_level'] + current_data['_bonus']
                del current_data['_level']
                del current_data['_bonus']
                leaders[current_id] = current_data
                current_id = None
                current_data = None
                if len(leaders) == len(needed):
                    break

            m = re.match(r'^(\d+)=', line)
            if m:
                lid = int(m.group(1))
                if lid in needed:
                    current_id = lid
                    current_data = {'skill': 0, 'class': '', 'traits': [],
                                    '_level': 0, '_bonus': 0}
                else:
                    current_id = None
            continue

        if depth <= 1:
            continue

        if current_id is None:
            continue

        if depth == 2:
            m = re.match(r'^level=(\d+)', line)
            if m:
                current_data['_level'] = int(m.group(1))
            m = re.match(r'^bonus_skill_level=(\d+)', line)
            if m:
                current_data['_bonus'] = int(m.group(1))
            m = re.match(r'^class="([^"]+)"', line)
            if m:
                current_data['class'] = m.group(1)
            m = re.match(r'^traits="([^"]+)"', line)
            if m:
                current_data['traits'].append(m.group(1))

    # Finalize last leader if stream ended
    if current_id is not None and current_data is not None:
        current_data['skill'] = current_data['_level'] + current_data['_bonus']
        del current_data['_level']
        del current_data['_bonus']
        leaders[current_id] = current_data

    return leaders


def extract_sector_data(gamestate_path, country_id):
    """
    Extract sector information for the specified country.
    Pass 7: iterates the sectors= section.
    Returns: {sector_id: {'local_capital': planet_id, 'systems': [int]}}
    """
    sectors = {}
    in_sectors = False
    current_sector_id = None
    current_sector = None
    current_owner = None
    current_subsection = None

    for depth, line in stream_lines(gamestate_path):
        if not in_sectors:
            if depth == 0 and re.match(r'^sectors=', line):
                in_sectors = True
            continue
        if depth == 0 and line not in ('{', '}'):
            break

        # Sector ID at depth 1
        if depth == 1:
            m = re.match(r'^(\d+)=', line)
            if m:
                # Save previous sector if it belongs to our country
                if current_sector is not None and current_owner == country_id:
                    sectors[current_sector_id] = current_sector
                current_sector_id = int(m.group(1))
                current_sector = {'local_capital': None, 'systems': []}
                current_owner = None
                current_subsection = None
            elif line == 'none':
                current_sector = None
                current_owner = None
            continue

        if current_sector is None:
            continue

        if depth == 2:
            m = re.match(r'^owner=(\d+)', line)
            if m:
                current_owner = int(m.group(1))
            m = re.match(r'^local_capital=(\d+)', line)
            if m:
                current_sector['local_capital'] = int(m.group(1))
            if re.match(r'^systems=', line):
                current_subsection = 'systems'
                continue

        if current_subsection == 'systems' and depth == 3:
            nums = re.findall(r'\b(\d+)\b', line)
            current_sector['systems'].extend(int(n) for n in nums)
        elif current_subsection == 'systems' and depth <= 2 and line not in ('{', '}'):
            current_subsection = None

    # Save last sector
    if current_sector is not None and current_owner == country_id:
        sectors[current_sector_id] = current_sector

    return sectors


def build_planet_to_sector_map(gamestate_path, sector_data, planet_data):
    """
    Build mapping from planet_id to sector info for governor effects.
    Pass 8: iterates galactic_object= to map planets → systems → sectors.

    Returns: {planet_id: {
        'sector_id': int,
        'is_sector_capital': bool,
        'sector_governor': int|None  (leader_id from the sector capital)
    }}
    """
    # Build system_id → sector_id mapping from sector_data
    system_to_sector = {}
    for sec_id, sec in sector_data.items():
        for sys_id in sec['systems']:
            system_to_sector[sys_id] = sec_id

    # Build sector_id → governor (from the capital planet's governor field)
    sector_governor = {}
    sector_capitals = set()
    for sec_id, sec in sector_data.items():
        cap = sec['local_capital']
        if cap is not None:
            sector_capitals.add(cap)
            if cap in planet_data and planet_data[cap].get('governor') is not None:
                sector_governor[sec_id] = planet_data[cap]['governor']

    owned_planet_ids = set(planet_data.keys())

    # Parse galactic_object= to find which system each planet belongs to
    # Format: galactic_object= { 0= { planet=1569 planet=1570 ... } 1= { ... } }
    planet_to_system = {}
    in_go = False
    current_sys_id = None

    for depth, line in stream_lines(gamestate_path):
        if not in_go:
            if depth == 0 and re.match(r'^galactic_object=', line):
                in_go = True
            continue
        if depth == 0 and line not in ('{', '}'):
            break

        # System ID at depth 1
        if depth == 1 and line not in ('{', '}'):
            m = re.match(r'^(\d+)=', line)
            if m:
                current_sys_id = int(m.group(1))
            continue

        if current_sys_id is None:
            continue

        # Only process systems that are in our sectors
        if current_sys_id not in system_to_sector:
            continue

        # planet=<id> at depth 2 (individual entries, not a sub-block)
        if depth == 2:
            m = re.match(r'^planet=(\d+)', line)
            if m:
                pid = int(m.group(1))
                if pid in owned_planet_ids:
                    planet_to_system[pid] = current_sys_id

    # Build final mapping
    result = {}
    for pid in owned_planet_ids:
        sys_id = planet_to_system.get(pid)
        if sys_id is None:
            # Planet not found in any of our sectors' systems
            continue
        sec_id = system_to_sector.get(sys_id)
        if sec_id is None:
            continue
        result[pid] = {
            'sector_id': sec_id,
            'is_sector_capital': pid in sector_capitals,
            'sector_governor': sector_governor.get(sec_id),
        }

    return result


# ================================================================
# MODIFIER CALCULATOR
# ================================================================

def calculate_active_modifiers(country_data, species_data, pop_species):
    """
    Build the active modifier summary from all known sources.
    pop_species: {species_id: total_pop_count} for the country
    Returns: {
        'pops': float,       # empire_size_pops_mult (country-wide)
        'districts': float,  # empire_size_districts_mult
        'systems': float,    # empire_size_systems_mult
        'colonies': float,   # empire_size_colonies_mult
        'total': float,      # empire_size_mult (global)
        'sources': {type: [(source_name, value), ...]}
        'species_mults': {species_id: float}  # per-species mult
        'ascension_effect_mult': float  # planetary_ascension_effect_mult
        'ascension_effect_sources': [(source_name, value), ...]
    }
    """
    mods = {'pops': 0.0, 'districts': 0.0, 'systems': 0.0, 'colonies': 0.0, 'total': 0.0}
    sources = {k: [] for k in mods}

    def add(mod_dict, source_name):
        for typ, val in mod_dict.items():
            if typ in mods:
                mods[typ] += val
                sources[typ].append((source_name, val))

    # Traditions
    for trad in country_data['traditions']:
        if trad in TRADITION_MODIFIERS:
            add(TRADITION_MODIFIERS[trad], f"tradition: {trad}")

    # Technologies
    for tech in country_data['technologies']:
        if tech in TECH_MODIFIERS:
            add(TECH_MODIFIERS[tech], f"tech: {tech}")

    # Ascension perks
    for perk in country_data['ascension_perks']:
        if perk in ASCENSION_PERK_MODIFIERS:
            add(ASCENSION_PERK_MODIFIERS[perk], f"perk: {perk}")

    # Edicts
    for edict in country_data['edicts']:
        if edict in EDICT_MODIFIERS:
            add(EDICT_MODIFIERS[edict], f"edict: {edict}")

    # Civics
    for civic in country_data['civics']:
        if civic in CIVIC_MODIFIERS:
            add(CIVIC_MODIFIERS[civic], f"civic: {civic}")

    # Per-species species_empire_size_mult
    species_mults = {}
    for sp_id in pop_species:
        mult = 0.0
        if sp_id in species_data:
            sp = species_data[sp_id]
            # Trait-based mult
            for trait in sp['traits']:
                mult += TRAIT_SPECIES_EMPIRE_SIZE_MULT.get(trait, 0.0)
            # EvoPred per-trait mult
            evopred = sp.get('evopred_count', 0)
            mult += EVOPRED_PER_TRAIT_MULT * evopred
        species_mults[sp_id] = mult

    # Planetary ascension effect mult (from traditions + civics)
    asc_effect = 0.0
    asc_effect_sources = []
    for trad in country_data['traditions']:
        if trad in ASCENSION_EFFECT_TRADITIONS:
            val = ASCENSION_EFFECT_TRADITIONS[trad]
            asc_effect += val
            asc_effect_sources.append((f"tradition: {trad}", val))
    for civic in country_data['civics']:
        if civic in ASCENSION_EFFECT_CIVICS:
            val = ASCENSION_EFFECT_CIVICS[civic]
            asc_effect += val
            asc_effect_sources.append((f"civic: {civic}", val))

    return {**mods, 'sources': sources, 'species_mults': species_mults,
            'ascension_effect_mult': asc_effect,
            'ascension_effect_sources': asc_effect_sources}


# ================================================================
# EMPIRE SIZE CALCULATOR
# ================================================================

def calculate_breakdown(
    planet_data,            # {pid: {'district_ids', 'species_pops', 'ascension_tier', 'governor'}}
    district_levels,        # {district_id: level}
    total_systems,          # int
    modifiers,              # from calculate_active_modifiers
    species_data,           # for display labels
    leader_data,            # {leader_id: {'skill', 'class', 'traits'}}
    planet_sector_map,      # {pid: {'sector_id', 'is_sector_capital', 'sector_governor'}}
):
    """
    Calculate empire size breakdown by component with per-planet modifiers.

    Per-planet:
      ascension_factor = 1 - tier × BASE_REDUCTION × (1 + ascension_effect_mult)
      governor_pop_mult = GOVERNOR_RATE × skill_level  (pops only)
      planet_pops = Σ(pops × BASE_pops × (1 + species_mult + governor_pop_mult)) × asc_factor
      planet_districts = Σ(district_levels) × BASE_dist × asc_factor
      planet_colony = 1 × BASE_col × asc_factor

    Country-wide (after summing all planets):
      pops_component = sum(planet_pops) × (1 + empire_size_pops_mult)
      districts_component = sum(planet_districts) × (1 + empire_size_districts_mult)
      colonies_component = sum(planet_colony) × (1 + empire_size_colonies_mult)
      systems_component = total_systems × BASE_sys × (1 + empire_size_systems_mult)
    """
    sm = modifiers['species_mults']
    asc_effect_mult = modifiers['ascension_effect_mult']

    # Per-planet calculation
    total_pops_raw_no_planet_mods = 0.0   # raw pops before governor + ascension (for reporting)
    total_pops_after_planet = 0.0         # pops after governor + ascension
    total_districts_after_planet = 0.0
    total_colonies_after_planet = 0.0
    total_pops_by_species = defaultdict(float)

    # Per-species reporting (country-wide, without governor/ascension)
    pops_detail = defaultdict(lambda: {'count': 0, 'species_mult': 0.0, 'raw_contribution': 0.0})

    # Governor and ascension summaries for reporting
    governor_summary = {'planets_with_governor': 0, 'total_pops_reduction': 0.0}
    ascension_summary = defaultdict(int)  # tier → count of planets

    planet_details = {}  # per-planet details for report

    for pid, pd in planet_data.items():
        # Ascension tier
        tier = pd['ascension_tier']
        ascension_summary[tier] += 1
        asc_factor = 1.0 - tier * ASCENSION_TIER_BASE_REDUCTION * (1.0 + asc_effect_mult)
        asc_factor = max(0.0, asc_factor)

        # Governor pops modifier
        gov_id = pd.get('governor')
        sec_info = planet_sector_map.get(pid, {})
        gov_pop_mult = 0.0
        gov_skill = 0
        gov_type = None

        if gov_id is not None and gov_id in leader_data:
            # Planet has a direct governor (this is a sector capital)
            gov_skill = leader_data[gov_id]['skill']
            gov_pop_mult = GOVERNOR_PLANET_RATE * gov_skill
            gov_type = 'planet'
            governor_summary['planets_with_governor'] += 1
        elif sec_info.get('sector_governor') is not None:
            sec_gov_id = sec_info['sector_governor']
            if sec_gov_id in leader_data:
                gov_skill = leader_data[sec_gov_id]['skill']
                gov_pop_mult = GOVERNOR_SECTOR_RATE * gov_skill
                gov_type = 'sector'
                governor_summary['planets_with_governor'] += 1

        # Per-planet pops (with governor + ascension)
        planet_pops_raw = 0.0
        planet_pops_no_gov = 0.0
        planet_total_pop_count = 0
        for sp_id, pop_count in pd['species_pops'].items():
            sp_mult = sm.get(sp_id, 0.0)
            # Raw contribution (no governor, no ascension) for species reporting
            raw = pop_count * BASE['pops'] * (1.0 + sp_mult)
            pops_detail[sp_id]['count'] += pop_count
            pops_detail[sp_id]['species_mult'] = sp_mult
            pops_detail[sp_id]['raw_contribution'] += raw
            total_pops_by_species[sp_id] += pop_count

            # With governor
            with_gov = pop_count * BASE['pops'] * (1.0 + sp_mult + gov_pop_mult)
            planet_pops_raw += with_gov
            planet_pops_no_gov += raw
            planet_total_pop_count += pop_count

        planet_pops_after_asc = planet_pops_raw * asc_factor
        total_pops_raw_no_planet_mods += planet_pops_no_gov
        total_pops_after_planet += planet_pops_after_asc

        governor_summary['total_pops_reduction'] += (planet_pops_no_gov - planet_pops_raw)

        # Per-planet districts (with ascension)
        planet_district_levels = sum(
            district_levels.get(did, 0) for did in pd['district_ids'])
        planet_districts_raw = planet_district_levels * BASE['districts']
        planet_districts_after_asc = planet_districts_raw * asc_factor
        total_districts_after_planet += planet_districts_after_asc

        # Per-planet colony (with ascension)
        planet_colony_raw = BASE['colonies']
        planet_colony_after_asc = planet_colony_raw * asc_factor
        total_colonies_after_planet += planet_colony_after_asc

        planet_details[pid] = {
            'pops': planet_total_pop_count,
            'districts': planet_district_levels,
            'ascension_tier': tier,
            'asc_factor': asc_factor,
            'gov_type': gov_type,
            'gov_skill': gov_skill,
            'gov_pop_mult': gov_pop_mult,
            'pops_contribution': planet_pops_after_asc,
            'districts_contribution': planet_districts_after_asc,
            'colony_contribution': planet_colony_after_asc,
        }

    # Country-wide multipliers
    pops_mult = modifiers['pops']
    pops_component = total_pops_after_planet * (1.0 + pops_mult)

    districts_mult = modifiers['districts']
    total_district_levels_sum = sum(
        sum(district_levels.get(did, 0) for did in pd['district_ids'])
        for pd in planet_data.values())
    districts_component = total_districts_after_planet * (1.0 + districts_mult)

    systems_mult = modifiers['systems']
    systems_component = total_systems * BASE['systems'] * (1.0 + systems_mult)

    colonies_mult = modifiers['colonies']
    colonies_component = total_colonies_after_planet * (1.0 + colonies_mult)

    subtotal = pops_component + districts_component + systems_component + colonies_component
    total_mult = modifiers['total']
    empire_size = subtotal * (1.0 + total_mult)

    return {
        'pops_raw': total_pops_raw_no_planet_mods,
        'pops_after_planet_mods': total_pops_after_planet,
        'pops_component': pops_component,
        'pops_detail': dict(pops_detail),
        'pops_mult': pops_mult,
        'districts_raw': total_district_levels_sum * BASE['districts'],
        'districts_after_planet_mods': total_districts_after_planet,
        'districts_component': districts_component,
        'districts_mult': districts_mult,
        'systems_component': systems_component,
        'systems_mult': systems_mult,
        'colonies_raw': len(planet_data) * BASE['colonies'],
        'colonies_after_planet_mods': total_colonies_after_planet,
        'colonies_component': colonies_component,
        'colonies_mult': colonies_mult,
        'subtotal': subtotal,
        'total_mult': total_mult,
        'empire_size': empire_size,
        'governor_summary': governor_summary,
        'ascension_summary': dict(ascension_summary),
        'ascension_effect_mult': asc_effect_mult,
        'planet_details': planet_details,
        'total_pops_by_species': dict(total_pops_by_species),
        'total_district_levels': total_district_levels_sum,
    }


# ================================================================
# REPORT
# ================================================================

def print_report(breakdown, country_data, modifiers, species_data,
                 total_systems, systems_total_matched, systems_excluded,
                 game_reported=None):
    """Print formatted empire size breakdown report."""
    W = 65
    SEP = '═' * W

    def pct(v):
        return f"{v*100:+.1f}%"

    def fmt_sources(src_list):
        if not src_list:
            return "    (none)"
        lines = []
        for name, val in src_list:
            lines.append(f"    {name:<45} {pct(val)}")
        return '\n'.join(lines)

    es = breakdown['empire_size']
    game = game_reported or country_data.get('empire_size')

    print(SEP)
    print(f" EMPIRE SIZE BREAKDOWN — Country {DEFAULT_COUNTRY_ID}: {country_data['name']}")
    print(SEP)
    print()

    # ── PLANET MODIFIERS SUMMARY ──
    asc = breakdown['ascension_summary']
    if any(t > 0 for t in asc):
        print("PLANET ASCENSION TIERS:")
        asc_eff = breakdown['ascension_effect_mult']
        for tier in sorted(asc.keys()):
            if tier == 0:
                continue
            reduction = tier * ASCENSION_TIER_BASE_REDUCTION * (1.0 + asc_eff)
            print(f"    Tier {tier}: {asc[tier]} planets  "
                  f"(−{reduction*100:.1f}% to pops/districts/colony)")
        if asc.get(0, 0) > 0:
            print(f"    Tier 0: {asc[0]} planets  (no reduction)")
        print(f"  planetary_ascension_effect_mult = {pct(asc_eff)}:")
        print(fmt_sources(modifiers['ascension_effect_sources']))
        print()

    gov = breakdown['governor_summary']
    if gov['planets_with_governor'] > 0:
        print("GOVERNOR EFFECTS:")
        print(f"    {gov['planets_with_governor']} planets with governor coverage")
        print(f"    Total pops reduction from governors: {gov['total_pops_reduction']:.2f}")
        print()

    # ── POPULATIONS ──
    total_pops = sum(d['count'] for d in breakdown['pops_detail'].values())
    print(f"POPULATIONS  [{total_pops:,} pops]")
    print(f"  Base:  {total_pops:,} × {BASE['pops']} = {total_pops * BASE['pops']:.2f}")
    print()
    print("  Per-species species_empire_size_mult:")
    for sp_id, det in sorted(breakdown['pops_detail'].items(),
                              key=lambda x: -x[1]['raw_contribution']):
        traits_note = ""
        if sp_id in species_data:
            evopred = species_data[sp_id].get('evopred_count', 0)
            if evopred:
                traits_note = f"  [{evopred} evopred traits]"
        print(f"    species {sp_id}: {det['count']:>8,} pops  "
              f"mult={pct(det['species_mult'])}  "
              f"raw={det['raw_contribution']:7.2f}{traits_note}")
    print(f"  Raw pops (species mults only):          {breakdown['pops_raw']:.2f}")
    print(f"  After governor + ascension:             {breakdown['pops_after_planet_mods']:.2f}")
    print()
    print(f"  empire_size_pops_mult = {pct(breakdown['pops_mult'])}:")
    print(fmt_sources(modifiers['sources']['pops']))
    print(f"  POPS COMPONENT: {breakdown['pops_after_planet_mods']:.2f}"
          f" × (1 {pct(breakdown['pops_mult'])})"
          f" = {breakdown['pops_component']:.1f}")
    print()

    # ── DISTRICTS ──
    total_dl = breakdown['total_district_levels']
    print(f"DISTRICTS  [{total_dl} total district levels across all owned planets]")
    print(f"  Base:  {total_dl} × {BASE['districts']} = {breakdown['districts_raw']:.1f}")
    print(f"  After ascension:                        {breakdown['districts_after_planet_mods']:.1f}")
    print(f"  empire_size_districts_mult = {pct(breakdown['districts_mult'])}:")
    print(fmt_sources(modifiers['sources']['districts']))
    print(f"  DISTRICTS COMPONENT: {breakdown['districts_after_planet_mods']:.1f}"
          f" × (1 {pct(breakdown['districts_mult'])})"
          f" = {breakdown['districts_component']:.1f}")
    print()

    # ── SYSTEMS ──
    print(f"SYSTEMS  [{total_systems} owned systems]")
    if systems_excluded > 0:
        print(f"  Starbases matched by fleet: {systems_total_matched}  "
              f"(excluded {systems_excluded} orbital rings/DSCs)")
    print(f"  Base:  {total_systems} × {BASE['systems']} = {float(total_systems):.1f}")
    print(f"  empire_size_systems_mult = {pct(breakdown['systems_mult'])}:")
    print(fmt_sources(modifiers['sources']['systems']))
    print(f"  SYSTEMS COMPONENT: {breakdown['systems_component']:.1f}")
    print()

    # ── COLONIES ──
    n_col = len(country_data['owned_planets'])
    print(f"COLONIES  [{n_col} owned planets]")
    print(f"  Base:  {n_col} × {BASE['colonies']} = {breakdown['colonies_raw']:.1f}")
    print(f"  After ascension:                        {breakdown['colonies_after_planet_mods']:.1f}")
    print(f"  empire_size_colonies_mult = {pct(breakdown['colonies_mult'])}:")
    print(fmt_sources(modifiers['sources']['colonies']))
    print(f"  COLONIES COMPONENT: {breakdown['colonies_after_planet_mods']:.1f}"
          f" × (1 {pct(breakdown['colonies_mult'])})"
          f" = {breakdown['colonies_component']:.1f}")
    print()

    # ── GLOBAL MULT ──
    print(f"GLOBAL empire_size_mult = {pct(breakdown['total_mult'])}:")
    print(fmt_sources(modifiers['sources']['total']))
    print()

    # ── TOTALS ──
    print(SEP)
    print(f"  Subtotal (before global mult):  {breakdown['subtotal']:.2f}")
    print(f"  × (1 {pct(breakdown['total_mult'])}) = {breakdown['total_mult']+1:.3f}")
    print(f"  CALCULATED EMPIRE SIZE:         {es:.2f}  →  {round(es)}")
    if game is not None:
        diff = es - game
        print(f"  GAME-REPORTED EMPIRE SIZE:      {game}")
        print(f"  DISCREPANCY:                    {diff:+.2f}  ({diff/game*100:+.1f}%)")
        if abs(diff) > 2:
            print()
            print("  Per-component comparison:")
            print(f"     {'Component':<12} {'Calculated':>12}")
            print(f"     {'-'*30}")
            for comp, calc_val in [
                ('Pops', breakdown['pops_component']),
                ('Districts', breakdown['districts_component']),
                ('Systems', breakdown['systems_component']),
                ('Colonies', breakdown['colonies_component']),
            ]:
                print(f"     {comp:<12} {calc_val:>10.1f}")
    print()

    # ── GROWING PAINS ──
    neg_pct = max(0.1, min(1.0, 1.1 - 0.001 * round(es)))
    threshold = 1000
    gap = round(es) - threshold
    print(f"  negative_empire_size_percent = max(0.1, 1.1 - 0.001 × {round(es)}) = {neg_pct:.3f}")
    if gap > 0:
        print(f"  Growing Pains floor threshold: empire_size < {threshold}")
        print(f"  Current gap to threshold:      +{gap} points")
        print(f"  (Progress multiplier stuck at 0.1 minimum until gap is closed)")
    else:
        print(f"  ✓ Empire size below {threshold} — Growing Pains progress multiplier > 0.1")
    print(SEP)


# ================================================================
# MAIN
# ================================================================

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    save_folder = Path(sys.argv[1])
    country_id = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_COUNTRY_ID
    gamestate = save_folder / 'gamestate'

    if not gamestate.exists():
        print(f"Error: {gamestate} not found")
        sys.exit(1)

    gs = str(gamestate)
    print(f"Parsing: {gamestate}  (country {country_id})")

    print("Pass 1/8: species data ...")
    species_data = extract_species_data(gs)
    print(f"  → {len(species_data)} species loaded")

    print("Pass 2/8: country data ...")
    country_data = extract_country_data(gs, country_id)
    print(f"  → {len(country_data['traditions'])} traditions, "
          f"{len(country_data['technologies'])} techs, "
          f"{len(country_data['ascension_perks'])} perks, "
          f"{len(country_data['civics'])} civics, "
          f"{len(country_data['owned_planets'])} owned planets")

    print("Pass 3/8: planet data ...")
    planet_data = extract_planet_data(gs, country_data['owned_planets'])
    all_district_ids = []
    total_pops_by_species = defaultdict(float)
    for pid, pd in planet_data.items():
        all_district_ids.extend(pd['district_ids'])
        for sp_id, npops in pd['species_pops'].items():
            total_pops_by_species[sp_id] += npops
    # Summarize ascension tiers
    asc_counts = defaultdict(int)
    for pd in planet_data.values():
        asc_counts[pd['ascension_tier']] += 1
    asc_note = ', '.join(f"T{t}:{c}" for t, c in sorted(asc_counts.items()) if t > 0)
    print(f"  → {len(all_district_ids)} district refs, "
          f"{sum(total_pops_by_species.values()):.0f} pops, "
          f"ascension: {asc_note or 'none'}")

    print("Pass 4/8: district levels ...")
    district_levels = extract_district_levels(gs, all_district_ids)
    total_district_levels = sum(district_levels.values())
    missing_districts = len(all_district_ids) - len(district_levels)
    print(f"  → {total_district_levels} total district levels "
          f"(from {len(district_levels)} unique IDs)")
    if missing_districts:
        print(f"  ⚠ {missing_districts} district IDs not found in districts= section")

    owned_fleets = country_data.get('owned_fleets', [])
    print(f"Pass 5/8: owned systems ({len(owned_fleets)} owned fleets) ...")
    total_systems, systems_total_matched, systems_excluded = count_owned_systems(gs, owned_fleets)
    print(f"  → {total_systems} owned systems "
          f"({systems_total_matched} matched, {systems_excluded} excluded)")

    # Collect all governor leader IDs from planet data
    governor_ids = set()
    for pd in planet_data.values():
        if pd.get('governor') is not None:
            governor_ids.add(pd['governor'])

    print("Pass 6/8: leader data ...")
    leader_data = extract_leader_data(gs, governor_ids)
    print(f"  → {len(leader_data)} leaders loaded "
          f"(skills: {', '.join(str(ld['skill']) for ld in leader_data.values()) or 'none'})")

    print("Pass 7/8: sector data ...")
    sector_data = extract_sector_data(gs, country_id)
    # Collect sector governor IDs (from capital planets' governor field)
    for sec in sector_data.values():
        cap = sec['local_capital']
        if cap is not None and cap in planet_data:
            gov = planet_data[cap].get('governor')
            if gov is not None:
                governor_ids.add(gov)
    # Re-fetch any newly discovered governors
    missing_govs = governor_ids - set(leader_data.keys())
    if missing_govs:
        extra_leaders = extract_leader_data(gs, missing_govs)
        leader_data.update(extra_leaders)
        print(f"  → {len(sector_data)} sectors, +{len(extra_leaders)} sector governors loaded")
    else:
        print(f"  → {len(sector_data)} sectors")

    print("Pass 8/8: galactic objects (planet→sector map) ...")
    planet_sector_map = build_planet_to_sector_map(gs, sector_data, planet_data)
    mapped = sum(1 for p in planet_data if p in planet_sector_map)
    print(f"  → {mapped}/{len(planet_data)} planets mapped to sectors")

    print()
    modifiers = calculate_active_modifiers(
        country_data, species_data, dict(total_pops_by_species))

    breakdown = calculate_breakdown(
        planet_data, district_levels, total_systems,
        modifiers, species_data, leader_data, planet_sector_map
    )

    print_report(
        breakdown, country_data, modifiers, species_data,
        total_systems, systems_total_matched, systems_excluded,
        game_reported=country_data.get('empire_size')
    )


if __name__ == '__main__':
    main()
