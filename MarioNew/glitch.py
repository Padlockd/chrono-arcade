import pygame
import random

class GlitchRect:
    def __init__(self, height, width, scale):
        self.rect = pygame.Rect(
            height + random.randint(-10, 10) * scale, 
            random.randint(0, width), 
            random.randint(10, 100) * scale,
            random.randint(10, 200) * scale 
        )
        self.r = random.randint(0, 255)
        self.g = random.randint(0, 255)
        self.b = random.randint(0, 255)

    def update(self):
        if self.get_max_pixel() == 0:
            return
        if self.r > 0: 
            self.r = max(self.r - random.randint(5, 10), 0)
        if self.g > 0: 
            self.g = max(self.g - random.randint(5, 10), 0)
        if self.b > 0: 
            self.b = max(self.b - random.randint(5, 10), 0)

        self.rect.w = max(10, self.rect.w + random.randint(-3, 3))
        self.rect.h = max(10, self.rect.h + random.randint(-3, 3))
        self.rect.y = max(0, self.rect.y + random.randint(-3, 3))
        self.rect.x = self.rect.x + random.randint(-3, 3)

    def get_max_pixel(self):
        return max(self.r, self.g, self.b)

    def draw(self, screen):
        colour = (self.r, self.g, self.b)
        pygame.draw.rect(screen, colour, self.rect)

class Glitch:
    def __init__(self, width, scale, start_height = -20):
        self.rects = []
        self.height = start_height * scale
        self.delta_height = 1
        self.width = width
        self.scale = scale

    def update(self, screen_width):
        for i in range(1, 4 + self.delta_height // 5):
            self.rects.append(GlitchRect(screen_width - self.height, self.width, self.scale))
        self.height += self.delta_height

        if self.height > 0:
            self.delta_height += 1

    def draw(self, screen, screen_width):
        pygame.draw.rect(screen, (0, 0, 0), pygame.Rect(screen_width - self.height, 0, self.height, self.width))
        for rect in self.rects:
            rect.update()
            rect.draw(screen)
