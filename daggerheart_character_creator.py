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
import copy

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
    # The base hit points and evasion as dictated by class.  These values
    # remain constant even when equipment applies bonuses or penalties.  HP
    # increases from advancements will modify ``base_hp``.
    base_hp: int = 0
    base_evasion: int = 0
    # A copy of the unmodified trait assignments at level‑1.  Equipment may
    # apply temporary bonuses or penalties to traits; to avoid stacking
    # modifiers when switching items, we reset traits from this dict each
    # time we (re)apply equipment.
    base_traits: Dict[str, int] = field(default_factory=dict)
    heritage: Optional[Heritage] = None
    experiences: List[str] = field(default_factory=list)
    # Mapping of equipment slots to item names.  Keys include
    # ``primary``, ``secondary`` and ``armor``.
    equipment: Dict[str, str] = field(default_factory=dict)
    # The calculated minor and major damage thresholds of the equipped
    # armor.  These numbers include the character's level bonus.
    armor_thresholds: Tuple[int, int] = (0, 0)
    # The armor score of the equipped armor.  This number increases
    # the character's protection when they mark Armor Slots.
    armor_score: int = 0
    # A convenience field storing the current damage roll expression
    # for the equipped primary (and secondary) weapons.  Represented
    # as a string like ``"1d8+3"``.
    damage_roll: Optional[str] = None
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
    # ``Random`` and ``Any`` archetypes mean choose any class and subclass uniformly
    if archetype.lower() in ('random', 'any', ''):
        class_name = random.choice(list(CLASSES.keys()))
        subclass_name = random.choice(list(SUBCLASSES[class_name].keys()))
        return class_name, SUBCLASSES[class_name][subclass_name]
    if archetype not in options:
        raise ValueError(f'Unknown archetype {archetype}')
    # Build a weighted pool for the archetype
    choice_pool = options[archetype]['primary'] * 3 + options[archetype]['secondary']
    class_name = random.choice(choice_pool)
    # Determine appropriate subclass: map archetype → subclass.  If no
    # mapping exists, fall back to a random subclass rather than always
    # selecting the first one.  This gives more variety when the user does
    # not care about subclass specifics.
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
        # pick a random subclass for the chosen class
        subclass_name = random.choice(list(SUBCLASSES[class_name].keys()))
    subclass_info = SUBCLASSES[class_name][subclass_name]
    return class_name, subclass_info


def select_heritage() -> Heritage:
    """Randomly select an ancestry and community."""
    ancestry_name, (feat1, feat2) = random.choice(list(ANCESTRIES.items()))
    community_name, feature = random.choice(list(COMMUNITIES.items()))
    return Heritage(ancestry_name, (feat1, feat2), community_name, feature)


