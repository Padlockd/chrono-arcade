import pygame
import sys
import texture
import glitch as G
import random
import string
import RPi.GPIO as GPIO
import paho.mqtt.client as mqtt

GPIO.setmode(GPIO.BOARD)
LEFT_PIN = 3
RIGHT_PIN = 5
JUMP_PIN = 7
COIN_PIN = 11
GPIO.setup([LEFT_PIN, RIGHT_PIN, JUMP_PIN, COIN_PIN], GPIO.IN, pull_up_down=GPIO.PUD_UP)
COIN_POWER_PIN = 8
GPIO.setup(COIN_POWER_PIN, GPIO.OUT)

# Initialize Pygame
pygame.init()
pygame.mixer.init()

# Screen dimensions
pre_display = pygame.surface.Surface((480,640))
screen = pygame.display.set_mode((640,480), pygame.FULLSCREEN)
WIDTH, HEIGHT = 480, 640
SCALE_FACTOR = 0.66
pygame.mouse.set_visible(False)

# Colors
SKY = (92, 148, 252)
BLACK = (0, 0, 0)
GREEN = (30, 180, 110)
BLUE = (0, 0, 255)

# MQTT settings
BROKER = "192.168.1.80"
PUB_TOPIC = "Arcade/Mario/pub"
SUB_TOPIC = "Arcade/Mario/sub"

# Initialize screen
pygame.display.set_caption("Sidescrolling Platformer")

# Clock for controlling frame rate
clock = pygame.time.Clock()
FPS = 30

#SPRITES AND STUFF
TILE_SIZE = 32
sprite_sheet = texture.SpriteSheet("./Sprites.png", 2, (0, 0, 0))
FLOOR_SPRITE = sprite_sheet.images_at([
    pygame.Rect(64, 0, 16, 16)
])
FLOOR_SIDE_SPRITE = sprite_sheet.images_at([
    pygame.Rect(96, 0, 16, 16)
])
FLOOR_CORNER_SPRITE = sprite_sheet.images_at([
    pygame.Rect(112, 0, 16, 16)
])
UNDERGROUND_SPRITE = sprite_sheet.images_at([
    pygame.Rect(80, 0, 16, 16)
])

BRICKS_SPRITE = sprite_sheet.images_at([
    pygame.Rect(48, 0, 16, 16)
])
BLOCK_SPRITE = sprite_sheet.images_at([
    pygame.Rect(48, 0, 16, 16)
])
LUCKY_BLOCK_SPRITES = sprite_sheet.images_at([
    pygame.Rect(0, 0, 16, 16),
    pygame.Rect(16, 0, 16, 16),
])

GOOMBA_SPRITES = sprite_sheet.images_at([
    pygame.Rect(0, 16, 16, 16),
    pygame.Rect(16, 16, 16, 16)
])
GOOMBA_DEATH_SPRITE = sprite_sheet.images_at([
    pygame.Rect(32, 16, 16, 16)
])
PIRANHA_PLANT_SPRITES = sprite_sheet.images_at([
    pygame.Rect(48, 48, 16, 23),
    pygame.Rect(64, 48, 16, 23),
])

PLAYER_STAND_SPRITE = sprite_sheet.images_at([
    pygame.Rect(0, 32, 16, 16)
])
PLAYER_RUN_SPRITES = sprite_sheet.images_at([
    pygame.Rect(16, 32, 16, 16),
    pygame.Rect(32, 32, 16, 16),
    pygame.Rect(48, 32, 16, 16)
])
PLAYER_JUMP_SPRITE = sprite_sheet.images_at([
    pygame.Rect(64, 32, 16, 16)
])
PLAYER_DEATH_SPRITE = sprite_sheet.images_at([
    pygame.Rect(80, 32, 16, 16)
])

CLOUD__SPRITES = sprite_sheet.images_at([
    pygame.Rect(0, 48, 16, 32),
    pygame.Rect(16, 48, 16, 32),
    pygame.Rect(32, 48, 16, 32)
])

COIN_SPRITES = sprite_sheet.images_at([
    pygame.Rect(48, 16, 16, 16),
    pygame.Rect(64, 16, 16, 16),
    pygame.Rect(80, 16, 16, 16),
    pygame.Rect(64, 16, 16, 16)
])

