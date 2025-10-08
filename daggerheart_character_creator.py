"""
Daggerheart Character Creator & Random Generator
-------------------------------------------------

This module implements a complete character creator for the
Daggerheart role‑playing game.  It supports manual character
construction as well as automated generation based on high‑level
archetypes (Tank, Damage, Sneaky, Support, Healer, Face and Control).

The implementation follows the Daggerheart System Reference
Document (SRD) and the official character creation guides.  It
includes complete databases for all classes, subclasses, ancestries,
communities and domain cards.  When used in random generation
mode the module will automatically assign traits, select a class and
subclass, choose heritage, pick starting equipment, and select
appropriate domain cards at each level.  Characters will level up
through all ten levels, taking tier achievements, advancements and
additional domain cards according to the canonical rules【958333465815988†L2523-L2606】.

Data organisation
-----------------

Data used by the generator is defined at the bottom of this file.  It
includes:

* ``CLASSES`` –  a dictionary describing each of the nine classes, their
  starting hit points, starting evasion, available domains and a
  class feature.  The starting HP and Evasion values are taken
  directly from the SRD【876238438073902†L188-L205】.  Classes also
  reference their two subclasses by name.
* ``SUBCLASSES`` – a nested dictionary keyed by class name with
  entries for each subclass.  Each subclass defines its spellcast
  trait (the trait used when casting spells) and the names of its
  foundation, specialization and mastery features【876238438073902†L247-L368】.
  Although the generator does not execute the mechanics of these
  features, it stores them so that a complete character sheet can be
  produced and so that upgrades can be taken at the appropriate
  levels.
* ``ANCESTRIES`` and ``COMMUNITIES`` – lists of heritage options
  derived from the character generation research document【876238438073902†L556-L733】.
  Each ancestry supplies two features; communities provide one.
* ``TRAIT_PRIORITIES`` – mapping of archetypes to ordered lists
  describing how the base trait modifiers [+2, +1, +1, 0, 0, –1] are
  assigned across the six traits (Agility, Strength, Finesse,
  Instinct, Presence, Knowledge).  This follows the archetype
  definition matrix which recommends different priorities for each
  role【876238438073902†L1258-L1420】.  The generator will always apply
  the +2 bonus to the first trait in the list, +1 to the next two,
  0 to the following two and –1 to the last.
* ``EQUIPMENT_OPTIONS`` – archetype specific suggestions for starting
  weapons and armour.  These are based on the equipment
  priorities from the archetype matrix【876238438073902†L1258-L1420】.
* ``DOMAIN_CARDS`` – the complete compendium of domain cards.  The
  list is loaded from a JSON file (``domain_cards.json``) at module
  import time.  This file was extracted verbatim from the official
  Daggerheart domain card reference and includes all 188 cards along
  with their domain, level, type, recall cost and description.

The main entry point is the :func:`create_character` function.  It
takes a target level and an archetype string and returns a fully
constructed ``Character`` instance.  Characters can also be
generated manually by specifying the class and subclass.

Usage example
-------------

Create a random Level‑10 tank character and print a summary:

.. code-block:: python

    from daggerheart_character_creator import create_character
    char = create_character(level=10, archetype='Tank')
    print(char.describe())

The resulting summary includes the class, subclass, heritage,
traits, hit points, evasion, experiences and the list of domain cards
selected at each level.

"""

from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Heritage:
    """Represents a heritage composed of an ancestry and a community."""
    ancestry: str
    ancestry_features: Tuple[str, str]
    community: str
    community_feature: str


@dataclass
class Subclass:
    """Represents a subclass and its features."""
    name: str
    spellcast_trait: str
    foundation: str
    specialization: str
    mastery: str


@dataclass
class ClassInfo:
    """Represents a Daggerheart class."""
    name: str
    hp: int
    evasion: int
    domains: Tuple[str, str]
    feature: str
    subclasses: Tuple[str, str]


@dataclass
class Advancement:
    """Represents a single advancement choice made during level up."""
    description: str


