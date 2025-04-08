import pygame
import random
import string
import glitch as g
import texture
import RPi.GPIO as GPIO
import paho.mqtt.client as mqtt

GPIO.setmode(GPIO.BOARD)
LEFT_PIN = 3
RIGHT_PIN = 5
COIN_PIN = 11
GPIO.setup([LEFT_PIN, RIGHT_PIN, COIN_PIN], GPIO.IN, pull_up_down=GPIO.PUD_UP)
COIN_POWER_PIN = 8
GPIO.setup(COIN_POWER_PIN, GPIO.OUT)

# Initialize pygame
pygame.init()
pygame.mixer.init()
clock = pygame.time.Clock()
FPS = 30

# MQTT settings
BROKER = "192.168.1.80"
PUB_TOPIC = "Arcade/Racing/pub"
SUB_TOPIC = "Arcade/Racing/sub"

# Setup display
pre_display = pygame.surface.Surface((600,800))
screen = pygame.display.set_mode((800,600), pygame.FULLSCREEN)
WIDTH, HEIGHT = 600, 800
SCALE_FACTOR = 1
pygame.mouse.set_visible(False)

OBSTACLE_DELAY_MIN, OBSTACLE_DELAY_MAX = 30, 60
speed = 15 * SCALE_FACTOR

# Sprites and animations
sprite_sheet = texture.SpriteSheet("Sprites.png", 5 * SCALE_FACTOR, (0, 0, 0))
OBSTACLE_SPRITES = sprite_sheet.images_at([
    pygame.Rect(0, 0, 20, 34)
])

PLAYER_SPRITES = sprite_sheet.images_at([
    pygame.Rect(0, 35, 20, 34)
])

ROAD_SPRITES = sprite_sheet.images_at([
    pygame.Rect(40, 0, 120, 160)
])

LIFE_SPRITES = sprite_sheet.images_at([
    pygame.Rect(20, 0, 7, 7)
])

FONT_PATH = "joystix monospace.otf"
score_font = pygame.font.Font(FONT_PATH, int(24 * SCALE_FACTOR))
main_font = pygame.font.Font(FONT_PATH, int(36 * SCALE_FACTOR))
title_font = pygame.font.Font(FONT_PATH, int(52 * SCALE_FACTOR))

SCORE_UPDATE_RATE = 3
SCORE_DELTA = 25

# Sound
PLAYER_CRASH_SOUND = pygame.mixer.Sound("./Audio/RCrash.wav")
PLAYER_CRASH_SOUND.set_volume(0.25)
GLITCH_SOUND = pygame.mixer.Sound("./Audio/Glitch.wav")
GLITCH_SOUND.set_volume(0.1)
START_SOUND = pygame.mixer.Sound("./Audio/CountdownChime.wav")
START_SOUND.set_volume(0.25)

class RoadSegment(pygame.sprite.Sprite):
    def __init__(self, offset):
        super().__init__()
        self.texture = texture.Texture(ROAD_SPRITES, 10)
        self.image = self.texture.get_sprite()
        self.rect = self.image.get_rect()

        self.rect.x = 0
        self.rect.y = offset

    def update(self):
        self.rect.y += speed * 2
        if self.rect.y > HEIGHT * 1.5:
            self.rect.y -= HEIGHT * 3

class Road:
    def __init__(self):
        self.segments = pygame.sprite.Group()
        for i in range(3):
            self.segments.add(RoadSegment((i - 1) * HEIGHT))
        
    def update(self):
        for seg in self.segments:
            seg.update()

    def draw(self, screen):
        self.segments.draw(screen)