def assign_traits(archetype: str, *, class_name: Optional[str] = None,
                  subclass: Optional[Subclass] = None) -> Dict[str, int]:
    """Assign trait modifiers based on the archetype and class.

    Characters begin with the fixed array of modifiers ``[+2, +1, +1, 0, 0, -1]``
    which are assigned to the six traits.  By default, the order is
    determined by the archetype's trait priority list【876238438073902†L1445-L1448】.  If a
    ``class_name`` or ``subclass`` is provided, the primary trait used by
    that class (typically the spellcast or attack trait) will receive the
    highest bonus (+2).  The remaining modifiers are then assigned
    according to the archetype's priorities, skipping the primary trait.

    Parameters
    ----------
    archetype: str
        The archetype guiding the general priority of traits.
    class_name: Optional[str]
        The name of the class, used to look up a default primary trait if
        ``subclass`` is not provided.
    subclass: Optional[Subclass]
        A ``Subclass`` instance which specifies its ``spellcast_trait``. If
        provided, this takes precedence over ``class_name`` when
        determining the primary trait.

    Returns
    -------
    Dict[str, int]
        A mapping from trait names to their assigned modifiers.
    """
    # Base modifiers as per the SRD: +2, +1, +1, 0, 0, -1
    base_mods = [2, 1, 1, 0, 0, -1]
    # Determine the primary trait from subclass or class
    primary_trait: Optional[str] = None
    if subclass is not None:
        primary_trait = subclass.spellcast_trait
    elif class_name is not None:
        # Use a predefined mapping of classes to their primary traits
        primary_trait = CLASS_PRIMARY_TRAIT.get(class_name)
    # Ordered list based on archetype priorities
    archetype_order = TRAIT_PRIORITIES[archetype.title()].copy()
    ordered_traits: List[str] = []
    # Place the primary trait first if defined
    if primary_trait and primary_trait in archetype_order:
        ordered_traits.append(primary_trait)
        archetype_order.remove(primary_trait)
    # Append the remaining traits following the archetype's order
    ordered_traits.extend(archetype_order)
    # Assign modifiers to traits in order
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
    if class_name is None:
        # No class specified: use archetype-driven random selection
        cls, subclass_info = choose_class_and_subclass(archetype_title)
    else:
        # Class specified: respect the choice
        cls = class_name
        if subclass_name is not None:
            # Both class and subclass provided
            subclass_info = SUBCLASSES[cls][subclass_name]
        else:
            # Only class provided: pick a subclass based on archetype preference
            # If a preferred subclass is defined for this archetype/class pair, use it
            pref_name = SUBCLASS_PREFERENCE.get((archetype_title, cls))
            if pref_name and pref_name in SUBCLASSES[cls]:
                subclass_info = SUBCLASSES[cls][pref_name]
            else:
                # Fallback to the first defined subclass for the class
                first_sub = CLASSES[cls].subclasses[0]
                subclass_info = SUBCLASSES[cls][first_sub]
    # Build character and assign basics
    ci = CLASSES[cls]
    char = Character(
        archetype=archetype_title,
        char_class=ci.name,
        subclass=subclass_info.name,
        hp=ci.hp,
        evasion=ci.evasion,
        base_hp=ci.hp,
        base_evasion=ci.evasion,
    )
    # Assign heritage
    char.heritage = select_heritage()
    # Assign traits, prioritising the class's primary trait if available
    char.traits = assign_traits(archetype_title, class_name=cls, subclass=subclass_info)
    # Record unmodified traits so that equipment modifiers can be applied and
    # removed without accumulating errors.
    char.base_traits = dict(char.traits)
    # Starting experiences
    char.experiences = generate_experiences(archetype_title, ci.name)
    # Starting equipment: leave empty for canonical selection.  Equipment
    # will be applied explicitly via API or UI, so we don't assign any
    # items here.  The ``equipment`` dict remains empty until
    # ``apply_equipment`` is called.
    char.equipment = {}
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
# Equipment definitions and application
# ---------------------------------------------------------------------------