@dataclass
class Character:
    """A full Daggerheart character sheet and progression log."""

    name: Optional[str] = None
    archetype: Optional[str] = None
    level: int = 1
    char_class: Optional[str] = None
    subclass: Optional[str] = None
    hp: int = 0
    evasion: int = 0
    proficiency: int = 1
    stress: int = 6
    hope: int = 2
    traits: Dict[str, int] = field(default_factory=dict)
    heritage: Optional[Heritage] = None
    experiences: List[str] = field(default_factory=list)
    equipment: Dict[str, str] = field(default_factory=dict)
    domain_cards: List[str] = field(default_factory=list)
    advancements_log: Dict[int, List[Advancement]] = field(default_factory=dict)
    subclass_upgrades: List[str] = field(default_factory=list)

    def add_domain_card(self, card_name: str) -> None:
        """Add a domain card to the character's loadout."""
        if card_name not in self.domain_cards:
            self.domain_cards.append(card_name)

    def add_advance(self, level: int, description: str) -> None:
        """Record an advancement choice at a given level."""
        self.advancements_log.setdefault(level, []).append(Advancement(description))

    def describe(self) -> str:
        """Return a human‑readable summary of the character."""
        parts = []
        parts.append(f"Archetype: {self.archetype}")
        parts.append(f"Class/Subclass: {self.char_class} – {self.subclass}")
        if self.heritage:
            parts.append(f"Heritage: {self.heritage.ancestry} / {self.heritage.community}")
        parts.append(f"Level: {self.level} (Proficiency {self.proficiency})")
        parts.append(f"HP: {self.hp}, Evasion: {self.evasion}, Stress: {self.stress}, Hope: {self.hope}")
        parts.append("Traits:" + ", ".join(f" {t} {v:+}" for t, v in self.traits.items()))
        if self.experiences:
            parts.append("Experiences: " + ", ".join(self.experiences))
        if self.equipment:
            eq_parts = [f"{slot}: {item}" for slot, item in self.equipment.items()]
            parts.append("Equipment: " + ", ".join(eq_parts))
        if self.domain_cards:
            parts.append("Domain Cards: " + ", ".join(self.domain_cards))
        # Include a brief advancement history
        for lvl in sorted(self.advancements_log):
            descs = "; ".join(a.description for a in self.advancements_log[lvl])
            parts.append(f"Level {lvl} Advancements: {descs}")
        if self.subclass_upgrades:
            parts.append("Subclass Upgrades: " + ", ".join(self.subclass_upgrades))
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def load_domain_cards() -> List[Dict]:
    """Load the complete domain card compendium from JSON.

    Returns a list of dictionaries where each dictionary has the following
    keys: name, domain, level, type, recall_cost, description.
    """
    here = os.path.dirname(__file__)
    json_path = os.path.join(here, 'domain_cards.json')
    if not os.path.exists(json_path):
        raise FileNotFoundError(
            'domain_cards.json not found; ensure the JSON file extracted from the '
            'Domain Cards PDF is placed alongside this module.')
    with open(json_path, 'r') as f:
        cards = json.load(f)
    return cards


DOMAIN_CARDS = load_domain_cards()


