import pygame
import random
import string
import sys
import paho.mqtt.client as mqtt
import texture
import glitch as g

try:
    import RPi.GPIO as GPIO

    GPIO.setmode(GPIO.BOARD)
    LEFT_PIN = 3
    RIGHT_PIN = 5
    SHOOT_PIN = 7
    COIN_PIN = 11
    GPIO.setup([LEFT_PIN, RIGHT_PIN, SHOOT_PIN, COIN_PIN], GPIO.IN, pull_up_down=GPIO.PUD_UP)
    COIN_POWER_PIN = 8
    GPIO.setup(COIN_POWER_PIN, GPIO.OUT)
    DEBUG = False
except:
    print("Starting program without RPi.GPIO")
    DEBUG = True

# Initialize Pygame
pygame.init()
pygame.mixer.init()

# Screen dimensions
pre_display = pygame.surface.Surface((600,800))
screen = pygame.display.set_mode((800,600), pygame.FULLSCREEN)
WIDTH, HEIGHT = 600, 800
SCALE_FACTOR = 1
pygame.mouse.set_visible(False)

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)

# MQTT settings
BROKER = "192.168.1.80"
PUB_TOPIC = "Arcade/Space_Invaders/pub"
SUB_TOPIC = "Arcade/Space_Invaders/sub"

# Initialize screen
pygame.display.set_caption("Space Invaders")

# Clock for controlling frame rate
clock = pygame.time.Clock()
FPS = 30
MAX_LEVEL = 2

# Sprites and animations
sprite_sheet = texture.SpriteSheet("EntitySprites.png", 4 * SCALE_FACTOR, (0, 0, 0))

ENEMY_SPRITES = sprite_sheet.images_at([
    pygame.Rect(1, 18, 12, 10),
    pygame.Rect(14, 18, 12, 10),
])

PLAYER_SPRITES = sprite_sheet.images_at([
    pygame.Rect(1, 1, 16, 16),
    pygame.Rect(18, 1, 16, 16)
])

BULLET_SPRITES = sprite_sheet.images_at([
    pygame.Rect(35, 1, 4, 8),
    pygame.Rect(40, 1, 4, 8)
])

E_BULLET_SPRITES = sprite_sheet.images_at([
    pygame.Rect(35, 10, 4, 6),
    pygame.Rect(40, 10, 4, 6)
])

BG_SPRITES = sprite_sheet.images_at([
    pygame.Rect(50, 1, 150, 200)
])

LIFE_SPRITES = sprite_sheet.images_at([
    pygame.Rect(1, 39, 7, 7)
])

FONT_PATH = "joystix monospace.otf"
score_font = pygame.font.Font(FONT_PATH, int(24 * SCALE_FACTOR))
main_font = pygame.font.Font(FONT_PATH, int(36 * SCALE_FACTOR))
title_font = pygame.font.Font(FONT_PATH, int(52 * SCALE_FACTOR))

# Audio
PLAYER_SHOOT_SOUND = pygame.mixer.Sound("./Audio/SIPlayerShoot.wav")
PLAYER_SHOOT_SOUND.set_volume(0.2)
PLAYER_DEATH_SOUND = pygame.mixer.Sound("./Audio/SIPlayerDeath.wav")
PLAYER_DEATH_SOUND.set_volume(0.25)
ALIEN_HIT_SOUND = pygame.mixer.Sound("./Audio/SIAlienHit.wav")
ALIEN_HIT_SOUND.set_volume(0.25)
ALIEN_DEATH_SOUND = pygame.mixer.Sound("./Audio/SIAlienDeath.wav")
ALIEN_DEATH_SOUND.set_volume(0.1)
GLITCH_SOUND = pygame.mixer.Sound("./Audio/Glitch.wav")
GLITCH_SOUND.set_volume(0.1)
START_SOUND = pygame.mixer.Sound("./Audio/CountdownChime.wav")
START_SOUND.set_volume(0.25)

