import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import pygame
import time
import random

pygame.init()

# ================= SCREEN =================
screen = pygame.display.set_mode((800, 700))
pygame.display.set_caption("Hearthstone")
icon = pygame.image.load("./image_add/Screenshot 2025-11-27 151541.png")
pygame.display.set_icon(icon)

# ================= FONTS =================
simple_font = pygame.font.SysFont('Arial', 24)
title_font = pygame.font.SysFont('Arial', 36)

# ================= IMAGES =================
entertainment = pygame.transform.smoothscale(
    pygame.image.load("./image_add/IMG_3857.PNG"), (600, 400)
)
loading_img = pygame.transform.smoothscale(
    pygame.image.load("./image_add/IMG_3858.PNG"), (700, 500)
)
game_bg = pygame.transform.scale(
    pygame.image.load(r"D:\MAZ\MAZ\image_add\Screenshot 2025-12-16 175133.png"),
    (800, 700)
)

import pygame

# --------- hero images ---------
hero_images = {
    "sylvanas": pygame.image.load("./bgknowhow-main/images/heroes/BG23_HERO_306_render_80.webp"),
    "lich_king": pygame.image.load("./bgknowhow-main/images/heroes/TB_BaconShop_HERO_22_render_80.webp"),
    "millhouse": pygame.image.load("./bgknowhow-main/images/heroes/TB_BaconShop_HERO_49_render_80.webp"),
    "yogg_saron": pygame.image.load("./bgknowhow-main/images/heroes/TB_BaconShop_HERO_35_render_80.webp")
}

def show_hero_selection_screen(screen, simple_font, title_font):
    screen.fill((30 , 30 , 60))
    
    selection_title = title_font.render("Choose Your Hero" , True , (255 , 215 , 0))
    title_rect = selection_title.get_rect(center=(400 , 50))
    screen.blit(selection_title, title_rect)
    
    hero_width = 150
    hero_height = 200
    spacing = 50
    start_x = 100
    base_y = 250
    name_y = 350
    
    heroes_data = [
        {"name": "Sylvanas" , "key" : "sylvanas" , "x" : start_x},
        {"name": "Lich King" , "key" : "lich_king" , "x" : start_x + hero_width + spacing},
        {"name": "Millhouse" , "key" : "millhouse" , "x" : start_x + 2 * (hero_width + spacing)},
        {"name": "Yogg-Saron" , "key" : "yogg_saron" , "x" : start_x + 3 * (hero_width + spacing)}
    ]
    
    hero_rects = {}
    for hero in heroes_data:
        hero_scaled = pygame.transform.smoothscale(hero_images[hero["key"]] , (hero_width , hero_height))
        hero_rect = hero_scaled.get_rect(center=(hero["x"] , base_y))
        screen.blit(hero_scaled, hero_rect)
        hero_rects[hero["key"]] = hero_rect
        
        hero_name = simple_font.render(hero["name"] , True , (255, 255, 255))
        hero_name_rect = hero_name.get_rect(center=(hero["x"] , name_y))
        screen.blit(hero_name, hero_name_rect)
    
    instruction = simple_font.render("Click on a hero to select", True, (200, 200, 200))
    instruction_rect = instruction.get_rect(center=(400, 500))
    screen.blit(instruction, instruction_rect)
    
    return hero_rects

#--- Heroes ---
class Sylvanas :
    def __init__(self , screen , x , y) :
        self.screen = screen
        self.x = x
        self.y = y
        self.name = "Sylvanas Windrunner"
        self.hero_power_name = "Reclaimed Souls"
        self.hero_power_cost = 1
        self.hero_power_description = "Give +2/+1 to your minions that died last combat."
        self.portrait = pygame.image.load("./bgknowhow-main/images/heroes/BG23_HERO_306_render_80.webp")
        self.portrait = pygame.transform.scale(self.portrait, (100, 100))

    def draw(self):
        self.screen.blit(self.portrait , (self.x , self.y))
        font = pygame.font.Font(None , 24)
        name_text = font.render(self.name , True, (255, 255, 255))
        power_text = font.render(f"{self.hero_power_name} ({self.hero_power_cost} Gold)", True, (200, 200, 100))
        desc_text = font.render(self.hero_power_description, True, (200, 200, 200))
        self.screen.blit(name_text, (self.x, self.y + 110))
        self.screen.blit(power_text, (self.x, self.y + 130))
        self.screen.blit(desc_text, (self.x, self.y + 150))

    def use_hero_power(self, gold):
        if gold >= self.hero_power_cost:
            print(f"{self.name} used {self.hero_power_name}!")
            return gold - self.hero_power_cost
        else:
            print("Not enough Gold!")
            return gold

