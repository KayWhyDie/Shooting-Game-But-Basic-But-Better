import pygame, random, math

# Ekran boyutu
WIDTH, HEIGHT = 800, 600
FPS = 60

# Siper sınıfı
class Cover:
    def __init__(self, x, y, w, h):
        self.rect = pygame.Rect(x, y, w, h)

    def draw(self, screen):
        pygame.draw.rect(screen, (100,100,100), self.rect)

# Asker sınıfı
class Soldier:
    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        self.color = color
        self.radius = 10
        self.hp = 100
        self.speed = 1.5
        self.reload_time = random.randint(30, 60)
        self.reload_counter = 0
        self.weapon_length = 15
        self.face_expression = 'default'  # default, shooting, hit
        self.speech_timer = 0
        self.speech_text = ''

    def in_cover(self, covers):
        for c in covers:
            if c.rect.collidepoint(self.x, self.y):
                return True
        return False

    def move_towards(self, target):
        dx, dy = target.x - self.x, target.y - self.y
        dist = math.hypot(dx, dy)
        if dist > 1:
            self.x += dx/dist * self.speed
            self.y += dy/dist * self.speed
        self.stay_in_bounds()

    def dodge_bullets(self, bullets):
        for b in bullets:
            dx, dy = b.x - self.x, b.y - self.y
            dist = math.hypot(dx, dy)
            if dist < 60:
                self.x -= dx/dist * self.speed * 2
                self.y -= dy/dist * self.speed * 2
        self.stay_in_bounds()

    def stay_in_bounds(self):
        self.x = max(self.radius, min(WIDTH - self.radius, self.x))
        self.y = max(self.radius, min(HEIGHT - self.radius, self.y))

    def update(self, enemies, bullets, covers):
        if not enemies:
            return
        self.dodge_bullets(bullets)
        target = min(enemies, key=lambda e: math.hypot(e.x-self.x, e.y-self.y))
        if not self.in_cover(covers) and math.hypot(target.x-self.x, target.y-self.y) > 30:
            self.move_towards(target)
        self.reload_counter +=1
        if self.reload_counter >= self.reload_time:
            self.reload_counter = 0
            bullets.append(Bullet(self.x + (self.weapon_length if self.color==(255,0,0) else -self.weapon_length), self.y, target.x, target.y, self.color))
            self.face_expression = 'shooting'
            self.speech_text = 'Bang!'
            self.speech_timer = 30
        elif self.face_expression != 'hit':
            self.face_expression = 'default'

        if self.speech_timer > 0:
            self.speech_timer -= 1
        else:
            self.speech_text = ''

    def draw(self, screen):
        # Asker
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)
        # Silah çizimi
        weapon_end_x = self.x + self.weapon_length if self.color==(255,0,0) else self.x - self.weapon_length
        pygame.draw.line(screen, (0,0,0), (self.x, self.y), (weapon_end_x, self.y), 3)
        # HP bar
        pygame.draw.rect(screen, (0,0,0), (self.x-10, self.y-15, 20,4))
        pygame.draw.rect(screen, (0,255,0), (self.x-10, self.y-15, 20*self.hp/100,4))
        # Basit yüz ifadeleri
        eye_offset = 3
        mouth_offset = 5
        pygame.draw.circle(screen, (0,0,0), (int(self.x-eye_offset), int(self.y-eye_offset)), 2)
        pygame.draw.circle(screen, (0,0,0), (int(self.x+eye_offset), int(self.y-eye_offset)), 2)
        if self.face_expression == 'shooting':
            pygame.draw.line(screen, (0,0,0), (self.x-3, self.y+mouth_offset), (self.x+3, self.y+mouth_offset), 2)
        elif self.face_expression == 'hit':
            pygame.draw.arc(screen, (0,0,0), (self.x-4, self.y+mouth_offset, 8, 4), math.pi, 2*math.pi, 2)
        else:
            pygame.draw.line(screen, (0,0,0), (self.x-3, self.y+mouth_offset), (self.x+3, self.y+mouth_offset), 1)
        # Speech bubble
        if self.speech_text:
            font = pygame.font.SysFont(None, 16)
            text_surf = font.render(self.speech_text, True, (255,255,255))
            pygame.draw.rect(screen, (0,0,0), (self.x-15, self.y-35, text_surf.get_width()+6, text_surf.get_height()+4))
            screen.blit(text_surf, (self.x-12, self.y-33))

# Mermi sınıfı
class Bullet:
    def __init__(self, x, y, tx, ty, color):
        self.x = x
        self.y = y
        dx, dy = tx-x, ty-y
        dist = math.hypot(dx, dy)
        self.vx = dx/dist * 5
        self.vy = dy/dist * 5
        self.color = color
        self.radius = 3
        self.damage = 10

    def update(self):
        self.x += self.vx
        self.y += self.vy

    def draw(self, screen):
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)

# Ana simülasyon
def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("2D Asker Savaşı - Siperli")
    clock = pygame.time.Clock()

    covers = [Cover(random.randint(100,700), random.randint(50,450), 50, random.randint(100,200)) for _ in range(3)]

    red_team = [Soldier(random.randint(50,200), random.randint(50,550), (255,0,0)) for _ in range(5)]
    blue_team = [Soldier(random.randint(600,750), random.randint(50,550), (0,0,255)) for _ in range(5)]
    bullets = []

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        for s in red_team:
            s.update(blue_team, bullets, covers)
        for s in blue_team:
            s.update(red_team, bullets, covers)

        for b in bullets[:]:
            b.update()
            for team in [red_team, blue_team]:
                for s in team:
                    if math.hypot(b.x-s.x, b.y-s.y) < b.radius + s.radius and b.color != s.color:
                        if not s.in_cover(covers):
                            s.hp -= b.damage
                            s.face_expression = 'hit'
                            s.speech_text = 'Ouch!'
                            s.speech_timer = 30
                        if b in bullets: bullets.remove(b)

        red_team = [s for s in red_team if s.hp>0]
        blue_team = [s for s in blue_team if s.hp>0]

        screen.fill((50,50,50))
        for c in covers:
            c.draw(screen)
        for s in red_team + blue_team:
            s.draw(screen)
        for b in bullets:
            b.draw(screen)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()

if __name__=='__main__':
    main()
