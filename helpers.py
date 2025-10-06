import pygame
import random
import math
from typing import List, Tuple

# Import game_core types only as needed to avoid heavy coupling
from game_core import Soldier

def play_sound_obj(snd, sounds=None):
    """Play a pygame Sound on an available channel, with optional debug logging using `sounds` dict.
    snd: a pygame.mixer.Sound-like object
    sounds: optional dict mapping names to Sound objects (used to log the logical name)
    """
    try:
        if not snd:
            return
        # debug: try to find a logical name
        try:
            sname = None
            if sounds:
                for _k, _v in (sounds.items() if isinstance(sounds, dict) else []):
                    if _v is snd:
                        sname = _k; break
            if sname:
                try:
                    length = getattr(snd, 'get_length', lambda: None)()
                except Exception:
                    length = 'unknown'
                print(f"PLAY_SOUND_OBJ: name={sname} len={length}")
            else:
                try:
                    length = getattr(snd, 'get_length', lambda: None)()
                except Exception:
                    length = repr(snd)
                print(f"PLAY_SOUND_OBJ: snd_len={length}")
        except Exception:
            pass
        ch = pygame.mixer.find_channel(True)
        if ch:
            ch.play(snd)
    except Exception:
        try:
            snd.play()
        except Exception:
            pass


def spawn_explosion(x, y, explosion_frames: List, generic_images: List, explosion_anims: List, image_particles: List, magnitude=1.0):
    """Spawn an explosion animation and image-particles using the provided resource lists.
    This is separated so main can maintain the resource lists while keeping logic here.
    """
    if explosion_frames:
        explosion_anims.append({'x': x + random.uniform(-4, 4), 'y': y + random.uniform(-4, 4), 'frame': 0, 'tick': 2.0})
    if generic_images:
        for _ in range(random.randint(8, 15)):
            img = random.choice(generic_images)
            ip = {
                'img': img,
                'x': x + random.uniform(-12 * magnitude, 12 * magnitude),
                'y': y + random.uniform(-12 * magnitude, 12 * magnitude),
                'vx': random.uniform(-3, 3),
                'vy': random.uniform(-3, 3),
                'life': random.randint(24, 90),
                'rot': random.uniform(0, 360),
                'rot_speed': random.uniform(-6, 6),
                'scale': random.uniform(0.3, 1.2)
            }
            image_particles.append(ip)


def make_roguelike_covers(w, h, cell=96, fill_prob=0.18):
    cols = max(4, w // cell)
    rows = max(3, h // cell)
    covers = []
    from game_core import Cover
    for r in range(rows):
        for c in range(cols):
            cx = int((c + 0.5) * (w / cols))
            cy = int((r + 0.5) * (h / rows))
            if cx < 140 or cx > w - 140:
                continue
            if random.random() < fill_prob:
                ww = random.randint(int(cell*0.5), int(cell*0.95))
                hh = random.randint(int(cell*0.4), int(cell*0.9))
                covers.append(Cover(cx - ww//2, cy - hh//2, ww, hh))
    for _ in range(3):
        ww = random.randint(80, 180); hh = random.randint(40, 140)
        x = random.randint(160, max(160, w-200)); y = random.randint(60, max(60, h-120))
        covers.append(Cover(x, y, ww, hh))
    return covers


def make_team(xmin, xmax, color, n=5, side=None, sprite_red=None, sprite_green=None, weapon_ak=None, weapon_m4=None, sounds=None, screen_h=720):
    """Create a team of Soldier instances. This helper accepts the images and sounds the caller uses.
    Returns a list of Soldier objects.
    """
    roles = ['rifle','rifle','grenadier','medic','heavy']
    team = []
    for i in range(n):
        role = random.choice(roles)
        s = Soldier(random.randint(xmin,xmax), random.randint(50,screen_h-50), color, role=role)
        if color == (255,0,0):
            s.sprite = sprite_red
        else:
            s.sprite = sprite_green
        if role == 'heavy' or role == 'grenadier':
            s.weapon_img = weapon_ak
            s.weapon_sound = (sounds.get('ak47') if sounds else None) or (sounds.get('shoot_red') if sounds else None)
            s.weapon_key = 'ak47'
        else:
            s.weapon_img = weapon_m4
            s.weapon_sound = (sounds.get('m4a1') if sounds else None) or ((sounds.get('shoot_blue') if sounds else None) if color==(0,0,255) else (sounds.get('shoot_red') if sounds else None))
            s.weapon_key = 'm4a1'
        team.append(s)
        try:
            wk = getattr(s, 'weapon_key', None)
            if side is not None:
                s.side = side
            else:
                if color == (255,0,0):
                    s.side = 'T'
                else:
                    s.side = 'CT'
            print(f"SPAWN_SOLDIER: name={s.name} role={role} weapon_key={wk} side={getattr(s,'side',None)} sound_loaded={'yes' if (wk and sounds and sounds.get(wk)) else 'no'}")
        except Exception:
            pass
    return team