class Car(pygame.sprite.Sprite):
    def __init__(self, lanes):
        super().__init__()
        self.texture = texture.Texture(PLAYER_SPRITES, 10)
        self.image = self.texture.get_sprite()
        self.rect = self.image.get_rect()

        self.lanes = lanes
        self.lane = 1
        self.rect.center = (self.lanes[self.lane], int(HEIGHT - self.rect.h))
    
    def move_left(self):
        if self.lane > 0:
            self.lane -= 1
            self.rect.center = (self.lanes[self.lane], int(HEIGHT - self.rect.h))
    
    def move_right(self):
        if self.lane < 2:
            self.lane += 1
            self.rect.center = (self.lanes[self.lane], int(HEIGHT - self.rect.h))

    def update(self):
        self.texture.update()
        self.image = self.texture.get_sprite()

class Obstacle(pygame.sprite.Sprite):
    def __init__(self, lane):
        super().__init__()
        self.texture = texture.Texture(OBSTACLE_SPRITES, 10)
        self.image = self.texture.get_sprite()
        self.rect = self.image.get_rect()

        self.rect.center = (lane, 0)
        self.speed = speed
    
    def move(self):
        self.rect.y += self.speed
        if self.rect.y > HEIGHT:
            self.kill()

def on_message(client, userdata, message):
    global restart_game
    global is_active
    global force_start
    payload = message.payload.decode()
    print(payload)
    if payload == "lock":
        restart_game = True
        GPIO.output(COIN_POWER_PIN, GPIO.HIGH)
        client.publish(PUB_TOPIC, "Locked")
    if payload == "activate":
        is_active = True
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
client.on_message = on_message
client.on_connect = on_connect
client.connect(BROKER)
restart_game = False
force_start = False
is_active = False

def main(lives):
    global SCALE_FACTOR
    global restart_game
    # Constants
    LANE_WIDTH = (WIDTH - 180 * SCALE_FACTOR) // 3
    WHITE = (255, 255, 255)
    lanes = [LANE_WIDTH * i + LANE_WIDTH // 2 + 90 * SCALE_FACTOR for i in range(3)]

    life_sprite = texture.Texture(LIFE_SPRITES, 10).get_sprite()
    life_text = score_font.render(f"x{lives}", True, WHITE)

    # Game loop
    running = True
    next_obstacle = random.randint(OBSTACLE_DELAY_MIN, OBSTACLE_DELAY_MAX)

    next_score = SCORE_UPDATE_RATE
    score = 0
    glitch = None

    # Initialize car
    car = Car(lanes)
    car_group = pygame.sprite.Group(car)
    obstacles = pygame.sprite.Group()
    road = Road()
    win = False
    
    pygame.mixer.music.load("./Audio/RMusicLoop.wav")
    pygame.mixer.music.play()

    prev_left_state = GPIO.input(LEFT_PIN)
    prev_right_state = GPIO.input(RIGHT_PIN)

    while running:
        if restart_game:
            return True
        pre_display.fill(WHITE)
        
        # Event handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT:
                    car.move_left()
                elif event.key == pygame.K_RIGHT:
                    car.move_right()
            
        if GPIO.input(LEFT_PIN) != prev_left_state and prev_left_state:
            car.move_left()
        if GPIO.input(RIGHT_PIN) != prev_right_state and prev_right_state:
            car.move_right()
        prev_left_state = GPIO.input(LEFT_PIN)
        prev_right_state = GPIO.input(RIGHT_PIN)
        
        # Spawn obstacles
        if glitch is None or glitch.delta_height == 1:
            next_obstacle -= 1
            if next_obstacle == 0:
                next_obstacle = random.randint(OBSTACLE_DELAY_MIN, OBSTACLE_DELAY_MAX)
                spawn_lanes = random.sample(lanes, 2)
                for lane in spawn_lanes:
                    obstacles.add(Obstacle(lane))

        # Increase Score
        next_score -= 1
        if next_score == 0:
            next_score = SCORE_UPDATE_RATE
            if glitch is None:
                score += SCORE_DELTA
            else:
                score = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))

        # Move obstacles
        for obs in obstacles:
            obs.move()

        road.update()
        
        # Draw car and obstacles
        road.draw(pre_display)
        car_group.draw(pre_display)
        obstacles.draw(pre_display)

        # Draw overlay
        if glitch is not None:
            glitch.update()
            glitch.draw(pre_display)
            if glitch.height > 3 * HEIGHT:
                running = False
                win = True
                pygame.mixer.fadeout(1500)
        else:
            if score >= 4000:
                glitch = g.Glitch(WIDTH, SCALE_FACTOR, -50)
                GLITCH_SOUND.play(-1)
                pygame.mixer.music.fadeout(1000)
            
            # Check for collisions
            if len(pygame.sprite.groupcollide(obstacles, car_group, False, False)) > 0:
                running = False
                win = False
                pygame.mixer.music.stop()
                PLAYER_CRASH_SOUND.play()
        
        score_text = score_font.render(f"score: {score}", True, (200, 0, 0))
        pre_display.blit(score_text, (10 * SCALE_FACTOR, 10 * SCALE_FACTOR))

        pre_display.blit(life_text, (
                WIDTH - (10 * SCALE_FACTOR + life_text.get_width()),
                10 * SCALE_FACTOR))
        pre_display.blit(life_sprite, (
                WIDTH - (10 * SCALE_FACTOR + life_sprite.get_width() + life_text.get_width()), 
                10 * SCALE_FACTOR))

        screen.blit(pygame.transform.rotate(pre_display, 90), (0,0))
        pygame.display.flip()
        clock.tick(FPS)
    
    if win:
        screen.fill((0, 0, 0))
        pygame.display.flip()
    return win