class LichKing:
    def __init__(self, screen, x, y):
        self.screen = screen
        self.x = x
        self.y = y
        self.name = "The Lich King"
        self.hero_power_name = "Reborn Rites"
        self.hero_power_cost = 1
        self.hero_power_description = "Give a friendly minion Reborn for the next combat only."
        self.portrait = pygame.image.load("./bgknowhow-main/images/heroes/TB_BaconShop_HERO_22_render_80.webp")
        self.portrait = pygame.transform.scale(self.portrait, (100, 100))

    def draw(self):
        self.screen.blit(self.portrait, (self.x, self.y))
        font = pygame.font.Font(None, 24)
        name_text = font.render(self.name, True, (255, 255, 255))
        power_text = font.render(f"{self.hero_power_name} ({self.hero_power_cost} Gold)", True, (200, 200, 100))
        desc_text = font.render(self.hero_power_description, True, (200, 200, 200))
        self.screen.blit(name_text, (self.x, self.y + 110))
        self.screen.blit(power_text, (self.x, self.y + 130))
        self.screen.blit(desc_text, (self.x, self.y + 150))

    def use_hero_power(self, gold, target_minion="Friendly Minion"):
        if gold >= self.hero_power_cost:
            print(f"{self.name} used {self.hero_power_name} on {target_minion}!")
            return gold - self.hero_power_cost
        else:
            print("Not enough Gold!")
            return gold
        





class MillhouseManastorm:
    def __init__(self, screen, x, y) :
        self.screen = screen
        self.x = x
        self.y = y
        self.name = "Millhouse Manastorm"
        self.hero_power_name = "Manastorm"
        self.hero_power_cost = 0 
        self.hero_power_description = "Minions cost 2 Gold. Refreshes cost 2 Gold. Start with 3 Gold. (Tavern upgrades cost 1 more)"
        self.portrait = pygame.image.load("./bgknowhow-main/images/heroes/TB_BaconShop_HERO_49_render_80.webp")
        self.portrait = pygame.transform.scale(self.portrait, (100, 100))
        self.is_passive = True

    def draw(self):
        self.screen.blit(self.portrait, (self.x, self.y))
        font = pygame.font.Font(None, 24)
        name_text = font.render(self.name, True, (255, 255, 255))
        power_text = font.render(f"{self.hero_power_name} (Passive)", True, (100, 200, 255))
        

        desc_lines = self.hero_power_description.split('. ')
        
        self.screen.blit(name_text, (self.x, self.y + 110))
        self.screen.blit(power_text, (self.x, self.y + 130))
        

        y_offset = 150
        for line in desc_lines:
            if line: 
                desc_text = font.render(line.strip() + ".", True, (200, 200, 200))
                self.screen.blit(desc_text, (self.x, self.y + y_offset))
                y_offset += 20

    def use_hero_power(self, gold):

        print(f"{self.name}'s ability is passive and always active!")
        return gold 

    def apply_passive_effects(self, base_minion_cost, base_refresh_cost, base_upgrade_cost):

        modified_minion_cost = base_minion_cost + 2 
        modified_refresh_cost = base_refresh_cost + 2
        modified_upgrade_cost = base_upgrade_cost + 1
        
        return modified_minion_cost, modified_refresh_cost, modified_upgrade_cost
    





