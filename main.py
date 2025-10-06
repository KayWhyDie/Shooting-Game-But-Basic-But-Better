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

from game_core import Cover, Crate, Particle, Grenade, Bullet, Soldier, set_screen_size, set_frame_scale, _line_blocked_by_covers
from concurrent.futures import ThreadPoolExecutor
from helpers import play_sound_obj, spawn_explosion, make_roguelike_covers, make_team
from debug_tools import spawn_pawn, spawn_bomb_carrier_sandbox, give_bomb_to_random_team, clear_entities
from bomb import draw_bomb, drop_bomb_at, reset_round_bomb
from ui import draw_hud

# Main
def main():
    global screen_w, screen_h
    # request a Windows audio backend before initializing SDL so mixer chooses the right driver
    try:
        os.environ['SDL_AUDIODRIVER'] = 'directsound'
    except Exception:
        pass
    pygame.init()
    # Ensure mixer is initialized for sound playback; safe-guard for systems where audio backend failed
    try:
        pygame.mixer.init()
    except Exception:
        print('Warning: pygame.mixer failed to initialize; sounds may not play')
    # increase mixer channels so multiple gunshots can overlap without cutting previous ones
    try:
        pygame.mixer.set_num_channels(32)
    except Exception:
        pass
    info = pygame.display.Info()
    # start windowed by default to avoid aggressive fullscreen/alt-tab behavior
    windowed_size = WINDOWED_DEFAULT
    screen_w, screen_h = windowed_size
    screen = pygame.display.set_mode(windowed_size, pygame.RESIZABLE)
    set_screen_size(screen_w, screen_h)
    pygame.display.set_caption("2D Asker Savaşı - Gelişmiş")
    fullscreen = False
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
    # set defaults for sound volumes where loaded
    try:
        if sounds.get('m4a1'): sounds['m4a1'].set_volume(0.7)
        if sounds.get('ak47'): sounds['ak47'].set_volume(0.7)
        if sounds.get('explosion'): sounds['explosion'].set_volume(0.8)
    except Exception:
        pass

    # the play_sound_obj helper is provided by helpers.py and imported at module top

    # ensure game_core uses the same play helper so AI sound plays are logged and channel-aware
    try:
        import game_core as _gc
        _gc.play_sound_local = lambda s: play_sound_obj(s, sounds)
    except Exception:
        pass

    # load sprites
    sprite_red = load_image_prefer_source('red.png')
    sprite_green = load_image_prefer_source('green.png')
    weapon_ak = load_image_prefer_source('ak47.png')
    weapon_m4 = load_image_prefer_source('m4a1.png')
    bomb_img = load_image_prefer_source('bomb.png')
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
                # log missing expected sounds for easier debugging
            # debug: print sound load status (helps track missing sounds like m4a1)
            try:
                for k in list(sounds.keys()):
                    print(f"Sound '{k}': {'loaded' if sounds.get(k) else 'missing'}")
            except Exception:
                pass
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

    # spawn_explosion helper is provided by helpers.py; call with resource lists where used

    # team and cover helpers are provided by helpers.py (make_team, make_roguelike_covers)

    # Menu state
    mode = 'menu'  # 'menu', 'play', 'simulation', 'sandbox'
    menu_options = ['Play', 'Simulation', 'Sandbox']
    menu_idx = 0

    bullets = []
    grenades = []
    particles = []
    explosion_anims = []
    image_particles = []
    crates = []
    hit_marks = []  # small markers for player-hit impact points
    kill_feed = []  # list of {'text': str, 'life': int}
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
    # bomb state: carried_by -> Soldier or None; planted boolean and site_rect
    bomb = {'carried_by': None, 'planted': False, 'planted_by': None, 'x': None, 'y': None, 'site_rect': None}

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
                # F: toggle fullscreen/windowed
                if event.key == pygame.K_f:
                    try:
                        if fullscreen:
                            pygame.display.set_mode(windowed_size, pygame.RESIZABLE)
                            screen_w, screen_h = windowed_size
                            fullscreen = False
                        else:
                            info = pygame.display.Info()
                            screen = pygame.display.set_mode((info.current_w, info.current_h), pygame.FULLSCREEN)
                            screen_w, screen_h = info.current_w, info.current_h
                            fullscreen = True
                        set_screen_size(screen_w, screen_h)
                    except Exception:
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
                        # generate roguelike-style covers for more walls
                        covers = make_roguelike_covers(screen_w, screen_h, cell=96, fill_prob=0.18)
                        bullets.clear(); grenades.clear(); particles.clear(); crates.clear()
                        if choice == 'Play':
                            # pick randomly which color becomes T (they'll carry/plant the bomb)
                            # red_color and blue_color refer to sprite color; T/CT assignment is per-team
                            # we'll make either red or blue the Terrorist (T) side for this match
                            t_color = random.choice([(255,0,0), (0,0,255)])
                            ct_color = (0,0,255) if t_color == (255,0,0) else (255,0,0)
                            # when creating teams, pass the side so all members share it
                            if t_color == (255,0,0):
                                red_team = make_team(50, int(screen_w*0.25), (255,0,0), 5, side='T', sprite_red=sprite_red, sprite_green=sprite_green, weapon_ak=weapon_ak, weapon_m4=weapon_m4, sounds=sounds, screen_h=screen_h)
                                blue_team = make_team(int(screen_w*0.75), screen_w-50, (0,0,255), 5, side='CT', sprite_red=sprite_red, sprite_green=sprite_green, weapon_ak=weapon_ak, weapon_m4=weapon_m4, sounds=sounds, screen_h=screen_h)
                            else:
                                red_team = make_team(50, int(screen_w*0.25), (255,0,0), 5, side='CT', sprite_red=sprite_red, sprite_green=sprite_green, weapon_ak=weapon_ak, weapon_m4=weapon_m4, sounds=sounds, screen_h=screen_h)
                                blue_team = make_team(int(screen_w*0.75), screen_w-50, (0,0,255), 5, side='T', sprite_red=sprite_red, sprite_green=sprite_green, weapon_ak=weapon_ak, weapon_m4=weapon_m4, sounds=sounds, screen_h=screen_h)
                            # create a player soldier
                            player = Soldier(100, screen_h//2, (255,0,0), role='rifle')
                            player.controlled = True
                            player.mag_capacity = 30; player.mag = 30; player.reserve = 90
                            # make player's rifle effectively full-auto by reducing the per-shot cooldown
                            # but keep a realistic reload duration (~3 seconds)
                            player.reload_time_frames = 180
                            player.reload_time = 6
                            player.sprite = sprite_red; player.weapon_img = weapon_m4; player.weapon_sound = sounds.get('m4a1')
                            player.weapon_key = 'm4a1'
                            try:
                                print(f"SPAWN_PLAYER: name={player.name} weapon_key={getattr(player,'weapon_key',None)} sound_loaded={'yes' if sounds.get(getattr(player,'weapon_key',None)) else 'no'}")
                            except Exception:
                                pass
                            # replace one AI with player so player is part of the 5-member red team
                            if red_team:
                                red_team[0] = player
                            # create a bomb site on the CT spawn and give the bomb to a random T soldier
                            try:
                                # determine which color is CT to place the site in their spawn area
                                if (red_team and getattr(red_team[0], 'side', None) == 'CT'):
                                    bomb_site = pygame.Rect(20, screen_h//2 - 48, 96, 96)
                                else:
                                    bomb_site = pygame.Rect(screen_w-20-96, screen_h//2 - 48, 96, 96)
                                bomb['site_rect'] = bomb_site
                                bomb['planted'] = False; bomb['planted_by'] = None; bomb['carried_by'] = None
                                # give the bomb to a random T team soldier
                                t_candidates = [s for s in (red_team + blue_team) if getattr(s, 'side', None) == 'T']
                                if t_candidates:
                                    carrier = random.choice(t_candidates)
                                    carrier.carrying_bomb = True
                                    bomb['carried_by'] = carrier
                            except Exception:
                                pass
                        elif choice == 'Simulation':
                            # simulation: full AI 5v5, no player control
                            # pick randomly which color is T
                            t_color = random.choice([(255,0,0), (0,0,255)])
                            if t_color == (255,0,0):
                                red_team = make_team(50, int(screen_w*0.25), (255,0,0), 5, side='T', sprite_red=sprite_red, sprite_green=sprite_green, weapon_ak=weapon_ak, weapon_m4=weapon_m4, sounds=sounds, screen_h=screen_h)
                                blue_team = make_team(int(screen_w*0.75), screen_w-50, (0,0,255), 5, side='CT', sprite_red=sprite_red, sprite_green=sprite_green, weapon_ak=weapon_ak, weapon_m4=weapon_m4, sounds=sounds, screen_h=screen_h)
                            else:
                                red_team = make_team(50, int(screen_w*0.25), (255,0,0), 5, side='CT', sprite_red=sprite_red, sprite_green=sprite_green, weapon_ak=weapon_ak, weapon_m4=weapon_m4, sounds=sounds, screen_h=screen_h)
                                blue_team = make_team(int(screen_w*0.75), screen_w-50, (0,0,255), 5, side='T', sprite_red=sprite_red, sprite_green=sprite_green, weapon_ak=weapon_ak, weapon_m4=weapon_m4, sounds=sounds, screen_h=screen_h)
                            # ensure no player object remains and no soldier is marked controlled
                            player = None
                            for s in red_team+blue_team:
                                s.controlled = False
                                s.mag_capacity = 30; s.mag = 30; s.reserve = 90; s.reload_time_frames = 90
                        elif choice == 'Sandbox':
                            # sandbox: empty scene for debugging; no teams, start empty and let user spawn via debug keys
                            red_team = []
                            blue_team = []
                            player = None
                            bullets.clear(); grenades.clear(); particles.clear(); crates.clear(); explosion_anims.clear(); image_particles.clear()
                            # ensure no bomb in sandbox
                            bomb['carried_by'] = None; bomb['planted'] = False; bomb['planted_by'] = None; bomb['site_rect'] = None
                        # reset round state and scores
                        round_state = 1; rounds = {'red':0,'blue':0}
                        mode = choice.lower()
                # debug keys available while in a mode (not in menu)
                if event.key == pygame.K_e and mode != 'menu':
                    mx, my = pygame.mouse.get_pos()
                    spawn_explosion(mx, my, explosion_frames, generic_images, explosion_anims, image_particles, magnitude=1.0)
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
                # spawn a test pawn in Sandbox with K
                if event.key == pygame.K_k and mode == 'sandbox':
                    mx, my = pygame.mouse.get_pos()
                    # spawn a test rifleman for the active side (blue)
                    spawn_pawn(mx, my, (0,0,255), 'rifle', blue_team, sprite_green, weapon_m4, 'm4a1')
                # spawn a red test pawn in sandbox (Y)
                if event.key == pygame.K_y and mode == 'sandbox':
                    mx, my = pygame.mouse.get_pos()
                    spawn_pawn(mx, my, (255,0,0), 'rifle', red_team, sprite_red, weapon_m4, 'm4a1')
                # spawn a red bomb-carrying pawn in sandbox (U)
                if event.key == pygame.K_u and mode == 'sandbox':
                    mx, my = pygame.mouse.get_pos()
                    s = spawn_pawn(mx, my, (255,0,0), 'rifle', red_team, sprite_red, weapon_m4, 'm4a1')
                    s.carrying_bomb = True
                    bomb['carried_by'] = s
                # plant bomb (P) if carrying and inside site
                if event.key == pygame.K_p and mode != 'menu':
                    try:
                        if bomb.get('carried_by') is not None and bomb.get('site_rect') is not None:
                            cb = bomb['carried_by']
                            if bomb['site_rect'].collidepoint(int(cb.x), int(cb.y)):
                                bomb['planted'] = True
                                bomb['planted_by'] = cb
                                bomb['carried_by'] = None
                                # award round to planting team and advance round
                                team_name = 'blue' if getattr(cb, 'color', None) == (0,0,255) else 'red'
                                rounds[team_name] = rounds.get(team_name, 0) + 1
                                round_state = 2; round_timer = 180
                                print(f"BOMB: planted by {getattr(cb,'name',None)} team={team_name}")
                    except Exception:
                        pass
                # debug: give bomb to a soldier or spawn a bomb-carrying soldier in sandbox (B)
                if event.key == pygame.K_b and mode != 'menu':
                    try:
                        mx,my = pygame.mouse.get_pos()
                        if mode == 'sandbox':
                            spawn_bomb_carrier_sandbox(mx, my, blue_team, sprite_green, weapon_m4, 'm4a1', bomb)
                        else:
                            # in play/simulation, give the bomb to a random blue soldier if exists
                            give_bomb_to_random_team(blue_team, bomb)
                    except Exception:
                        pass
                # drop bomb at mouse (O) — if carried, drop it here; otherwise place a dropped bomb
                if event.key == pygame.K_o and mode != 'menu':
                    try:
                        mx, my = pygame.mouse.get_pos()
                        # if a carrier exists, force-drop at mouse
                        cb = bomb.get('carried_by')
                        if cb is not None:
                            try:
                                cb.carrying_bomb = False
                            except Exception:
                                pass
                            bomb['carried_by'] = None
                        bomb['x'] = int(mx); bomb['y'] = int(my); bomb['planted'] = False
                        print(f"DEBUG: bomb dropped at {bomb['x']},{bomb['y']}")
                    except Exception:
                        pass
                # give bomb to a random T-side pawn (G)
                if event.key == pygame.K_g and mode != 'menu':
                    try:
                        t_candidates = [s for s in (red_team + blue_team) if getattr(s, 'side', None) == 'T']
                        if t_candidates:
                            give_bomb_to_random_team(t_candidates, bomb)
                    except Exception:
                        pass
                # clear bullets/grenades/particles (C)
                if event.key == pygame.K_c and mode != 'menu':
                    try:
                        clear_entities(bullets, grenades, particles)
                        print('DEBUG: cleared bullets, grenades, and particles')
                    except Exception:
                        pass
                    except Exception:
                        pass
                # allow forcing weapon sounds in sandbox/debug modes
                if event.key == pygame.K_h and mode != 'menu':
                    if sounds.get('m4a1'):
                        try: play_sound_obj(sounds['m4a1'], sounds)
                        except Exception: pass
                if event.key == pygame.K_j and mode != 'menu':
                    if sounds.get('ak47'):
                        try: play_sound_obj(sounds['ak47'], sounds)
                        except Exception: pass
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
            # attempt movement but avoid entering covers (slide along if blocked)
            cand_x = player.x + mvx
            cand_y = player.y + mvy
            blocked = False
            for cov in covers:
                try:
                    if cov.rect.collidepoint(cand_x, cand_y):
                        blocked = True
                        break
                except Exception:
                    pass
            if not blocked:
                player.x = cand_x; player.y = cand_y
            else:
                # try sliding on X only
                cand_x2 = player.x + mvx
                blocked_x = any((cov.rect.collidepoint(cand_x2, player.y) for cov in covers))
                cand_y2 = player.y + mvy
                blocked_y = any((cov.rect.collidepoint(player.x, cand_y2) for cov in covers))
                if not blocked_x:
                    player.x = cand_x2
                elif not blocked_y:
                    player.y = cand_y2
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
            # use frame-scaled timing (matches AI which uses FRAME_SCALE)
            player.reload_counter += frame_scale
            if mbuttons[0] and not player.reloading and player.reload_counter >= player.reload_time and player.mag>0:
                # prevent player shooting through solid covers
                if not _line_blocked_by_covers(player.x, player.y, mx, my, covers):
                    bullets.append(Bullet(player.x + player.weapon_length, player.y, mx, my, player.color, damage=player.damage, owner=player))
                try:
                    # prefer weapon_key mapping to avoid accidental explosion sound usage
                    wk = getattr(player, 'weapon_key', None)
                    s = None
                    if wk and sounds.get(wk):
                        s = sounds.get(wk)
                    else:
                        s = (sounds.get('shoot_red') if player.color == (255,0,0) else sounds.get('shoot_blue'))
                    if s and s is not sounds.get('explosion') and s is not sounds.get('grenade'):
                        play_sound_obj(s, sounds)
                except Exception:
                    pass
                player.mag -= 1
                player.reload_counter = 0
            # debug: force play weapon sounds
            if keys[pygame.K_h]:
                if sounds.get('m4a1'):
                    try: play_sound_obj(sounds['m4a1'], sounds)
                    except Exception: pass
            if keys[pygame.K_j]:
                if sounds.get('ak47'):
                    try: play_sound_obj(sounds['ak47'], sounds)
                    except Exception: pass
                player.recoil_timer = 3
            # handle player reload timer if reloading (frame-scaled)
            if player.reloading:
                player.reload_timer -= frame_scale
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
            s.update(blue_team, bullets, grenades, covers, crates, red_team, sounds, bomb)
        for s in list(blue_team):
            s.update(red_team, bullets, grenades, covers, crates, blue_team, sounds, bomb)

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
            # cover collision: bullets are blocked by covers (act like walls)
            blocked = False
            for cov in covers:
                try:
                    if cov.rect.collidepoint(b.x, b.y):
                        # spawn small impact particles and remove bullet
                        for _ in range(4): particles.append(Particle(b.x, b.y, random.uniform(-1.5,1.5), random.uniform(-1.5,1.5), random.randint(6,12), (180,180,180)))
                        try: bullets.remove(b)
                        except: pass
                        blocked = True
                        break
                except Exception:
                    pass
            if blocked:
                continue
            hit = False
            for team in [red_team, blue_team]:
                for s in team:
                    if b.color != s.color and math.hypot(b.x-s.x, b.y-s.y) < b.radius + s.radius:
                        if not s.in_cover(covers):
                            if s.shield>0:
                                s.shield -=1
                            else:
                                # record last attacker for kill feed
                                try:
                                    s.last_attacker = getattr(b.owner, 'name', None)
                                except Exception:
                                    s.last_attacker = None
                                s.hp -= b.damage
                                s.face_expression = 'hit'; s.speech_text = 'Ouch!'; s.speech_timer = 30
                                # if soldier was carrying the bomb, drop it here
                                try:
                                    if getattr(s, 'carrying_bomb', False):
                                        s.carrying_bomb = False
                                        if bomb.get('carried_by') is s:
                                            bomb['carried_by'] = None
                                            # place dropped bomb near soldier
                                            bomb['x'] = int(s.x + random.randint(-8,8))
                                            bomb['y'] = int(s.y + random.randint(-8,8))
                                            bomb['planted'] = False
                                except Exception:
                                    pass
                                # play damage sound if available
                                try:
                                    if sounds.get('damage'):
                                        try: play_sound_obj(sounds['damage'], sounds)
                                        except Exception: pass
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
                    try: play_sound_obj(sounds['explosion'], sounds)
                    except Exception: pass
                camera_shake = 12
                # spawn visuals using the shared helper (faster animation + random generic images)
                spawn_explosion(g.x, g.y, explosion_frames, generic_images, explosion_anims, image_particles, magnitude=1.0)
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
        # produce kill-feed entries for soldiers who just died
        newly_dead = [s for s in (prev_red + prev_blue) if getattr(s, 'hp', 0) <= 0]
        for d in newly_dead:
            try:
                killer = getattr(d, 'last_attacker', None) or 'Unknown'
                feed_text = f"{killer} killed {getattr(d, 'name', 'Soldier')}"
                kill_feed.append({'text': feed_text, 'life': 180})
            except Exception:
                pass
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
                    # respawn teams unless sandbox
                    if mode != 'sandbox':
                        # pick which color is Terrorist this round
                        t_color = random.choice([(255,0,0), (0,0,255)])
                        if t_color == (255,0,0):
                            red_team = make_team(50,200,(255,0,0),5, side='T', sprite_red=sprite_red, sprite_green=sprite_green, weapon_ak=weapon_ak, weapon_m4=weapon_m4, sounds=sounds, screen_h=screen_h)
                            blue_team = make_team(600,750,(0,0,255),5, side='CT', sprite_red=sprite_red, sprite_green=sprite_green, weapon_ak=weapon_ak, weapon_m4=weapon_m4, sounds=sounds, screen_h=screen_h)
                        else:
                            red_team = make_team(50,200,(255,0,0),5, side='CT', sprite_red=sprite_red, sprite_green=sprite_green, weapon_ak=weapon_ak, weapon_m4=weapon_m4, sounds=sounds, screen_h=screen_h)
                            blue_team = make_team(600,750,(0,0,255),5, side='T', sprite_red=sprite_red, sprite_green=sprite_green, weapon_ak=weapon_ak, weapon_m4=weapon_m4, sounds=sounds, screen_h=screen_h)
                        bullets.clear(); grenades.clear(); particles.clear(); crates.clear()
                        # reset bomb for normal rounds; place site on CT spawn and give bomb to a T soldier
                        try:
                            if (red_team and getattr(red_team[0], 'side', None) == 'CT'):
                                bomb_site = pygame.Rect(20, screen_h//2 - 48, 96, 96)
                            else:
                                bomb_site = pygame.Rect(screen_w-20-96, screen_h//2 - 48, 96, 96)
                            bomb['site_rect'] = bomb_site
                            bomb['planted'] = False; bomb['planted_by'] = None; bomb['carried_by'] = None
                            t_candidates = [s for s in (red_team + blue_team) if getattr(s, 'side', None) == 'T']
                            if t_candidates:
                                carrier = random.choice(t_candidates)
                                carrier.carrying_bomb = True
                                bomb['carried_by'] = carrier
                        except Exception:
                            bomb['carried_by'] = None; bomb['planted'] = False; bomb['planted_by'] = None; bomb['site_rect'] = None
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
            # inset equals pawn radius so clamp matches exactly
            border_inset = int(max_radius)
            # draw a 1px inner rect showing playable/clamped area exactly
            inner_left = border_inset
            inner_top = border_inset
            inner_w = max(0, screen_w - border_inset*2)
            inner_h = max(0, screen_h - border_inset*2)
            try:
                color = (255, 120, 50)
                rect = pygame.Rect(inner_left, inner_top, inner_w, inner_h)
                # draw an inner rect border (1 px). Using rect fixes asymmetric off-by-one issues.
                pygame.draw.rect(screen, color, rect, 1)
            except Exception:
                pass
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
        # draw bomb indicators & carrier visuals (delegated to bomb module)
        try:
            draw_bomb(screen, bomb, bomb_img)
        except Exception:
            pass

        # draw HUD and overlays via ui module (centralizes HUD code)
        try:
            fonts = {'_default_font': _default_font, '_small_font': _small_font, '_ammo_font': _ammo_font, '_title_font': _title_font}
            state = {'screen_w': screen_w, 'screen_h': screen_h, 'mode': mode, 'round_state': round_state, 'rounds': rounds, 'kill_feed': kill_feed, 'explosion_frames': explosion_frames, 'generic_images': generic_images, 'explosion_anims': explosion_anims, 'image_particles': image_particles, 'player': player, 'death_text_timer': death_text_timer, 'hit_marks': hit_marks}
            draw_hud(screen, fonts, state)
        except Exception:
            pass

        pygame.display.flip()

    pygame.quit()

if __name__ == '__main__':
    main()