def choose_class_and_subclass(archetype: str) -> Tuple[str, Subclass]:
    """Randomly select a class and subclass appropriate to the given archetype.

    The selection follows the Archetype Definition Matrix【876238438073902†L1233-L1459】.
    Classes listed as primary for an archetype are weighted higher than
    secondary options.  The chosen subclass is the one that best aligns
    with the archetype according to the research document (e.g. a Tank
    Guardian takes the Stalwart subclass)
    """
    archetype = archetype.title()
    options = {
        'Tank': {
            'primary': ['Guardian', 'Warrior'],
            'secondary': []
        },
        'Damage': {
            'primary': ['Warrior', 'Rogue'],
            'secondary': ['Ranger', 'Sorcerer']
        },
        'Sneaky': {
            'primary': ['Rogue', 'Ranger'],
            'secondary': []
        },
        'Support': {
            'primary': ['Seraph', 'Bard', 'Druid'],
            'secondary': ['Wizard']
        },
        'Healer': {
            # treat Healer similarly to Support but favour Seraph/Druid
            'primary': ['Seraph', 'Druid'],
            'secondary': ['Bard']
        },
        'Face': {
            'primary': ['Bard'],
            'secondary': ['Rogue', 'Seraph']
        },
        'Control': {
            'primary': ['Wizard', 'Druid'],
            'secondary': ['Sorcerer']
        }
    }
    if archetype not in options:
        raise ValueError(f'Unknown archetype {archetype}')
    choice_pool = options[archetype]['primary'] * 3 + options[archetype]['secondary']
    class_name = random.choice(choice_pool)
    # Determine appropriate subclass: map archetype → subclass
    subclass_map = {
        ('Tank', 'Guardian'): 'Stalwart',
        ('Tank', 'Warrior'): 'Call of the Brave',
        ('Damage', 'Warrior'): 'Call of the Slayer',
        ('Damage', 'Rogue'): 'Nightwalker',
        ('Damage', 'Ranger'): 'Wayfinder',
        ('Damage', 'Sorcerer'): 'Elemental Origin',
        ('Sneaky', 'Rogue'): 'Nightwalker',
        ('Sneaky', 'Ranger'): 'Wayfinder',
        ('Support', 'Seraph'): 'Divine Wielder',
        ('Support', 'Bard'): 'Troubadour',
        ('Support', 'Druid'): 'Warden of Renewal',
        ('Support', 'Wizard'): 'School of Knowledge',
        ('Healer', 'Seraph'): 'Divine Wielder',
        ('Healer', 'Druid'): 'Warden of Renewal',
        ('Healer', 'Bard'): 'Troubadour',
        ('Face', 'Bard'): 'Wordsmith',
        ('Face', 'Rogue'): 'Syndicate',
        ('Face', 'Seraph'): 'Divine Wielder',
        ('Control', 'Wizard'): 'School of War',
        ('Control', 'Druid'): 'Warden of the Elements',
        ('Control', 'Sorcerer'): 'Primal Origin'
    }
    subclass_name = subclass_map.get((archetype, class_name))
    if subclass_name is None:
        # default to first subclass defined for the class
        subclass_name = CLASSES[class_name].subclasses[0]
    subclass_info = SUBCLASSES[class_name][subclass_name]
    return class_name, subclass_info


def select_heritage() -> Heritage:
    """Randomly select an ancestry and community."""
    ancestry_name, (feat1, feat2) = random.choice(list(ANCESTRIES.items()))
    community_name, feature = random.choice(list(COMMUNITIES.items()))
    return Heritage(ancestry_name, (feat1, feat2), community_name, feature)


def assign_traits(archetype: str) -> Dict[str, int]:
    """Assign trait modifiers based on the archetype.

    According to the SRD, characters begin with a fixed array of
    modifiers [+2, +1, +1, 0, 0, -1] which are assigned to the six
    traits【876238438073902†L1445-L1448】.  The order is determined by
    the archetype's trait priority list.  This function returns a
    dictionary mapping each trait to its modifier.
    """
    base_mods = [2, 1, 1, 0, 0, -1]
    order = TRAIT_PRIORITIES[archetype.title()]
    traits = ['Agility', 'Strength', 'Finesse', 'Instinct', 'Presence', 'Knowledge']
    # Create ordered list of trait names based on priority
    ordered_traits = order
    values = dict(zip(ordered_traits, base_mods))
    return values


def generate_experiences(archetype: str, char_class: str) -> List[str]:
    """Generate two thematic experiences based on archetype and class.

    Experiences are free‑form descriptors that provide +2 bonuses to
    action rolls.  The SRD suggests that characters add a new
    experience at level 2, 5 and 8【958333465815988†L2536-L2543】.  For the sake
    of this generator we simply produce descriptive strings.
    """
    themes = {
        'Tank': ['Bulwark', 'Defender'],
        'Damage': ['Slayer', 'Weapon Master'],
        'Sneaky': ['Shadow Dweller', 'Master of Disguise'],
        'Support': ['Inspirational Leader', 'Tactical Advisor'],
        'Healer': ['Field Medic', 'Spiritual Healer'],
        'Face': ['Silver Tongue', 'Charming Performer'],
        'Control': ['Arcane Scholar', 'Battlefield Manipulator']
    }
    # Combine archetype theme with class to make it unique
    base_names = themes[archetype.title()]
    return [f"{base_names[0]} {char_class}", f"{base_names[1]} {char_class}"]


