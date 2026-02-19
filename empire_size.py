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

# --- Governor skill effects (NOT yet parsed by this script) ---
# Planet governors: species_empire_size_mult = -0.02 per skill level
# Sector governors: species_empire_size_mult = -0.01 per skill level
# Source: common/static_modifiers/00_static_modifiers.txt
# A level-8 planet governor reduces all pops on that planet by -16% empire size.
# To include this, parse governor skill levels from the leaders= section
# and weight by pops on each planet. This is the main source of the pops gap.
# Estimated total effect: -10% to -25% additional empire_size_pops_mult

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

    return data


def extract_planet_data(gamestate_path, owned_planet_ids):
    """
    For each owned planet, extract:
      - district IDs (from districts={...} array)
      - pops per species (from species_information={N={num_pops=X}})
    Returns: {planet_id: {'district_ids': [int], 'species_pops': {species_id: int}}}
    """
    owned_set = set(owned_planet_ids)
    planet_data = {pid: {'district_ids': [], 'species_pops': {}} for pid in owned_set}

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


def count_owned_systems(gamestate_path, country_graphical_culture):
    """
    Count systems owned by this country using the starbase_mgr section.
    Strategy: each starbase entry has station=N where N is a ship ID.
    That ship has a graphical_culture matching the owning country.

    NOTE: This counts all starbases including orbital platforms.
    Orbital platforms add ~5-8% overcounting vs game-reported system count
    (e.g., 466 counted vs 432 actual). The overcounting is documented in output.
    """
    # Build ship_id -> graphical_culture from the ships section
    ship_culture = {}
    in_ships = False
    ship_id = None

    for depth, line in stream_lines(gamestate_path):
        if not in_ships:
            if depth == 0 and re.match(r'^ships=', line):
                in_ships = True
            continue
        if depth == 0 and line not in ('{', '}'):
            break
        if depth == 1:
            m = re.match(r'^(\d+)=', line)
            if m:
                ship_id = int(m.group(1))
        if depth == 2 and ship_id is not None:
            m = re.match(r'^graphical_culture="([^"]+)"', line)
            if m:
                ship_culture[ship_id] = m.group(1)

    # Count starbases for this culture
    count = 0
    in_sm = False
    sb_id = None

    for depth, line in stream_lines(gamestate_path):
        if not in_sm:
            if depth == 0 and re.match(r'^starbase_mgr=', line):
                in_sm = True
            continue
        if depth == 0 and line not in ('{', '}'):
            break
        if depth == 2:
            m = re.match(r'^(\d+)=', line)
            if m:
                sb_id = int(m.group(1))
        if depth == 3 and sb_id is not None:
            m = re.match(r'^station=(\d+)', line)
            if m:
                ship_n = int(m.group(1))
                if ship_culture.get(ship_n) == country_graphical_culture:
                    count += 1

    return count


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

    return {**mods, 'sources': sources, 'species_mults': species_mults}


# ================================================================
# EMPIRE SIZE CALCULATOR
# ================================================================

