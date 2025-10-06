import random
from game_core import Soldier


def spawn_pawn(mx, my, color, role, team_list, sprite, weapon_img, weapon_key):
    """Spawn a pawn at (mx,my) with given properties and append to team_list.
    Returns the created Soldier.
    """
    s = Soldier(mx, my, color, role=role)
    s.sprite = sprite
    s.weapon_img = weapon_img
    s.weapon_key = weapon_key
    team_list.append(s)
    return s


def spawn_bomb_carrier_sandbox(mx, my, team_list, sprite, weapon_img, weapon_key, bomb):
    """Spawn a blue/green pawn carrying the bomb in sandbox mode and attach bomb to them."""
    s = spawn_pawn(mx, my, (0,0,255), 'rifle', team_list, sprite, weapon_img, weapon_key)
    s.carrying_bomb = True
    bomb['carried_by'] = s
    return s


def give_bomb_to_random_team(team_list, bomb):
    """Give the bomb to a random soldier in team_list (if non-empty)."""
    if not team_list:
        return None
    carrier = random.choice(team_list)
    carrier.carrying_bomb = True
    bomb['carried_by'] = carrier
    return carrier


def clear_entities(bullets, grenades, particles):
    bullets.clear(); grenades.clear(); particles.clear()

import random
from game_core import Soldier


def spawn_pawn(mx, my, color, role, team_list, sprite=None, weapon_img=None, weapon_key=None):
    """Spawn a pawn at (mx,my) with given properties and append to team_list.
    Returns the created Soldier.
    """
    s = Soldier(mx, my, color, role=role)
    if sprite is not None:
        s.sprite = sprite
    if weapon_img is not None:
        s.weapon_img = weapon_img
    if weapon_key is not None:
        s.weapon_key = weapon_key
    team_list.append(s)
    return s


def spawn_bomb_carrier_sandbox(mx, my, team_list, sprite=None, weapon_img=None, weapon_key=None, bomb=None):
    """Spawn a pawn carrying the bomb in sandbox mode and attach bomb to them."""
    s = spawn_pawn(mx, my, (0, 0, 255), 'rifle', team_list, sprite, weapon_img, weapon_key)
    s.carrying_bomb = True
    if bomb is not None:
        bomb['carried_by'] = s
    return s


def give_bomb_to_random_team(team_list, bomb):
    """Give the bomb to a random soldier in team_list (if non-empty)."""
    if not team_list:
        return None
    carrier = random.choice(team_list)
    carrier.carrying_bomb = True
    if bomb is not None:
        bomb['carried_by'] = carrier
    return carrier


def clear_entities(bullets, grenades, particles):
    """Clear the provided lists of entities (in-place)."""
    try:
        bullets.clear()
    except Exception:
        bullets[:] = []
    try:
        grenades.clear()
    except Exception:
        grenades[:] = []
    try:
        particles.clear()
    except Exception:
        particles[:] = []