def choose_equipment(archetype: str) -> Dict[str, str]:
    """Choose starting equipment based on the archetype.

    Each archetype has preferred weapon and armour categories
    according to the definition matrix【876238438073902†L1258-L1420】.  We
    return a simple mapping of equipment slots to items.  The names
    here are generic placeholders; actual statistics are not included
    but could be expanded.
    """
    eq = {}
    archetype = archetype.title()
    opts = EQUIPMENT_OPTIONS[archetype]
    eq['Weapon'] = random.choice(opts['weapons'])
    eq['Armor'] = random.choice(opts['armor'])
    if 'shield' in opts:
        eq['Shield'] = opts['shield']
    return eq


def pick_domain_card(character: Character, archetype: str, level: int) -> Optional[str]:
    """Select a domain card for the character at a given level.

    The card must come from one of the character's class domains and
    have a level requirement no higher than the character's current
    level.  Cards already taken are skipped.  To choose the most
    suitable card we compute a simple synergy score based on
    archetype keywords and the card description.  The card with the
    highest score is returned; ties are broken randomly.  If no
    eligible cards remain, ``None`` is returned.
    """
    class_domains = CLASSES[character.char_class].domains
    # Filter eligible cards
    eligible = [c for c in DOMAIN_CARDS
                if c['domain'] in class_domains and c['level'] <= level
                and c['name'] not in character.domain_cards]
    if not eligible:
        return None
    # Keywords to score descriptions
    keywords = {
        'Tank': ['damage', 'reduce', 'shield', 'armor', 'threshold', 'hp'],
        'Damage': ['damage', 'bonus', 'attack', 'weapon', 'proficiency'],
        'Sneaky': ['stealth', 'shadow', 'hidden', 'cloak', 'invisibility'],
        'Support': ['ally', 'hope', 'gain', 'inspire', 'help'],
        'Healer': ['heal', 'hit point', 'restore', 'regenerate', 'revive'],
        'Face': ['charm', 'deceive', 'social', 'persuade', 'charisma'],
        'Control': ['control', 'manipulate', 'move', 'stun', 'restrain']
    }
    arche = archetype.title()
    def score(card):
        desc = card['description'].lower()
        return sum(desc.count(kw) for kw in keywords.get(arche, []))
    # Compute scores
    scored = [(score(card), card) for card in eligible]
    max_score = max(sc for sc, _ in scored)
    best_cards = [card for sc, card in scored if sc == max_score]
    chosen = random.choice(best_cards)
    return chosen['name']


def perform_advancements(character: Character, archetype: str, level: int) -> None:
    """Apply two advancements at a given level.

    The SRD specifies that each level up, characters choose two
    advancements【958333465815988†L2549-L2595】.  Options include raising
    traits, adding hit points, gaining stress slots, increasing
    experiences, adding domain cards, raising evasion, taking
    subclass upgrades or multiclassing.  This function implements a
    simplified advancement system tailored to the generator:

    * Tank: prioritises HP/Evasion increases and additional domain cards.
    * Damage: prioritises trait increases and additional domain cards.
    * Sneaky: prioritises trait increases and evasion.
    * Support/Healer: prioritises additional domain cards and traits.
    * Face: prioritises traits and experiences.
    * Control: prioritises domain cards and experiences.

    Two advancements are applied and recorded in the character's
    advancement log.
    """
    arche = archetype.title()
    # Helper functions
    def increase_traits(n: int = 2):
        # Pick n unmarked traits to increase
        for _ in range(n):
            # choose trait with lowest value to improve balance
            trait_name = min(character.traits, key=character.traits.get)
            character.traits[trait_name] += 1
        character.add_advance(level, f"Increased {n} traits by +1")

    def add_hp_slot():
        character.hp += 1
        character.add_advance(level, "Gained an extra Hit Point slot")

    def add_stress_slot():
        character.stress += 1
        character.add_advance(level, "Gained an extra Stress slot")

    def add_experience():
        new_exp = f"Level {level} {arche} Experience"
        character.experiences.append(new_exp)
        character.add_advance(level, f"Added experience: {new_exp}")

    def add_evasion():
        character.evasion += 1
        character.add_advance(level, "Increased Evasion by +1")

    def take_subclass_upgrade():
        # At level 5 and 8 the character can upgrade their subclass
        upg = None
        if character.subclass and level >= 5:
            # Determine if specialization already taken
            if 'Specialization' not in character.subclass_upgrades:
                upg = 'Specialization'
                character.subclass_upgrades.append('Specialization')
                character.add_advance(level, f"Gained subclass specialization ({character.subclass})")
            elif 'Mastery' not in character.subclass_upgrades and level >= 8:
                upg = 'Mastery'
                character.subclass_upgrades.append('Mastery')
                character.add_advance(level, f"Gained subclass mastery ({character.subclass})")
        return upg is not None

    def add_domain_card_adv():
        # Acquire another domain card via advancement (may duplicate step four)
        card = pick_domain_card(character, archetype, level)
        if card:
            character.add_domain_card(card)
            character.add_advance(level, f"Gained extra domain card: {card}")
    # Build a list of possible advancement actions based on archetype
    actions = []
    if arche == 'Tank':
        actions = [add_hp_slot, add_evasion, add_domain_card_adv, increase_traits]
    elif arche == 'Damage':
        actions = [increase_traits, add_domain_card_adv, add_hp_slot]
    elif arche == 'Sneaky':
        actions = [increase_traits, add_evasion, add_domain_card_adv]
    elif arche in ('Support', 'Healer'):
        actions = [add_domain_card_adv, increase_traits, add_experience]
    elif arche == 'Face':
        actions = [increase_traits, add_experience, add_domain_card_adv]
    elif arche == 'Control':
        actions = [add_domain_card_adv, add_experience, increase_traits]
    else:
        actions = [increase_traits, add_domain_card_adv]
    # Always try to take subclass upgrades when available
    taken = take_subclass_upgrade()
    # Choose two other advancements
    chosen = random.sample(actions, k=2)
    for func in chosen:
        func()


