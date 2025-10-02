import pygame, random, math

# Screen size used by entities; updated from main via set_screen_size
SCREEN_W = 800
SCREEN_H = 600

def set_screen_size(w, h):
    global SCREEN_W, SCREEN_H
    SCREEN_W, SCREEN_H = w, h

def clamp(v, a, b):
    return max(a, min(b, v))

# Cover
class Cover:
    def __init__(self, x, y, w, h):
        self.rect = pygame.Rect(x, y, w, h)

    def draw(self, screen):
        pygame.draw.rect(screen, (100,100,100), self.rect)

# Crate / Power-up
class Crate:
    def __init__(self, x, y, kind):
        self.x = x
        self.y = y
        self.kind = kind  # 'heal', 'fast_reload', 'shield'
        self.radius = 10
        self.timer = 600

    def draw(self, screen):
        color = (0,200,0) if self.kind=='heal' else (200,200,0) if self.kind=='fast_reload' else (150,150,255)
        pygame.draw.rect(screen, color, (self.x-10, self.y-10, 20, 20))

# Particle (sparks/smoke)
class Particle:
    def __init__(self, x, y, vx, vy, life, color, radius=2):
        self.x = x; self.y = y; self.vx = vx; self.vy = vy
        self.life = life; self.color = color; self.radius = radius

    def update(self):
        self.x += self.vx; self.y += self.vy
        self.vx *= 0.98; self.vy *= 0.98
        self.life -= 1

    def draw(self, screen):
        if self.life>0:
            pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)

# Grenade
class Grenade:
    def __init__(self, x, y, tx, ty):
        self.x, self.y = x, y
        dx, dy = tx-x, ty-y
        dist = math.hypot(dx, dy) or 1
        self.vx = dx/dist * 3
        self.vy = dy/dist * 3
        self.timer = 90  # frames before explosion
        self.radius = 6
        self.bounce = 0.6

    def update(self):
        # travel in the thrown direction with light friction (top-down)
        self.x += self.vx
        self.y += self.vy
        # slight friction so grenades slow down naturally
        self.vx *= 0.995
        self.vy *= 0.995
        if self.x < self.radius or self.x > SCREEN_W-self.radius:
            self.vx *= -self.bounce
            self.x = clamp(self.x, self.radius, SCREEN_W-self.radius)
        if self.y < self.radius or self.y > SCREEN_H-self.radius:
            self.vy *= -self.bounce
            self.y = clamp(self.y, self.radius, SCREEN_H-self.radius)
        self.timer -= 1

    def explode(self, soldiers, particles):
        # spawn smoke
        for _ in range(20):
            particles.append(Particle(self.x, self.y, random.uniform(-2,2), random.uniform(-2,2), random.randint(20,40), (100,100,100), radius=3))
        for s in soldiers:
            if math.hypot(self.x-s.x, self.y-s.y) < 80:
                s.hp -= 30
                s.face_expression = 'hit'
                s.speech_text = 'Argh!'
                s.speech_timer = 30

    def draw(self, screen):
        pygame.draw.circle(screen, (200,200,0), (int(self.x), int(self.y)), self.radius)

# Bullet
class Bullet:
    def __init__(self, x, y, tx, ty, color, damage=10, owner=None):
        self.x = x; self.y = y
        dx, dy = tx-x, ty-y
        dist = math.hypot(dx, dy) or 1
        self.vx = dx/dist * 7
        self.vy = dy/dist * 7
        self.color = color
        self.radius = 3
        self.damage = damage
        self.owner = owner

    def update(self):
        self.x += self.vx; self.y += self.vy

    def draw(self, screen):
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)

