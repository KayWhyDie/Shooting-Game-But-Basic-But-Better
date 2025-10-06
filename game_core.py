import pygame
import random
import math

# small helper so modules inside game_core can play sounds using available mixer channels
def play_sound_local(snd):
    try:
        if not snd:
            return
        ch = pygame.mixer.find_channel(True)
        if ch:
            ch.play(snd)
    except Exception:
        try:
            snd.play()
        except Exception:
            pass

# Screen size used by entities; main updates this via set_screen_size
SCREEN_W = 800
SCREEN_H = 600


def set_screen_size(w: int, h: int) -> None:
    global SCREEN_W, SCREEN_H
    SCREEN_W, SCREEN_H = int(w), int(h)


# FRAME_SCALE: 1.0 ~= 60 FPS. Main loop should call set_frame_scale(dt_ms / (1000/60))
FRAME_SCALE = 1.0


def set_frame_scale(scale: float) -> None:
    global FRAME_SCALE
    try:
        FRAME_SCALE = max(0.01, float(scale))
    except Exception:
        FRAME_SCALE = 1.0

# Default reload/fire cadence for all soldiers (frames)
DEFAULT_RELOAD_TIME = 45


def clamp(v, a, b):
    return max(a, min(b, v))


def _line_blocked_by_covers(x1, y1, x2, y2, covers):
    # return True if any cover rect intersects the segment (x1,y1)-(x2,y2)
    # Use a conservative sampling approach (step along the line) to avoid
    # corner-case misses from integer clipping and thin intersections.
    try:
        if not covers:
            return False
        dx = x2 - x1; dy = y2 - y1
        dist = math.hypot(dx, dy) or 1.0
        # sample roughly every 4 pixels along the segment
        step = max(1, int(dist // 4))
        steps = max(1, int(dist / step))
        for i in range(steps + 1):
            t = i / float(steps)
            sx = x1 + dx * t
            sy = y1 + dy * t
            for c in covers:
                if c.rect.collidepoint(sx, sy):
                    return True
        # final fallback: also try clipline as a quick check
        for c in covers:
            if c.rect.clipline((int(x1), int(y1), int(x2), int(y2))):
                return True
    except Exception:
        pass
    return False

# Small pool of bot names
BOT_NAMES = [
    'Viper','Rook','Ghost','Echo','Nova','Blitz','Hawk','Mako','Raven','Zephyr',
    'Drift','Sable','Onyx','Jinx','Kite','Frost','Atlas','Crimson','Byte','Volt'
]

def random_bot_name():
    try:
        return random.choice(BOT_NAMES)
    except Exception:
        return 'Bot'


class Cover:
    def __init__(self, x, y, w, h):
        self.rect = pygame.Rect(int(x), int(y), int(w), int(h))

    def draw(self, screen):
        pygame.draw.rect(screen, (100, 100, 100), self.rect)


class Crate:
    def __init__(self, x, y, kind: str = 'heal'):
        self.x = float(x)
        self.y = float(y)
        self.kind = kind
        self.radius = 10
        self.timer = 600

    def draw(self, screen):
        color = (0, 200, 0) if self.kind == 'heal' else (200, 200, 0) if self.kind == 'fast_reload' else (150, 150, 255)
        pygame.draw.rect(screen, color, (int(self.x) - 10, int(self.y) - 10, 20, 20))


class Particle:
    def __init__(self, x, y, vx, vy, life, color, radius=2):
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.life = float(life)
        self.color = color
        self.radius = int(radius)

    def update(self):
        self.x += self.vx * FRAME_SCALE
        self.y += self.vy * FRAME_SCALE
        # gentle drag
        self.vx *= (0.98 ** FRAME_SCALE)
        self.vy *= (0.98 ** FRAME_SCALE)
        self.life -= FRAME_SCALE

    def draw(self, screen):
        if self.life > 0:
            pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)


class Grenade:
    def __init__(self, x, y, tx, ty, owner=None):
        self.x = float(x)
        self.y = float(y)
        dx = float(tx) - self.x
        dy = float(ty) - self.y
        dist = math.hypot(dx, dy) or 1.0
        self.vx = dx / dist * 3.0
        self.vy = dy / dist * 3.0
        self.timer = 90.0
        self.radius = 6
        self.bounce = 0.6
        self.owner = owner

    def update(self):
        self.x += self.vx * FRAME_SCALE
        self.y += self.vy * FRAME_SCALE
        self.vx *= (0.995 ** FRAME_SCALE)
        self.vy *= (0.995 ** FRAME_SCALE)
        if self.x < self.radius or self.x > SCREEN_W - self.radius:
            self.vx *= -self.bounce
            self.x = clamp(self.x, self.radius, SCREEN_W - self.radius)
        if self.y < self.radius or self.y > SCREEN_H - self.radius:
            self.vy *= -self.bounce
            self.y = clamp(self.y, self.radius, SCREEN_H - self.radius)
        self.timer -= FRAME_SCALE

    def explode(self, soldiers, particles):
        # grey shrapnel particle effect removed (visuals are handled centrally in main.spawn_explosion)
        for s in soldiers:
            if math.hypot(self.x - s.x, self.y - s.y) < 80:
                # attribute owner (if present) for kill feed
                try:
                    if getattr(self, 'owner', None) is not None:
                        s.last_attacker = getattr(self.owner, 'name', None)
                except Exception:
                    pass
                s.hp -= 30
                s.face_expression = 'hit'
                s.speech_text = 'Argh!'
                s.speech_timer = 30

    def draw(self, screen):
        pygame.draw.circle(screen, (200, 200, 0), (int(self.x), int(self.y)), self.radius)


class Bullet:
    def __init__(self, x, y, tx, ty, color, damage=10, owner=None):
        self.x = float(x)
        self.y = float(y)
        dx = float(tx) - self.x
        dy = float(ty) - self.y
        dist = math.hypot(dx, dy) or 1.0
        self.vx = dx / dist * 7.0
        self.vy = dy / dist * 7.0
        self.color = color
        self.radius = 3
        self.damage = damage
        self.owner = owner

    def update(self):
        self.x += self.vx * FRAME_SCALE
        self.y += self.vy * FRAME_SCALE

    def draw(self, screen):
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)


