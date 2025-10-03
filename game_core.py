import pygame
import random
import math

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
    def __init__(self, x, y, tx, ty):
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
    def __init__(self, x, y, color, role='rifle'):
        self.x = float(x)
        self.y = float(y)
        self.color = color
        self.role = role
        self.radius = 10
        self.max_hp = 100
        self.hp = self.max_hp
        self.speed = 1.5
        # firing cooldown (frames) and counter
        self.reload_counter = 0.0
        # temporary retreat when too close to an enemy
        self.temporary_retreat_frames = 0
        self.temporary_retreat_target = None
        self.weapon_length = 15
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

        # role based tuning (unified reload/fire rate)
        self.reload_time = DEFAULT_RELOAD_TIME
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

    def in_cover(self, covers):
        for c in covers:
            if c.rect.collidepoint(self.x, self.y):
                return True
        return False

    def move_towards(self, target):
        dx = target.x - self.x
        dy = target.y - self.y
        dist = math.hypot(dx, dy) or 1.0
        if dist > 1.0:
            self.x += dx / dist * (self.speed * FRAME_SCALE)
            self.y += dy / dist * (self.speed * FRAME_SCALE)
        self.stay_in_bounds()

    def dodge_bullets(self, bullets):
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
                self.x -= dx / dist * (self.speed * 1.0 * FRAME_SCALE)
                self.y -= dy / dist * (self.speed * 1.0 * FRAME_SCALE)
                # set cooldown so the soldier won't dodge again immediately
                self.dodge_timer = self.dodge_cooldown_frames
                break
        self.stay_in_bounds()

    def stay_in_bounds(self):
        self.x = clamp(self.x, self.radius, SCREEN_W - self.radius)
        self.y = clamp(self.y, self.radius, SCREEN_H - self.radius)

    def update(self, enemies, bullets, grenades, covers, crates, allies, sounds):
        # simple retreat logic when alone
        if allies is not None and len(allies) <= 1 and random.random() < 0.02:
            self.retreating = True
        if self.retreating:
            # move toward a safe X position but do not return; allow firing and other logic
            target_x = 50 if self.color == (255, 0, 0) else SCREEN_W - 50
            dx = target_x - self.x
            if abs(dx) > 5:
                self.x += math.copysign(self.speed * 1.5 * FRAME_SCALE, dx)
            self.stay_in_bounds()
            # if pinned at border (can't move further) and enemies are nearby, cancel retreat so soldier fights
            pinned = (self.x <= self.radius + 1) or (self.x >= SCREEN_W - self.radius - 1)
            if pinned and enemies:
                # if an enemy is within threat distance, stop retreating so soldier can engage
                nearest_enemy = min(enemies, key=lambda e: math.hypot(e.x - self.x, e.y - self.y))
                if math.hypot(nearest_enemy.x - self.x, nearest_enemy.y - self.y) < 220:
                    self.retreating = False

        # still allow dodging while moving
        self.dodge_bullets(bullets)

        # find nearest enemy target
        target = None
        if enemies:
            target = min(enemies, key=lambda e: math.hypot(e.x - self.x, e.y - self.y))
        if target is not None:
            try:
                self.facing_right = (target.x > self.x)
            except Exception:
                pass

        # seek crates if nearby
        if crates:
            try:
                nearest_crate = min(crates, key=lambda c: math.hypot(c.x - self.x, c.y - self.y))
                if math.hypot(nearest_crate.x - self.x, nearest_crate.y - self.y) < (140 * FRAME_SCALE):
                    self.move_towards(nearest_crate)
            except Exception:
                pass

        # Role-based desired engagement ranges (units)
        desired_ranges = {
            'sniper': 420,
            'rifle': 220,
            'grenadier': 260,
            'medic': 140,
            'heavy': 60,
        }

        # If we have a target and are not in cover, decide movement
        if target and not self.in_cover(covers):
            dist_to_target = math.hypot(target.x - self.x, target.y - self.y)
            desired = desired_ranges.get(self.role, 180)

            # If soldier is completely out of ammo (no mag and no reserve), try to pick up an ammo/fast_reload crate first.
            if self.mag <= 0 and self.reserve <= 0:
                ammo_crates = [c for c in crates if getattr(c, 'kind', '') in ('ammo', 'fast_reload')]
                if ammo_crates:
                    nearest = min(ammo_crates, key=lambda c: math.hypot(c.x - self.x, c.y - self.y))
                    # step towards crate carefully to avoid border-clamping
                    dx = nearest.x - self.x
                    dy = nearest.y - self.y
                    d = math.hypot(dx, dy) or 1.0
                    cand_x = self.x + (dx / d) * (self.speed * FRAME_SCALE)
                    cand_y = self.y + (dy / d) * (self.speed * FRAME_SCALE)
                    if not (cand_x <= self.radius or cand_x >= SCREEN_W - self.radius or cand_y <= self.radius or cand_y >= SCREEN_H - self.radius):
                        self.x = cand_x; self.y = cand_y
                    else:
                        # small lateral nudge to try free space
                        self.x += (self.speed * 0.5 * FRAME_SCALE) * (1 if self.x < SCREEN_W/2 else -1)
                else:
                    # no ammo available, close to enemies to melee
                    self.move_towards(target)
            else:
                # Normal ranged behavior: approach if too far
                if dist_to_target > (desired + 20):
                    self.move_towards(target)
                elif dist_to_target < max(12, (desired * 0.5)):
                    # too close: try to step away, but avoid border-clamping
                    if self.role != 'heavy' and not getattr(self, 'controlled', False):
                        # if a temporary retreat target is active, move toward it
                        if self.temporary_retreat_frames > 0 and self.temporary_retreat_target:
                            try:
                                tx, ty = self.temporary_retreat_target
                                dx = tx - self.x; dy = ty - self.y
                                d = math.hypot(dx, dy) or 1.0
                                self.x += (dx / d) * (self.speed * 1.5 * FRAME_SCALE)
                                self.y += (dy / d) * (self.speed * 1.5 * FRAME_SCALE)
                                self.temporary_retreat_frames -= 1
                                if self.temporary_retreat_frames <= 0:
                                    self.temporary_retreat_target = None
                            except Exception:
                                self.temporary_retreat_target = None
                        else:
                            dx = self.x - target.x
                            dy = self.y - target.y
                            dd = math.hypot(dx, dy) or 1.0
                            step_x = self.x + (dx / dd) * (self.speed * 1.2 * FRAME_SCALE)
                            step_y = self.y + (dy / dd) * (self.speed * 1.2 * FRAME_SCALE)
                            if (step_x <= self.radius or step_x >= SCREEN_W - self.radius or step_y <= self.radius or step_y >= SCREEN_H - self.radius):
                                # can't step directly away because of map border - try nearest cover
                                if covers:
                                    try:
                                        nearest_cover = min(covers, key=lambda c: math.hypot(c.rect.centerx - self.x, c.rect.centery - self.y))
                                        # move a small step toward cover
                                        cdx = nearest_cover.rect.centerx - self.x
                                        cdy = nearest_cover.rect.centery - self.y
                                        cd = math.hypot(cdx, cdy) or 1.0
                                        self.x += (cdx / cd) * (self.speed * FRAME_SCALE)
                                        self.y += (cdy / cd) * (self.speed * FRAME_SCALE)
                                        self.stay_in_bounds()
                                    except Exception:
                                        pass
                            else:
                                self.x = step_x; self.y = step_y; self.stay_in_bounds()
                # if reloading, seek cover while reloading
                if self.reloading and covers:
                    try:
                        nearest_cover = min(covers, key=lambda c: math.hypot(c.rect.centerx - self.x, c.rect.centery - self.y))
                        dx = nearest_cover.rect.centerx - self.x
                        dy = nearest_cover.rect.centery - self.y
                        d = math.hypot(dx, dy) or 1.0
                        self.x += (dx / d) * (self.speed * FRAME_SCALE)
                        self.y += (dy / d) * (self.speed * FRAME_SCALE)
                        self.stay_in_bounds()
                    except Exception:
                        pass

    # firing cadence scaled by FRAME_SCALE so higher FPS doesn't make soldiers shoot faster
        self.reload_counter += FRAME_SCALE

        # handle active reload timer (when reloading)
        if self.reloading:
            self.reload_timer -= FRAME_SCALE
            if self.reload_timer <= 0:
                needed = max(0, self.mag_capacity - self.mag)
                to_load = min(needed, self.reserve)
                self.reserve -= to_load
                self.mag += to_load
                self.reloading = False

        # medic heals teammates instead of firing
        if self.role == 'medic' and self.reload_counter >= self.reload_time:
            self.reload_counter = 0
            if allies:
                ally = min([a for a in allies if a is not self and a.hp > 0], key=lambda a: math.hypot(a.x - self.x, a.y - self.y), default=None)
                if ally and math.hypot(ally.x - self.x, ally.y - self.y) < 100:
                    ally.hp = min(ally.max_hp, ally.hp + 25)
                    self.face_expression = 'shooting'
                    self.speech_text = 'Medic!'
                    self.speech_timer = 30
        else:
            if self.reload_counter >= self.reload_time and target:
                # If we're out of ammo, start reload
                if self.mag <= 0:
                    if self.reserve > 0 and not self.reloading:
                        self.reloading = True
                        self.reload_timer = self.reload_time_frames
                else:
                    did_fire = False
                    if self.role == 'grenadier' and random.random() < 0.25:
                        if self.mag > 0:
                            grenades.append(Grenade(self.x, self.y, target.x, target.y))
                            if sounds and sounds.get('grenade'):
                                try:
                                    sounds['grenade'].play()
                                except Exception:
                                    pass
                            self.mag -= 1
                            did_fire = True
                        else:
                            # no mag: start reload if possible
                            if self.reserve > 0 and not self.reloading:
                                self.reloading = True
                                self.reload_timer = self.reload_time_frames
                                self.speech_text = 'RELOADING'
                                self.speech_timer = 60
                                self.retreating = True
                                # immediate small step toward nearest cover if available
                                if covers:
                                    try:
                                        nc = min(covers, key=lambda c: math.hypot(c.rect.centerx - self.x, c.rect.centery - self.y))
                                        dx = nc.rect.centerx - self.x; dy = nc.rect.centery - self.y
                                        d = math.hypot(dx, dy) or 1.0
                                        self.x += (dx / d) * (self.speed * FRAME_SCALE)
                                        self.y += (dy / d) * (self.speed * FRAME_SCALE)
                                        self.stay_in_bounds()
                                    except Exception:
                                        pass
                    else:
                        if self.mag > 0:
                            bdx = self.weapon_length if self.color == (255, 0, 0) else -self.weapon_length
                            bullets.append(Bullet(self.x + bdx, self.y, target.x, target.y, self.color, damage=self.damage, owner=self))
                            # try to play a sound if available
                            try:
                                if getattr(self, 'weapon_sound', None):
                                    self.weapon_sound.play()
                                else:
                                    if sounds:
                                        (sounds.get('shoot_red') if self.color == (255, 0, 0) else sounds.get('shoot_blue')) and (sounds.get('shoot_red') if self.color == (255, 0, 0) else sounds.get('shoot_blue')).play()
                            except Exception:
                                pass
                            self.mag -= 1
                            did_fire = True
                        else:
                            # no mag: start reload if possible
                            if self.reserve > 0 and not self.reloading:
                                self.reloading = True
                                self.reload_timer = self.reload_time_frames
                                self.speech_text = 'RELOADING'
                                self.speech_timer = 60
                                self.retreating = True
                                if covers:
                                    try:
                                        nc = min(covers, key=lambda c: math.hypot(c.rect.centerx - self.x, c.rect.centery - self.y))
                                        dx = nc.rect.centerx - self.x; dy = nc.rect.centery - self.y
                                        d = math.hypot(dx, dy) or 1.0
                                        self.x += (dx / d) * (self.speed * FRAME_SCALE)
                                        self.y += (dy / d) * (self.speed * FRAME_SCALE)
                                        self.stay_in_bounds()
                                    except Exception:
                                        pass

                    if did_fire:
                        self.reload_counter = 0
                        self.face_expression = 'shooting'
                        self.speech_text = 'Bang!'
                        self.speech_timer = 30
                        self.recoil_timer = 3

        if self.face_expression != 'hit' and self.reload_counter < self.reload_time / 4:
            self.face_expression = 'default'
        if self.speech_timer > 0:
            self.speech_timer -= FRAME_SCALE
        else:
            self.speech_text = ''
        if self.recoil_timer > 0:
            self.recoil_timer -= FRAME_SCALE
        if self.melee_timer > 0:
            self.melee_timer -= FRAME_SCALE

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
            ammo_y = sy - 33
            screen.blit(ammo_s, (ammo_x, ammo_y))
        except Exception:
            pass

        if self.speech_text:
            font = pygame.font.SysFont(None, 16)
            text_surf = font.render(self.speech_text, True, (255, 255, 255))
            tx = sx - text_surf.get_width() // 2
            ty = sy - 48
            pygame.draw.rect(screen, (0, 0, 0), (tx - 3, ty - 2, text_surf.get_width() + 6, text_surf.get_height() + 4))
            screen.blit(text_surf, (tx, ty))