def calculate_breakdown(
    total_pops_by_species,  # {species_id: pop_count}
    total_district_levels,  # int (sum of all owned district levels)
    total_systems,          # int
    total_colonies,         # int (owned_planets count)
    modifiers,              # from calculate_active_modifiers
    species_data            # for display labels
):
    """
    Calculate empire size breakdown by component.
    Formula:
      pops_raw     = Σ (pops_of_species * BASE_pops * (1 + species_empire_size_mult))
      pops_comp    = pops_raw * (1 + empire_size_pops_mult)
      dist_comp    = total_districts * BASE_dist * (1 + empire_size_districts_mult)
      sys_comp     = total_systems  * BASE_sys  * (1 + empire_size_systems_mult)
      col_comp     = total_colonies * BASE_col  * (1 + empire_size_colonies_mult)
      subtotal     = pops_comp + dist_comp + sys_comp + col_comp
      empire_size  = subtotal * (1 + empire_size_mult)
    Returns detailed breakdown dict.
    """
    sm = modifiers['species_mults']

    # Pop contributions by species
    pops_detail = {}
    pops_raw = 0.0
    for sp_id, count in total_pops_by_species.items():
        sp_mult = sm.get(sp_id, 0.0)
        contribution = count * BASE['pops'] * (1.0 + sp_mult)
        pops_detail[sp_id] = {
            'count': count,
            'species_mult': sp_mult,
            'raw_contribution': contribution,
        }
        pops_raw += contribution

    pops_mult = modifiers['pops']
    pops_component = pops_raw * (1.0 + pops_mult)

    districts_mult = modifiers['districts']
    districts_component = total_district_levels * BASE['districts'] * (1.0 + districts_mult)

    systems_mult = modifiers['systems']
    systems_component = total_systems * BASE['systems'] * (1.0 + systems_mult)

    colonies_mult = modifiers['colonies']
    colonies_component = total_colonies * BASE['colonies'] * (1.0 + colonies_mult)

    subtotal = pops_component + districts_component + systems_component + colonies_component
    total_mult = modifiers['total']
    empire_size = subtotal * (1.0 + total_mult)

    return {
        'pops_raw': pops_raw,
        'pops_component': pops_component,
        'pops_detail': pops_detail,
        'pops_mult': pops_mult,
        'districts_component': districts_component,
        'districts_mult': districts_mult,
        'systems_component': systems_component,
        'systems_mult': systems_mult,
        'colonies_component': colonies_component,
        'colonies_mult': colonies_mult,
        'subtotal': subtotal,
        'total_mult': total_mult,
        'empire_size': empire_size,
    }


# ================================================================
# REPORT
# ================================================================

