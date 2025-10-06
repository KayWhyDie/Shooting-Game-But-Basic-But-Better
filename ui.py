import pygame


def draw_hud(screen, fonts, state):
    """Draw HUD, sandbox overlay, kill feed, debug info, ammo and death text, hit marks.
    fonts: dict with keys '_default_font','_small_font','_ammo_font','_title_font'
    state: dict with many runtime fields (see usage in main.py)
    """
    _default_font = fonts.get('_default_font')
    _small_font = fonts.get('_small_font')
    _ammo_font = fonts.get('_ammo_font')
    _title_font = fonts.get('_title_font')
    screen_w = state.get('screen_w')
    screen_h = state.get('screen_h')
    mode = state.get('mode')
    import pygame


    def draw_hud(screen, fonts, state):
        """Draw HUD elements: round info, debug overlays, kill feed, ammo, death text and hit marks.

        fonts: dict with keys '_default_font','_small_font','_ammo_font','_title_font'
        state: runtime state dict (uses keys from main.py)
        """
        _default_font = fonts.get('_default_font')
        _small_font = fonts.get('_small_font')
        _ammo_font = fonts.get('_ammo_font')
        _title_font = fonts.get('_title_font')

        screen_w = state.get('screen_w', 800)
        screen_h = state.get('screen_h', 600)
        mode = state.get('mode')
        round_state = state.get('round_state')
        rounds = state.get('rounds', {'red': 0, 'blue': 0})
        kill_feed = state.get('kill_feed', [])
        explosion_frames = state.get('explosion_frames', [])
        generic_images = state.get('generic_images', [])
        explosion_anims = state.get('explosion_anims', [])
        image_particles = state.get('image_particles', [])
        player = state.get('player')
        death_text_timer = state.get('death_text_timer', 0)
        hit_marks = state.get('hit_marks', [])

        # round state text
        try:
            if _default_font:
                txt = _default_font.render(f"Round: {round_state}  Rounds R:{rounds.get('red',0)} B:{rounds.get('blue',0)}", True, (255,255,255))
                screen.blit(txt, (8, 8))
        except Exception:
            pass

        # sandbox debug overlay (top-left)
        if mode == 'sandbox':
            try:
                lines = [
                    "Sandbox mode - debug shortcuts:",
                    "H: play m4a1",
                    "J: play ak47",
                    "E: spawn explosion at mouse",
                    "G: spawn generic particles at mouse",
                ]
                for i, l in enumerate(lines):
                    if _small_font:
                        s = _small_font.render(l, True, (200,200,255) if i == 0 else (200,200,200))
                        screen.blit(s, (8, 8 + (i * (s.get_height() + 2))))
            except Exception:
                pass

        # kill feed (top-right)
        try:
            if _small_font:
                kx = screen_w - 8
                ky = 48
                for k in list(kill_feed):
                    s = _small_font.render(k.get('text', ''), True, (255, 220, 180))
                    r = s.get_rect(topright=(kx, ky))
                    screen.blit(s, r)
                    ky += s.get_height() + 4
                    k['life'] = k.get('life', 0) - 1
                    if k['life'] <= 0:
                        try:
                            kill_feed.remove(k)
                        except Exception:
                            pass
        except Exception:
            pass

        # debug asset counters
        try:
            if _small_font:
                dbg = f"ExplFrames: {len(explosion_frames)}  GenImgs: {len(generic_images)}  ActiveExpl: {len(explosion_anims)}  ImgParts: {len(image_particles)}"
                dbg_s = _small_font.render(dbg, True, (200,200,200))
                screen.blit(dbg_s, (8, 32))
        except Exception:
            pass

        # player ammo
        if mode == 'play' and player:
            try:
                if _ammo_font:
                    ammo_s = _ammo_font.render(f"Ammo: {getattr(player, 'mag', 0)}/{getattr(player, 'reserve', 0)}", True, (255,255,0))
                    screen.blit(ammo_s, (screen_w - 10 - ammo_s.get_width(), 10))
                    if getattr(player, 'reloading', False):
                        r_s = _ammo_font.render('RELOADING...', True, (255,120,0))
                        screen.blit(r_s, (screen_w - 10 - r_s.get_width(), 34))
            except Exception:
                pass

        # death text
        if mode == 'play' and death_text_timer > 0:
            try:
                if _title_font:
                    dt_surf = _title_font.render('YOU DIED', True, (220,40,40))
                    screen.blit(dt_surf, (screen_w//2 - dt_surf.get_width()//2, screen_h//2 - dt_surf.get_height()//2))
            except Exception:
                pass

        # hit marks
        try:
            for hm in list(hit_marks):
                x = int(hm.get('x', 0)); y = int(hm.get('y', 0))
                life = hm.get('life', 0)
                try:
                    pygame.draw.line(screen, (255,80,80), (x-6, y-6), (x+6, y+6), 2)
                    pygame.draw.line(screen, (255,80,80), (x+6, y-6), (x-6, y+6), 2)
                except Exception:
                    pass
                hm['life'] = life - 1
                if hm['life'] <= 0:
                    try:
                        hit_marks.remove(hm)
                    except Exception:
                        pass
        except Exception:
            pass