PIPE_SPRITE = sprite_sheet.images_at([
    pygame.Rect(96, 16, 32, 32)
])

CASTLE_SPRITE = sprite_sheet.images_at([
    pygame.Rect(0, 80, 80, 80)
])

FONT_PATH = "joystix monospace.otf"
score_font = pygame.font.Font(FONT_PATH, int(24 * SCALE_FACTOR))
main_font = pygame.font.Font(FONT_PATH, int(36 * SCALE_FACTOR))
title_font = pygame.font.Font(FONT_PATH, int(52 * SCALE_FACTOR))
score = 0

# Sounds
COIN_SOUND = pygame.mixer.Sound("./Audio/SMCoin.wav")
COIN_SOUND.set_volume(0.25)
PLAYER_JUMP_SOUND = pygame.mixer.Sound("./Audio/SMPlayerJump.wav")
PLAYER_JUMP_SOUND.set_volume(0.25)
GOOMBA_DEATH_SOUND = pygame.mixer.Sound("./Audio/SMGoombaDeath.wav")
GOOMBA_DEATH_SOUND.set_volume(0.25)
GLITCH_SOUND = pygame.mixer.Sound("./Audio/Glitch.wav")
GLITCH_SOUND.set_volume(0.25)
PLAYER_DEATH_SOUND = pygame.mixer.Sound("./Audio/SMPlayerDeath.wav")
START_SOUND = pygame.mixer.Sound("./Audio/CountdownChime.wav")
START_SOUND.set_volume(0.25)

# Player class
class Player(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.texture = texture.Texture(PLAYER_STAND_SPRITE, 5)
        self.image = self.texture.get_sprite()

        self.rect = self.image.get_rect()
        self.rect.x = 1 * TILE_SIZE
        self.rect.y = 13 * TILE_SIZE
        self.speed_x = 0
        self.speed_y = 0
        self.base_speed = 10 * SCALE_FACTOR
        self.gravity = 1.6 * SCALE_FACTOR
        self.jump_strength = -24
        self.on_ground = False
        self.is_controllable = True

    def update(self, platforms, lucky_blocks):
        global score
        self.speed_y += self.gravity
        self.rect.y += self.speed_y
        new_items = []

        # Check for collisions with platforms
        self.on_ground = False
        if self.is_controllable:
            for block in lucky_blocks:
                if self.rect.colliderect(block.rect):
                    if self.speed_y > 0:  # Falling
                        self.rect.bottom = block.rect.top
                        self.speed_y = 0
                        self.on_ground = True
                    elif self.speed_y < 0:  # Jumping upwards
                        self.rect.top = block.rect.bottom
                        self.speed_y = 0
                        new_items.append(block.open())
                        score += 250

            for platform in platforms:
                if self.rect.colliderect(platform.rect):
                    if self.speed_y > 0:  # Falling
                        self.rect.bottom = platform.rect.top
                        self.speed_y = 0
                        self.on_ground = True
                    elif self.speed_y < 0:  # Jumping upwards
                        self.rect.top = platform.rect.bottom
                        self.speed_y = 0

        self.rect.x += self.speed_x
        if self.is_controllable:
            for platform in platforms:
                if self.rect.colliderect(platform.rect):
                    if self.speed_x > 0:
                        self.rect.right = platform.rect.left
                    elif self.speed_x < 0:
                        self.rect.left = platform.rect.right
                        
            for block in lucky_blocks:
                if self.rect.colliderect(block.rect):
                    if self.speed_x > 0:
                        self.rect.right = block.rect.left
                    elif self.speed_x < 0:
                        self.rect.left = block.rect.right

        if self.rect.bottom >= HEIGHT:
            self.die()

        if self.on_ground:
            if self.speed_x != 0:
                self.texture.set_sprite_set(PLAYER_RUN_SPRITES)
            else:
                self.texture.set_sprite_set(PLAYER_STAND_SPRITE)

        self.texture.update()
        self.image = self.texture.get_sprite()

        return (self.is_controllable, new_items)
        
    def animate(self):
        self.texture.update()
        self.image = self.texture.get_sprite()

    def die(self):
        if self.is_controllable:
            self.texture.set_sprite_set(PLAYER_DEATH_SPRITE)
            PLAYER_DEATH_SOUND.play()
            self.is_controllable = False
            self.speed_y = self.jump_strength * SCALE_FACTOR
            self.speed_x = 0

    def jump(self, force = False):
        if self.on_ground or force:
            self.texture.set_sprite_set(PLAYER_JUMP_SPRITE)
            self.speed_y = self.jump_strength * SCALE_FACTOR
            PLAYER_JUMP_SOUND.play()

    def move(self, direction):
        self.speed_x = self.base_speed * direction

    def check_input(self, events):
        if not self.is_controllable:
            return
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    self.jump()
            if event.type == pygame.KEYUP:
                if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                    self.speed_x = 0

        # Player movement
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] or not GPIO.input(LEFT_PIN):
            self.move(-1)
            self.texture.set_flipped(True)
        if keys[pygame.K_RIGHT] or not GPIO.input(RIGHT_PIN):
            self.move(1)
            self.texture.set_flipped(False)
        if not GPIO.input(JUMP_PIN):
            self.jump()
        if GPIO.input(LEFT_PIN) and GPIO.input(RIGHT_PIN) and not (keys[pygame.K_LEFT] or keys[pygame.K_RIGHT]):
            self.speed_x = 0