# Player class
class Player(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.texture = texture.Texture(PLAYER_SPRITES, 10)
        self.image = self.texture.get_sprite()
        self.rect = self.image.get_rect()
        self.rect.center = (WIDTH // 2, HEIGHT - (100 * SCALE_FACTOR))
        self.speed = 5 * SCALE_FACTOR

        # gun stuff
        self.last_shot_time = 0
        self.shoot_cooldown = 500  # milliseconds
        self.is_shooting = False
        self.gun_broken = False
        self.flash_cycle = 0

    def update(self, keys):
        self.texture.update()
        self.image = self.texture.get_sprite()
        
        if (keys[pygame.K_LEFT] or (not DEBUG and not GPIO.input(LEFT_PIN))) and self.rect.left > 0:
            self.rect.x -= self.speed
        if (keys[pygame.K_RIGHT] or (not DEBUG and not GPIO.input(RIGHT_PIN))) and self.rect.right < WIDTH:
            self.rect.x += self.speed

    def animate(self):
        self.texture.update()
        self.image = self.texture.get_sprite()

    def shoot(self):
        current_time = pygame.time.get_ticks()
        if self.gun_broken == False:
            if current_time - self.last_shot_time > self.shoot_cooldown and self.is_shooting:
                self.last_shot_time = current_time
                bullet = Bullet(self.rect.centerx, self.rect.top)
                PLAYER_SHOOT_SOUND.play()
                return bullet
        else:
            if current_time - self.last_shot_time > self.shoot_cooldown:
                self.last_shot_time = current_time
                if self.flash_cycle == 1:
                    self.flash_cycle = 0
                else:
                    self.flash_cycle = 1
        return None

    def start_shooting(self):
        self.is_shooting = True
    
    def stop_shooting(self):
        self.is_shooting = False

    def break_gun(self):
        self.gun_broken = True

# Enemy class
class Enemy(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.texture = texture.Texture(ENEMY_SPRITES, 15)
        self.image = self.texture.get_sprite()
        self.rect = self.image.get_rect()
        self.rect.topleft = (x, y)
        self.health = 1

    def damage(self):
        self.health -= 1
        if self.health == 0:
            self.kill()
            ALIEN_DEATH_SOUND.play()
            return True
        ALIEN_HIT_SOUND.play()
        return False
    
    def animate(self):
        self.texture.update()
        x, y = self.rect.topleft
        self.image = self.texture.get_sprite()
        self.rect = self.image.get_rect()
        self.rect.topleft = x, y

    def shoot(self):
        bullet = EnemyBullet(self.rect.centerx, self.rect.bottom)
        return bullet

class EnemyGroup:
    def __init__(self):
        global stage
        self.enemies = pygame.sprite.Group()
        self.speed = 1 + stage
        self.bullets = pygame.sprite.Group()
        self.shot_chance = 900 - (100 * stage)

    def add(self, enemy):
        self.enemies.add(enemy)

    def update(self, player_gun_broken):
        move_down = False
        for enemy in self.enemies:
            enemy.animate()

            if not player_gun_broken:
                enemy.rect.x += self.speed
                if ((enemy.rect.right >= (WIDTH - 25) and self.speed > 0) 
                        or (enemy.rect.left <= (25) and self.speed < 0)):
                    move_down = True

                if random.randint(0, self.shot_chance) == 0:
                    bullet = enemy.shoot()
                    self.bullets.add(bullet)

        for bullet in self.bullets:
            bullet.update()

        if move_down:
            self.speed = -self.speed
            if not player_gun_broken:
                for enemy in self.enemies:
                    enemy.rect.y += 40 * SCALE_FACTOR

    def descend(self):
        move_down = False
        for enemy in self.enemies:
            enemy.animate()
            if enemy.rect.y < 100:
                move_down = True

        if move_down:
            for enemy in self.enemies:
                enemy.rect.y += 2 * SCALE_FACTOR

        return move_down

    def draw(self, surface):
        self.enemies.draw(surface)
        self.bullets.draw(surface)

    def check_collision(self, bullets):
        hits = pygame.sprite.groupcollide(self.enemies, bullets, False, True)
        score = 0
        kill_count = 0
        for enemy in hits:
            score += 100
            if isinstance(enemy, Enemy):
                if enemy.damage():
                    score += 200
                    kill_count += 1
        return (score, kill_count)
    
    def check_bullet_collisions(self, player):
        hits = pygame.sprite.groupcollide(pygame.sprite.GroupSingle(player), self.bullets, False, True)
        return len(hits)
    
    def is_empty(self):
        return len(self.enemies) == 0

    def has_reached_player(self):
        for enemy in self.enemies:
            if enemy.rect.bottom >= HEIGHT - (75 * SCALE_FACTOR):
                return True
        return False

# Bullet class
class Bullet(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.texture = texture.Texture(BULLET_SPRITES, 5)
        self.image = self.texture.get_sprite()
        self.rect = self.image.get_rect()
        self.rect.center = (x, y)
        self.speed = -10 * SCALE_FACTOR

    def update(self):
        self.texture.update()
        self.image = self.texture.get_sprite()
        self.rect.y += self.speed
        if self.rect.bottom < 0:
            self.kill()

class EnemyBullet(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.texture = texture.Texture(E_BULLET_SPRITES, 5)
        self.image = self.texture.get_sprite()
        self.rect = self.image.get_rect()
        self.rect.center = (x, y)
        self.speed = 5 * SCALE_FACTOR

    def update(self):
        self.texture.update()
        self.image = self.texture.get_sprite()
        self.rect.y += self.speed
        if self.rect.bottom > HEIGHT:
            self.kill()

class SpaceSegment(pygame.sprite.Sprite):
    def __init__(self, offset):
        super().__init__()
        self.texture = texture.Texture(BG_SPRITES, 10)
        self.image = self.texture.get_sprite()
        self.rect = self.image.get_rect()

        self.rect.x = 0
        self.rect.y = offset

    def update(self):
        self.rect.y += 5
        if self.rect.y > HEIGHT * 1.5:
            self.rect.y -= HEIGHT * 3

class Background():
    def __init__(self):
        self.segments = pygame.sprite.Group()
        for i in range(3):
            self.segments.add(SpaceSegment((i - 1) * HEIGHT))
        
    def update(self):
        for seg in self.segments:
            seg.update()

    def draw(self, screen):
        self.segments.draw(screen)

def on_message(client, userdata, message):
    global restart_game
    global is_active
    global force_start
    global stage

    payload = message.payload.decode()
    print(payload)
    if payload == "lock":
        restart_game = True
        if not DEBUG:
            GPIO.output(COIN_POWER_PIN, GPIO.HIGH)
        client.publish(PUB_TOPIC, "Locked")

    if payload == "activate":
        is_active = True
        stage = 1
        if not DEBUG:
            GPIO.output(COIN_POWER_PIN, GPIO.LOW)

    if payload == "start":
        force_start = True

def on_connect(client, userdata, flags, properties):
    try:
        client.subscribe(SUB_TOPIC)
    except:
        print("Failed to subscribe")

# Initialize MQTT client
client = mqtt.Client()
if not DEBUG:
    client.on_message = on_message
    client.on_connect = on_connect
    client.connect(BROKER)
restart_game = False
is_active = False
force_start = False
stage = 1
background = Background()

def main(lives):
    global background
    global restart_game
    global stage

    player = Player()
    player_group = pygame.sprite.Group(player)

    while stage <= MAX_LEVEL:
        # Initialize player and sprite groups
        bullets = pygame.sprite.Group()
        enemy_group = EnemyGroup()

        # Create enemies
        for row in range(4):
            for col in range(7):
                enemy = Enemy((60 + col * 50) * SCALE_FACTOR, (20 - row * 40) * SCALE_FACTOR)
                enemy_group.add(enemy)

        running = True
        score = 0
        kill_count = 0
        win = False

        glitch = None

        pygame.mixer.music.load("./Audio/SIMusicIntro.wav")
        pygame.mixer.music.play()
        pygame.mixer.music.queue("./Audio/SIMusicLoop.wav", ".wav", -1)

        while enemy_group.descend():
            if restart_game:
                return True

            pre_display.fill(BLACK)
            background.update()
            background.draw(pre_display)

            player.animate()
            player_group.draw(pre_display)
            bullets.draw(pre_display)
            enemy_group.draw(pre_display)
            
            message = main_font.render(f"Level {stage}", True, RED)
            pre_display.blit(message, (WIDTH // 2 - message.get_width() // 2, HEIGHT // 2 - message.get_height() // 2))
        
            screen.blit(pygame.transform.rotate(pre_display, 90), (0,0))
            pygame.display.flip()
            clock.tick(FPS)

        life_sprite = texture.Texture(LIFE_SPRITES, 10).get_sprite()
        life_text = score_font.render(f"x{lives}", True, WHITE)

        while running:
            if restart_game:
                return True
            
            pre_display.fill(BLACK)

            background.update()
            background.draw(pre_display)

            # Event handling
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        player.start_shooting()
                if event.type == pygame.KEYUP:
                    if event.key == pygame.K_SPACE:
                        player.stop_shooting()
            
            if (not DEBUG and GPIO.input(SHOOT_PIN)):
                player.stop_shooting()
            else:
                player.start_shooting()
                        
            bullet = player.shoot()
            if bullet:
                bullets.add(bullet)

            # Update
            keys = pygame.key.get_pressed()
            player.update(keys)
            bullets.update()
            enemy_group.update(player.gun_broken)

            # Check for game over
            if not player.gun_broken:
                if enemy_group.has_reached_player() or enemy_group.check_bullet_collisions(player) > 0:
                    running = False
                    PLAYER_DEATH_SOUND.play()
            
            # Draw
            player_group.draw(pre_display)
            bullets.draw(pre_display)
            enemy_group.draw(pre_display)

            if player.flash_cycle == 1:
                message = main_font.render("Gun Failure", True, RED)
                pre_display.blit(message, (WIDTH // 2 - message.get_width() // 2, HEIGHT // 2 - message.get_height() // 2))

            if glitch is None:
                if kill_count >= 10 and stage == MAX_LEVEL:
                    player.break_gun()
                    glitch = g.Glitch(WIDTH, SCALE_FACTOR, -50)
                    GLITCH_SOUND.play(-1)
                    pygame.mixer.music.stop()
                elif kill_count >= 28:
                    stage += 1
                    win = True
                    break
                
                # Check for bullet-enemy collisions
                col_check = enemy_group.check_collision(bullets)
                score += col_check[0]
                kill_count += col_check[1]
            else:
                glitch.update()
                glitch.draw(pre_display)
                score = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
                if glitch.height > HEIGHT * 3:
                    running = False
                    win = True
                    pygame.mixer.fadeout(1500)

            # Display score
            score_text = score_font.render(f"Score: {score}", True, WHITE)
            pre_display.blit(score_text, (10, 10))

            pre_display.blit(life_text, (
                    WIDTH - (10 * SCALE_FACTOR + life_text.get_width()),
                    10 * SCALE_FACTOR))
            pre_display.blit(life_sprite, (
                    WIDTH - (10 * SCALE_FACTOR + life_sprite.get_width() + life_text.get_width()),
                    10 * SCALE_FACTOR))

            # Update display
            screen.blit(pygame.transform.rotate(pre_display, 90), (0,0))
            pygame.display.flip()

            # Limit frame rate
            clock.tick(FPS)
        if not win or (win and not running):
            break
        else:
            message = main_font.render("Next Level", True, GREEN)
            pre_display.blit(message, (WIDTH // 2 - message.get_width() // 2, HEIGHT // 2 - message.get_height() // 2))
            
            screen.blit(pygame.transform.rotate(pre_display, 90), (0,0))
            pygame.display.flip()
            pygame.time.wait(3000)

    # Display win/lose message
    pygame.mixer.music.stop()
    pre_display.fill(BLACK)
    if not win:
        message = main_font.render("Game Over", True, RED)
    pre_display.blit(message, (WIDTH // 2 - message.get_width() // 2, HEIGHT // 2 - message.get_height() // 2))
    
    screen.blit(pygame.transform.rotate(pre_display, 90), (0,0))
    pygame.display.flip()
    return win

def lose():
    pre_display.fill(BLACK)
    glitch = g.Glitch(WIDTH, SCALE_FACTOR, -50)
    GLITCH_SOUND.play(-1)
    while glitch.height < HEIGHT * 3:
        message = main_font.render("Game Over", True, RED)
        pre_display.blit(message, (WIDTH // 2 - message.get_width() // 2, HEIGHT // 2 - message.get_height() // 2))
        glitch.update()
        glitch.draw(pre_display)
        
        screen.blit(pygame.transform.rotate(pre_display, 90), (0,0))
        pygame.display.flip()
        clock.tick(FPS)
    pygame.mixer.fadeout(1500)

def await_start():
    global background
    global restart_game
    global force_start

    waiting = True
    counter = 0
    countdown = False

    player = Player()
    player_group = pygame.sprite.GroupSingle(player)

    pre_display.fill(BLACK)
    background.update()
    background.draw(pre_display)

    player.animate()
    player_group.draw(pre_display)

    title1 = title_font.render("Cosmic", False, WHITE)
    title2 = title_font.render("Clash", False, WHITE)

    pre_display.blit(title1, (WIDTH // 2 - title1.get_width() // 2, HEIGHT // 2 - title1.get_height() // 2 - 5 * SCALE_FACTOR))
    pre_display.blit(title2, (WIDTH // 2 - title2.get_width() // 2, HEIGHT // 2 + 5 * SCALE_FACTOR))

    screen.blit(pygame.transform.rotate(pre_display, 90), (0,0))
    pygame.display.flip()

    while True:
        if restart_game:
            return False

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    countdown = True
                    counter = 0
                    START_SOUND.play()
                    return True

        if (not DEBUG and not GPIO.input(COIN_PIN) or force_start):
            force_start = False
            countdown = True
            counter = 0
            START_SOUND.play()
            break
                    
        """
        if countdown:
            prompt = score_font.render(str(((FPS * 3) - counter) // FPS + 1), False, GREEN)
            pre_display.blit(prompt, (WIDTH // 2 - prompt.get_width() // 2, HEIGHT // 2 + prompt.get_height() // 2 + title2.get_height()))
            if counter >= FPS * 3:
                break
        elif (counter // 30) % 2 == 0:
            prompt = score_font.render("Insert Coin To Start", False, GREEN)
            pre_display.blit(prompt, (WIDTH // 2 - prompt.get_width() // 2, HEIGHT // 2 + prompt.get_height() // 2 + title2.get_height()))
        counter += 1"
        """
    return True

if __name__ == "__main__":
    client.loop_start()
    while True:
        screen.fill((0, 0, 0))
        pygame.display.flip()
        pygame.mixer.music.stop()

        is_active = False
        while (not DEBUG and not is_active):
            pygame.time.wait(100)
            
        restart_game = False
        if not await_start(): # await_start() returns False if restart_game == True
            continue
        lives = 3

        if not DEBUG:
            GPIO.output(COIN_POWER_PIN, GPIO.HIGH)
        client.publish(PUB_TOPIC, "Started")

        while True:
            if main(lives): # if player wins
                pre_display.fill(BLACK)

                prompt = score_font.render("Slide right.", False, (255, 0, 0))
                pre_display.blit(prompt, (WIDTH // 2 - prompt.get_width() // 2, HEIGHT // 2 + prompt.get_height() // 2))
                screen.blit(pygame.transform.rotate(pre_display, 90), (0,0))

                pygame.display.flip()
                client.publish(PUB_TOPIC, "Completed")
                while not restart_game:
                    pygame.time.wait(100)
                break
            else:
                if lives <= 1:
                    lose()
                    pre_display.fill(BLACK)

                    prompt = score_font.render("Slide right.", False, (255, 0, 0))
                    pre_display.blit(prompt, (WIDTH // 2 - prompt.get_width() // 2, HEIGHT // 2 + prompt.get_height() // 2))
                    screen.blit(pygame.transform.rotate(pre_display, 90), (0,0))

                    client.publish(PUB_TOPIC, "Completed")
                    while not restart_game:
                        pygame.time.wait(100)
                    break
                else:
                    pygame.time.wait(1500)
                    lives -= 1

client.loop_stop()