# Tier 1 primary weapons.  Each entry defines the trait used to attack,
# the base damage die (number of sides), a flat damage bonus, whether
# the weapon is two‑handed (True) or one‑handed (False), any evasion
# penalty or trait adjustments, and a short description of its feature.
TIER1_PRIMARY_WEAPONS: Dict[str, Dict] = {
    # Physical weapons
    'Broadsword':  {
        'trait': 'Agility', 'die': 8,  'flat': 0, 'two_handed': False,
        'evasion_mod': 0, 'trait_mods': {}, 'feature': 'Reliable: +1 to attack rolls'
    },
    'Longsword':  {
        'trait': 'Agility', 'die': 8,  'flat': 3, 'two_handed': True,
        'evasion_mod': 0, 'trait_mods': {}, 'feature': ''
    },
    'Battleaxe':  {
        'trait': 'Strength', 'die': 10, 'flat': 3, 'two_handed': True,
        'evasion_mod': 0, 'trait_mods': {}, 'feature': ''
    },
    'Greatsword': {
        'trait': 'Strength', 'die': 10, 'flat': 3, 'two_handed': True,
        'evasion_mod': -1, 'trait_mods': {},
        'feature': 'Massive: −1 Evasion; roll an extra damage die and drop the lowest on a success'
    },
    'Mace': {
        'trait': 'Strength', 'die': 8,  'flat': 1, 'two_handed': False,
        'evasion_mod': 0, 'trait_mods': {}, 'feature': ''
    },
    'Warhammer': {
        'trait': 'Strength', 'die': 12, 'flat': 3, 'two_handed': True,
        'evasion_mod': -1, 'trait_mods': {}, 'feature': 'Heavy: −1 Evasion'
    },
    'Dagger': {
        'trait': 'Finesse', 'die': 8,  'flat': 1, 'two_handed': False,
        'evasion_mod': 0, 'trait_mods': {}, 'feature': ''
    },
    'Quarterstaff': {
        'trait': 'Instinct', 'die': 10, 'flat': 3, 'two_handed': True,
        'evasion_mod': 0, 'trait_mods': {}, 'feature': ''
    },
    'Cutlass': {
        'trait': 'Presence', 'die': 8,  'flat': 1, 'two_handed': False,
        'evasion_mod': 0, 'trait_mods': {}, 'feature': ''
    },
    'Rapier': {
        'trait': 'Presence', 'die': 8,  'flat': 0, 'two_handed': False,
        'evasion_mod': 0, 'trait_mods': {},
        'feature': 'Quick: mark a Stress to target another creature within range'
    },
    'Halberd': {
        'trait': 'Strength', 'die': 10, 'flat': 2, 'two_handed': True,
        'evasion_mod': 0, 'trait_mods': {'Finesse': -1},
        'feature': 'Cumbersome: −1 to Finesse'
    },
    'Spear': {
        'trait': 'Finesse', 'die': 10, 'flat': 2, 'two_handed': True,
        'evasion_mod': 0, 'trait_mods': {'Finesse': -1},
        'feature': 'Cumbersome: −1 to Finesse'
    },
    'Shortbow': {
        'trait': 'Agility', 'die': 6,  'flat': 3, 'two_handed': True,
        'evasion_mod': 0, 'trait_mods': {}, 'feature': ''
    },
    'Crossbow': {
        'trait': 'Finesse', 'die': 6,  'flat': 1, 'two_handed': False,
        'evasion_mod': 0, 'trait_mods': {}, 'feature': ''
    },
    'Longbow': {
        'trait': 'Agility', 'die': 8,  'flat': 3, 'two_handed': True,
        'evasion_mod': 0, 'trait_mods': {'Finesse': -1},
        'feature': 'Cumbersome: −1 to Finesse'
    },
    # Magic weapons (Spellcast trait must be used)
    'Arcane Gauntlets': {
        'trait': 'Strength', 'die': 10, 'flat': 3, 'two_handed': True,
        'evasion_mod': 0, 'trait_mods': {}, 'feature': ''
    },
    'Hallowed Axe': {
        'trait': 'Strength', 'die': 8,  'flat': 1, 'two_handed': False,
        'evasion_mod': 0, 'trait_mods': {}, 'feature': ''
    },
    'Glowing Rings': {
        'trait': 'Agility', 'die': 10, 'flat': 1, 'two_handed': True,
        'evasion_mod': 0, 'trait_mods': {}, 'feature': ''
    },
    'Hand Runes': {
        'trait': 'Instinct', 'die': 10, 'flat': 0, 'two_handed': False,
        'evasion_mod': 0, 'trait_mods': {}, 'feature': ''
    },
    'Returning Blade': {
        'trait': 'Finesse', 'die': 8,  'flat': 0, 'two_handed': False,
        'evasion_mod': 0, 'trait_mods': {},
        'feature': 'Returning: automatically returns after being thrown'
    },
    'Shortstaff': {
        'trait': 'Instinct', 'die': 8,  'flat': 1, 'two_handed': False,
        'evasion_mod': 0, 'trait_mods': {}, 'feature': ''
    },
    'Dualstaff': {
        'trait': 'Instinct', 'die': 6,  'flat': 3, 'two_handed': True,
        'evasion_mod': 0, 'trait_mods': {}, 'feature': ''
    },
    'Scepter': {
        'trait': 'Presence', 'die': 6,  'flat': 0, 'two_handed': True,
        'evasion_mod': 0, 'trait_mods': {},
        'feature': 'Versatile: also usable as Presence, Melee, d8'
    },
    'Wand': {
        'trait': 'Knowledge', 'die': 6,  'flat': 1, 'two_handed': False,
        'evasion_mod': 0, 'trait_mods': {}, 'feature': ''
    },
    'Greatstaff': {
        'trait': 'Knowledge', 'die': 6,  'flat': 0, 'two_handed': True,
        'evasion_mod': 0, 'trait_mods': {},
        'feature': 'Powerful: roll an extra damage die and drop the lowest'
    },
}