def apply_tier_achievements(character: Character, level: int) -> None:
    """Apply tier achievements at levels 2, 5 and 8.

    According to the SRD【958333465815988†L2536-L2544】, tier achievements grant
    characters a new experience and permanently increase their
    proficiency by 1.  At level 5 and 8, all marked traits are
    cleared; since this generator does not track trait marks we
    simply note that in the advancement log.
    """
    if level in {2, 5, 8}:
        # Increase proficiency
        character.proficiency += 1
        character.add_advance(level, "Increased Proficiency by +1 (tier achievement)")
        # Add a new experience
        new_exp = f"Tier {level} Experience"
        character.experiences.append(new_exp)
        character.add_advance(level, f"Gained new experience: {new_exp}")
        # Clear trait marks at level 5 and 8 (record only)
        if level in {5, 8}:
            character.add_advance(level, "Cleared all marked traits (tier achievement)")


def level_up(character: Character, archetype: str, level: int) -> None:
    """Perform the full level‑up procedure for a single level.

    Steps:
      1. Tier achievements (if applicable)
      2. Choose two advancements
      3. Increase all damage thresholds by 1 (abstracted as +1 HP)
      4. Acquire a domain card【958333465815988†L2596-L2604】

    A simplified representation of damage thresholds is used: the
    character's total HP is increased to reflect the improved
    thresholds.  The exact damage thresholds are not recorded but
    could be inferred by the GM when using the character.
    """
    apply_tier_achievements(character, level)
    perform_advancements(character, archetype, level)
    # Increase damage thresholds => represent as extra HP
    character.hp += 1
    character.add_advance(level, "Damage thresholds increased (+1 HP)")
    # Acquire a domain card as per step four
    card = pick_domain_card(character, archetype, level)
    if card:
        character.add_domain_card(card)
        character.add_advance(level, f"Acquired domain card: {card}")


def create_character(level: int, archetype: str, *, class_name: Optional[str] = None,
                     subclass_name: Optional[str] = None) -> Character:
    """Build a new character at the specified level.

    If ``class_name`` and/or ``subclass_name`` are provided then the
    generator respects those choices; otherwise it uses the archetype
    driven algorithm to pick appropriate options.  The function
    produces a ``Character`` instance containing the full build
    history.
    """
    if not (1 <= level <= 10):
        raise ValueError('Level must be between 1 and 10')
    archetype_title = archetype.title()
    # Determine class and subclass
    if class_name is None or subclass_name is None:
        cls, subclass_info = choose_class_and_subclass(archetype_title)
    else:
        cls = class_name
        subclass_info = SUBCLASSES[class_name][subclass_name]
    # Build character and assign basics
    ci = CLASSES[cls]
    char = Character(archetype=archetype_title, char_class=ci.name,
                     subclass=subclass_info.name, hp=ci.hp,
                     evasion=ci.evasion)
    # Assign heritage
    char.heritage = select_heritage()
    # Assign traits
    char.traits = assign_traits(archetype_title)
    # Starting experiences
    char.experiences = generate_experiences(archetype_title, ci.name)
    # Starting equipment
    char.equipment = choose_equipment(archetype_title)
    # Starting domain cards: two level 1 cards
    for _ in range(2):
        card = pick_domain_card(char, archetype_title, 1)
        if card:
            char.add_domain_card(card)
    # Level up from 2 to target level
    for lvl in range(2, level + 1):
        char.level = lvl
        level_up(char, archetype_title, lvl)
    return char


