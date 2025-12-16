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

# --------- background image ---------
game_bg_original = pygame.image.load(r"D:\MAZ\MAZ\image_add\Screenshot 2025-12-16 175133.png")
game_bg = pygame.transform.scale(game_bg_original, (800, 700))  

# --------- game state ---------
show_loading = True
show_second_loading = False
show_hero_selection = False
time_start_loading = 0
selected_hero = None
hero_rects = {}
running = True

# --------- sample game state for first phase ---------
player_state = {
    "Exir": 3,
    "board": [],  
    "hand": [],  
    "shop": []  
}

# --------- Turn system ---------
current_turn = 0
turn_cards_queue = ["Alleycat", "Murloc Tidehunter", "Rockpool Hunter", "Selfless Hero"]

def next_turn():
    global current_turn
    current_turn += 1

    if turn_cards_queue:
        next_card = turn_cards_queue.pop(0)
        player_state["hand"].append(next_card)
        print(f"Turn {current_turn}: {next_card} added to hand!")

def draw_game_board(screen, font, state, selected_hero=None):
    screen.blit(game_bg, (0, 0)) 

    # --- Board ---
    for i, minion in enumerate(state["board"]):
        rect = pygame.Rect(50 + i*100, 250, 80, 100)
        pygame.draw.rect(screen, (50, 50, 50), rect)  
        if minion:
            text = font.render(minion, True, (255, 255, 255))
            screen.blit(text, (rect.x+5, rect.y+40))

    # --- Hand ---
    for i, card in enumerate(state["hand"]):
        rect = pygame.Rect(50 + i*70, 500, 60, 90)
        pygame.draw.rect(screen, (80, 80, 80), rect)
        text = font.render(card, True, (255, 255, 255))
        screen.blit(text, (rect.x+5, rect.y+35))

    # --- Shop ---
    for i, card in enumerate(state["shop"]):
        rect = pygame.Rect(50 + i*100, 50, 80, 100)
        pygame.draw.rect(screen, (100, 50, 50), rect)
        text = font.render(card, True, (255, 255, 255))
        screen.blit(text, (rect.x+5, rect.y+40))

    # --- Exir display ---
    Exir_text = font.render(f"Exir: {state['Exir']}", True, (255, 255, 0))
    screen.blit(Exir_text, (650, 10))

    # --- Hero image ---
    if selected_hero:
        hero_img = hero_images[selected_hero]
        hero_img_small = pygame.transform.scale(hero_img, (120, 177))  # سایز کوچک برای پایین صفحه
        hero_rect = hero_img_small.get_rect()
        hero_rect.bottomleft = (316, 630)  
        screen.blit(hero_img_small, hero_rect)


# --------- main loop ---------
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                if show_loading:
                    show_loading = False
                    show_second_loading = True
                    time_start_loading = time.time()
                elif show_second_loading:
                    pass  
                elif show_hero_selection:
                    pass
                else:
                    next_turn()

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
        draw_game_board(screen, simple_font, player_state, selected_hero)

    
    pygame.display.update()

pygame.quit()
