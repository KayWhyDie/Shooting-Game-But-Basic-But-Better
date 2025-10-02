# Full rewrite: menu + play & simulation modes + ammo/reload + enlarged start window
import pygame, random, math, os, sys
from resources import load_sound_prefer_source, load_image_prefer_source

# Basic settings
WIDTH, HEIGHT = 800, 600
FPS = 60
# runtime screen size (updates when toggling fullscreen)
screen_w, screen_h = WIDTH, HEIGHT

from game_core import Cover, Crate, Particle, Grenade, Bullet, Soldier, set_screen_size

# Main
def main():
    global screen_w, screen_h
    pygame.init()
    os.environ['SDL_AUDIODRIVER'] = 'directsound'
    info = pygame.display.Info()
    # start enlarged so borders don't interfere (use most of the screen)
    init_w = min(1200, int(info.current_w * 0.9))
    init_h = min(800, int(info.current_h * 0.85))
    windowed_size = (init_w, init_h)
    screen = pygame.display.set_mode(windowed_size, pygame.RESIZABLE)
    screen_w, screen_h = windowed_size
    set_screen_size(screen_w, screen_h)
    pygame.display.set_caption("2D Asker Savaşı - Gelişmiş")
    fullscreen = False
    clock = pygame.time.Clock()

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
    crates = []
    hit_marks = []  # small markers for player-hit impact points

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
                if event.key == pygame.K_F11 or event.key == pygame.K_f:
                    fullscreen = not fullscreen
                    if fullscreen:
                        info = pygame.display.Info()
                        screen = pygame.display.set_mode((info.current_w, info.current_h), pygame.NOFRAME)
                        screen_w, screen_h = info.current_w, info.current_h
                        set_screen_size(screen_w, screen_h)
                    else:
                        screen = pygame.display.set_mode(windowed_size, pygame.RESIZABLE)
                        screen_w, screen_h = windowed_size
                        set_screen_size(screen_w, screen_h)
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
                            red_team = make_team(50, int(screen_w*0.25), (255,0,0), 4)
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
                            # replace one AI with player to keep numbers reasonable
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
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if mode == 'menu' and event.button == 1:
                    # click confirms current selection
                    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))

        # Menu drawing & early continue
        if mode == 'menu':
            screen.fill((30,30,30))
            title_f = pygame.font.SysFont(None, 64)
            t = title_f.render('Shooting Game - Menu', True, (220,220,220))
            screen.blit(t, (screen_w//2 - t.get_width()//2, screen_h//6))
            mf = pygame.font.SysFont(None, 36)
            for i, opt in enumerate(menu_options):
                color = (255,255,0) if i==menu_idx else (200,200,200)
                txt = mf.render(opt, True, color)
                screen.blit(txt, (screen_w//2 - txt.get_width()//2, screen_h//2 + i*48))
            small = pygame.font.SysFont(None,18)
            inst = small.render('Use Up/Down and Enter or click to choose. F toggles windowed fullscreen.', True, (180,180,180))
            screen.blit(inst, (10, screen_h-30))
            pygame.display.flip(); clock.tick(FPS); continue

        # spawn occasional crate
        if random.random() < 0.002 and len(crates) < 3:
            kind = random.choice(['heal','fast_reload','shield'])
            crates.append(Crate(random.randint(100,screen_w-100), random.randint(50,screen_h-50), kind))

        # player input handling (if any)
        keys = pygame.key.get_pressed()
        mbuttons = pygame.mouse.get_pressed()
        mx, my = pygame.mouse.get_pos()
        if mode == 'play' and player:
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
            b.update()
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

        # draw player ammo in play mode
        if mode == 'play' and player:
            try:
                af = pygame.font.SysFont(None, 22)
                ammo_s = af.render(f"Ammo: {player.mag}/{player.reserve}", True, (255,255,0))
                screen.blit(ammo_s, (screen_w-10-ammo_s.get_width(), 10))
                # show reload indicator
                if player.reloading:
                    r_s = af.render('RELOADING...', True, (255,120,0))
                    screen.blit(r_s, (screen_w-10-r_s.get_width(), 34))
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
        clock.tick(FPS)

    pygame.quit()

if __name__ == '__main__':
    main()