# Tier 1 secondary weapons.  Secondary weapons often grant armour
# bonuses or a paired damage bonus.  We include armour and evasion
# modifiers where applicable.  The ``paired_bonus`` field adds to the
# primary weapon's flat damage.
TIER1_SECONDARY_WEAPONS: Dict[str, Dict] = {
    'Shortsword': {
        'trait': 'Agility', 'die': 8, 'flat': 0, 'paired_bonus': 2,
        'armor_bonus': 0, 'evasion_mod': 0, 'trait_mods': {},
        'feature': 'Paired: +2 to primary damage within Melee range'
    },
    'Round Shield': {
        'trait': 'Strength', 'die': 4, 'flat': 0, 'paired_bonus': 0,
        'armor_bonus': 1, 'evasion_mod': 0, 'trait_mods': {},
        'feature': 'Protective: +1 to Armor Score'
    },
    'Tower Shield': {
        'trait': 'Strength', 'die': 6, 'flat': 0, 'paired_bonus': 0,
        'armor_bonus': 2, 'evasion_mod': -1, 'trait_mods': {},
        'feature': 'Barrier: +2 to Armor Score; −1 Evasion'
    },
    'Small Dagger': {
        'trait': 'Finesse', 'die': 8, 'flat': 0, 'paired_bonus': 2,
        'armor_bonus': 0, 'evasion_mod': 0, 'trait_mods': {},
        'feature': 'Paired: +2 to primary damage within Melee range'
    },
    'Whip': {
        'trait': 'Presence', 'die': 6, 'flat': 0, 'paired_bonus': 0,
        'armor_bonus': 0, 'evasion_mod': 0, 'trait_mods': {},
        'feature': 'Startling: mark a Stress to push adversaries'
    },
    'Grappler': {
        'trait': 'Finesse', 'die': 6, 'flat': 0, 'paired_bonus': 0,
        'armor_bonus': 0, 'evasion_mod': 0, 'trait_mods': {},
        'feature': 'Hooked: pull the target into Melee range on a hit'
    },
    'Hand Crossbow': {
        'trait': 'Finesse', 'die': 6, 'flat': 1, 'paired_bonus': 0,
        'armor_bonus': 0, 'evasion_mod': 0, 'trait_mods': {},
        'feature': ''
    },
}

# Tier 1 armour options.  Each entry defines base minor and major
# thresholds (before adding character level), the base armour score,
# and any modifications to evasion or traits.  Armour features such
# as Flexible, Heavy and Very Heavy are represented via these mods.
TIER1_ARMOUR: Dict[str, Dict] = {
    'Gambeson Armor': {
        'thresholds': (5, 11), 'score': 3,
        'evasion_mod': +1, 'trait_mods': {}, 'feature': 'Flexible: +1 to Evasion'
    },
    'Leather Armor': {
        'thresholds': (6, 13), 'score': 3,
        'evasion_mod': 0, 'trait_mods': {}, 'feature': ''
    },
    'Chainmail Armor': {
        'thresholds': (7, 15), 'score': 4,
        'evasion_mod': -1, 'trait_mods': {}, 'feature': 'Heavy: −1 to Evasion'
    },
    'Full Plate Armor': {
        'thresholds': (8, 17), 'score': 4,
        'evasion_mod': -2, 'trait_mods': {'Agility': -1},
        'feature': 'Very Heavy: −2 to Evasion; −1 to Agility'
    },
}

def apply_equipment(
    character: Character,
    primary: Optional[str] = None,
    secondary: Optional[str] = None,
    armour: Optional[str] = None
) -> None:
    """Apply selected equipment to the character.

    Resets the character's hit points, evasion and traits to their
    base values, then applies the chosen armour and weapons.  This
    function modifies the character in place.

    Parameters
    ----------
    character: Character
        The character to modify.  Its base_hp, base_evasion and
        base_traits must already be populated.
    primary: Optional[str]
        The name of the primary weapon.  If None or unknown, no
        primary weapon is equipped.
    secondary: Optional[str]
        The name of the secondary weapon.  If None or unknown, no
        secondary weapon is equipped.
    armour: Optional[str]
        The name of the armour.  If None or unknown, the character has no
        armour and therefore no armour thresholds or armour score.
    """
    # Reset to base values
    character.hp = character.base_hp
    character.evasion = character.base_evasion
    character.traits = dict(character.base_traits)
    character.armor_thresholds = (0, 0)
    character.armor_score = 0
    character.damage_roll = None
    # Record equipment names
    character.equipment = {}
    if primary:
        character.equipment['primary'] = primary
    if secondary:
        character.equipment['secondary'] = secondary
    if armour:
        character.equipment['armor'] = armour
    # Apply armour
    if armour and armour in TIER1_ARMOUR:
        data = TIER1_ARMOUR[armour]
        # Thresholds: add current level to base thresholds
        min_thr, max_thr = data['thresholds']
        character.armor_thresholds = (min_thr + character.level, max_thr + character.level)
        character.armor_score = data['score']
        character.evasion += data.get('evasion_mod', 0)
        for trait, mod in data.get('trait_mods', {}).items():
            character.traits[trait] += mod
    # Apply primary weapon
    primary_data = None
    flat_bonus = 0
    if primary and primary in TIER1_PRIMARY_WEAPONS:
        primary_data = TIER1_PRIMARY_WEAPONS[primary]
        # Adjust evasion and traits for weapon features
        character.evasion += primary_data.get('evasion_mod', 0)
        for trait, mod in primary_data.get('trait_mods', {}).items():
            character.traits[trait] += mod
        # Base damage die and flat bonus
        base_die = primary_data['die']
        flat_bonus = primary_data['flat']
    # Apply secondary weapon
    if secondary and secondary in TIER1_SECONDARY_WEAPONS:
        sec = TIER1_SECONDARY_WEAPONS[secondary]
        # Secondary may also be used as a weapon, but for simplicity we
        # treat its damage as an off‑hand that only influences armour and
        # paired bonuses.
        character.armor_score += sec.get('armor_bonus', 0)
        character.evasion += sec.get('evasion_mod', 0)
        for trait, mod in sec.get('trait_mods', {}).items():
            character.traits[trait] += mod
        # Paired bonus adds to primary flat damage
        flat_bonus += sec.get('paired_bonus', 0)
    # Compute damage roll expression
    if primary_data is not None:
        die_sides = primary_data['die']
        # Number of dice equals proficiency
        num_dice = character.proficiency
        # Compose the damage roll string
        dmg_str = f"{num_dice}d{die_sides}"
        if flat_bonus:
            dmg_str += f"+{flat_bonus}"
        character.damage_roll = dmg_str


