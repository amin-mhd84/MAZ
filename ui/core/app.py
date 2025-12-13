import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import pygame
import time
from ui.screens.recruit_screen import show_hero_selection_screen, hero_images

pygame.init()

# --------- screen ---------
screen = pygame.display.set_mode((800, 700))
pygame.display.set_caption("Hearthstone")
icon = pygame.image.load("./image_add/Screenshot 2025-11-27 151541.png")
pygame.display.set_icon(icon)

# --------- fonts ---------
simple_font = pygame.font.SysFont('Arial', 24)
title_font = pygame.font.SysFont('Arial', 36)

# --------- loading images ---------
entertainment_original = pygame.image.load("./image_add/IMG_3857.PNG")
entertainment = pygame.transform.smoothscale(entertainment_original , (600 , 400))

image_for_loading_original = pygame.image.load("./image_add/IMG_3858.PNG")
image_for_loading = pygame.transform.smoothscale(image_for_loading_original , (700 , 500))

# --------- game state ---------
show_loading = True
show_second_loading = False
show_hero_selection = False
time_start_loading = 0
selected_hero = None
hero_rects = {}
running = True

# --------- main loop ---------
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN and show_loading:
                show_loading = False
                show_second_loading = True
                time_start_loading = time.time()
        elif event.type == pygame.MOUSEBUTTONDOWN and show_hero_selection:
            mouse_pos = pygame.mouse.get_pos()
            for hero_key, rect in hero_rects.items():
                if rect.collidepoint(mouse_pos):
                    selected_hero = hero_key
                    print(f"{hero_key} selected!")
                    show_hero_selection = False
                    break

    # --------- screens ---------
    if show_loading:
        screen.fill((0 , 0 , 0))
        entertainment_rect = entertainment.get_rect(center=(400 , 350))
        screen.blit(entertainment, entertainment_rect)

        press_text = simple_font.render("Press ENTER to start", True, (255, 255, 255))
        press_rect = press_text.get_rect(center=(400, 550))
        screen.blit(press_text, press_rect)
    
    elif show_second_loading:
        screen.fill((0, 0, 0))
        loading_rect = image_for_loading.get_rect(center=(400 , 300))
        screen.blit(image_for_loading , loading_rect)
        
        loading_text = simple_font.render("Loading...", True, (255, 255, 255))
        loading_text_rect = loading_text.get_rect(center=(400, 450))
        screen.blit(loading_text, loading_text_rect)
        
        if time.time() - time_start_loading >= 3:
            show_second_loading = False
            show_hero_selection = True
    
    elif show_hero_selection:
        hero_rects = show_hero_selection_screen(screen, simple_font, title_font)
    
    else:
        screen.fill((0, 0, 0))
        if selected_hero:
            game_text = simple_font.render(f"Game Started! Selected Hero: {selected_hero}", True, (255, 255, 255))
        else:
            game_text = simple_font.render("Game Started! Main screen will be here", True, (255, 255, 255))
        game_rect = game_text.get_rect(center=(400, 350))
        screen.blit(game_text, game_rect)
    
    pygame.display.update()

pygame.quit()