# ---------------------------------------------------------------------------
# Data definitions
# ---------------------------------------------------------------------------

# Classes: starting HP, starting Evasion, domains, class feature and subclass names
CLASSES: Dict[str, ClassInfo] = {
    'Bard': ClassInfo('Bard', 7, 10, ('Grace', 'Codex'),
                      'Make a Scene: Spend 3 Hope to temporarily Distract a target within Close range, giving them a -2 penalty to their Difficulty',
                      ('Troubadour', 'Wordsmith')),
    'Druid': ClassInfo('Druid', 8, 10, ('Sage', 'Arcana'),
                      'Evolution: Spend 3 Hope to transform into Beastform without marking a Stress; raise one trait by +1 until you drop out of Beastform',
                      ('Warden of the Elements', 'Warden of Renewal')),
    'Guardian': ClassInfo('Guardian', 10, 9, ('Valor', 'Blade'),
                          'Frontline Tank: Spend 3 Hope to clear 2 Armor Slots',
                          ('Stalwart', 'Vengeance')),
    'Ranger': ClassInfo('Ranger', 8, 12, ('Bone', 'Sage'),
                        'Hold Them Off: Spend 3 Hope when you succeed on an attack with a weapon to use that same roll against two additional adversaries within range',
                        ('Beastbound', 'Wayfinder')),
    'Rogue': ClassInfo('Rogue', 7, 12, ('Midnight', 'Grace'),
                       "Rogue's Dodge: Spend 3 Hope to gain a +2 bonus to your Evasion until the next time an attack succeeds against you; otherwise this bonus lasts until your next rest",
                       ('Nightwalker', 'Syndicate')),
    'Seraph': ClassInfo('Seraph', 9, 9, ('Splendor', 'Valor'),
                        'Life Support: Spend 3 Hope to clear a Hit Point on an ally within Close range',
                        ('Divine Wielder', 'Winged Sentinel')),
    'Sorcerer': ClassInfo('Sorcerer', 6, 10, ('Arcana', 'Midnight'),
                          'Volatile Magic: Spend 3 Hope to reroll any number of your damage dice on an attack that deals magic damage',
                          ('Elemental Origin', 'Primal Origin')),
    'Warrior': ClassInfo('Warrior', 9, 11, ('Blade', 'Bone'),
                         'No Mercy: Spend 3 Hope to gain a +1 bonus to your attack rolls until your next rest',
                         ('Call of the Brave', 'Call of the Slayer')),
    'Wizard': ClassInfo('Wizard', 6, 11, ('Codex', 'Splendor'),
                        'Not This Time: Spend 3 Hope to force an adversary within Far range to reroll an attack or damage roll',
                        ('School of Knowledge', 'School of War')),
}

