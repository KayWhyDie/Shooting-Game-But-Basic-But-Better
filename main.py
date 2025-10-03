# Full rewrite: menu + play & simulation modes + ammo/reload + enlarged start window
import pygame, random, math, os, sys, re
from resources import load_sound_prefer_source, load_image_prefer_source

# Basic settings
# Windowed default size (used when leaving fullscreen)
WINDOWED_DEFAULT = (1280, 720)
# Start fullscreen at this resolution
START_FULLSCREEN_SIZE = (1920, 1080)
FPS = 144
# runtime screen size (updates when toggling fullscreen)
screen_w, screen_h = WINDOWED_DEFAULT

from game_core import Cover, Crate, Particle, Grenade, Bullet, Soldier, set_screen_size, set_frame_scale
from concurrent.futures import ThreadPoolExecutor

# Main
def main():
    global screen_w, screen_h
    pygame.init()
    os.environ['SDL_AUDIODRIVER'] = 'directsound'
    info = pygame.display.Info()
    # start in fullscreen at the current display resolution, with a smaller windowed fallback
    windowed_size = WINDOWED_DEFAULT
    start_full = (info.current_w, info.current_h)
    screen = pygame.display.set_mode(start_full, pygame.FULLSCREEN)
    screen_w, screen_h = start_full
    set_screen_size(screen_w, screen_h)
    pygame.display.set_caption("2D Asker Savaşı - Gelişmiş")
    fullscreen = True
    clock = pygame.time.Clock()
    # thread pool for light-weight parallel updates
    executor = ThreadPoolExecutor(max_workers=max(2, (os.cpu_count() or 2) - 1))
    # cached fonts
    _title_font = pygame.font.SysFont(None, 64)
    _menu_font = pygame.font.SysFont(None, 36)
    _small_font = pygame.font.SysFont(None,18)
    _ammo_font = pygame.font.SysFont(None, 22)
    _default_font = pygame.font.SysFont(None, 20)

    # load sounds if available (resources prefers source/)
    sounds = {}
    sounds['shoot_red'] = load_sound_prefer_source('rifle1.mp3')
    sounds['shoot_blue'] = load_sound_prefer_source('rifle2.mp3')
    sounds['explosion'] = load_sound_prefer_source('explosion.mp3')
    sounds['grenade'] = sounds['explosion']
    sounds['ak47'] = load_sound_prefer_source('ak47.mp3')
    sounds['m4a1'] = load_sound_prefer_source('m4a1.mp3')
    sounds['damage'] = load_sound_prefer_source('damage.mp3')

    # load sprites
    sprite_red = load_image_prefer_source('red.png')
    sprite_green = load_image_prefer_source('green.png')
    weapon_ak = load_image_prefer_source('ak47.png')
    weapon_m4 = load_image_prefer_source('m4a1.png')
    # load explosion frames and generic images. Support files in source/ and source/explosion/
    explosion_frames = []
    generic_images = []
    search_dirs = []
    if os.path.isdir('source'):
        search_dirs.append('source')
    exdir = os.path.join('source', 'explosion')
    if os.path.isdir(exdir):
        search_dirs.append(exdir)

    # collect candidates first so we can sort explosion frames numerically by their suffix
    explosion_candidates = []  # list of (index_or_None, path)
    generic_candidates = []
    for d in search_dirs:
        try:
            for fn in os.listdir(d):
                lf = fn.lower()
                if not lf.endswith('.png'):
                    continue
                path = os.path.join(d, fn)
                if 'explosion' in lf:
                    # try to extract a numeric suffix from the filename (take the last number found)
                    nums = re.findall(r"(\d+)", lf)
                    idx = int(nums[-1]) if nums else None
                    explosion_candidates.append((idx, path))
                    continue
                if lf.startswith('generic'):
                    generic_candidates.append(path)
        except Exception:
            pass

    # sort explosion candidates: those with numeric index first in ascending order, others after
    explosion_candidates.sort(key=lambda t: (t[0] is None, t[0] if t[0] is not None else 0))

    # load explosion frames in sorted numeric order (if available)
    for idx, path in explosion_candidates:
        try:
            img = pygame.image.load(path).convert_alpha()
        except Exception:
            img = None
        if img is not None:
            explosion_frames.append(img)

    # load generic images (keep order but images will be chosen randomly at explosion time)
    for path in generic_candidates:
        try:
            img = pygame.image.load(path).convert_alpha()
        except Exception:
            img = None
        if img is not None:
            generic_images.append(img)

    # helper to spawn an explosion animation + image-particles at (x,y)
    def spawn_explosion(x, y, magnitude=1.0):
        # magnitude may be used to scale particle count / camera shake elsewhere
        if explosion_frames:
            # faster animation: smaller tick value and use frame_scale to advance
            explosion_anims.append({'x': x + random.uniform(-4, 4), 'y': y + random.uniform(-4, 4), 'frame': 0, 'tick': 2.0})
        if generic_images:
            # spawn more particles for real explosions; randomized count (8-15)
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

    # helper to create teams (used in both modes)
    def make_team(xmin, xmax, color, n=5):
        roles = ['rifle','rifle','grenadier','medic','heavy']
        team = []
        for i in range(n):
            role = random.choice(roles)
            s = Soldier(random.randint(xmin,xmax), random.randint(50,screen_h-50), color, role=role)
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

    # Menu state
    mode = 'menu'  # 'menu', 'play', 'simulation'
    menu_options = ['Play', 'Simulation']
    menu_idx = 0

    bullets = []
    grenades = []
    particles = []
    explosion_anims = []
    image_particles = []
    crates = []
    hit_marks = []  # small markers for player-hit impact points
    death_text_timer = 0

    # round/score
    rounds = {'red':0,'blue':0}
    round_state = 1
    round_timer = 0
    best_of = 5

    camera_shake = 0

    running = True
    red_team = []
    blue_team = []
    player = None
    covers = []

    while running:
        # compute frame_scale based on actual ms per frame vs baseline 60fps
        dt_ms = clock.tick(FPS)
        baseline_ms = 1000.0 / 60.0
        frame_scale = max(0.01, dt_ms / baseline_ms)
        try:
            set_frame_scale(frame_scale)
        except Exception:
            pass
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                windowed_size = (event.w, event.h)
                if not fullscreen:
                    screen = pygame.display.set_mode(windowed_size, pygame.RESIZABLE)
                    screen_w, screen_h = windowed_size
                    set_screen_size(screen_w, screen_h)
            elif event.type == pygame.KEYDOWN:
                # F / F11 fullscreen toggle disabled because we start fullscreen by default
                pass
                # ESC returns to main menu from any mode
                if event.key == pygame.K_ESCAPE:
                    # reset state and go back to menu
                    mode = 'menu'
                    menu_idx = 0
                    bullets.clear(); grenades.clear(); particles.clear(); crates.clear()
                    red_team = []
                    blue_team = []
                    player = None
                    round_state = 1
                    round_timer = 0
                    rounds = {'red':0,'blue':0}
                    continue
                # menu navigation
                if mode == 'menu':
                    if event.key == pygame.K_UP:
                        menu_idx = (menu_idx-1) % len(menu_options)
                    elif event.key == pygame.K_DOWN:
                        menu_idx = (menu_idx+1) % len(menu_options)
                    elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                        choice = menu_options[menu_idx]
                        # initialize game depending on choice
                        covers = [Cover(random.randint(100,screen_w-200), random.randint(50,screen_h-150), 50, random.randint(60,160)) for _ in range(3)]
                        bullets.clear(); grenades.clear(); particles.clear(); crates.clear()
                        if choice == 'Play':
                            # spawn full 5v5, then replace one red soldier with the player-controlled soldier
                            red_team = make_team(50, int(screen_w*0.25), (255,0,0), 5)
                            blue_team = make_team(int(screen_w*0.75), screen_w-50, (0,0,255), 5)
                            # create a player soldier
                            player = Soldier(100, screen_h//2, (255,0,0), role='rifle')
                            player.controlled = True
                            player.mag_capacity = 30; player.mag = 30; player.reserve = 90
                            # make player's rifle effectively full-auto by reducing the per-shot cooldown
                            # but keep a realistic reload duration (~3 seconds)
                            player.reload_time_frames = 180
                            player.reload_time = 6
                            player.sprite = sprite_red; player.weapon_img = weapon_m4; player.weapon_sound = sounds.get('m4a1')
                            # replace one AI with player so player is part of the 5-member red team
                            if red_team:
                                red_team[0] = player
                        else:
                            # simulation: full AI 5v5, no player control
                            red_team = make_team(50, int(screen_w*0.25), (255,0,0), 5)
                            blue_team = make_team(int(screen_w*0.75), screen_w-50, (0,0,255), 5)
                            # ensure no player object remains and no soldier is marked controlled
                            player = None
                            for s in red_team+blue_team:
                                s.controlled = False
                                s.mag_capacity = 30; s.mag = 30; s.reserve = 90; s.reload_time_frames = 90
                        round_state = 1; rounds = {'red':0,'blue':0}
                        mode = choice.lower()
                # debug keys available while in a mode (not in menu)
                if event.key == pygame.K_e and mode != 'menu':
                    mx, my = pygame.mouse.get_pos()
                    spawn_explosion(mx, my, magnitude=1.0)
                if event.key == pygame.K_g and mode != 'menu':
                    # spawn only generic image particles at mouse
                    mx, my = pygame.mouse.get_pos()
                    if generic_images:
                        for _ in range(random.randint(5, 12)):
                            img = random.choice(generic_images)
                            ip = {
                                'img': img,
                                'x': mx + random.uniform(-24, 24),
                                'y': my + random.uniform(-24, 24),
                                'vx': random.uniform(-3, 3),
                                'vy': random.uniform(-3, 3),
                                'life': random.randint(24, 90),
                                'rot': random.uniform(0, 360),
                                'rot_speed': random.uniform(-6, 6),
                                'scale': random.uniform(0.3, 1.4)
                            }
                            image_particles.append(ip)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if mode == 'menu' and event.button == 1:
                    # click confirms current selection
                    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))

        # Menu drawing & early continue (use cached fonts)
        if mode == 'menu':
            screen.fill((30,30,30))
            t = _title_font.render('Shooting Game - Menu', True, (220,220,220))
            screen.blit(t, (screen_w//2 - t.get_width()//2, screen_h//6))
            for i, opt in enumerate(menu_options):
                color = (255,255,0) if i==menu_idx else (200,200,200)
                txt = _menu_font.render(opt, True, color)
                screen.blit(txt, (screen_w//2 - txt.get_width()//2, screen_h//2 + i*48))
            inst = _small_font.render('Use Up/Down and Enter or click to choose. F toggles windowed fullscreen.', True, (180,180,180))
            screen.blit(inst, (10, screen_h-30))
            pygame.display.flip(); continue

        # spawn occasional crate (rate scales with frame_scale)
        if random.random() < 0.002 * frame_scale and len(crates) < 3:
            kind = random.choice(['heal','fast_reload','shield'])
            crates.append(Crate(random.randint(100,screen_w-100), random.randint(50,screen_h-50), kind))

        # player input handling (if any) - only while player exists and is alive
        keys = pygame.key.get_pressed()
        mbuttons = pygame.mouse.get_pressed()
        mx, my = pygame.mouse.get_pos()
        if mode == 'play' and player and getattr(player, 'hp', 0) > 0:
            # movement WASD
            mvx = mvy = 0
            if keys[pygame.K_w] or keys[pygame.K_UP]: mvy -= player.speed*1.8
            if keys[pygame.K_s] or keys[pygame.K_DOWN]: mvy += player.speed*1.8
            if keys[pygame.K_a] or keys[pygame.K_LEFT]: mvx -= player.speed*1.8
            if keys[pygame.K_d] or keys[pygame.K_RIGHT]: mvx += player.speed*1.8
            player.x += mvx; player.y += mvy
            player.stay_in_bounds()
            # face based on mouse position so the texture mirrors correctly
            try:
                player.facing_right = (mx > player.x)
            except Exception:
                pass
            # reload key
            if keys[pygame.K_r] and not player.reloading and player.mag < player.mag_capacity and player.reserve>0:
                player.reloading = True; player.reload_timer = player.reload_time_frames
            # AUTO-RELOAD: if mag empty and there is reserve, start reload automatically
            if player.mag <= 0 and player.reserve > 0 and not player.reloading:
                player.reloading = True
                player.reload_timer = player.reload_time_frames
            # shooting with left mouse
            player.reload_counter += 1
            if mbuttons[0] and not player.reloading and player.reload_counter >= player.reload_time and player.mag>0:
                bullets.append(Bullet(player.x + player.weapon_length, player.y, mx, my, player.color, damage=player.damage, owner=player))
                try:
                    if getattr(player, 'weapon_sound', None): player.weapon_sound.play()
                except Exception:
                    pass
                player.mag -= 1
                player.reload_counter = 0
                player.recoil_timer = 3
            # handle player reload timer if reloading
            if player.reloading:
                player.reload_timer -= 1
                if player.reload_timer <= 0:
                    needed = max(0, player.mag_capacity - player.mag)
                    to_load = min(needed, player.reserve)
                    player.reserve -= to_load
                    player.mag += to_load
                    player.reloading = False

        # update entities (skip controlled player as it's handled above)
        for s in list(red_team):
            if getattr(s, 'controlled', False):
                continue
            s.update(blue_team, bullets, grenades, covers, crates, red_team, sounds)
        for s in list(blue_team):
            s.update(red_team, bullets, grenades, covers, crates, blue_team, sounds)

        # parallel updates for cheap objects - safe because these do not access pygame surfaces
        try:
            if bullets:
                list(executor.map(lambda o: o.update(), bullets))
            if grenades:
                list(executor.map(lambda o: o.update(), grenades))
            if particles:
                # cap particle count for performance
                if len(particles) > 1200:
                    del particles[1200:]
                list(executor.map(lambda o: o.update(), particles))
        except Exception:
            for b in bullets: b.update()
            for g in grenades: g.update()
            for p in particles: p.update()

        # Collision resolution and melee handling (pairwise)
        # Prevent any soldiers (including teammates) from occupying the same space.
        # If two opposing soldiers overlap, a melee attack is attempted (subject to melee cooldown).
        all_soldiers = red_team + blue_team
        n = len(all_soldiers)
        for i in range(n):
            for j in range(i+1, n):
                a = all_soldiers[i]
                b = all_soldiers[j]
                dx = b.x - a.x; dy = b.y - a.y
                dist = math.hypot(dx, dy) or 0.001
                min_dist = a.radius + b.radius
                if dist < min_dist:
                    # separate them equally so they no longer overlap
                    overlap = (min_dist - dist) / 2.0
                    nx, ny = dx/dist, dy/dist
                    a.x -= nx * overlap
                    a.y -= ny * overlap
                    b.x += nx * overlap
                    b.y += ny * overlap
                    a.stay_in_bounds(); b.stay_in_bounds()
                    # If they're on opposing teams, resolve melee (cooldown enforced)
                    if getattr(a, 'color', None) is not None and getattr(b, 'color', None) is not None and a.color != b.color:
                        try:
                            if getattr(a, 'melee_timer', 0) <= 0:
                                b.hp -= getattr(a, 'melee_damage', 10)
                                a.melee_timer = getattr(a, 'melee_cooldown_frames', 180)
                                a.face_expression = 'hit'; a.speech_text = 'Slash!'; a.speech_timer = 20
                            if getattr(b, 'melee_timer', 0) <= 0:
                                a.hp -= getattr(b, 'melee_damage', 10)
                                b.melee_timer = getattr(b, 'melee_cooldown_frames', 180)
                                b.face_expression = 'hit'; b.speech_text = 'Slash!'; b.speech_timer = 20
                        except Exception:
                            pass

        for b in bullets[:]:
            # remove offscreen
            if b.x<0 or b.x>screen_w or b.y<0 or b.y>screen_h:
                try: bullets.remove(b)
                except: pass
                continue
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
                                # play damage sound if available
                                try:
                                    if sounds.get('damage'):
                                        sounds['damage'].play()
                                except Exception:
                                    pass
                                # spawn a hit mark if this bullet was fired by the player in play mode
                                try:
                                    if mode == 'play' and b.owner is not None and getattr(b.owner, 'controlled', False):
                                        hit_marks.append({'x': b.x, 'y': b.y, 'life': 30})
                                except Exception:
                                    pass
                        # particles
                        for _ in range(6): particles.append(Particle(b.x, b.y, random.uniform(-2,2), random.uniform(-2,2), random.randint(8,16), (255,200,100)))
                        if b in bullets: bullets.remove(b)
                        hit = True
                        break
                if hit: break

        for g in grenades[:]:
            if g.timer <= 0:
                # explosion logic: handle damage and small particles (in grenades.explode)
                g.explode(red_team+blue_team, particles)
                if sounds.get('explosion'):
                    try: sounds['explosion'].play()
                    except Exception: pass
                camera_shake = 12
                # spawn visuals using the shared helper (faster animation + random generic images)
                spawn_explosion(g.x, g.y, magnitude=1.0)
                # remove grenade
                try: grenades.remove(g)
                except Exception: pass

        # update particles (removals only; updates happened above)
        for p in particles[:]:
            if p.life <= 0:
                try: particles.remove(p)
                except: pass

        # update explosion animations
        for ea in explosion_anims[:]:
            # advance tick scaled by frame_scale so animation speed is stable across fps
            try:
                ea['tick'] -= frame_scale
            except Exception:
                ea['tick'] -= 1
            if ea['tick'] <= 0:
                ea['frame'] += 1
                ea['tick'] = 2.0
            if ea['frame'] >= len(explosion_frames):
                try: explosion_anims.remove(ea)
                except: pass

        # update image particles
        for ip in image_particles[:]:
            ip['x'] += ip['vx'] * frame_scale
            ip['y'] += ip['vy'] * frame_scale
            ip['vy'] += 0.05 * frame_scale  # slight gravity
            ip['rot'] += ip['rot_speed'] * frame_scale
            ip['life'] -= 1 * frame_scale
            if ip['life'] <= 0:
                try: image_particles.remove(ip)
                except: pass

        # update hit marks
        for hm in hit_marks[:]:
            hm['life'] -= 1
            if hm['life'] <= 0:
                try: hit_marks.remove(hm)
                except: pass

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
        prev_red = red_team
        prev_blue = blue_team
        red_team = [s for s in red_team if s.hp>0]
        blue_team = [s for s in blue_team if s.hp>0]
        # If the controlled player died this frame, clear the player reference so it can no longer act
        try:
            if player is not None and getattr(player, 'hp', 0) <= 0:
                # set a short death display timer
                death_text_timer = 180
                player = None
        except Exception:
            player = None

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

        # draw a visible map border so the playable area is clear
        try:
            # compute inset based on the largest soldier radius so the border matches clamping
            all_soldiers = red_team + blue_team
            default_inset = 10
            if all_soldiers:
                max_radius = max(getattr(s, 'radius', default_inset) for s in all_soldiers)
            else:
                max_radius = default_inset
            border_inset = int(max_radius)
            rect = pygame.Rect(border_inset, border_inset, max(0, screen_w - border_inset*2), max(0, screen_h - border_inset*2))
            pygame.draw.rect(screen, (255, 120, 50), rect, 4)
        except Exception:
            pass
        for c in covers: c.draw(screen)
        for s in red_team + blue_team: s.draw(screen)
        for b in bullets: b.draw(screen)
        for g in grenades: g.draw(screen)
        for p in particles: p.draw(screen)
        # draw explosion animations (if frames available)
        if explosion_frames:
            for ea in explosion_anims:
                fi = ea['frame']
                if 0 <= fi < len(explosion_frames):
                    img = explosion_frames[fi]
                    try:
                        rect = img.get_rect(center=(int(ea['x']), int(ea['y'])))
                        screen.blit(img, rect)
                    except Exception:
                        pass
        # draw image particles
        for ip in image_particles:
            try:
                img = ip['img']
                # scale and rotate per-particle
                try:
                    w,h = img.get_size()
                    tw = max(4, int(w * ip['scale']))
                    th = max(4, int(h * ip['scale']))
                    srf = pygame.transform.smoothscale(img, (tw, th))
                except Exception:
                    srf = img
                srf = pygame.transform.rotate(srf, ip['rot'])
                r = srf.get_rect(center=(int(ip['x']), int(ip['y'])))
                screen.blit(srf, r)
            except Exception:
                pass

        for cr in crates: cr.draw(screen)

        # HUD (use cached font)
        txt = _default_font.render(f"Round state: {round_state}  Rounds R:{rounds['red']} B:{rounds['blue']}", True, (255,255,255))
        screen.blit(txt, (8,8))
        # lightweight debug overlay to validate explosion assets and active effects
        try:
            dbg = f"ExplFrames: {len(explosion_frames)}  GenImgs: {len(generic_images)}  ActiveExpl: {len(explosion_anims)}  ImgParts: {len(image_particles)}"
            dbg_s = _small_font.render(dbg, True, (200,200,200))
            screen.blit(dbg_s, (8, 32))
        except Exception:
            pass

        # draw player ammo in play mode
        if mode == 'play' and player:
            try:
                ammo_s = _ammo_font.render(f"Ammo: {player.mag}/{player.reserve}", True, (255,255,0))
                screen.blit(ammo_s, (screen_w-10-ammo_s.get_width(), 10))
                # show reload indicator
                if player.reloading:
                    r_s = _ammo_font.render('RELOADING...', True, (255,120,0))
                    screen.blit(r_s, (screen_w-10-r_s.get_width(), 34))
            except Exception:
                pass
        # if player died recently, show death text
        if mode == 'play' and death_text_timer > 0:
            try:
                death_text_timer -= 1
                dt_surf = _title_font.render('YOU DIED', True, (220,40,40))
                screen.blit(dt_surf, (screen_w//2 - dt_surf.get_width()//2, screen_h//2 - dt_surf.get_height()//2))
            except Exception:
                pass

        # draw hit marks
        for hm in hit_marks:
            x = int(hm['x']); y = int(hm['y'])
            life = hm.get('life', 0)
            alpha = int(255 * (life / 30)) if life>0 else 0
            # simple red X
            try:
                pygame.draw.line(screen, (255,80,80), (x-6,y-6), (x+6,y+6), 2)
                pygame.draw.line(screen, (255,80,80), (x+6,y-6), (x-6,y+6), 2)
            except Exception:
                pass

        pygame.display.flip()

    pygame.quit()

if __name__ == '__main__':
    main()