def lose():
    pre_display.fill((0, 0, 0))
    glitch = g.Glitch(WIDTH, SCALE_FACTOR, -50)
    GLITCH_SOUND.play(-1)
    while glitch.height < HEIGHT * 3:
        message = main_font.render("Game Over", True, (255, 0, 0))
        pre_display.blit(message, (WIDTH // 2 - message.get_width() // 2, HEIGHT // 2 - message.get_height() // 2))
        glitch.update()
        glitch.draw(pre_display)
        screen.blit(pygame.transform.rotate(pre_display, 90), (0,0))
        pygame.display.flip()
        clock.tick(FPS)
    pygame.mixer.fadeout(1500)

def await_start():
    global SCALE_FACTOR
    global restart_game
    global force_start
    # Constants
    LANE_WIDTH = (WIDTH - 180 * SCALE_FACTOR) // 3
    WHITE = (255, 255, 255)
    lanes = [LANE_WIDTH * i + LANE_WIDTH // 2 + 90 * SCALE_FACTOR for i in range(3)]

    # Initialize car
    car = Car(lanes)
    car_group = pygame.sprite.Group(car)
    road = Road()
    
    counter = 0
    countdown = False
    
    while True:
        if restart_game:
            return False

        road.update()
        
        # Draw car and obstacles
        road.draw(pre_display)
        car_group.draw(pre_display)

        title1 = title_font.render("Neon", False, (255, 0, 255))
        title2 = title_font.render("Drift", False, (255, 0, 255))
        
        pre_display.blit(title1, (WIDTH // 2 - title1.get_width() // 2, HEIGHT // 2 - title1.get_height() // 2 - 5 * SCALE_FACTOR))
        pre_display.blit(title2, (WIDTH // 2 - title2.get_width() // 2, HEIGHT // 2 + 5 * SCALE_FACTOR))

        if countdown:
            prompt = score_font.render(str(((FPS * 3) - counter) // FPS + 1), False, (0, 255, 0))
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
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    countdown = True
                    counter = 0
                    START_SOUND.play()
        
        if not GPIO.input(COIN_PIN) or force_start:
            force_start = False
            countdown = True
            counter = 0
            START_SOUND.play()
    return True

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
        GPIO.output(COIN_POWER_PIN, GPIO.HIGH)
        client.publish(PUB_TOPIC, "Started")
        
        while True:
            if main(lives): # if player wins
                screen.fill((0, 0, 0))

                prompt = score_font.render("Pull right side open.", False, (255, 0, 0))
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

                    prompt = score_font.render("Pull right side open.", False, (255, 0, 0))
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