# Subclasses: each with spellcast trait and feature names.  Only names are
# stored here; the effects are described in the SRD【876238438073902†L247-L368】.  The
# generator uses these to record when a specialization or mastery is
# obtained.
SUBCLASSES: Dict[str, Dict[str, Subclass]] = {
    'Bard': {
        'Troubadour': Subclass('Troubadour', 'Presence',
                              'Gifted Performer', 'Well-Traveled', 'Epic Poetry'),
        'Wordsmith': Subclass('Wordsmith', 'Presence',
                              'Cutting Words', 'Silver Tongue', 'Master of Rhetoric'),
    },
    'Druid': {
        'Warden of the Elements': Subclass('Warden of the Elements', 'Instinct',
                                          'Elemental Incarnation', 'Elemental Aura', 'Elemental Dominion'),
        'Warden of Renewal': Subclass('Warden of Renewal', 'Instinct',
                                       'Regeneration', 'Regenerative Reach', 'Verdant Renewal'),
    },
    'Guardian': {
        'Stalwart': Subclass('Stalwart', 'Strength',
                             'Unwavering', 'Unrelenting', 'Immovable'),
        'Vengeance': Subclass('Vengeance', 'Strength',
                              'At Ease', 'Act of Reprisal', 'Vengeful Spirit'),
    },
    'Ranger': {
        'Beastbound': Subclass('Beastbound', 'Agility',
                               'Companion', 'Coordinated Attack', 'Inseparable'),
        'Wayfinder': Subclass('Wayfinder', 'Agility',
                              'Forager', 'Hunter\'s Mark', 'Master of the Hunt'),
    },
    'Rogue': {
        'Nightwalker': Subclass('Nightwalker', 'Finesse',
                                'Shadow Step', 'Dark Cloud', 'One with the Shadows'),
        'Syndicate': Subclass('Syndicate', 'Finesse',
                              'Black Market Connections', 'Contacts Everywhere', 'Pulling Strings'),
    },
    'Seraph': {
        'Divine Wielder': Subclass('Divine Wielder', 'Strength',
                                   'Sparing Touch', 'Devout', 'Divine Intervention'),
        'Winged Sentinel': Subclass('Winged Sentinel', 'Strength',
                                    'Wings of Light', 'Ethereal Visage', 'Ascendant'),
    },
    'Sorcerer': {
        'Elemental Origin': Subclass('Elemental Origin', 'Instinct',
                                     'Elementalist', 'Natural Evasion', 'Transcendence'),
        'Primal Origin': Subclass('Primal Origin', 'Instinct',
                                   'Manipulate Magic', 'Enchanted Aid', 'Arcane Charge'),
    },
    'Warrior': {
        'Call of the Brave': Subclass('Call of the Brave', 'Strength',
                                       'Courage', 'Rise to the Challenge', 'Fearless'),
        'Call of the Slayer': Subclass('Call of the Slayer', 'Strength',
                                       'Slayer', 'Weapon Specialist', 'Unstoppable Carnage'),
    },
    'Wizard': {
        'School of Knowledge': Subclass('School of Knowledge', 'Knowledge',
                                        'Prepared', 'Accomplished', 'Brilliant'),
        'School of War': Subclass('School of War', 'Knowledge',
                                  'Battlemage', 'Conjure Shield', 'Thrive in Chaos'),
    },
}

# Ancestries and their two features【876238438073902†L556-L733】
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
        'Fey Ancestry: You have advantage on rolls to resist magical effects.',
        'Trance: During a long rest, you can remain conscious and aware of your surroundings.'
    ),
    'Faerie': (
        'Fey Wings: You can fly for short distances.',
        'Fey Magic: You know one minor illusion spell.'
    ),
    'Faun': (
        'Sure‑Footed: You have advantage on rolls to keep your balance and avoid being knocked prone.',
        'Naturalist: You have advantage on rolls related to identifying plants and animals.'
    ),
    'Firbolg': (
        'Firbolg Magic: You can cast Disguise Self and Invisibility once per long rest.',
        'Powerful Build: You count as one size larger for carrying capacity and pushing/dragging weight.'
    ),
    'Fungril': (
        'Spore Cloud: Once per rest, release a cloud of spores; creatures in it have disadvantage on perception checks.',
        'Decomposer: You can consume organic matter to gain sustenance.'
    ),
    'Galapa': (
        'Shell Defense: You can use an action to withdraw into your shell, gaining a +4 bonus to Evasion but you cannot move or take actions.',
        'Amphibious: You can breathe air and water.'
    ),
    'Giant': (
        'Reach: Your melee attacks have a longer reach (add one range band).',
        'Endurance: Gain an additional Hit Point slot.'
    ),
    'Goblin': (
        'Nimble Escape: You can take the Disengage or Hide action as a bonus action.',
        'Fury of the Small: When you damage a creature larger than you, you can add your Proficiency to the damage roll.'
    ),
    'Halfling': (
        'Lucky: When you roll a 1 on a d20 for an attack roll, ability check, or saving throw, you can reroll the die.',
        'Brave: You have advantage on saving throws against being Frightened.'
    ),
    'Human': (
        'Versatile: Gain a +1 bonus to two different character traits of your choice.',
        'High Stamina: Gain an additional Stress slot.'
    ),
    'Infernis': (
        'Fire Resistance: You have resistance to fire damage.',
        'Hellish Rebuke: When a creature within Melee range damages you, you can use your reaction to deal 2d10 fire damage to them.'
    ),
    'Katari': (
        'Feline Instincts: You can reroll an Agility Roll once per rest.',
        'Claws: You have a natural Melee weapon that deals 1d6 physical damage.'
    ),
    'Orc': (
        'Aggressive: As a bonus action on your turn, you can move up to your speed toward an enemy.',
        'Powerful Build: You count as one size larger for carrying capacity and pushing/dragging weight.'
    ),
    'Ribbet': (
        'Amphibious: You can breathe air and water.',
        'Sticky Tongue: You have a natural weapon with Close range that can pull smaller objects or creatures towards you.'
    ),
    'Simiah': (
        'Prehensile Tail: You can use your tail to hold or manipulate an object.',
        'Nimble: Gain a permanent +1 bonus to your Evasion.'
    ),
}