class YoggSaron:
    def __init__(self, screen, x, y):
        self.screen = screen
        self.x = x
        self.y = y
        self.name = "Yogg-Saron"
        self.hero_power_name = "Puzzle Box"
        self.hero_power_cost = 2
        self.hero_power_description = "Add a random minion from your current Tavern Tier to your hand."
        self.portrait = pygame.image.load("./bgknowhow-main/images/heroes/TB_BaconShop_HERO_35_render_80.webp")
        self.portrait = pygame.transform.scale(self.portrait, (100, 100))
        self.current_tavern_tier = 1

    def draw(self):
        self.screen.blit(self.portrait, (self.x, self.y))
        font = pygame.font.Font(None, 24)
        name_text = font.render(self.name, True, (255, 255, 255))
        power_text = font.render(f"{self.hero_power_name} ({self.hero_power_cost} Gold)", True, (200, 200, 100))
        desc_text = font.render(self.hero_power_description, True, (200, 200, 200))
        

        tavern_tier_text = font.render(f"Current Tavern Tier: {self.current_tavern_tier}", True, (150, 220, 150))
        
        self.screen.blit(name_text, (self.x, self.y + 110))
        self.screen.blit(power_text, (self.x, self.y + 130))
        self.screen.blit(desc_text, (self.x, self.y + 150))
        self.screen.blit(tavern_tier_text, (self.x, self.y + 170))

    def use_hero_power(self, gold):
        if gold >= self.hero_power_cost:
            print(f"{self.name} used {self.hero_power_name}!")
            print(f"Adding a random minion from Tavern Tier {self.current_tavern_tier} to hand...")
            


            random_minion = self.get_random_minion_from_tier(self.current_tavern_tier)
            print(f"Added {random_minion} to your hand!")
            
            return gold - self.hero_power_cost
        else:
            print("Not enough Gold!")
            return gold

    def get_random_minion_from_tier(self, tier):


        minions_by_tier = {
            1: ["Alleycat", "Murloc Tidehunter", "Rockpool Hunter", "Selfless Hero"],
            2: ["Glyph Guardian", "Kaboom Bot", "Murloc Warleader", "Old Murk-Eye"],
            3: ["Crackling Cyclone", "Floating Watcher", "Houndmaster", "Imp Gang Boss"],
            4: ["Cave Hydra", "Defender of Argus", "Menagerie Magician", "Virmen Sensei"],
            5: ["Annihilan Battlemaster", "Baron Rivendare", "Lightfang Enforcer", "Mama Bear"],
            6: ["Ghastcoiler", "Kalecgos", "Maexxna", "Zapp Slywick"]
        }
        
        if tier in minions_by_tier and minions_by_tier[tier]:
            return random.choice(minions_by_tier[tier])
        return "Unknown Minion"

    def upgrade_tavern_tier(self):
        if self.current_tavern_tier < 6:
            self.current_tavern_tier += 1
            print(f"{self.name} upgraded to Tavern Tier {self.current_tavern_tier}!")
        else:
            print("Already at maximum Tavern Tier!")
# ================= CONSTANTS =================
SHOP_X, SHOP_Y, SHOP_W, SHOP_H, SHOP_GAP = 50, 50, 80, 100, 100
HAND_X, HAND_Y, HAND_W, HAND_H, HAND_GAP = 50, 500, 60, 90, 70
BOARD_X, BOARD_Y, BOARD_W, BOARD_H, BOARD_GAP = 50, 250, 80, 100, 100

END_TURN_RECT = pygame.Rect(650, 600, 120, 50)

# ================= GAME STATE =================
show_loading = True
show_second_loading = False
show_hero_selection = False
time_start_loading = 0
selected_hero = None
hero_rects = {}
running = True
game_over = False

player_state = {
    "gold": 3,
    "hp": 30,
    "board": [],
    "hand": [],
    "shop": []
}

all_minions = [
    "Buzzing Vermin",
    "Wrath Weaver",
    "Harmless Bonehead",
    "Eternal Knight"
]