def print_report(breakdown, country_data, modifiers, species_data,
                 total_districts, total_systems, game_reported=None,
                 orbital_note=False):
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
    print(f"  Raw pops subtotal (after per-species mults): {breakdown['pops_raw']:.2f}")
    print()
    print(f"  empire_size_pops_mult = {pct(breakdown['pops_mult'])}:")
    print(fmt_sources(modifiers['sources']['pops']))
    print(f"  POPS COMPONENT: {breakdown['pops_raw']:.2f} × (1 {pct(breakdown['pops_mult'])}) "
          f"= {breakdown['pops_component']:.2f}")
    print()

    # ── DISTRICTS ──
    print(f"DISTRICTS  [{total_districts} total district levels across all owned planets]")
    print(f"  Base:  {total_districts} × {BASE['districts']} = {total_districts * BASE['districts']:.1f}")
    print(f"  empire_size_districts_mult = {pct(breakdown['districts_mult'])}:")
    print(fmt_sources(modifiers['sources']['districts']))
    print(f"  DISTRICTS COMPONENT: {breakdown['districts_component']:.2f}")
    print()

    # ── SYSTEMS ──
    orbital_caveat = " (incl. orbital platforms — may overcount by ~5-8%)" if total_systems > 0 else ""
    print(f"SYSTEMS  [{total_systems} starbase entries{orbital_caveat}]")
    print(f"  Base:  {total_systems} × {BASE['systems']} = {float(total_systems):.1f}")
    print(f"  empire_size_systems_mult = {pct(breakdown['systems_mult'])}:")
    print(fmt_sources(modifiers['sources']['systems']))
    print(f"  SYSTEMS COMPONENT: {breakdown['systems_component']:.2f}")
    print()

    # ── COLONIES ──
    n_col = len(country_data['owned_planets'])
    print(f"COLONIES  [{n_col} owned planets]")
    print(f"  Base:  {n_col} × {BASE['colonies']} = {n_col * BASE['colonies']:.1f}")
    print(f"  empire_size_colonies_mult = {pct(breakdown['colonies_mult'])}:")
    print(fmt_sources(modifiers['sources']['colonies']))
    print(f"  COLONIES COMPONENT: {breakdown['colonies_component']:.2f}")
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
            print("  ⚠  Per-component gap analysis (calc vs game tooltip):")
            gm = 1.0 + breakdown['total_mult']  # global multiplier factor
            # Report each component's contribution to the discrepancy
            gaps = {
                'Pops':      breakdown['pops_component'],
                'Districts': breakdown['districts_component'],
                'Systems':   breakdown['systems_component'],
                'Colonies':  breakdown['colonies_component'],
            }
            hints = {
                'Pops':      "governor species_empire_size_mult (-2%/lvl planet, -1%/lvl sector)",
                'Districts': "unknown source — check edicts, building effects",
                'Systems':   "orbital platforms overcounting — subtract ~34 for this empire",
                'Colonies':  "unknown source — check edicts or additional perk effects",
            }
            total_gap = 0
            for comp, calc_val in gaps.items():
                gap_contribution = calc_val * gm - 0  # just show calc value
                total_gap += calc_val
            # Show raw component gaps in subtotal units
            print(f"     {'Component':<12} {'Calculated':>12} {'→ Hint if gap exists'}")
            print(f"     {'-'*60}")
            for comp, calc_val in gaps.items():
                hint = hints[comp]
                print(f"     {comp:<12} {calc_val:>10.1f}   ({hint})")
            print()
            print(f"     → Add missing modifiers to SETTINGS section to close gaps")
            print(f"     → Governor effects require parsing planet governor skill levels")
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

    print(f"Parsing: {gamestate}  (country {country_id})")
    print("Pass 1/5: species data ...")
    species_data = extract_species_data(str(gamestate))
    print(f"  → {len(species_data)} species loaded")

    print("Pass 2/5: country data ...")
    country_data = extract_country_data(str(gamestate), country_id)
    print(f"  → {len(country_data['traditions'])} traditions, "
          f"{len(country_data['technologies'])} techs, "
          f"{len(country_data['ascension_perks'])} perks, "
          f"{len(country_data['owned_planets'])} owned planets")

    print("Pass 3/5: planet data ...")
    planet_data = extract_planet_data(str(gamestate), country_data['owned_planets'])
    all_district_ids = []
    total_pops_by_species = defaultdict(float)
    for pid, pd in planet_data.items():
        all_district_ids.extend(pd['district_ids'])
        for sp_id, npops in pd['species_pops'].items():
            total_pops_by_species[sp_id] += npops
    print(f"  → {len(all_district_ids)} district references, "
          f"{sum(total_pops_by_species.values()):.0f} pops across "
          f"{len(total_pops_by_species)} species")

    print("Pass 4/5: district levels ...")
    district_levels = extract_district_levels(str(gamestate), all_district_ids)
    total_district_levels = sum(district_levels.values())
    missing_districts = len(all_district_ids) - len(district_levels)
    print(f"  → {total_district_levels} total district levels "
          f"(from {len(district_levels)} unique IDs)")
    if missing_districts:
        print(f"  ⚠ {missing_districts} district IDs not found in districts= section")

    culture = country_data.get('graphical_culture', 'unknown')
    print(f"Pass 5/5: owned systems (starbases with culture='{culture}') ...")
    total_systems = count_owned_systems(str(gamestate), culture)
    print(f"  → {total_systems} owned systems")

    print()
    modifiers = calculate_active_modifiers(
        country_data, species_data, dict(total_pops_by_species))

    breakdown = calculate_breakdown(
        dict(total_pops_by_species),
        total_district_levels,
        total_systems,
        len(country_data['owned_planets']),
        modifiers,
        species_data
    )

    print_report(
        breakdown, country_data, modifiers, species_data,
        total_district_levels, total_systems,
        game_reported=country_data.get('empire_size')
    )


if __name__ == '__main__':
    main()