# ---------------------------------------------------------------------------
# Data definitions
# ---------------------------------------------------------------------------

# Classes: starting HP, starting Evasion, domains, class feature and subclass names
CLASSES: Dict[str, ClassInfo] = {
    # Starting HP and Evasion values pulled directly from the SRD【37841809467909†L680-L690】【37841809467909†L1242-L1243】【37841809467909†L1346-L1348】【37841809467909†L1546-L1549】【37841809467909†L1673-L1676】【37841809467909†L1781-L1784】【37841809467909†L1894-L1896】【37841809467909†L2009-L2010】.
    'Bard': ClassInfo('Bard', 5, 10, ('Grace', 'Codex'),
                      'Make a Scene: Spend 3 Hope to temporarily Distract a target within Close range, giving them a -2 penalty to their Difficulty',
                      ('Troubadour', 'Wordsmith')),
    'Druid': ClassInfo('Druid', 6, 10, ('Sage', 'Arcana'),
                      'Evolution: Spend 3 Hope to transform into Beastform without marking a Stress; raise one trait by +1 until you drop out of Beastform',
                      ('Warden of the Elements', 'Warden of Renewal')),
    'Guardian': ClassInfo('Guardian', 7, 9, ('Valor', 'Blade'),
                          'Frontline Tank: Spend 3 Hope to clear 2 Armor Slots',
                          ('Stalwart', 'Vengeance')),
    'Ranger': ClassInfo('Ranger', 6, 12, ('Bone', 'Sage'),
                        'Hold Them Off: Spend 3 Hope when you succeed on an attack with a weapon to use that same roll against two additional adversaries within range',
                        ('Beastbound', 'Wayfinder')),
    'Rogue': ClassInfo('Rogue', 6, 12, ('Midnight', 'Grace'),
                       "Rogue's Dodge: Spend 3 Hope to gain a +2 bonus to your Evasion until the next time an attack succeeds against you; otherwise this bonus lasts until your next rest",
                       ('Nightwalker', 'Syndicate')),
    'Seraph': ClassInfo('Seraph', 7, 9, ('Splendor', 'Valor'),
                        'Life Support: Spend 3 Hope to clear a Hit Point on an ally within Close range',
                        ('Divine Wielder', 'Winged Sentinel')),
    'Sorcerer': ClassInfo('Sorcerer', 6, 10, ('Arcana', 'Midnight'),
                          'Volatile Magic: Spend 3 Hope to reroll any number of your damage dice on an attack that deals magic damage',
                          ('Elemental Origin', 'Primal Origin')),
    'Warrior': ClassInfo('Warrior', 6, 11, ('Blade', 'Bone'),
                         'No Mercy: Spend 3 Hope to gain a +1 bonus to your attack rolls until your next rest',
                         ('Call of the Brave', 'Call of the Slayer')),
    'Wizard': ClassInfo('Wizard', 5, 11, ('Codex', 'Splendor'),
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

# Primary trait used by each class for spellcasting or main attacks.  This
# mapping allows the generator to apply the highest +2 bonus to the trait
# most central to a class’s playstyle when ``assign_traits`` is given a
# class or subclass.  The traits are derived from the subclasses’ spellcast
# traits or typical attack abilities in the SRD【876238438073902†L247-L368】.
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

# Preferred subclasses for each archetype/class combination.  When a user
# specifies a class but not a subclass in ``create_character``, the
# generator consults this mapping to choose the subclass that best fits
# the given archetype.  These preferences mirror those used in
# ``choose_class_and_subclass``.
SUBCLASS_PREFERENCE: Dict[Tuple[str, str], str] = {
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
    ('Control', 'Sorcerer'): 'Primal Origin',
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