# ================= DRAW =================
def draw_game_board():
    screen.blit(game_bg, (0, 0))

    # --- Shop ---
    for i, card in enumerate(player_state["shop"]):
        rect = pygame.Rect(SHOP_X + i*SHOP_GAP, SHOP_Y, SHOP_W, SHOP_H)
        pygame.draw.rect(screen, (120, 50, 50), rect)
        if card:
            text = simple_font.render(card, True, (255, 255, 255))
            screen.blit(text, (rect.x+5, rect.y+40))

    # --- Board ---
    for i, card in enumerate(player_state["board"]):
        rect = pygame.Rect(BOARD_X + i*BOARD_GAP, BOARD_Y, BOARD_W, BOARD_H)
        pygame.draw.rect(screen, (50, 50, 50), rect)
        text = simple_font.render(card, True, (255, 255, 255))
        screen.blit(text, (rect.x+5, rect.y+40))

    # --- Hand ---
    for i, card in enumerate(player_state["hand"]):
        rect = pygame.Rect(HAND_X + i*HAND_GAP, HAND_Y, HAND_W, HAND_H)
        pygame.draw.rect(screen, (80, 80, 80), rect)
        text = simple_font.render(card, True, (255, 255, 255))
        screen.blit(text, (rect.x+5, rect.y+35))

    # --- Stats ---
    gold_text = simple_font.render(f"Gold: {player_state['gold']}", True, (255, 255, 0))
    hp_text = simple_font.render(f"HP: {player_state['hp']}", True, (255, 80, 80))
    screen.blit(gold_text, (650, 10))
    screen.blit(hp_text, (650, 40))

    # --- End Turn ---
    pygame.draw.rect(screen, (180, 50, 50), END_TURN_RECT)
    end_text = simple_font.render("End Turn", True, (255,255,255))
    screen.blit(end_text, (END_TURN_RECT.x+10, END_TURN_RECT.y+10))

    # --- Hero ---
    if selected_hero:
        hero_img = pygame.transform.scale(hero_images[selected_hero], (120, 177))
        screen.blit(hero_img, (316, 520))

def draw_game_over():
    screen.fill((0,0,0))
    text = title_font.render("GAME OVER", True, (255,0,0))
    screen.blit(text, text.get_rect(center=(400,300)))

# ================= MAIN LOOP =================
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if game_over:
            continue

        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            if show_loading:
                show_loading = False
                show_second_loading = True
                time_start_loading = time.time()

        elif event.type == pygame.MOUSEBUTTONDOWN and show_hero_selection:
            mouse_pos = pygame.mouse.get_pos()
            for hero_key, rect in hero_rects.items():
                if rect.collidepoint(mouse_pos):
                    selected_hero = hero_key
                    show_hero_selection = False
                    player_state["shop"] = random.sample(all_minions, 3)

        elif event.type == pygame.MOUSEBUTTONDOWN and not show_hero_selection:
            mouse_pos = pygame.mouse.get_pos()

            # BUY
            for i, card in enumerate(player_state["shop"]):
                rect = pygame.Rect(SHOP_X + i*SHOP_GAP, SHOP_Y, SHOP_W, SHOP_H)
                if rect.collidepoint(mouse_pos) and card:
                    if player_state["gold"] >= 3:
                        player_state["gold"] -= 3
                        player_state["hand"].append(card)
                        player_state["shop"][i] = None

            # PLAY
            for i, card in enumerate(player_state["hand"]):
                rect = pygame.Rect(HAND_X + i*HAND_GAP, HAND_Y, HAND_W, HAND_H)
                if rect.collidepoint(mouse_pos):
                    if len(player_state["board"]) < 7:
                        player_state["board"].append(card)
                        player_state["hand"].pop(i)
                    break

            # END TURN → COMBAT
            if END_TURN_RECT.collidepoint(mouse_pos):
                damage = len(player_state["board"])
                player_state["hp"] -= damage

                if player_state["hp"] <= 0:
                    game_over = True
                else:
                    player_state["gold"] = min(10, player_state["gold"] + 1)
                    player_state["shop"] = random.sample(all_minions, 3)

    # ---------- SCREENS ----------
    if show_loading:
        screen.fill((0,0,0))
        screen.blit(entertainment, entertainment.get_rect(center=(400,350)))
        screen.blit(simple_font.render("Press ENTER", True, (255,255,255)), (320, 550))

    elif show_second_loading:
        screen.fill((0,0,0))
        screen.blit(loading_img, loading_img.get_rect(center=(400,300)))
        if time.time() - time_start_loading > 2:
            show_second_loading = False
            show_hero_selection = True

    elif show_hero_selection:
        hero_rects = show_hero_selection_screen(screen, simple_font, title_font)

    elif game_over:
        draw_game_over()

    else:
        draw_game_board()

    pygame.display.update()

pygame.quit()
