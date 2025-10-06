import random
import pygame


def reset_round_bomb(bomb, red_team, blue_team, screen_w, screen_h):
    """Reset bomb state at round start: place site on CT spawn and give bomb to a T soldier."""
    if red_team and getattr(red_team[0], 'side', None) == 'CT':
        bomb_site = pygame.Rect(20, screen_h // 2 - 48, 96, 96)
    else:
        bomb_site = pygame.Rect(screen_w - 20 - 96, screen_h // 2 - 48, 96, 96)
    bomb['site_rect'] = bomb_site
    bomb['planted'] = False
    bomb['planted_by'] = None
    bomb['carried_by'] = None
    t_candidates = [s for s in (red_team + blue_team) if getattr(s, 'side', None) == 'T']
    if t_candidates:
        carrier = random.choice(t_candidates)
        carrier.carrying_bomb = True
        import random
        import pygame


        def reset_round_bomb(bomb, red_team, blue_team, screen_w, screen_h):
            """Reset bomb state at round start.

            Places the bomb site on the CT side and gives the bomb to a random T.
            """
            import random
            import pygame


            def reset_round_bomb(bomb, red_team, blue_team, screen_w, screen_h):
                """Reset bomb state at round start.

                Places the bomb site on the CT side (opposite the T spawn) and gives the bomb
                to a random T on either team if available.
                """
                # Place the bomb site on the CT side: if red team's first soldier is CT, place site on left.
                if red_team and getattr(red_team[0], 'side', None) == 'CT':
                    bomb_site = pygame.Rect(20, screen_h // 2 - 48, 96, 96)
                else:
                    bomb_site = pygame.Rect(screen_w - 20 - 96, screen_h // 2 - 48, 96, 96)

                bomb['site_rect'] = bomb_site
                bomb['planted'] = False
                bomb['planted_by'] = None
                bomb['carried_by'] = None
                bomb['x'] = None
                bomb['y'] = None

                # Give the bomb to a random T on either team
                t_candidates = [s for s in (red_team + blue_team) if getattr(s, 'side', None) == 'T']
                if t_candidates:
                    carrier = random.choice(t_candidates)
                    try:
                        carrier.carrying_bomb = True
                    except Exception:
                        # best-effort: some test objects may not have the attribute
                        pass
                    bomb['carried_by'] = carrier


            def drop_bomb_at(bomb, x, y):
                """Drop the bomb at (x, y) and clear any carrier reference."""
                cb = bomb.get('carried_by')
                if cb is not None:
                    try:
                        cb.carrying_bomb = False
                    except Exception:
                        pass
                    bomb['carried_by'] = None

                bomb['x'] = int(x)
                bomb['y'] = int(y)
                bomb['planted'] = False


            def draw_bomb(screen, bomb, bomb_img=None):
                """Draw the bomb site, a carried bomb on the carrier's back, and a planted bomb.

                - site: draws a circular indicator and cross over the site rect
                - carried: attempts to blit a scaled bomb_img on the carrier's back, falls back to a circle
                - planted: draws the bomb centered in the site rect
                """
                # Draw bomb site indicator
                sr = bomb.get('site_rect')
                if sr is not None:
                    cx, cy = sr.center
                    rr = max(8, min(sr.width, sr.height) // 2)
                    try:
                        pygame.draw.circle(screen, (200, 60, 60), (cx, cy), rr, 2)
                        pygame.draw.line(screen, (200, 60, 60), (cx - rr // 2, cy - rr // 2), (cx + rr // 2, cy + rr // 2), 2)
                        pygame.draw.line(screen, (200, 60, 60), (cx - rr // 2, cy + rr // 2), (cx + rr // 2, cy - rr // 2), 2)
                    except Exception:
                        try:
                            pygame.draw.rect(screen, (120, 40, 40), sr, 2)
                        except Exception:
                            pass

                # Draw carried bomb on carrier's back
                cb = bomb.get('carried_by')
                if cb is not None:
                    try:
                        facing_right = getattr(cb, 'facing_right', True)
                        radius = getattr(cb, 'radius', 12)
                        off_x = -int(radius * 0.4) if facing_right else int(radius * 0.4)
                        bx = int(getattr(cb, 'x', 0) + off_x)
                        by = int(getattr(cb, 'y', 0) + int(radius * 0.2))

                        if bomb_img is not None:
                            try:
                                scale = max(16, int(radius * 1.6))
                                s = pygame.transform.smoothscale(bomb_img, (scale, scale))
                                r = s.get_rect(center=(bx, by))
                                screen.blit(s, r)
                            except Exception:
                                pygame.draw.circle(screen, (200, 180, 40), (bx, by), max(8, radius // 2))
                        else:
                            pygame.draw.circle(screen, (200, 180, 40), (bx, by), max(8, radius // 2))
                    except Exception:
                        pass

                # Draw planted bomb inside the site (if planted)
                if bomb.get('planted') and sr is not None:
                    cx, cy = sr.center
                    if bomb_img is not None:
                        try:
                            s = pygame.transform.smoothscale(bomb_img, (max(24, sr.width // 2), max(24, sr.height // 2)))
                            r = s.get_rect(center=(cx, cy))
                            screen.blit(s, r)
                        except Exception:
                            try:
                                pygame.draw.circle(screen, (200, 80, 80), (cx, cy), 12)
                            except Exception:
                                pass
                    else:
                        try:
                            pygame.draw.circle(screen, (200, 80, 80), (cx, cy), 12)
                        except Exception:
                            pass
