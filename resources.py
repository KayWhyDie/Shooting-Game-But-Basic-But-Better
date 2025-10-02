import pygame, os

# Sound loader: returns pygame.mixer.Sound or None
def try_load_sound(path):
    try:
        return pygame.mixer.Sound(path)
    except Exception:
        return None

# Image loader: returns Surface or None
def try_load_image(path):
    try:
        return pygame.image.load(path).convert_alpha()
    except Exception:
        return None

# Convenience loaders that prefer source/ directory when present
def load_sound_prefer_source(name):
    # name is filename like 'rifle1.mp3'
    s = try_load_sound(os.path.join('source', name))
    if s: return s
    return try_load_sound(name)

def load_image_prefer_source(name):
    i = try_load_image(os.path.join('source', name))
    if i: return i
    return try_load_image(name)