class Soldier:
    def __init__(self, x, y, color, role='rifle', name=None):
        self.x = float(x)
        self.y = float(y)
        self.color = color
        self.role = role
        # assign a readable name for kill notifications and debug
        self.name = name if name else random_bot_name()
        # slightly larger pawns for better visibility
        self.radius = 17
        self.max_hp = 100
        self.hp = self.max_hp
        self.speed = 1.5
        # firing cooldown (frames) and counter
        # start with a randomized counter so not all pawns fire at the same time
        self.reload_counter = random.uniform(0.0, DEFAULT_RELOAD_TIME)
        # temporary retreat when too close to an enemy
        self.temporary_retreat_frames = 0
        self.temporary_retreat_target = None
        # slightly longer weapon length so guns are more visible
        self.weapon_length = 26
        self.face_expression = 'default'
        self.speech_timer = 0.0
        self.speech_text = ''
        self.shield = 0
        self.retreating = False
        self.recoil_timer = 0.0
        # dodge cooldown to avoid continuous high-power dodging
        self.dodge_cooldown_frames = 30.0
        self.dodge_timer = 0.0
        # ammo
        self.mag_capacity = 30
        self.mag = self.mag_capacity
        self.reserve = 90
        self.reloading = False
        self.reload_time_frames = 180.0
        self.reload_timer = 0.0
        self.controlled = False
        # melee
        self.melee_cooldown_frames = 180.0
        self.melee_timer = 0.0
        self.melee_damage = 20
        self.facing_right = True
        # debug cooldown to avoid spamming console when diagnosing firing issues
        self._debug_fire_cooldown = 0.0
        # bomb carrying flag (used by bomb game mode)
        self.carrying_bomb = False
        # simple stuck detection: remember recent positions
        self._last_pos_check_x = self.x
        self._last_pos_check_y = self.y
        self._stuck_frames = 0

        # role based tuning (unified reload/fire rate)
        self.reload_time = DEFAULT_RELOAD_TIME
        # keep a base reload time to apply a small random jitter per-shot
        self.reload_time_base = float(self.reload_time)
        if role == 'sniper':
            self.damage = 40
            self.range = 900
        elif role == 'heavy':
            self.damage = 6
            self.speed = 1.0
            self.max_hp = 150
            self.hp = 150
            self.radius = 12
        elif role == 'medic':
            self.damage = 0
            self.range = 120
            self.speed = 1.6
        elif role == 'grenadier':
            self.damage = 8
            self.range = 350
        else:
            self.damage = 12
            self.range = 400

        # finalize reload_time_base based on potentially modified reload_time
        try:
            self.reload_time_base = float(self.reload_time)
        except Exception:
            self.reload_time_base = float(DEFAULT_RELOAD_TIME)
        # initialize reload counter based on the finalized base so AI are staggered
        try:
            self.reload_counter = random.uniform(0.0, max(1.0, self.reload_time_base))
        except Exception:
            self.reload_counter = random.uniform(0.0, DEFAULT_RELOAD_TIME)

    def in_cover(self, covers):
        for c in covers:
            if c.rect.collidepoint(self.x, self.y):
                return True
        return False

    def move_towards(self, target, covers):
        # move toward target but avoid entering cover rectangles
        dx = target.x - self.x
        dy = target.y - self.y
        dist = math.hypot(dx, dy) or 1.0
        if dist > 1.0:
            step_x = self.x + dx / dist * (self.speed * FRAME_SCALE)
            step_y = self.y + dy / dist * (self.speed * FRAME_SCALE)
            # prefer full step if not blocked
            if not self.blocked_by_covers(step_x, step_y, covers):
                self.x = step_x; self.y = step_y
            else:
                # try smaller steps and axis-aligned moves to slide along obstacles
                tried = False
                for factor in (0.6, 0.4, 0.2):
                    sx = self.x + dx / dist * (self.speed * FRAME_SCALE * factor)
                    sy = self.y + dy / dist * (self.speed * FRAME_SCALE * factor)
                    if not self.blocked_by_covers(sx, sy, covers):
                        self.x = sx; self.y = sy; tried = True; break
                if not tried:
                    # axis slide attempts
                    sx = self.x + dx / dist * (self.speed * FRAME_SCALE)
                    if not self.blocked_by_covers(sx, self.y, covers):
                        self.x = sx
                    else:
                        sy = self.y + dy / dist * (self.speed * FRAME_SCALE)
                        if not self.blocked_by_covers(self.x, sy, covers):
                            self.y = sy
        self.stay_in_bounds()

    def blocked_by_covers(self, x, y, covers):
        # returns True if the point (x,y) would be inside any cover rect
        try:
            for c in covers:
                if c.rect.collidepoint(x, y):
                    return True
        except Exception:
            pass
        return False

    def try_move_to(self, x, y, covers):
        # safe move with cover checks; returns True if moved
        if not self.blocked_by_covers(x, y, covers):
            self.x = x; self.y = y; return True
        # try sliding on x
        if not self.blocked_by_covers(x, self.y, covers):
            self.x = x; return True
        # try sliding on y
        if not self.blocked_by_covers(self.x, y, covers):
            self.y = y; return True
        return False

    def dodge_bullets(self, bullets, covers):
        # reduce dodge power and impose a cooldown
        if self.dodge_timer > 0:
            # count down cooldown
            self.dodge_timer -= FRAME_SCALE
            self.dodge_timer = max(0.0, self.dodge_timer)
            return
        for b in bullets:
            dx = b.x - self.x
            dy = b.y - self.y
            dist = math.hypot(dx, dy) or 1.0
            # reduced detection radius
            if dist < 40:
                # smaller dodge distance
                cand_x = self.x - dx / dist * (self.speed * 1.0 * FRAME_SCALE)
                cand_y = self.y - dy / dist * (self.speed * 1.0 * FRAME_SCALE)
                # only dodge into free space
                if not self.blocked_by_covers(cand_x, cand_y, covers):
                    self.x = cand_x; self.y = cand_y
                # set cooldown so the soldier won't dodge again immediately
                self.dodge_timer = self.dodge_cooldown_frames
                break
        self.stay_in_bounds()

    def stay_in_bounds(self):
        self.x = clamp(self.x, self.radius, SCREEN_W - self.radius)
        self.y = clamp(self.y, self.radius, SCREEN_H - self.radius)

    def update(self, enemies, bullets, grenades, covers, crates, allies, sounds, bomb=None):
        # Basic per-frame updates for soldiers with cover-aware movement
        # Retreat if alone occasionally
        if allies is not None and len(allies) <= 1 and random.random() < 0.02:
            self.retreating = True

        if self.retreating:
            target_x = 50 if self.color == (255, 0, 0) else SCREEN_W - 50
            dx = target_x - self.x
            if abs(dx) > 5:
                self.try_move_to(self.x + math.copysign(self.speed * 1.5 * FRAME_SCALE, dx), self.y, covers)
            self.stay_in_bounds()
            # cancel retreat if enemy nearby
            if enemies:
                nearest_enemy = min(enemies, key=lambda e: math.hypot(e.x - self.x, e.y - self.y))
                if math.hypot(nearest_enemy.x - self.x, nearest_enemy.y - self.y) < 220:
                    self.retreating = False

        # dodge bullets (cover-aware)
        self.dodge_bullets(bullets, covers)

        # find nearest enemy
        target = None
        if enemies:
            target = min(enemies, key=lambda e: math.hypot(e.x - self.x, e.y - self.y))
            try:
                self.facing_right = (target.x > self.x)
            except Exception:
                pass

        # seek crates
        if crates:
            try:
                nearest_crate = min(crates, key=lambda c: math.hypot(c.x - self.x, c.y - self.y))
                if math.hypot(nearest_crate.x - self.x, nearest_crate.y - self.y) < (140 * FRAME_SCALE):
                    self.move_towards(nearest_crate, covers)
            except Exception:
                pass

        # engagement ranges
        desired_ranges = {'sniper':420,'rifle':220,'grenadier':260,'medic':140,'heavy':60}

        # movement & engagement
        if target and not self.in_cover(covers):
            dist_to_target = math.hypot(target.x - self.x, target.y - self.y)
            desired = desired_ranges.get(self.role, 180)

            # pick up ammo if empty and none in mag/reserve
            if self.mag <= 0 and self.reserve <= 0:
                ammo_crates = [c for c in crates if getattr(c,'kind','') in ('ammo','fast_reload')]
                if ammo_crates:
                    nearest = min(ammo_crates, key=lambda c: math.hypot(c.x - self.x, c.y - self.y))
                    dx = nearest.x - self.x; dy = nearest.y - self.y
                    d = math.hypot(dx, dy) or 1.0
                    cand_x = self.x + (dx / d) * (self.speed * FRAME_SCALE)
                    cand_y = self.y + (dy / d) * (self.speed * FRAME_SCALE)
                    self.try_move_to(cand_x, cand_y, covers)
                else:
                    self.move_towards(target, covers)
            else:
                if dist_to_target > (desired + 20):
                    self.move_towards(target, covers)
                elif dist_to_target < max(12, (desired * 0.5)) and self.role != 'heavy' and not getattr(self,'controlled',False):
                    # create distance: set temporary retreat target
                    dx = self.x - target.x; dy = self.y - target.y
                    dd = math.hypot(dx, dy) or 1.0
                    retreat_distance = max(40, desired * 0.8)
                    rx = clamp(self.x + (dx / dd) * retreat_distance, self.radius, SCREEN_W - self.radius)
                    ry = clamp(self.y + (dy / dd) * retreat_distance, self.radius, SCREEN_H - self.radius)
                    self.temporary_retreat_target = (rx, ry)
                    self.temporary_retreat_frames = int(30 * FRAME_SCALE) if FRAME_SCALE>0 else 30
                    self.try_move_to(self.x + (dx / dd) * (self.speed * 1.5 * FRAME_SCALE), self.y + (dy / dd) * (self.speed * 1.5 * FRAME_SCALE), covers)
                # if reloading, seek cover while reloading
                if self.reloading and covers:
                    try:
                        nearest_cover = min(covers, key=lambda c: math.hypot(c.rect.centerx - self.x, c.rect.centery - self.y))
                        dx = nearest_cover.rect.centerx - self.x; dy = nearest_cover.rect.centery - self.y
                        d = math.hypot(dx, dy) or 1.0
                        self.try_move_to(self.x + (dx / d) * (self.speed * FRAME_SCALE), self.y + (dy / d) * (self.speed * FRAME_SCALE), covers)
                    except Exception:
                        pass

        # firing cadence scaled by FRAME_SCALE
        self.reload_counter += FRAME_SCALE

        # handle reload timer
        if self.reloading:
            self.reload_timer -= FRAME_SCALE
            if self.reload_timer <= 0:
                needed = max(0, self.mag_capacity - self.mag)
                to_load = min(needed, self.reserve)
                self.reserve -= to_load
                self.mag += to_load
                self.reloading = False

        # medic heals
        if self.role == 'medic' and self.reload_counter >= self.reload_time:
            if allies:
                damaged = [a for a in allies if a is not self and a.hp > 0 and a.hp <= a.max_hp - 10]
                if damaged:
                    ally = min(damaged, key=lambda a: math.hypot(a.x - self.x, a.y - self.y))
                    if math.hypot(ally.x - self.x, ally.y - self.y) < 100:
                        ally.hp = min(ally.max_hp, ally.hp + 25)
                        self.face_expression = 'shooting'
                        self.speech_text = 'Medic!'
                        self.speech_timer = 30
                        self.reload_counter = 0
        else:
            if self.reload_counter >= self.reload_time and target:
                if self.mag <= 0:
                    if self.reserve > 0 and not self.reloading:
                        self.reloading = True; self.reload_timer = self.reload_time_frames
                else:
                    did_fire = False
                    if self.role == 'grenadier' and random.random() < 0.25:
                        if self.mag > 0:
                            # do not lob grenades through solid cover
                            if not _line_blocked_by_covers(self.x, self.y, target.x, target.y, covers):
                                # ensure grenade spawn point isn't inside a cover
                                if not self.blocked_by_covers(self.x, self.y, covers):
                                    grenades.append(Grenade(self.x, self.y, target.x, target.y, owner=self))
                                else:
                                    # try to nudge out of cover
                                    self.try_move_to(self.x + (self.speed * FRAME_SCALE), self.y, covers)
                            else:
                                # try a minor lateral sidestep to get LOS
                                self.try_move_to(self.x + (self.speed * FRAME_SCALE) * (1 if random.random()<0.5 else -1), self.y, covers)
                            if sounds and sounds.get('grenade'):
                                try: play_sound_local(sounds['grenade'])
                                except Exception: pass
                            self.mag -= 1; did_fire = True
                        else:
                            if self.reserve > 0 and not self.reloading:
                                self.reloading = True; self.reload_timer = self.reload_time_frames
                                self.speech_text = 'RELOADING'; self.speech_timer = 60; self.retreating = True
                                if covers:
                                    try:
                                        nc = min(covers, key=lambda c: math.hypot(c.rect.centerx - self.x, c.rect.centery - self.y))
                                        dx = nc.rect.centerx - self.x; dy = nc.rect.centery - self.y
                                        d = math.hypot(dx, dy) or 1.0
                                        self.try_move_to(self.x + (dx / d) * (self.speed * FRAME_SCALE), self.y + (dy / d) * (self.speed * FRAME_SCALE), covers)
                                    except Exception: pass
                    else:
                        if self.mag > 0:
                            # do not shoot through cover; require line-of-sight
                            if not _line_blocked_by_covers(self.x, self.y, target.x, target.y, covers):
                                bdx = self.weapon_length if self.color == (255,0,0) else -self.weapon_length
                                spawn_x = self.x + bdx
                                spawn_y = self.y
                                if not self.blocked_by_covers(spawn_x, spawn_y, covers):
                                    bullets.append(Bullet(spawn_x, spawn_y, target.x, target.y, self.color, damage=self.damage, owner=self))
                                    # play weapon sound for this soldier (prefer weapon_key -> sounds mapping)
                                    try:
                                        if sounds is not None:
                                            s = None
                                            wk = getattr(self, 'weapon_key', None)
                                            if wk:
                                                s = sounds.get(wk)
                                            if s is None:
                                                s = (sounds.get('shoot_red') if self.color == (255,0,0) else sounds.get('shoot_blue'))
                                            # avoid playing explosion/grenade sound as a weapon sound
                                            if s and s is not sounds.get('explosion') and s is not sounds.get('grenade'):
                                                play_sound_local(s)
                                    except Exception:
                                        pass
                                else:
                                    # weapon muzzle would be inside cover; try a small sidestep
                                    self.try_move_to(self.x + (self.speed * FRAME_SCALE) * (1 if random.random()<0.5 else -1), self.y, covers)
                            else:
                                # attempt small lateral sidestep to acquire LOS
                                self.try_move_to(self.x + (self.speed * FRAME_SCALE) * (1 if random.random()<0.5 else -1), self.y, covers)
                                try:
                                    if sounds is not None:
                                        s = None
                                        wk = getattr(self, 'weapon_key', None)
                                        if wk:
                                            s = sounds.get(wk)
                                        if s is None:
                                            s = (sounds.get('shoot_red') if self.color == (255,0,0) else sounds.get('shoot_blue'))
                                        if s:
                                            play_sound_local(s)
                                except Exception:
                                    pass
                            self.mag -= 1; did_fire = True
                        else:
                            if self.reserve > 0 and not self.reloading:
                                self.reloading = True; self.reload_timer = self.reload_time_frames
                                self.speech_text = 'RELOADING'; self.speech_timer = 60; self.retreating = True
                                if covers:
                                    try:
                                        nc = min(covers, key=lambda c: math.hypot(c.rect.centerx - self.x, c.rect.centery - self.y))
                                        dx = nc.rect.centerx - self.x; dy = nc.rect.centery - self.y
                                        d = math.hypot(dx, dy) or 1.0
                                        self.try_move_to(self.x + (dx / d) * (self.speed * FRAME_SCALE), self.y + (dy / d) * (self.speed * FRAME_SCALE), covers)
                                    except Exception: pass

                    if did_fire:
                        # reset counter and apply small random jitter to next shot interval to reduce perfect overlap
                        self.reload_counter = 0
                        # jitter reload_time between 85% and 135% of base
                        try:
                            self.reload_time = max(2, int(self.reload_time_base * random.uniform(0.85, 1.35)))
                        except Exception:
                            self.reload_time = self.reload_time_base
                        self.face_expression = 'shooting'; self.speech_text = 'Bang!'; self.speech_timer = 30; self.recoil_timer = 3
                    else:
                        # if we had a valid target and enough ammo and the reload counter was sufficient but we still didn't fire,
                        # log a short debug line (rate-limited) to help locate cases where AI silently stops shooting
                        try:
                            if target and self.mag > 0 and not self.reloading and self.reload_counter >= self.reload_time and self._debug_fire_cooldown <= 0:
                                print(f"[AI DEBUG] {getattr(self,'name', 'AI')} had target at {int(target.x)},{int(target.y)} but didn't fire. role={self.role} mag={self.mag} reload={self.reload_counter:.1f}/{self.reload_time}")
                                self._debug_fire_cooldown = 120.0
                        except Exception:
                            pass

        if self.face_expression != 'hit' and self.reload_counter < self.reload_time / 4:
            self.face_expression = 'default'
        if self.speech_timer > 0: self.speech_timer -= FRAME_SCALE
        else: self.speech_text = ''
        if self.recoil_timer > 0: self.recoil_timer -= FRAME_SCALE
        if self.melee_timer > 0: self.melee_timer -= FRAME_SCALE

        # debug cooldown countdown
        if getattr(self, '_debug_fire_cooldown', 0) > 0:
            self._debug_fire_cooldown = max(0.0, self._debug_fire_cooldown - FRAME_SCALE)

        # make sure soldier isn't stuck inside a cover - push to nearest edge
        try: self.avoid_covers(covers)
        except Exception: pass

        # simple stuck detection: if position hasn't changed for many frames, nudge
        try:
            if abs(self.x - self._last_pos_check_x) < 0.5 and abs(self.y - self._last_pos_check_y) < 0.5:
                self._stuck_frames += 1
            else:
                self._stuck_frames = 0
            self._last_pos_check_x = self.x; self._last_pos_check_y = self.y
            if self._stuck_frames > max(20, int(10 * FRAME_SCALE)):
                # apply a small random jitter to try to free the pawn
                jitter_x = random.uniform(-8.0, 8.0)
                jitter_y = random.uniform(-8.0, 8.0)
                self.try_move_to(self.x + jitter_x, self.y + jitter_y, covers)
                self._stuck_frames = 0
        except Exception:
            pass

        # Bomb pickup/seek logic for T-side soldiers: if the bomb is dropped (not carried)
        # T soldiers will try to retrieve it: move towards it if within a seek radius,
        # and pick up automatically when close enough.
        try:
            if bomb is not None and getattr(self, 'side', None) == 'T' and not getattr(self, 'carrying_bomb', False):
                # if bomb is currently on ground
                bx = bomb.get('x'); by = bomb.get('y')
                carried = bomb.get('carried_by')
                if carried is None and bx is not None and by is not None:
                    dx = bx - self.x; dy = by - self.y
                    dist = math.hypot(dx, dy) or 0.001
                    # if very close, pick up
                    if dist < 26:
                        self.carrying_bomb = True
                        bomb['carried_by'] = self
                        bomb['x'] = None; bomb['y'] = None
                    # if within seek distance, move toward bomb (pathfind around covers)
                    elif dist < 300:
                        # attempt to move toward bomb but avoid entering covers
                        try:
                            self.move_towards(type('P', (), {'x': bx, 'y': by})(), covers)
                        except Exception:
                            pass
        except Exception:
            pass

    def avoid_covers(self, covers):
        # if soldier is inside any cover rect, move them to the nearest exterior edge
        for c in covers:
            if c.rect.collidepoint(self.x, self.y):
                left = c.rect.left - self.radius
                right = c.rect.right + self.radius
                top = c.rect.top - self.radius
                bottom = c.rect.bottom + self.radius
                # compute distances to each candidate exterior x/y
                dx_left = abs(self.x - left)
                dx_right = abs(self.x - right)
                dy_top = abs(self.y - top)
                dy_bottom = abs(self.y - bottom)
                # choose smallest movement axis
                min_dx = min(dx_left, dx_right)
                min_dy = min(dy_top, dy_bottom)
                if min_dx < min_dy:
                    # push horizontally
                    self.x = left if dx_left < dx_right else right
                else:
                    # push vertically
                    self.y = top if dy_top < dy_bottom else bottom
                # ensure still in bounds
                self.stay_in_bounds()

    def draw(self, screen):
        sx, sy = int(self.x), int(self.y)
        img = getattr(self, 'sprite', None)
        if img:
            try:
                orig_w, orig_h = img.get_size()
                size = max(12, int(self.radius * 2 + 8))
                scale_w = int(orig_w / orig_h * size)
                scaled = pygame.transform.smoothscale(img, (scale_w, size))
            except Exception:
                scaled = pygame.transform.smoothscale(img, (size, size))
            draw_img = scaled if getattr(self, 'facing_right', True) else pygame.transform.flip(scaled, True, False)
            rect = draw_img.get_rect(center=(sx, sy))
            screen.blit(draw_img, rect)
            # draw weapon image if available (on top of sprite)
            wimg = getattr(self, 'weapon_img', None)
            if wimg:
                try:
                    ow, oh = wimg.get_size()
                    tw = max(8, int(self.radius * 2))
                    th = max(6, int(self.radius))
                    wscaled = pygame.transform.smoothscale(wimg, (tw, th))
                except Exception:
                    wscaled = pygame.transform.smoothscale(wimg, (max(8, self.radius * 2), max(6, self.radius)))
                wdraw = wscaled if getattr(self, 'facing_right', True) else pygame.transform.flip(wscaled, True, False)
                recoil_off = -1 if self.recoil_timer > 0 else 0
                wx = sx + (int(self.weapon_length / 2) + recoil_off) if getattr(self, 'facing_right', True) else sx - (int(self.weapon_length / 2) + recoil_off)
                wy = sy
                wrect = wdraw.get_rect(center=(wx, wy))
                screen.blit(wdraw, wrect)
        else:
            pygame.draw.circle(screen, self.color, (sx, sy), self.radius)
            recoil = -1 if self.recoil_timer > 0 else 0
            weapon_end_x = int(self.x + (self.weapon_length if self.color == (255, 0, 0) else -self.weapon_length) + recoil)
            pygame.draw.line(screen, (0, 0, 0), (sx, sy), (weapon_end_x, sy), 3)
            # if no sprite, still draw weapon image when available
            wimg = getattr(self, 'weapon_img', None)
            if wimg:
                try:
                    ow, oh = wimg.get_size()
                    tw = max(8, int(self.radius * 2))
                    th = max(6, int(self.radius))
                    wscaled = pygame.transform.smoothscale(wimg, (tw, th))
                except Exception:
                    wscaled = pygame.transform.smoothscale(wimg, (max(8, self.radius * 2), max(6, self.radius)))
                wdraw = wscaled if getattr(self, 'facing_right', True) else pygame.transform.flip(wscaled, True, False)
                recoil_off = -1 if self.recoil_timer > 0 else 0
                wx = sx + (int(self.weapon_length / 2) + recoil_off) if getattr(self, 'facing_right', True) else sx - (int(self.weapon_length / 2) + recoil_off)
                wy = sy
                wrect = wdraw.get_rect(center=(wx, wy))
                screen.blit(wdraw, wrect)

        # health bar
        pygame.draw.rect(screen, (0, 0, 0), (sx - 10, sy - 15, 20, 4))
        pygame.draw.rect(screen, (0, 255, 0), (sx - 10, sy - 15, int(20 * self.hp / self.max_hp), 4))

        # ammo overlay
        try:
            ammo_font = pygame.font.SysFont(None, 14)
            ammo_text = f"{self.mag}/{self.reserve}"
            ammo_s = ammo_font.render(ammo_text, True, (255, 255, 0))
            ammo_x = sx - ammo_s.get_width() // 2
            # place ammo display below the pawn to avoid overlap with name
            ammo_y = sy + self.radius + 6
            screen.blit(ammo_s, (ammo_x, ammo_y))
        except Exception:
            pass

        # draw name above pawn (slightly above the sprite)
        try:
            name_font = pygame.font.SysFont(None, 14)
            name_s = name_font.render(str(getattr(self, 'name', '')), True, (230,230,230))
            nx = sx - name_s.get_width() // 2
            ny = sy - 30
            screen.blit(name_s, (nx, ny))
        except Exception:
            pass

        # draw speech text above the name so it's visually on top
        if self.speech_text:
            try:
                font = pygame.font.SysFont(None, 16)
                text_surf = font.render(self.speech_text, True, (255, 255, 255))
                tx = sx - text_surf.get_width() // 2
                ty = sy - 52
                pygame.draw.rect(screen, (0, 0, 0), (tx - 3, ty - 2, text_surf.get_width() + 6, text_surf.get_height() + 4))
                screen.blit(text_surf, (tx, ty))
            except Exception:
                pass

        # debug: small dot showing ready-to-fire (helps diagnose AI that should fire but doesn't)
        try:
            if getattr(self, 'mag', 0) > 0 and getattr(self, 'reload_counter', 0) >= getattr(self, 'reload_time', 1):
                pygame.draw.circle(screen, (0, 220, 0), (sx, sy - self.radius - 6), 3)
        except Exception:
            pass

        # draw side label near pawn (T or CT) if present
        try:
            side = getattr(self, 'side', None)
            if side:
                font = pygame.font.SysFont(None, 14)
                side_text = 'CT' if side == 'CT' else 'T'
                s_surf = font.render(side_text, True, (200,200,255) if side_text=='CT' else (200,100,100))
                # place label to lower-left of the pawn
                sx_lbl = sx - self.radius - s_surf.get_width() - 4
                sy_lbl = sy + self.radius - 6
                screen.blit(s_surf, (sx_lbl, sy_lbl))
        except Exception:
            pass