# Platform class
class Platform(pygame.sprite.Sprite):
    def __init__(self, x, y, width, height, sprite_set, flipped):
        super().__init__()
        self.texture = texture.Texture(sprite_set, 1)
        self.texture.set_flipped(flipped)
        self.image = self.texture.get_sprite()

        self.rect = self.image.get_rect()
        self.rect.w *= width
        self.rect.h *= height
        self.rect.topleft = (x * TILE_SIZE, y * TILE_SIZE)
        self.width = width
        self.height = height

    def draw(self, screen, camera_x):
        for x in range(self.width):
            for y in range(self.height):
                screen.blit(self.image, (x * TILE_SIZE - camera_x + self.rect.x, y * TILE_SIZE + self.rect.y))

class Goomba(pygame.sprite.Sprite):
    def __init__(self, x, y, max_x, min_x):
        super().__init__()
        self.texture = texture.Texture(GOOMBA_SPRITES, 15)
        self.image = self.texture.get_sprite()

        self.rect = self.image.get_rect()
        self.rect.topleft = (x * TILE_SIZE, y * TILE_SIZE)
        self.speed_x = -3 * SCALE_FACTOR
        
        self.max_x = max_x * TILE_SIZE
        self.min_x = min_x * TILE_SIZE
        self.death_counter = None

    def update(self, player, enemies):
        if self.death_counter is not None:
            self.death_counter -= 1
            if self.death_counter == 0:
                self.kill()
            return
        
        self.texture.update()
        self.image = self.texture.get_sprite()
        if pygame.Rect.colliderect(self.rect, player.rect) and player.is_controllable:
            diff_x = abs(self.rect.x - player.rect.x)
            diff_y = abs(self.rect.y - player.rect.y)
            if diff_x > diff_y * 2:
                player.die()
            else:
                self.die()
                player.speed_y = player.jump_strength * SCALE_FACTOR / 2

        self.rect.x += self.speed_x

        switch_direction = False
        for enemy in enemies:
            if enemy == self:
                continue
            if pygame.Rect.colliderect(self.rect, enemy.rect):
                switch_direction = True
        
        if ((self.rect.x > self.max_x and self.speed_x > 0)
                or (self.rect.x < self.min_x and self.speed_x < 0)):
            switch_direction = True
            
        if switch_direction:
            self.speed_x = - self.speed_x

    def die(self):
        global score
        self.death_counter = 30
        self.texture.set_sprite_set(GOOMBA_DEATH_SPRITE)
        self.image = self.texture.get_sprite()
        GOOMBA_DEATH_SOUND.play()
        score += 100
                
    def draw(self, screen, camera_x):
        screen.blit(self.image, (self.rect.x - camera_x, self.rect.y))

