import pygame

class SpriteSheet(object):
    def __init__(self, filename, scale, colourkey = None):
        self.scale = scale
        self.colourkey = colourkey
        try:
            self.sheet = pygame.image.load(filename).convert_alpha()
        except:
            print(f'Unable to load spritesheet image: {filename}')
            raise SystemExit
        print("Success")
    
    # Load a specific image from a specific rectangle
    def image_at(self, rectangle):
        rect = pygame.Rect(rectangle)
        image = pygame.Surface(rect.size).convert()
        image.blit(self.sheet, (0, 0), rect)

        w = rect.w * self.scale
        h = rect.h * self.scale
        image = pygame.transform.scale(image, (w, h))

        if self.colourkey is not None:
            if self.colourkey == -1:
                self.colourkey = image.get_at((0,0))
            image.set_colorkey(self.colourkey)
        return image
    
    # Load a whole bunch of images and return them as a list
    def images_at(self, rects):
        "Loads multiple images, supply a list of coordinates" 
        return [self.image_at(rect) for rect in rects]
    
    # Load a whole strip of images
    def load_strip(self, rect, image_count):
        "Loads a strip of images and returns them as a list"
        tups = [(rect[0]+rect[2]*x, rect[1], rect[2], rect[3])
                for x in range(image_count)]
        return self.images_at(tups)
    
class Texture():
    def __init__(self, sprite_set, animation_speed):
        self.sprite_set = sprite_set
        self.updates_per_frame = animation_speed
        self.update_count = 0
        self.current_frame = 0

    def update(self):
        self.update_count += 1
        if self.update_count >= self.updates_per_frame:
            self.update_count = 0
            self.current_frame += 1
            self.current_frame %= len(self.sprite_set)

    def get_sprite(self):
        return self.sprite_set[self.current_frame]
