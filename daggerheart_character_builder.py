# Daggerheart Character Builder (step‑by‑step)
# -------------------------------------------
#
# This module provides a data‑driven, archetype‑free character
# creation system for the Daggerheart role‑playing game.  It allows
# callers (for example, a web UI) to guide the player through each
# stage of character creation and level advancement without relying on
# random archetype heuristics.  All class, subclass, ancestry,
# community and domain card data are loaded from the SRD and the
# Creation Package, and all canonically published domain cards are
# available.  The primary trait for each class is exposed to help
# guide trait allocation.

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any


@dataclass
class Heritage:
    """Represents a heritage composed of an ancestry and a community."""
    ancestry: str
    ancestry_features: Tuple[str, str]
    community: str
    community_feature: str


@dataclass
class Character:
    """Represents a Daggerheart character as it is built level by level."""
    name: Optional[str] = None
    level: int = 1
    char_class: Optional[str] = None
    subclass: Optional[str] = None
    heritage: Optional[Heritage] = None
    traits: Dict[str, int] = field(default_factory=dict)
    experiences: List[str] = field(default_factory=list)
    hp: int = 0
    evasion: int = 0
    proficiency: int = 1
    stress: int = 6
    hope: int = 2
    # Equipment selections (set via apply_equipment)
    equipment: Dict[str, str] = field(default_factory=dict)
    armor_thresholds: Tuple[int, int] = (0, 0)
    armor_score: int = 0
    damage_roll: Optional[str] = None
    # Domain cards chosen so far
    domain_cards: List[str] = field(default_factory=list)
    # Record of advancements chosen at each level
    advancements_log: Dict[int, List[str]] = field(default_factory=dict)
    # Track subclass upgrades (e.g. specialization, mastery)
    subclass_upgrades: List[str] = field(default_factory=list)
    # Store base stats so equipment can reset values
    base_hp: int = 0
    base_evasion: int = 0
    base_traits: Dict[str, int] = field(default_factory=dict)

    def record_advancement(self, level: int, description: str) -> None:
        self.advancements_log.setdefault(level, []).append(description)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_json_file(filename: str) -> Any:
    """Load a JSON file from the module directory or repo root."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, filename),
        os.path.join(os.path.dirname(here), filename),
        os.path.join(os.path.dirname(here), 'public', filename),
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    raise FileNotFoundError(f"{filename} not found in {candidates}")


# Load the complete list of domain cards.  Each entry has the keys
# name, domain, level, type, recall_cost and description.  Cards whose
# level is None are treated as unusable for character creation and are
# filtered out in helper functions.
DOMAIN_CARDS: List[Dict[str, Any]] = _load_json_file('domain_cards.json')


# ---------------------------------------------------------------------------
# Canonical data tables (classes, subclasses, ancestries, communities)
# ---------------------------------------------------------------------------

@dataclass
class ClassInfo:
    name: str
    hp: int
    evasion: int
    domains: Tuple[str, str]
    feature: str
    subclasses: Tuple[str, str]


@dataclass
class SubclassInfo:
    name: str
    spellcast_trait: str
    foundation: str
    specialization: str
    mastery: str


# Starting HP/Evasion and domains follow the SRD.  Features are
# descriptive text summarising the class ability as in the SRD.  Each
# class lists the names of its two subclasses.  These definitions can
# be extended or modified if future expansions add more subclasses.
CLASSES: Dict[str, ClassInfo] = {
    'Bard': ClassInfo('Bard', 5, 10, ('Grace', 'Codex'),
                      'Make a Scene: spend Hope to distract a foe within Close range',
                      ('Troubadour', 'Wordsmith')),
    'Druid': ClassInfo('Druid', 6, 10, ('Sage', 'Arcana'),
                      'Evolution: spend Hope to transform into Beastform without Stress',
                      ('Warden of the Elements', 'Warden of Renewal')),
    'Guardian': ClassInfo('Guardian', 7, 9, ('Valor', 'Blade'),
                         'Frontline Tank: spend Hope to clear 2 Armor Slots',
                         ('Stalwart', 'Vengeance')),
    'Ranger': ClassInfo('Ranger', 6, 12, ('Bone', 'Sage'),
                       'Hold Them Off: spend Hope to attack multiple foes',
                       ('Beastbound', 'Wayfinder')),
    'Rogue': ClassInfo('Rogue', 6, 12, ('Midnight', 'Grace'),
                      "Rogue's Dodge: spend Hope to boost your Evasion", 
                      ('Nightwalker', 'Syndicate')),
    'Seraph': ClassInfo('Seraph', 7, 9, ('Splendor', 'Valor'),
                        'Life Support: spend Hope to clear a Hit Point on an ally',
                        ('Divine Wielder', 'Winged Sentinel')),
    'Sorcerer': ClassInfo('Sorcerer', 6, 10, ('Arcana', 'Midnight'),
                         'Volatile Magic: spend Hope to reroll damage dice',
                         ('Elemental Origin', 'Primal Origin')),
    'Warrior': ClassInfo('Warrior', 6, 11, ('Blade', 'Bone'),
                        'No Mercy: spend Hope to gain a bonus to attack rolls',
                        ('Call of the Brave', 'Call of the Slayer')),
    'Wizard': ClassInfo('Wizard', 5, 11, ('Codex', 'Splendor'),
                       'Not This Time: spend Hope to force an adversary to reroll',
                       ('School of Knowledge', 'School of War')),
}


# Subclass definitions.  Spellcast trait indicates which trait is used when
# casting spells for that subclass.  Feature names summarise the
# subclass progression; they are purely descriptive in this code.
SUBCLASSES: Dict[str, Dict[str, SubclassInfo]] = {
    'Bard': {
        'Troubadour': SubclassInfo('Troubadour', 'Presence',
                                   'Gifted Performer', 'Well‑Traveled', 'Epic Poetry'),
        'Wordsmith': SubclassInfo('Wordsmith', 'Presence',
                                  'Cutting Words', 'Silver Tongue', 'Master of Rhetoric'),
    },
    'Druid': {
        'Warden of the Elements': SubclassInfo('Warden of the Elements', 'Instinct',
                                               'Elemental Incarnation', 'Elemental Aura', 'Elemental Dominion'),
        'Warden of Renewal': SubclassInfo('Warden of Renewal', 'Instinct',
                                          'Regeneration', 'Regenerative Reach', 'Verdant Renewal'),
    },
    'Guardian': {
        'Stalwart': SubclassInfo('Stalwart', 'Strength',
                                 'Unwavering', 'Unrelenting', 'Immovable'),
        'Vengeance': SubclassInfo('Vengeance', 'Strength',
                                  'At Ease', 'Act of Reprisal', 'Vengeful Spirit'),
    },
    'Ranger': {
        'Beastbound': SubclassInfo('Beastbound', 'Agility',
                                   'Companion', 'Coordinated Attack', 'Inseparable'),
        'Wayfinder': SubclassInfo('Wayfinder', 'Agility',
                                  'Forager', "Hunter's Mark", 'Master of the Hunt'),
    },
    'Rogue': {
        'Nightwalker': SubclassInfo('Nightwalker', 'Finesse',
                                    'Shadow Step', 'Dark Cloud', 'One with the Shadows'),
        'Syndicate': SubclassInfo('Syndicate', 'Finesse',
                                  'Black Market Connections', 'Contacts Everywhere', 'Pulling Strings'),
    },
    'Seraph': {
        'Divine Wielder': SubclassInfo('Divine Wielder', 'Strength',
                                       'Sparing Touch', 'Devout', 'Divine Intervention'),
        'Winged Sentinel': SubclassInfo('Winged Sentinel', 'Strength',
                                        'Wings of Light', 'Ethereal Visage', 'Ascendant'),
    },
    'Sorcerer': {
        'Elemental Origin': SubclassInfo('Elemental Origin', 'Instinct',
                                         'Elementalist', 'Natural Evasion', 'Transcendence'),
        'Primal Origin': SubclassInfo('Primal Origin', 'Instinct',
                                      'Manipulate Magic', 'Enchanted Aid', 'Arcane Charge'),
    },
    'Warrior': {
        'Call of the Brave': SubclassInfo('Call of the Brave', 'Strength',
                                          'Courage', 'Rise to the Challenge', 'Fearless'),
        'Call of the Slayer': SubclassInfo('Call of the Slayer', 'Strength',
                                           'Slayer', 'Weapon Specialist', 'Unstoppable Carnage'),
    },
    'Wizard': {
        'School of Knowledge': SubclassInfo('School of Knowledge', 'Knowledge',
                                            'Prepared', 'Accomplished', 'Brilliant'),
        'School of War': SubclassInfo('School of War', 'Knowledge',
                                      'Battlemage', 'Conjure Shield', 'Thrive in Chaos'),
    },
}


# Primary trait suggestions per class.  These guide players when
# allocating their +2, +1, +1, 0, 0, -1 modifiers.  For example, a
# Sorcerer should invest heavily in Instinct and secondary points in
# Presence and Knowledge.  These values are suggestions; players may
# allocate traits however they wish.
CLASS_PRIMARY_TRAIT: Dict[str, str] = {
    'Bard': 'Presence',
    'Druid': 'Instinct',
    'Guardian': 'Strength',
    'Ranger': 'Agility',
    'Rogue': 'Finesse',
    'Seraph': 'Strength',
    'Sorcerer': 'Instinct',
    'Warrior': 'Strength',
    'Wizard': 'Knowledge',
}


# Canonical ancestries and their two features.  These values come
# directly from the Creation Package.  D&D terms such as "Fey
# Ancestry" and "Nimble Escape" have been removed in favour of the
# published Daggerheart features【373724897915597†L1890-L1920】.
ANCESTRIES: Dict[str, Tuple[str, str]] = {
    'Clank': (
        'Purposeful Design: Choose one Experience that aligns with your purpose; gain a permanent +1 bonus to it.',
        'Efficient: When you take a short rest, you can choose a long rest move instead.'
    ),
    'Drakona': (
        'Scales: When you would take Severe damage, mark a Stress to mark 1 fewer HP.',
        'Elemental Breath: Use an Instinct‑based weapon attack (d8 magic damage) within Very Close range.'
    ),
    'Dwarf': (
        'Thick Skin: When you take Minor damage, you can mark 2 Stress instead of 1 HP.',
        'Increased Fortitude: Spend 3 Hope to halve incoming physical damage.'
    ),
    'Elf': (
        'Quick Reactions: Mark a Stress to gain advantage on a reaction roll.',
        'Celestial Trance: During a long rest, you may enter a trance instead of sleeping; after the first six hours you may take an additional downtime move【373724897915597†L1890-L1920】.'
    ),
    'Faerie': (
        'Luckbender: Once per session, spend 3 Hope to reroll both Duality dice.',
        'Wings: You can fly; when you mark a Stress due to being attacked, gain +2 Evasion until the end of the round【373724897915597†L1932-L1941】.'
    ),
    'Faun': (
        'Caprine Leap: Once per rest, jump anywhere within Close range.',
        'Kick: You have a natural Melee weapon (d6 damage); mark a Stress to add +2 damage【373724897915597†L1958-L1964】.'
    ),
    'Firbolg': (
        'Charge: Move from Far into Melee and mark a Stress to deal 1d12 physical damage to all targets in Melee【373724897915597†L1981-L1987】.',
        'Unshakable: When you would mark a Stress, roll a d6; on a 6, ignore the Stress【373724897915597†L1981-L1987】.'
    ),
    'Fungril': (
        'Fungril Network: Telepathically communicate with other Fungril within Close range【373724897915597†L1991-L2002】.',
        'Death Connection: When a living creature dies within Close range, gain a fleeting memory or sensation【373724897915597†L1991-L2010】.'
    ),
    'Galapa': (
        'Shell: Add your Proficiency to your damage thresholds (both minor and major).',
        'Retract: Mark a Stress to withdraw into your shell; you cannot move but reduce all incoming physical damage to 0 until the start of your next turn【373724897915597†L2043-L2046】.'
    ),
    'Giant': (
        'Reach: Your melee attacks have a longer reach (add one range band).',
        'Endurance: Gain an additional Hit Point slot【373724897915597†L2043-L2046】.'
    ),
    'Goblin': (
        'Surefooted: You have advantage on Balance rolls and resist being knocked prone【373724897915597†L2061-L2064】.',
        'Danger Sense: You have advantage on Initiative and Awareness rolls【373724897915597†L2061-L2064】.'
    ),
    'Halfling': (
        'Luckbringer: Once per session, reroll a Duality result; you must take the new result【373724897915597†L2078-L2081】.',
        'Internal Compass: You always know which direction is north and cannot become lost【373724897915597†L2078-L2081】.'
    ),
    'Human': (
        'High Stamina: Gain an additional Stress slot【373724897915597†L2096-L2099】.',
        'Adaptability: Once per session, after you fail a roll, you may change one of your Experiences to better fit the current situation【373724897915597†L2096-L2099】.'
    ),
    'Infernis': (
        'Fearless: You are immune to the Frightened condition.',
        'Dread Visage: As a reaction when an adversary targets you, spend 2 Hope to force them to make a Presence roll against DC 12; on a failure they cannot target you this turn【373724897915597†L2124-L2127】.'
    ),
    'Katari': (
        'Feline Instincts: You can reroll an Agility roll once per rest【373724897915597†L2142-L2146】.',
        'Retracting Claws: You have a natural weapon (d6 physical damage); you may retract or extend your claws at will【373724897915597†L2142-L2146】.'
    ),
    'Orc': (
        'Aggressive: As a bonus action, move up to your speed toward a foe.',
        'Powerful Build: You count as one size larger for carrying capacity.'
    ),
    'Ribbet': (
        'Amphibious: You can breathe air and water.',
        'Sticky Tongue: You have a natural weapon with Close range that can pull smaller objects or creatures toward you.'
    ),
    'Simiah': (
        'Prehensile Tail: You can use your tail to hold or manipulate an object.',
        'Nimble: Gain a permanent +1 bonus to your Evasion.'
    ),
}


# Communities and their single features (from the Creation Package)
COMMUNITIES: Dict[str, str] = {
    'Highborne': 'Privilege: You have advantage on rolls when interacting with nobles or negotiating prices【373724897915597†L2274-L2276】.',
    'Loreborne': 'Well‑Read: You have advantage on Knowledge rolls involving history, politics or religion【373724897915597†L2293-L2294】.',
    'Orderborne': 'Dedicated: When you follow a clear plan or order, gain advantage on the first action roll to execute it【373724897915597†L2311-L2315】.',
    'Ridgeborne': 'Steady: You have advantage when traversing dangerous terrain or climbing【373724897915597†L2339-L2341】.',
    'Seaborne': 'Know the Tide: Collect tide tokens when you roll with Fear; spend them to add bonuses to Instinct rolls【373724897915597†L2364-L2369】.',
    'Slyborne': 'Scoundrel: You have advantage on Pickpocket and Deception rolls【373724897915597†L2386-L2388】.',
    'Underborne': 'Low‑Light Living: You can see clearly in dim light and complete darkness【373724897915597†L2406-L2409】.',
    'Wanderborne': 'Nomadic Pack: When travelling with a group, you can always find food and shelter for everyone【373724897915597†L2431-L2433】.',
    'Wildborne': 'Lightfoot: You have advantage on stealth rolls when moving through wilderness【373724897915597†L2452-L2453】.',
}


# Trait names used throughout the game
TRAITS: List[str] = ['Strength', 'Finesse', 'Agility', 'Instinct', 'Presence', 'Knowledge']


# ---------------------------------------------------------------------------
# Character creation functions
# ---------------------------------------------------------------------------

def list_ancestries() -> List[str]:
    """Return the list of available ancestries."""
    return list(ANCESTRIES.keys())


def list_communities() -> List[str]:
    """Return the list of available communities."""
    return list(COMMUNITIES.keys())


def list_classes() -> List[str]:
    """Return the list of available classes."""
    return list(CLASSES.keys())


def list_subclasses(class_name: str) -> List[str]:
    """Return the list of subclasses for a given class."""
    return list(SUBCLASSES[class_name].keys())


def recommend_trait_allocation(class_name: str) -> Dict[str, int]:
    """
    Provide a recommended distribution of trait modifiers for the given class.

    Characters in Daggerheart begin with modifiers +2, +1, +1, 0, 0 and –1.
    This function assigns +2 to the class's primary trait and +1 to two
    secondary traits.  Secondary traits are chosen arbitrarily here but
    can be adjusted.  The remaining traits receive +0 and the least
    important trait receives –1.
    """
    base_mods = [2, 1, 1, 0, 0, -1]
    primary = CLASS_PRIMARY_TRAIT[class_name]
    ordered = [primary] + [t for t in TRAITS if t != primary]
    return dict(zip(ordered, base_mods))


def create_base_character(level: int, class_name: str, subclass_name: str) -> Character:
    """
    Create an initial character at level 1 with the chosen class and subclass.

    Heritage, traits, experiences and starting domain cards are not
    assigned here.  Callers should assign them using the helper
    functions below.
    """
    if class_name not in CLASSES:
        raise ValueError(f"Unknown class {class_name}")
    if subclass_name not in SUBCLASSES[class_name]:
        raise ValueError(f"Unknown subclass {subclass_name} for class {class_name}")
    ci = CLASSES[class_name]
    sc = SUBCLASSES[class_name][subclass_name]
    char = Character(
        level=level,
        char_class=ci.name,
        subclass=sc.name,
        hp=ci.hp,
        evasion=ci.evasion,
        base_hp=ci.hp,
        base_evasion=ci.evasion,
    )
    return char


def assign_heritage(character: Character, ancestry: str, community: str) -> None:
    """Assign the heritage (ancestry + community) to the character."""
    if ancestry not in ANCESTRIES or community not in COMMUNITIES:
        raise ValueError("Invalid ancestry or community selection")
    feats = ANCESTRIES[ancestry]
    com_feat = COMMUNITIES[community]
    character.heritage = Heritage(ancestry, feats, community, com_feat)


def assign_traits_for_character(character: Character, trait_alloc: Dict[str, int]) -> None:
    """Assign base trait modifiers to the character and record them."""
    # Validate trait keys
    if set(trait_alloc.keys()) != set(TRAITS):
        raise ValueError("Trait allocation must specify all traits")
    # Validate that the modifiers sum to 3 (+2 +1 +1 +0 +0 -1)
    mods = sorted(trait_alloc.values(), reverse=True)
    if mods != [2, 1, 1, 0, 0, -1]:
        raise ValueError("Invalid trait allocation; must be [+2, +1, +1, 0, 0, -1] in some order")
    character.traits = dict(trait_alloc)
    character.base_traits = dict(trait_alloc)


def assign_experiences(character: Character) -> None:
    """
    Assign two default experiences for level 1 based solely on class.
    The SRD encourages players to invent their own experiences; here we
    provide generic ones based on the class name.
    """
    char_class = character.char_class
    if not char_class:
        return
    exp1 = f"Wanderer {char_class}"
    exp2 = f"Adventurer {char_class}"
    character.experiences = [exp1, exp2]


def choose_domain_cards_for_level(character: Character, level: int, chosen: Optional[List[str]] = None) -> List[str]:
    """
    Given a character and a level, return the list of available domain cards
    from the character's class domains.  If `chosen` is provided, it must
    contain one or two card names selected from this list; those will be
    added to the character.  Otherwise this function returns the list
    for the caller to present to the user.
    """
    domains = CLASSES[character.char_class].domains
    eligible = [c for c in DOMAIN_CARDS
                if c['domain'] in domains
                and c.get('level') is not None
                and c['level'] <= level
                and c['name'] not in character.domain_cards]
    # Return names and descriptions for UI display
    options = [f"{c['name']}: {c['description']}" for c in eligible]
    if chosen:
        # Validate chosen cards
        valid_names = {c['name'] for c in eligible}
        for name in chosen:
            if name not in valid_names:
                raise ValueError(f"Invalid domain card selection: {name}")
        for name in chosen:
            character.domain_cards.append(name)
        character.record_advancement(level, f"Chose domain card(s): {', '.join(chosen)}")
    return options


def increase_damage_thresholds(character: Character, level: int) -> None:
    """Increase damage thresholds at level up (represented as +1 HP)."""
    character.hp += 1
    character.record_advancement(level, "Damage thresholds increased (+1 HP)")


def apply_advancement(character: Character, level: int, choice: str) -> None:
    """
    Apply a single advancement choice at the given level.  Advancements may
    include increasing traits, adding HP, gaining Stress, improving
    Evasion, taking a new experience, or adding domain cards.  Choices
    must be one of a fixed set of strings.  This function records the
    advancement description.
    """
    if choice == 'Increase 2 traits':
        # Increase the two lowest traits by +1
        for _ in range(2):
            t = min(character.traits, key=character.traits.get)
            character.traits[t] += 1
        character.record_advancement(level, "Increased two traits by +1")
    elif choice == 'Gain 1 HP':
        character.hp += 1
        character.record_advancement(level, "Gained an extra Hit Point slot")
    elif choice == 'Gain 1 Stress':
        character.stress += 1
        character.record_advancement(level, "Gained an extra Stress slot")
    elif choice == 'Increase Evasion':
        character.evasion += 1
        character.record_advancement(level, "Increased Evasion by +1")
    elif choice == 'New Experience':
        exp = f"Level {level} Experience"
        character.experiences.append(exp)
        character.record_advancement(level, f"Added experience: {exp}")
    else:
        raise ValueError(f"Unknown advancement choice: {choice}")


def available_advancements() -> List[str]:
    """
    Return the list of available advancement options for level up.  At
    each level the player chooses two of these.  Domain cards are
    handled separately via choose_domain_cards_for_level.
    """
    return [
        'Increase 2 traits',
        'Gain 1 HP',
        'Gain 1 Stress',
        'Increase Evasion',
        'New Experience',
    ]


def apply_subclass_upgrade(character: Character, level: int) -> None:
    """
    Apply subclass upgrades at levels 5 and 8.  Characters gain
    specialization at level 5 and mastery at level 8.  This function
    records these upgrades in the character sheet.
    """
    if level == 5 and 'Specialization' not in character.subclass_upgrades:
        character.subclass_upgrades.append('Specialization')
        character.record_advancement(level, f"Gained subclass specialization ({character.subclass})")
    elif level == 8 and 'Mastery' not in character.subclass_upgrades:
        character.subclass_upgrades.append('Mastery')
        character.record_advancement(level, f"Gained subclass mastery ({character.subclass})")


# Example utility function for a full level up (levels 2–10).  A UI would
# prompt the user for two advancement choices and optional domain card
# selections at each level.  This function applies default actions if
# choices are not provided.
def level_up(character: Character, level: int, advancement_choices: Optional[List[str]] = None,
             domain_card_choices: Optional[List[str]] = None) -> None:
    """
    Perform a single level up.  Tier achievements occur at levels 2, 5 and
    8: gain +1 proficiency and a new experience, and clear trait marks
    (not modelled explicitly here).  The caller should provide exactly
    two advancement choices or leave it None to apply default (increase
    two traits twice).  Domain card choices, if provided, must be
    selected from the list returned by choose_domain_cards_for_level.
    """
    # Tier achievements
    if level in {2, 5, 8}:
        character.proficiency += 1
        exp = f"Tier {level} Experience"
        character.experiences.append(exp)
        character.record_advancement(level, f"Tier achievement: +1 Proficiency, gained experience {exp}")
    # Subclass upgrades
    apply_subclass_upgrade(character, level)
    # Apply two advancements
    if advancement_choices:
        if len(advancement_choices) != 2:
            raise ValueError("Exactly two advancement choices required per level")
        for choice in advancement_choices:
            apply_advancement(character, level, choice)
    else:
        # Default: increase two traits twice
        for _ in range(2):
            apply_advancement(character, level, 'Increase 2 traits')
    # Increase damage thresholds
    increase_damage_thresholds(character, level)
    # Domain card acquisition
    available = choose_domain_cards_for_level(character, level)
    if domain_card_choices:
        choose_domain_cards_for_level(character, level, domain_card_choices)
    else:
        # Default: pick the first available card
        names = [c.split(':')[0] for c in available]
        if names:
            choose_domain_cards_for_level(character, level, [names[0]])


__all__ = [
    'Character', 'Heritage', 'ClassInfo', 'SubclassInfo', 'CLASSES', 'SUBCLASSES',
    'ANCESTRIES', 'COMMUNITIES', 'CLASS_PRIMARY_TRAIT', 'TRAITS',
    'list_ancestries', 'list_communities', 'list_classes', 'list_subclasses',
    'recommend_trait_allocation', 'create_base_character', 'assign_heritage',
    'assign_traits_for_character', 'assign_experiences', 'choose_domain_cards_for_level',
    'increase_damage_thresholds', 'available_advancements', 'apply_advancement',
    'apply_subclass_upgrade', 'level_up'
]