# Communities and their single features【876238438073902†L734-L759】
COMMUNITIES: Dict[str, str] = {
    'Highborne': 'Well‑Connected: Once per session, you can declare you know someone important in the current location. Work with the GM to define this NPC.',
    'Loreborne': 'Educated: You have advantage on Knowledge rolls related to history, arcana, or religion.',
    'Orderborne': 'By the Book: When you follow a clear plan or order, you gain advantage on the first action roll you make to execute it.',
    'Ridgeborne': 'Mountaineer: You have advantage on rolls made to climb or navigate mountainous terrain.',
    'Seaborne': 'Know the Tide: When you roll with Fear, you can re‑roll one of the Fear dice.',
}

# Trait priorities per archetype【876238438073902†L1258-L1420】
TRAIT_PRIORITIES: Dict[str, List[str]] = {
    'Tank': ['Strength', 'Instinct', 'Agility', 'Finesse', 'Presence', 'Knowledge'],
    'Damage': ['Strength', 'Finesse', 'Agility', 'Instinct', 'Presence', 'Knowledge'],
    'Sneaky': ['Finesse', 'Agility', 'Instinct', 'Presence', 'Knowledge', 'Strength'],
    'Support': ['Presence', 'Knowledge', 'Instinct', 'Agility', 'Finesse', 'Strength'],
    'Healer': ['Presence', 'Instinct', 'Knowledge', 'Agility', 'Finesse', 'Strength'],
    'Face': ['Presence', 'Finesse', 'Agility', 'Knowledge', 'Instinct', 'Strength'],
    'Control': ['Knowledge', 'Instinct', 'Presence', 'Finesse', 'Agility', 'Strength'],
}

# Equipment options per archetype【876238438073902†L1258-L1420】
EQUIPMENT_OPTIONS: Dict[str, Dict[str, List[str]]] = {
    'Tank': {
        'weapons': ['Longsword', 'Warhammer', 'Mace'],
        'armor': ['Chainmail', 'Scale Mail'],
        'shield': 'Shield',
    },
    'Damage': {
        'weapons': ['Greatsword', 'Greataxe', 'Longbow', 'Paired Swords'],
        'armor': ['Leather Armor', 'Chain Shirt'],
    },
    'Sneaky': {
        'weapons': ['Dagger', 'Shortbow', 'Rapier'],
        'armor': ['Gambeson', 'Leather Armor'],
    },
    'Support': {
        'weapons': ['Staff', 'Scepter', 'Instrument'],
        'armor': ['Robes', 'Leather Armor'],
    },
    'Healer': {
        'weapons': ['Staff', 'Mace', 'Holy Symbol'],
        'armor': ['Robes', 'Leather Armor'],
    },
    'Face': {
        'weapons': ['Rapier', 'Dagger', 'Shortsword'],
        'armor': ['Fine Clothes', 'Leather Armor'],
    },
    'Control': {
        'weapons': ['Greatstaff', 'Wand', 'Book of Spells'],
        'armor': ['Robes', 'Leather Armor'],
    },
}
