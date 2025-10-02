import pygame, random, math, os

# Basic settings
WIDTH, HEIGHT = 800, 600
FPS = 60
# runtime screen size (updates when toggling fullscreen)
screen_w, screen_h = WIDTH, HEIGHT

# Utility
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
        if self.x < self.radius or self.x > screen_w-self.radius:
            self.vx *= -self.bounce
            self.x = clamp(self.x, self.radius, screen_w-self.radius)
        if self.y < self.radius or self.y > screen_h-self.radius:
            self.vy *= -self.bounce
            self.y = clamp(self.y, self.radius, screen_h-self.radius)
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
    def __init__(self, x, y, tx, ty, color, damage=10):
        self.x = x; self.y = y
        dx, dy = tx-x, ty-y
        dist = math.hypot(dx, dy) or 1
        self.vx = dx/dist * 7
        self.vy = dy/dist * 7
        self.color = color
        self.radius = 3
        self.damage = damage

    def update(self):
        self.x += self.vx; self.y += self.vy

    def draw(self, screen):
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)

# Soldier
class Soldier:
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
        self.reload_time_frames = 90  # frames to reload full mag
        self.reload_timer = 0
        self.controlled = False
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
        self.x = clamp(self.x, self.radius, screen_w-self.radius)
        self.y = clamp(self.y, self.radius, screen_h-self.radius)

    def update(self, enemies, bullets, grenades, covers, crates, allies, sounds):
        # allies used for medic & retreat logic
        if allies is not None and len(allies) <= 1 and random.random() < 0.02:
            self.retreating = True
        if self.retreating:
            target_x = 50 if self.color==(255,0,0) else screen_w-50
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
                # finish reload
                to_load = min(self.mag_capacity, self.reserve)
                self.reserve -= to_load
                self.mag = to_load
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
                # grenadier throws sometimes
                if self.role == 'grenadier' and random.random() < 0.25:
                    grenades.append(Grenade(self.x, self.y, target.x, target.y))
                    if sounds and sounds.get('grenade'): sounds['grenade'].play()
                    self.mag -= 1
                else:
                    bdx = self.weapon_length if self.color==(255,0,0) else -self.weapon_length
                    bullets.append(Bullet(self.x + bdx, self.y, target.x, target.y, self.color, damage=self.damage))
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
            # face based on horizontal position: left half -> face right, right half -> face left
            facing_right = self.x < screen_w/2
            draw_img = scaled if facing_right else pygame.transform.flip(scaled, True, False)
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
                wdraw = wscaled if facing_right else pygame.transform.flip(wscaled, True, False)
                recoil_off = -1 if self.recoil_timer>0 else 0
                wx = sx + (int(self.weapon_length/2) + recoil_off) if facing_right else sx - (int(self.weapon_length/2) + recoil_off)
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
        # simple face removed; sprites handle appearance
        if self.speech_text:
            font = pygame.font.SysFont(None, 16)
            text_surf = font.render(self.speech_text, True, (255,255,255))
            pygame.draw.rect(screen, (0,0,0), (sx-15, sy-35, text_surf.get_width()+6, text_surf.get_height()+4))
            screen.blit(text_surf, (sx-12, sy-33))
        # draw ammo overlay for AI or controlled soldier
        try:
            ammo_font = pygame.font.SysFont(None, 14)
            ammo_text = f"{self.mag}/{self.reserve}"
            ammo_s = ammo_font.render(ammo_text, True, (255,255,0))
            screen.blit(ammo_s, (sx-ammo_s.get_width()//2, sy-self.radius-28))
        except Exception:
            pass

# Main
def main():
    global screen_w, screen_h
    pygame.init()
    os.environ['SDL_AUDIODRIVER'] = 'directsound'
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption("2D Asker Savaşı - Gelişmiş")
    fullscreen = False
    clock = pygame.time.Clock()
    # store windowed size
    windowed_size = (WIDTH, HEIGHT)

    # load sounds if available
    sounds = {}
    def try_load(path):
        try:
            return pygame.mixer.Sound(path)
        except Exception:
            return None
    # media moved to source/ if present
    sounds['shoot_red'] = try_load(os.path.join('source','rifle1.mp3')) or try_load('rifle1.mp3')
    sounds['shoot_blue'] = try_load(os.path.join('source','rifle2.mp3')) or try_load('rifle2.mp3')
    sounds['explosion'] = try_load(os.path.join('source','explosion.mp3')) or try_load('explosion.mp3')
    sounds['grenade'] = sounds['explosion']
    # prefer weapon-specific sounds
    sounds['ak47'] = try_load(os.path.join('source','ak47.mp3')) or try_load('ak47.mp3')
    sounds['m4a1'] = try_load(os.path.join('source','m4a1.mp3')) or try_load('m4a1.mp3')

    # load sprites
    def try_image(path):
        try:
            return pygame.image.load(path).convert_alpha()
        except Exception:
            return None
    sprite_red = try_image(os.path.join('source','red.png')) or try_image('red.png')
    sprite_green = try_image(os.path.join('source','green.png')) or try_image('green.png')
    weapon_ak = try_image(os.path.join('source','ak47.png')) or try_image('ak47.png')
    weapon_m4 = try_image(os.path.join('source','m4a1.png')) or try_image('m4a1.png')

    covers = [Cover(random.randint(100,700), random.randint(50,450), 50, random.randint(100,200)) for _ in range(3)]

    # spawn teams with roles
    def make_team(xmin, xmax, color, n=5):
        roles = ['rifle','rifle','grenadier','medic','heavy']
        team = []
        for i in range(n):
            role = random.choice(roles)
            s = Soldier(random.randint(xmin,xmax), random.randint(50,550), color, role=role)
            # assign sprites based on color (red/blue)
            if color == (255,0,0):
                s.sprite = sprite_red
            else:
                s.sprite = sprite_green
            # weapon images and sounds per role
            if role == 'heavy' or role == 'grenadier':
                s.weapon_img = weapon_ak
                s.weapon_sound = sounds.get('ak47') or sounds.get('shoot_red')
            else:
                s.weapon_img = weapon_m4
                s.weapon_sound = sounds.get('m4a1') or (sounds.get('shoot_blue') if color==(0,0,255) else sounds.get('shoot_red'))
            team.append(s)
        return team

    red_team = make_team(50,200,(255,0,0),5)
    blue_team = make_team(600,750,(0,0,255),5)
    bullets = []
    grenades = []
    particles = []
    crates = []

    # round/score
    rounds = {'red':0,'blue':0}
    round_state = 1
    round_timer = 0
    best_of = 5

    camera_shake = 0

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                # update windowed size when user resizes the window
                windowed_size = (event.w, event.h)
                if not fullscreen:
                    screen = pygame.display.set_mode(windowed_size, pygame.RESIZABLE)
                    screen_w, screen_h = windowed_size
            elif event.type == pygame.KEYDOWN:
                # toggle fullscreen: F11 or F
                if event.key == pygame.K_F11 or event.key == pygame.K_f:
                    fullscreen = not fullscreen
                    if fullscreen:
                        info = pygame.display.Info()
                        screen = pygame.display.set_mode((info.current_w, info.current_h), pygame.NOFRAME)
                        screen_w, screen_h = info.current_w, info.current_h
                    else:
                        # restore resizable windowed mode
                        screen = pygame.display.set_mode(windowed_size, pygame.RESIZABLE)
                        screen_w, screen_h = windowed_size

        # spawn occasional crate
        if random.random() < 0.002 and len(crates) < 3:
            kind = random.choice(['heal','fast_reload','shield'])
            crates.append(Crate(random.randint(100,700), random.randint(50,550), kind))

        # update entities
        for s in red_team:
            s.update(blue_team, bullets, grenades, covers, crates, red_team, sounds)
        for s in blue_team:
            s.update(red_team, bullets, grenades, covers, crates, blue_team, sounds)

        for b in bullets[:]:
            b.update()
            # remove offscreen
            if b.x<0 or b.x>WIDTH or b.y<0 or b.y>HEIGHT:
                bullets.remove(b); continue
            hit = False
            for team in [red_team, blue_team]:
                for s in team:
                    if b.color != s.color and math.hypot(b.x-s.x, b.y-s.y) < b.radius + s.radius:
                        if not s.in_cover(covers):
                            if s.shield>0:
                                s.shield -=1
                            else:
                                s.hp -= b.damage
                                s.face_expression = 'hit'; s.speech_text = 'Ouch!'; s.speech_timer = 30
                        # particles
                        for _ in range(6): particles.append(Particle(b.x, b.y, random.uniform(-2,2), random.uniform(-2,2), random.randint(8,16), (255,200,100)))
                        if b in bullets: bullets.remove(b)
                        hit = True
                        break
                if hit: break

        for g in grenades[:]:
            g.update()
            if g.timer <= 0:
                # explosion
                g.explode(red_team+blue_team, particles)
                if sounds.get('explosion'): sounds['explosion'].play()
                camera_shake = 12
                # damage handled in explode
                grenades.remove(g)

        # update particles
        for p in particles[:]:
            p.update()
            if p.life <= 0: particles.remove(p)

        # crates pickup
        for c in crates[:]:
            c.timer -=1
            if c.timer<=0: crates.remove(c); continue
            for team in [red_team, blue_team]:
                for s in team:
                    if math.hypot(c.x-s.x, c.y-s.y) < 20:
                        if c.kind=='heal': s.hp = min(s.max_hp, s.hp+40)
                        elif c.kind=='fast_reload': s.reload_time = max(4, int(s.reload_time*0.6))
                        elif c.kind=='shield': s.shield += 1
                        crates.remove(c); break
                else:
                    continue
                break

        # cleanup dead
        red_team = [s for s in red_team if s.hp>0]
        blue_team = [s for s in blue_team if s.hp>0]

        # round logic
        if round_state == 1:
            if not red_team or not blue_team:
                winner = 'red' if blue_team==[] else 'blue'
                rounds[winner] += 1
                round_state = 2
                round_timer = 90
        elif round_state == 2:
            round_timer -=1
            if round_timer<=0:
                # reset for next round unless match over
                if rounds['red'] >= (best_of+1)//2 or rounds['blue'] >= (best_of+1)//2:
                    round_state = 3
                else:
                    # respawn teams
                    red_team = make_team(50,200,(255,0,0),5)
                    blue_team = make_team(600,750,(0,0,255),5)
                    bullets.clear(); grenades.clear(); particles.clear(); crates.clear()
                    round_state = 1

        # camera shake decay
        if camera_shake>0:
            camera_shake = max(0, camera_shake-1)

        # draw
        screen.fill((50,50,50))
        shake_x = random.randint(-camera_shake, camera_shake)
        shake_y = random.randint(-camera_shake, camera_shake)

        for c in covers: c.draw(screen)
        for s in red_team + blue_team: s.draw(screen)
        for b in bullets: b.draw(screen)
        for g in grenades: g.draw(screen)
        for p in particles: p.draw(screen)
        for cr in crates: cr.draw(screen)

        # HUD
        font = pygame.font.SysFont(None, 20)
        txt = font.render(f"Round state: {round_state}  Rounds R:{rounds['red']} B:{rounds['blue']}", True, (255,255,255))
        screen.blit(txt, (8,8))

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()

if __name__ == '__main__':
    main()