class Piranha_Plant(pygame.sprite.Sprite):
    def __init__(self, pipe_x, pipe_y):
        super().__init__()
        self.texture = texture.Texture(PIRANHA_PLANT_SPRITES, 15)
        self.image = self.texture.get_sprite()

        self.rect = self.image.get_rect()
        self.rect.bottomleft = (pipe_x * TILE_SIZE + TILE_SIZE / 2, pipe_y * TILE_SIZE)
        self.speed_x = -1.5 * SCALE_FACTOR
        self.death_counter = None

    def update(self, player, enemies):
        self.texture.update()
        self.image = self.texture.get_sprite()
        if pygame.Rect.colliderect(self.rect, player.rect) and player.is_controllable:
            player.die()

    def draw(self, screen, camera_x):
        screen.blit(self.image, (self.rect.x - camera_x, self.rect.y))

class Cloud(pygame.sprite.Sprite):
    def __init__(self, x, y, w):
        super().__init__()
        self.x = x
        self.y = y
        self.w = w
        self.texture = texture.Texture(CLOUD__SPRITES, 1)

    def draw(self, screen, camera_x):
        camera_x /= 2
        screen.blit(self.texture.get_sprite(), (self.x * TILE_SIZE - camera_x, self.y * TILE_SIZE))
        self.texture.update()
        for i in range(self.w):
            screen.blit(self.texture.get_sprite(), ((self.x + i + 1) * TILE_SIZE - camera_x, self.y * TILE_SIZE))
        self.texture.update()
        screen.blit(self.texture.get_sprite(), ((self.x + self.w + 1) * TILE_SIZE - camera_x, self.y * TILE_SIZE))
        self.texture.update()

class LuckyBlock(Platform):
    def __init__(self, x, y, item):
        super().__init__(x, y, 1, 1, LUCKY_BLOCK_SPRITES, False)
        self.opened = False
        self.item = item

    def open(self):
        if not self.opened:
            self.opened = True
            self.texture.update()
            self.image = self.texture.get_sprite()
            if self.item == "Coin":
                COIN_SOUND.play()
                return Coin(self.rect.x, self.rect.y)