# Soldier
class Soldier:
    """
    Soldier represents a single pawn in the simulation or player-controlled character.

    Attributes of note:
    - x, y: position
    - hp, max_hp: health values
    - mag, reserve: ammo counts for ranged combat
    - reload_*: reload timers and durations
    - melee_timer, melee_cooldown_frames, melee_damage: melee attack cooldown and damage
    - controlled: True if this soldier is the player-controlled pawn

    Methods:
    - update(...): performs AI movement, reloading and firing decisions
    - draw(screen): draws the soldier (sprite or primitive)

    This class is intended to be simple and easily modifiable; keep gameplay logic here minimal
    and put UI/asset loading outside the class.
    """
    def __init__(self, x, y, color, role='rifle'):
        self.x = x; self.y = y; self.color = color; self.role = role
        self.radius = 10
        self.max_hp = 100
        self.hp = self.max_hp
        self.speed = 1.5
        # firing cooldown (frames) and counter
        self.reload_counter = 0
        self.weapon_length = 15
        self.face_expression = 'default'
        self.speech_timer = 0; self.speech_text = ''
        self.shield = 0
        self.retreating = False
        self.recoil_timer = 0
        # ammo for both AI and player
        self.mag_capacity = 30
        self.mag = self.mag_capacity
        self.reserve = 90
        self.reloading = False
        self.reload_time_frames = 180  # frames to reload full mag (~3 seconds at 60fps)
        self.reload_timer = 0
        self.controlled = False
        # melee: close-quarters attack cooldown and damage
        # melee_timer counts down to 0; when <=0 the soldier can melee again
        self.melee_cooldown_frames = 180  # allow a melee once every ~3 seconds at 60 FPS
        self.melee_timer = 0
        # melee damage is smaller than many ranged hits but still meaningful
        self.melee_damage = 20
        # facing direction: True when sprite should face right, False when facing left
        # default to facing right because textures are drawn facing right
        self.facing_right = True
        # role params
        if role == 'sniper':
            self.reload_time = random.randint(120, 180); self.damage = 40; self.range = 900
        elif role == 'heavy':
            self.reload_time = random.randint(8, 18); self.damage = 6; self.speed = 1.0; self.max_hp = 150; self.hp = 150; self.radius = 12
        elif role == 'medic':
            self.reload_time = random.randint(30, 60); self.damage = 0; self.range = 120; self.speed = 1.6
        elif role == 'grenadier':
            self.reload_time = random.randint(40, 80); self.damage = 8; self.range = 350
        else:
            self.reload_time = random.randint(30, 60); self.damage = 12; self.range = 400

    def in_cover(self, covers):
        for c in covers:
            if c.rect.collidepoint(self.x, self.y):
                return True
        return False

    def move_towards(self, target):
        dx, dy = target.x - self.x, target.y - self.y
        dist = math.hypot(dx, dy) or 1
        if dist > 1:
            self.x += dx/dist * self.speed
            self.y += dy/dist * self.speed
        self.stay_in_bounds()

    def dodge_bullets(self, bullets):
        for b in bullets:
            dx, dy = b.x - self.x, b.y - self.y
            dist = math.hypot(dx, dy) or 1
            if dist < 60:
                self.x -= dx/dist * self.speed * 2
                self.y -= dy/dist * self.speed * 2
        self.stay_in_bounds()

    def stay_in_bounds(self):
        # clamp(value, min, max)
        self.x = clamp(self.x, self.radius, SCREEN_W-self.radius)
        self.y = clamp(self.y, self.radius, SCREEN_H-self.radius)

    def update(self, enemies, bullets, grenades, covers, crates, allies, sounds):
        # allies used for medic & retreat logic
        if allies is not None and len(allies) <= 1 and random.random() < 0.02:
            self.retreating = True
        if self.retreating:
            target_x = 50 if self.color==(255,0,0) else SCREEN_W-50
            dx = target_x - self.x
            if abs(dx) > 5:
                self.x += math.copysign(self.speed*1.5, dx)
            # ensure retreating soldiers stay in bounds
            self.stay_in_bounds()
            return

        self.dodge_bullets(bullets)
        target = None
        if enemies:
            target = min(enemies, key=lambda e: math.hypot(e.x-self.x, e.y-self.y))
        # set facing direction based on current target if available
        if target is not None:
            try:
                self.facing_right = (target.x > self.x)
            except Exception:
                pass

        # move to crates if nearby
        if crates:
            nearest_crate = min(crates, key=lambda c: math.hypot(c.x-self.x, c.y-self.y))
            if math.hypot(nearest_crate.x-self.x, nearest_crate.y-self.y) < 140:
                self.move_towards(nearest_crate)

        if target and not self.in_cover(covers) and math.hypot(target.x-self.x, target.y-self.y) > 30:
            self.move_towards(target)

        self.reload_counter += 1
        # handle reload timer if reloading
        if self.reloading:
            self.reload_timer -= 1
            if self.reload_timer <= 0:
                # finish reload: top up the magazine from reserve (don't overwrite any existing bullets)
                needed = max(0, self.mag_capacity - self.mag)
                to_load = min(needed, self.reserve)
                self.reserve -= to_load
                self.mag += to_load
                self.reloading = False

        # medic heals
        if self.role == 'medic' and self.reload_counter >= self.reload_time:
            self.reload_counter = 0
            if allies:
                ally = min([a for a in allies if a is not self and a.hp>0], key=lambda a: math.hypot(a.x-self.x, a.y-self.y), default=None)
                if ally and math.hypot(ally.x-self.x, ally.y-self.y) < 100:
                    ally.hp = min(ally.max_hp, ally.hp + 25)
                    self.face_expression = 'shooting'; self.speech_text = 'Medic!'; self.speech_timer = 30
        else:
            if self.reload_counter >= self.reload_time and target:
                dist = math.hypot(target.x-self.x, target.y-self.y)
                # If we're out of ammo, start reloading instead of firing
                if self.mag <= 0:
                    if self.reserve > 0 and not self.reloading:
                        self.reloading = True
                        self.reload_timer = self.reload_time_frames
                else:
                    # grenadier throws sometimes
                    if self.role == 'grenadier' and random.random() < 0.25:
                        grenades.append(Grenade(self.x, self.y, target.x, target.y))
                        if sounds and sounds.get('grenade'): sounds['grenade'].play()
                        self.mag -= 1
                    else:
                        bdx = self.weapon_length if self.color==(255,0,0) else -self.weapon_length
                        bullets.append(Bullet(self.x + bdx, self.y, target.x, target.y, self.color, damage=self.damage, owner=self))
                        # play per-soldier weapon sound if available, otherwise fallback to team sound
                        try:
                            if getattr(self, 'weapon_sound', None):
                                self.weapon_sound.play()
                            else:
                                (sounds.get('shoot_red') if self.color==(255,0,0) else sounds.get('shoot_blue')).play()
                        except Exception:
                            pass
                        self.mag -= 1
                self.reload_counter = 0
                self.face_expression = 'shooting'; self.speech_text = 'Bang!'; self.speech_timer = 30; self.recoil_timer = 3

        if self.face_expression != 'hit' and self.reload_counter < self.reload_time/4:
            self.face_expression = 'default'
        if self.speech_timer > 0:
            self.speech_timer -= 1
        else:
            self.speech_text = ''
        if self.recoil_timer>0:
            self.recoil_timer -=1
        # decrement melee cooldown timer each frame so melee becomes available again
        if self.melee_timer > 0:
            self.melee_timer -= 1

    def draw(self, screen):
        sx, sy = int(self.x), int(self.y)
        # If we have soldier images, draw them; otherwise fallback to circle
        img = None
        if hasattr(self, 'sprite') and self.sprite:
            img = self.sprite
        if img:
            # draw a small scaled sprite (keep very small)
            size = max(12, int(self.radius*2 + 8))
            try:
                orig_w, orig_h = img.get_size()
                scale_h = size
                scale_w = int(orig_w/orig_h * scale_h)
                scaled = pygame.transform.smoothscale(img, (scale_w, scale_h))
            except Exception:
                scaled = pygame.transform.smoothscale(img, (size, size))
            # face based on the soldier's current facing flag (set in update)
            draw_img = scaled if getattr(self, 'facing_right', True) else pygame.transform.flip(scaled, True, False)
            rect = draw_img.get_rect(center=(sx, sy))
            screen.blit(draw_img, rect)
            # draw weapon sprite if present
            wimg = getattr(self, 'weapon_img', None)
            if wimg:
                # scale weapon small
                try:
                    ow, oh = wimg.get_size()
                    tw = max(6, int(self.radius*2))
                    th = max(4, int(self.radius))
                    wscaled = pygame.transform.smoothscale(wimg, (tw, th))
                except Exception:
                    wscaled = pygame.transform.smoothscale(wimg, (max(6, self.radius*2), max(4, self.radius)))
                wdraw = wscaled if getattr(self, 'facing_right', True) else pygame.transform.flip(wscaled, True, False)
                recoil_off = -1 if self.recoil_timer>0 else 0
                wx = sx + (int(self.weapon_length/2) + recoil_off) if getattr(self, 'facing_right', True) else sx - (int(self.weapon_length/2) + recoil_off)
                wy = sy
                wrect = wdraw.get_rect(center=(wx, wy))
                screen.blit(wdraw, wrect)
        else:
            pygame.draw.circle(screen, self.color, (sx, sy), self.radius)
            recoil = -1 if self.recoil_timer>0 else 0
            weapon_end_x = int(self.x + (self.weapon_length if self.color==(255,0,0) else -self.weapon_length) + recoil)
            pygame.draw.line(screen, (0,0,0), (sx, sy), (weapon_end_x, sy), 3)
        pygame.draw.rect(screen, (0,0,0), (sx-10, sy-15, 20,4))
        pygame.draw.rect(screen, (0,255,0), (sx-10, sy-15, int(20*self.hp/self.max_hp),4))
        # draw ammo overlay for AI or controlled soldier (move to where speech used to appear)
        try:
            ammo_font = pygame.font.SysFont(None, 14)
            ammo_text = f"{self.mag}/{self.reserve}"
            ammo_s = ammo_font.render(ammo_text, True, (255,255,0))
            # place ammo where the 'ouch' speech was previously drawn
            ammo_x = sx - ammo_s.get_width()//2
            ammo_y = sy - 33
            screen.blit(ammo_s, (ammo_x, ammo_y))
        except Exception:
            pass

        # draw speech text slightly above the ammo so they don't overlap
        if self.speech_text:
            font = pygame.font.SysFont(None, 16)
            text_surf = font.render(self.speech_text, True, (255,255,255))
            tx = sx - text_surf.get_width()//2
            ty = sy - 48
            pygame.draw.rect(screen, (0,0,0), (tx-3, ty-2, text_surf.get_width()+6, text_surf.get_height()+4))
            screen.blit(text_surf, (tx, ty))