class Coin(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.texture = texture.Texture(COIN_SPRITES, 5)
        self.image = self.texture.get_sprite()
        self.rect = self.image.get_rect()
        self.rect.topleft = (x, y)
        self.speed_y = -15 * SCALE_FACTOR

    def update(self, player):
        self.texture.update()
        self.image = self.texture.get_sprite()

        self.rect.y += self.speed_y
        self.speed_y += SCALE_FACTOR
        print(self.image)
        if self.speed_y >= 10:
            self.kill()
            return False
        return True
            
    def draw(self, screen, camera_x):
        screen.blit(self.image, (self.rect.x - camera_x, self.rect.y))

class Castle(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.texture = texture.Texture(CASTLE_SPRITE, 1)
        self.image = self.texture.get_sprite()
        self.rect = self.image.get_rect()
        self.rect.topleft = (75 * TILE_SIZE, 9 * TILE_SIZE)
        self.glitch_rects = []
        for i in range(30):
            w = random.randint(5, 25)
            h = random.randint(5, 10)
            x = random.randint(0, 5 * TILE_SIZE - w) + self.rect.x
            y = random.randint(0, 5 * TILE_SIZE - h) + self.rect.y
            self.glitch_rects.append([pygame.Rect(x, y, w, h), 0, 0, 0])

    def update(self):
        for glitch in self.glitch_rects:
            glitch[1] = max(min(glitch[1] + random.randint(-48, 32), 255), 0) # randomly add (-10 to 10) to rgb and clamp between 0 and 255
            glitch[2] = max(min(glitch[2] + random.randint(-48, 32), 255), 0)
            glitch[3] = max(min(glitch[3] + random.randint(-48, 32), 255), 0)

            glitch[0].w = min(max(5, glitch[0].w + random.randint(-3, 3)), 25)
            glitch[0].h = min(max(5, glitch[0].h + random.randint(-2, 2)), 10)

            if random.randint(0, 20) == 0:
                glitch[0].x = random.randint(0, 5 * TILE_SIZE - glitch[0].w) + 75 * TILE_SIZE
                glitch[0].y = random.randint(0, 5 * TILE_SIZE - glitch[0].h) + 9 * TILE_SIZE
            else:
                glitch[0].x = min(max(75 * TILE_SIZE, glitch[0].x + random.randint(-10, 10)), (80 * TILE_SIZE) - glitch[0].w)
                glitch[0].y = min(max(9 * TILE_SIZE, glitch[0].y + random.randint(-10, 10)), (14 * TILE_SIZE) - glitch[0].h)
                
            
    def draw(self, screen, camera_x):
        screen.blit(self.image, (self.rect.x - camera_x, self.rect.y))
        for glitch in self.glitch_rects:
            drawRect = pygame.rect.Rect(glitch[0])
            drawRect.x -= camera_x
            pygame.draw.rect(screen, (glitch[1], glitch[2], glitch[3]), drawRect)

def create_floor_section(x, y, w, h):
    return [
        (x, y, 1, 1, FLOOR_CORNER_SPRITE, True),  # Ground
        (x, y + 1, 1, h - 1, FLOOR_SIDE_SPRITE, True),  # Ground
        (x + 1, y, w - 2, 1, FLOOR_SPRITE, False),  # Ground
        (x + w - 1, y, 1, 1, FLOOR_CORNER_SPRITE, False),  # Ground
        (x + 1, y + 1, w - 2, h - 1, UNDERGROUND_SPRITE, False),  # Ground
        (x + w - 1, y + 1, 1, h - 1, FLOOR_SIDE_SPRITE, False),  # Ground
    ]

def on_message(client, userdata, message):
    global restart_game
    global is_active
    payload = message.payload.decode()
    print(payload)
    if payload == "lock":
        restart_game = True
        GPIO.output(COIN_POWER_PIN, GPIO.LOW)
        client.publish(PUB_TOPIC, "Locked")
    if payload == "activate":
        is_active = True
        GPIO.output(COIN_POWER_PIN, GPIO.HIGH)

def on_connect(client, userdata, flags, properties):
    try:
        client.subscribe(SUB_TOPIC)
    except:
        print("Failed to subscribe")

# Initialize MQTT client
client = mqtt.Client()
client.on_message = on_message
client.on_connect = on_connect
client.connect(BROKER)
restart_game = False
is_active = False

def main(lives):
    global score
    global restart_game

    # Game initialization
    player = Player()

    platforms = pygame.sprite.Group()

    # Create platforms
    level = [
        (11, 11, 1, 1, BRICKS_SPRITE, False),
        (13, 11, 1, 1, BRICKS_SPRITE, False),
        (15, 11, 1, 1, BRICKS_SPRITE, False),
        
        (35, 13, 1, 1, BLOCK_SPRITE, False),
        (36, 12, 1, 2, BLOCK_SPRITE, False),
        (37, 11, 1, 4, BLOCK_SPRITE, False),
        
        (40, 11, 1, 4, BLOCK_SPRITE, False),
        (41, 12, 1, 2, BLOCK_SPRITE, False),
        (42, 13, 1, 1, BLOCK_SPRITE, False),

        (43, 9, 5, 1, BRICKS_SPRITE, False),
        (50, 9, 5, 1, BRICKS_SPRITE, False),
        
        (55, 12, 1, 1, PIPE_SPRITE, False),
        (18, 12, 1, 1, PIPE_SPRITE, False),
        
        (59, 13, 1, 1, BLOCK_SPRITE, False),
        (60, 12, 1, 2, BLOCK_SPRITE, False),
        (61, 11, 1, 3, BLOCK_SPRITE, False),
        (62, 10, 1, 4, BLOCK_SPRITE, False),
        (63, 9, 1, 6, BLOCK_SPRITE, False),

        (84, 9, 1, 5, BLOCK_SPRITE, False), #End Wall
        (-1, 9, 1, 5, BLOCK_SPRITE, False), #Start Wall
    ]
    level.extend(create_floor_section(-1, 14, 24, 6))
    level.extend(create_floor_section(26, 14, 12, 6))
    level.extend(create_floor_section(40, 14, 24, 6))
    level.extend(create_floor_section(67, 14, 24, 6))

    for x, y, w, h, s, f in level:
        platforms.add(Platform(x, y, w, h, s, f))

    lucky_blocks = pygame.sprite.Group()
    level_lucky_blocks = [
        (12, 11, "Coin"),
        (14, 11, "Coin"),
        (13, 8, "Coin"),
        (45, 6, "Coin"),
        (52, 6, "Coin"),
    ]

    for x, y, i in level_lucky_blocks:
        lucky_blocks.add(LuckyBlock(x, y, i))

    enemies = pygame.sprite.Group()
    level_enemies = [
        (17, 13, 17, 9),
        (26, 13, 34, 26),
        
        (44, 13, 54, 43),
        (47, 13, 54, 43),
        (50, 13, 54, 43),
        (53, 13, 54, 43),
    ]
    for x, y, mx, mn in level_enemies:
        enemies.add(Goomba(x, y, mx, mn))
    enemies.add(Piranha_Plant(55, 12))

    clouds = pygame.sprite.Group()
    level_clouds = [
        (3, 4, 2),
        (12, 6, 1),
        (19, 2, 2),
        (25, 5, 3),
    ]
    for x, y, w in level_clouds:
        clouds.add(Cloud(x, y, w))

    items = []

    # Camera offset
    camera_x = 0
    death_delay = 90

    castle = Castle()
    glitch = None

    # Game loop
    running = True
    win = False
    score = 0
    while death_delay > 0:
        if restart_game:
            return True

        r, g, b = SKY
        if camera_x > 50 * TILE_SIZE and camera_x < 63.5 * TILE_SIZE:
            r = 92 - (((camera_x / TILE_SIZE) - 50) / 13.5) * 80
            g = 148 - (((camera_x / TILE_SIZE) - 50) / 13.5) * 148
            b = 252 - (((camera_x / TILE_SIZE) - 50) / 13.5) * 252
        elif camera_x >= 63.5 * TILE_SIZE:
            r = 12
            g = 0
            b = 0
            score = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            
        if player.rect.x > 76.5 * TILE_SIZE and glitch is None:
            glitch = G.Glitch(HEIGHT, SCALE_FACTOR)
            GLITCH_SOUND.play(-1)
            player.speed_x = 0

        pre_display.fill((int(r), g, int(b)))

        # Event handling
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                running = False
                
        if glitch is None:
            player.check_input(events)

        # Update player and camera
        running, new_items = player.update(platforms, lucky_blocks)
        camera_x = min(max(0, player.rect.centerx - WIDTH // 2), 68.5 * TILE_SIZE)
        #camera_x = 72 * TILE_SIZE
        enemies.update(player, enemies)

        if new_items:
            items.extend(new_items)

        # Draw platforms with camera offset
        for cloud in clouds:
            cloud.draw(pre_display, camera_x)
        
        for platform in platforms:
            platform.draw(pre_display, camera_x)

        for block in lucky_blocks:
            block.draw(pre_display, camera_x)

        for enemy in enemies:
            enemy.draw(pre_display, camera_x)

        castle.update()
        castle.draw(pre_display, camera_x)

        i = []
        for item in items:
            if item:
                print(item)
                if item.update(player):
                    item.draw(pre_display, camera_x)
                    i.append(item)
        items = i

        # Draw player with camera offset
        pre_display.blit(player.image, (player.rect.x - camera_x, player.rect.y))

        if isinstance(score, int):
            score_text = score_font.render(f"Score: {score:04d}", False, (255, 255, 255))
        else:
            score_text = score_font.render(f"Score: {score}", False, (255, 255, 255))
        pre_display.blit(score_text, (5, 5))
        if glitch is not None:
            glitch.update(WIDTH)
            glitch.draw(pre_display, WIDTH)
            if glitch.height > WIDTH * 3:
                running = False
                win = True
                pygame.mixer.fadeout(1500)

        # Update display
        screen.blit(pygame.transform.rotate(pre_display, 90), (0,0))
        pygame.display.flip()

        # Limit frame rate
        clock.tick(FPS)
        if not running:
            death_delay -= 1

    return win

def await_start():
    global restart_game

    waiting = True
    counter = 0
    countdown = False

    player = Player()
    player_group = pygame.sprite.GroupSingle(player)

    platforms = pygame.sprite.Group()
    level = [
        (11, 11, 1, 1, BRICKS_SPRITE, False),
        (13, 11, 1, 1, BRICKS_SPRITE, False),
        (15, 11, 1, 1, BRICKS_SPRITE, False),
    ]
    level.extend(create_floor_section(-1, 14, 24, 6))

    for x, y, w, h, s, f in level:
        platforms.add(Platform(x, y, w, h, s, f))

    lucky_blocks = pygame.sprite.Group()
    level_lucky_blocks = [
        (12, 11, "Coin"),
        (14, 11, "Coin"),
        (13, 8, "Coin"),
    ]

    for x, y, i in level_lucky_blocks:
        lucky_blocks.add(LuckyBlock(x, y, i))

    clouds = pygame.sprite.Group()
    level_clouds = [
        (3, 4, 2),
        (12, 6, 1),
        (25, 5, 3),
    ]
    for x, y, w in level_clouds:
        clouds.add(Cloud(x, y, w))

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
                    counter = FPS * 3
                    START_SOUND.play()
     
        if not GPIO.input(COIN_PIN):
            countdown = True
            counter = FPS * 3
            START_SOUND.play()
                    
        pre_display.fill(SKY)
        player_group.draw(pre_display)

        for platform in platforms:
            platform.draw(pre_display, 0)

        for block in lucky_blocks:
            block.draw(pre_display, 0)

        for cloud in clouds:
            cloud.draw(pre_display, 0)
        
        title1 = title_font.render("Cosmic", False, (0,0,0))
        title2 = title_font.render("Clash", False, (0,0,0))

        pre_display.blit(title1, (WIDTH // 2 - title1.get_width() // 2, HEIGHT // 2 - title1.get_height() // 2 - 5 * SCALE_FACTOR))
        pre_display.blit(title2, (WIDTH // 2 - title2.get_width() // 2, HEIGHT // 2 + 5 * SCALE_FACTOR))

        if countdown:
            prompt = score_font.render(str(((FPS * 3) - counter) // FPS + 1), False, GREEN)
            pre_display.blit(prompt, (WIDTH // 2 - prompt.get_width() // 2, HEIGHT // 2 + prompt.get_height() // 2 + title2.get_height()))
            if counter >= FPS * 3:
                break
        elif (counter // 30) % 2 == 0:
            prompt = score_font.render("Insert Coin To Start", False, (0, 255, 0))
            pre_display.blit(prompt, (WIDTH // 2 - prompt.get_width() // 2, HEIGHT // 2 + prompt.get_height() // 2 + title2.get_height()))
        counter += 1

        screen.blit(pygame.transform.rotate(pre_display, 90), (0,0))
        pygame.display.flip()
        clock.tick(FPS)
    return True

def lose():
    pre_display.fill(BLACK)
    glitch = G.Glitch(HEIGHT, SCALE_FACTOR)
    GLITCH_SOUND.play(-1)
    while glitch.height < WIDTH * 3:
        message = main_font.render("Game Over", True, (255, 0, 0))
        pre_display.blit(message, (WIDTH // 2 - message.get_width() // 2, HEIGHT // 2 - message.get_height() // 2))
        glitch.update(HEIGHT)
        glitch.draw(pre_display, HEIGHT)
        
        screen.blit(pygame.transform.rotate(pre_display, 90), (0,0))
        pygame.display.flip()
        clock.tick(FPS)
    screen.fill((0, 0, 0))
    pygame.display.flip()
    pygame.mixer.fadeout(1500)

if __name__ == "__main__":
    client.loop_start()

    while True:
        screen.fill((0, 0, 0))
        pygame.display.flip()
        pygame.mixer.music.stop()
        
        is_active = False
        while not is_active:
            pygame.time.wait(100)
            
        restart_game = False
        if not await_start(): # await_start() returns False if restart_game == True
            continue
        lives = 5
        GPIO.output(COIN_POWER_PIN, GPIO.LOW)
        client.publish(PUB_TOPIC, "Started")
        
        while True:
            if main(lives): # if player wins
                client.publish(PUB_TOPIC, "Completed")
                while not restart_game:
                    pygame.time.wait(100)
                break
            else:
                if lives <= 1:
                    lose()
                    client.publish(PUB_TOPIC, "Completed")
                    while not restart_game:
                        pygame.time.wait(100)
                    break
                else:
                    lives -= 1

client.loop_stop()

pygame.quit()
sys.exit()
