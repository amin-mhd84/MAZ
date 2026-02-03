import pygame
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import random
import time
import math

from assets.minions.minions import create_minion, MinionManager

pygame.init()

screen = pygame.display.set_mode((800, 700))
pygame.display.set_caption("Hearthstone Battlegrounds")
icon = pygame.image.load("./image_add/Screenshot 2025-11-27 151541.png")
pygame.display.set_icon(icon)

game_bg = pygame.transform.scale(
    pygame.image.load(r"./image_add/Screenshot 2025-12-16 175133.png"),
    (800, 700)
)

clock = pygame.time.Clock()
running = True

# Game state
turn = 1
game_mode = "recruit"
selected_card = None
dragging_card = None

minion_manager = MinionManager(screen)

class Economy:
    def __init__(self):
        self.gold = 3
        self.max_gold = 10
        self.turn = 0
        self.tavern_tier = 1
        self.upgrade_cost_base = 5
        self.refresh_cost = 1
        self.minion_cost_base = 3
        
    def start_new_turn(self):
        self.turn += 1
        gold_gain = min(10, 3 + self.turn)
        self.gold = min(self.max_gold, gold_gain)
        
    def buy_minion(self):
        if self.gold >= self.minion_cost_base:
            self.gold -= self.minion_cost_base
            return True
        return False
        
    def sell_minion(self):
        self.gold = min(self.max_gold, self.gold + 1)
        return True
        
    def refresh_shop(self):
        if self.gold >= self.refresh_cost:
            self.gold -= self.refresh_cost
            return True
        return False
        
    def upgrade_tavern(self):
        costs = {1: 5, 2: 7, 3: 8, 4: 9, 5: 10}
        cost = costs.get(self.tavern_tier, 0)
        if self.gold >= cost and self.tavern_tier < 6:
            self.gold -= cost
            self.tavern_tier += 1
            return True
        return False

class ShopSystem:
    def __init__(self, screen, economy):
        self.screen = screen
        self.economy = economy
        self.shop_slots = []
        self.shop_positions = [
            (130, 200), (230, 200), (330, 200), (430, 200), (530, 200)
        ]
        self.frozen = False
        self.refresh()
        
    def refresh(self):
        if not self.frozen:
            self.shop_slots.clear()
            
            slot_count = min(3 + self.economy.tavern_tier // 2, 5)
            
            tier_minions = {
                1: ["BG31_803", "BGS_004", "BG28_300"],
                2: ["BG25_010", "BG29_140", "BG31_801"],
                3: ["BG25_011", "BG27_084"],
                4: ["BG31_809", "BG25_008", "BGS_044"],
                5: ["BG31_807", "BG25_009", "BG31_874", "BG25_354"],
                6: ["BGS_078", "BG21_005", "BG30_129"]
            }
            
            available_minions = []
            for tier in range(1, self.economy.tavern_tier + 1):
                available_minions.extend(tier_minions.get(tier, []))
            
            for i in range(slot_count):
                if available_minions:
                    card_id = random.choice(available_minions)
                    x, y = self.shop_positions[i]
                    minion = create_minion(self.screen, x, y, card_id)
                    minion.shop_index = i 
                    minion.cost = 3
                    self.shop_slots.append(minion)
        
    def buy_minion(self, index):
        if 0 <= index < len(self.shop_slots):
            if self.economy.buy_minion():
                minion = self.shop_slots[index]
                minion.in_hand = True
                minion.shop_index = None
                
                purchased_minion = self.shop_slots[index]
                self.shop_slots[index] = None 
                

                return purchased_minion
        return None
    
    def _add_new_minion_to_shop(self):
        tier_minions = {
            1: ["BG31_803", "BGS_004", "BG28_300"],
            2: ["BG25_010", "BG29_140", "BG31_801"],
            3: ["BG25_011", "BG27_084"],
            4: ["BG31_809", "BG25_008", "BGS_044"],
            5: ["BG31_807", "BG25_009", "BG31_874", "BG25_354"],
            6: ["BGS_078", "BG21_005", "BG30_129"]
        }
        
        available_minions = []
        for tier in range(1, self.economy.tavern_tier + 1):
            available_minions.extend(tier_minions.get(tier, []))
        
        if available_minions:
            slot_count = min(3 + self.economy.tavern_tier // 2, 5)
            
            while len(self.shop_slots) < slot_count:
                self.shop_slots.append(None)
            
            for i in range(slot_count):
                card_id = random.choice(available_minions)
                x, y = self.shop_positions[i]
                minion = create_minion(self.screen, x, y, card_id)
                minion.shop_index = i
                minion.cost = 3
                self.shop_slots[i] = minion  
    def toggle_freeze(self):
        self.frozen = not self.frozen
        return self.frozen
    
    def draw(self):
        if self.frozen:
            freeze_font = pygame.font.Font(None, 24)
            freeze_text = freeze_font.render("FROZEN", True, (100, 200, 255))
            self.screen.blit(freeze_text, (350, 280))
        
        for i in range(len(self.shop_positions)):
            x, y = self.shop_positions[i]
            
            slot_rect = pygame.Rect(x, y, 70, 100)
            pygame.draw.rect(self.screen, (40, 40, 60, 150), slot_rect)
            pygame.draw.rect(self.screen, (100, 100, 150), slot_rect, 2)
            
            if i < len(self.shop_slots) and self.shop_slots[i] is not None:
                self.shop_slots[i].draw()
                
                cost_font = pygame.font.Font(None, 20)
                cost_text = cost_font.render(f"{self.shop_slots[i].cost}G", True, (255, 215, 0))
                cost_rect = cost_text.get_rect(center=(x + 40, y - 15))
                self.screen.blit(cost_text, cost_rect)

class PlayerBoard:
    def __init__(self, screen):
        self.screen = screen
        self.board_minions = [] 
        self.hand_minions = []  
        self.board_positions = [
            (105, 340), (185, 340), (265, 340), (345, 340),
            (425, 340), (505, 340), (585, 340)
        ]
        self.hand_positions = [
            (180, 580), (270, 580), (360, 580), (450, 580), (540, 580),
        ]
        
    def add_to_hand(self, minion):
        if len(self.hand_minions) < 10:
            if self.hand_minions:
                next_index = len(self.hand_minions)
            else:
                next_index = 0
                
            if next_index < len(self.hand_positions):
                x, y = self.hand_positions[next_index]
                minion.x = x
                minion.y = y
                minion.in_hand = True
                self.hand_minions.append(minion)
                return True
        return False
    
    def play_to_board(self, minion_index, board_index=None):
        if len(self.board_minions) >= 7:
            print("Cannot play: Board already has 7 minions!")
            return False
            
        if 0 <= minion_index < len(self.hand_minions):
            minion = self.hand_minions.pop(minion_index)
            
            if board_index is not None and 0 <= board_index < len(self.board_positions):
                occupied = any(m.board_slot == board_index for m in self.board_minions)
                if occupied:
                    print(f"Slot {board_index} is already occupied!")
                    self.hand_minions.insert(minion_index, minion)
                    self._organize_hand()
                    return False
                    
                x, y = self.board_positions[board_index]
                minion.board_slot = board_index
            else:
                for slot in range(len(self.board_positions)):
                    occupied = any(m.board_slot == slot for m in self.board_minions)
                    if not occupied:
                        x, y = self.board_positions[slot]
                        minion.board_slot = slot
                        break
                else:
                    print("No empty slots available!")
                    self.hand_minions.insert(minion_index, minion)
                    self._organize_hand()
                    return False
            
            minion.x = x
            minion.y = y
            minion.in_hand = False
            minion.on_board = True
            self.board_minions.append(minion)
            
            self._organize_hand()
            return True
        return False

    def sell_minion(self, board_index):
        if 0 <= board_index < len(self.board_minions):
            minion = self.board_minions.pop(board_index)
            for i, m in enumerate(self.board_minions):
                if i < len(self.board_positions):
                    x, y = self.board_positions[i]
                    m.x = x
                    m.y = y
                    m.board_slot = i
            return minion
        return None
    
    def _organize_hand(self):
        """Reorganize minions in hand to fill empty spaces"""
        for i, minion in enumerate(self.hand_minions):
            if i < len(self.hand_positions):
                x, y = self.hand_positions[i]
                minion.x = x
                minion.y = y
    
    def draw(self):
        for minion in self.board_minions:
            minion.draw()
        
        for minion in self.hand_minions:
            minion.draw()

economy = Economy()
shop_system = ShopSystem(screen, economy)
player_board = PlayerBoard(screen)

player_health = 30
opponent_health = 30

font = pygame.font.Font(None, 32)
small_font = pygame.font.Font(None, 24)

buttons = {
    "RECRUIT": {"rect": pygame.Rect(660, 300, 100, 50), "text": "END TURN", "color": (255, 100, 100), "hover_color": (230, 70, 70)},
    "TIER": {"rect": pygame.Rect(230, 110, 80, 70), "text": "UPGRADE", "color": (50, 150, 50), "hover_color": (30, 130, 30)},
    "FROZE": {"rect": pygame.Rect(450, 80, 80, 50), "text": "FREEZE", "color": (100, 100, 255), "hover_color": (70, 70, 230)},
    "REFRESH": {"rect": pygame.Rect(450, 140, 100, 50), "text": "REFRESH", "color": (255, 200, 50), "hover_color": (230, 180, 30)},
    "SELL": {"rect": pygame.Rect(660, 370, 80, 40), "text": "SELL", "color": (200, 50, 50), "hover_color": (180, 30, 30)}
}

placeholders = {
    "hero": {"rect": pygame.Rect(330, 465, 90, 120), "color": (50, 50, 100, 180), "label": "Hero"},
    "opponent_hero": {"rect": pygame.Rect(330, 70, 90, 120), "color": (100, 50, 50, 180), "label": "Opponent"},
    "players": {"rect": pygame.Rect(30, 250, 50, 200), "color": (100, 50, 50, 180), "label": "players"},
}

golds = []
for i in range(10):
    golds.append(pygame.Rect(30 + i * 30, 50, 25, 30))

def draw_button(button_data, mouse_pos):
    button = button_data["rect"]
    color = button_data["hover_color"] if button.collidepoint(mouse_pos) else button_data["color"]
    
    pygame.draw.rect(screen, color, button, border_radius=8)
    pygame.draw.rect(screen, (255, 255, 255), button, 2, border_radius=8)
    
    text = small_font.render(button_data["text"], True, (255, 255, 255))
    text_rect = text.get_rect(center=button.center)
    screen.blit(text, text_rect)

def draw_placeholder(ph_data):
    ph_surface = pygame.Surface((ph_data["rect"].width, ph_data["rect"].height), pygame.SRCALPHA)
    pygame.draw.rect(ph_surface, ph_data["color"], (0, 0, ph_data["rect"].width, ph_data["rect"].height), border_radius=5)
    pygame.draw.rect(ph_surface, (255, 255, 255), (0, 0, ph_data["rect"].width, ph_data["rect"].height), 2, border_radius=5)
    
    screen.blit(ph_surface, ph_data["rect"])
    
    label = small_font.render(ph_data["label"], True, (255, 255, 255))
    label_rect = label.get_rect(center=ph_data["rect"].center)
    screen.blit(label, label_rect)

def draw_stats():
    turn_text = font.render(f"Turn: {turn}", True, (255, 255, 255))
    screen.blit(turn_text, (650, 20))

    tier_text = font.render(f"Tier: {economy.tavern_tier}", True, (100, 200, 255))
    screen.blit(tier_text, (650, 50))
    
    health_text = font.render(f"Health: {player_health}", True, (255, 50, 50))
    screen.blit(health_text, (650, 80))
    
    opp_health_text = font.render(f"Enemy: {opponent_health}", True, (255, 50, 50))
    screen.blit(opp_health_text, (650, 110))
    
    gold_text = font.render(f"GOLD: {economy.gold}/{economy.max_gold}", True, (255, 215, 0))
    screen.blit(gold_text, (30, 20))
    

    for i, crystal in enumerate(golds):
        if i < economy.max_gold:
            if i < economy.gold:
                pygame.draw.rect(screen, (255, 215, 0), crystal, border_radius=5)
                pygame.draw.rect(screen, (255, 215, 200), crystal, 2, border_radius=5)
                num = small_font.render(str(i + 1), True, (255, 255, 255))
                screen.blit(num, (crystal.x + 10, crystal.y + 10))
            else:
                pygame.draw.rect(screen, (150, 150, 0), crystal, border_radius=5)
                pygame.draw.rect(screen, (200, 200, 100), crystal, 2, border_radius=5)
        else:
            pygame.draw.rect(screen, (100, 100, 0), crystal, border_radius=5)
            pygame.draw.rect(screen, (150, 150, 50), crystal, 2, border_radius=5)

def draw_game_board():

    screen.blit(game_bg, (0, 0))
    
    turn_indicator = pygame.Rect(0, 0, 800, 5)
    pygame.draw.rect(screen, (255, 255, 100) if turn % 2 == 0 else (255, 100, 100), turn_indicator)
    
    for ph_key in placeholders:
        draw_placeholder(placeholders[ph_key])
    
    shop_system.draw()
    
    player_board.draw()
    
    draw_stats()
    
    mouse_pos = pygame.mouse.get_pos()
    for button_key in buttons:
        draw_button(buttons[button_key], mouse_pos)
    
    help_font = pygame.font.Font(None, 18)
    help_text = help_font.render("Click minions to buy, drag to board, right-click to sell", True, (200, 200, 255))
    screen.blit(help_text, (200, 680))

def get_minion_at_position(x, y):

    for minion in shop_system.shop_slots:
        if minion and minion.contains_point((x, y)):
            return minion, "shop"
    
    for minion in player_board.hand_minions:
        if minion and minion.contains_point((x, y)):
            return minion, "hand"
    
    for minion in player_board.board_minions:
        if minion and minion.contains_point((x, y)):
            return minion, "board"
    
    return None, None

while running:
    mouse_pos = pygame.mouse.get_pos()
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                if buttons["REFRESH"]["rect"].collidepoint(mouse_pos):
                    if economy.refresh_shop():
                        shop_system.refresh()
                        print(f"Refreshed shop. Gold: {economy.gold}")
                    else:
                        print("Not enough gold to refresh!")
                
                elif buttons["TIER"]["rect"].collidepoint(mouse_pos):
                    if economy.upgrade_tavern():
                        print(f"Upgraded to Tavern Tier {economy.tavern_tier}! Gold: {economy.gold}")
                    else:
                        print("Cannot upgrade!")
                
                elif buttons["FROZE"]["rect"].collidepoint(mouse_pos):
                    frozen = shop_system.toggle_freeze()
                    print(f"Shop {'frozen' if frozen else 'unfrozen'}!")
                
                elif buttons["RECRUIT"]["rect"].collidepoint(mouse_pos):
                    print("End Turn clicked!")
                    turn += 1
                    economy.start_new_turn()
                    shop_system.refresh()
                    print(f"Turn {turn}. Gold: {economy.gold}")
                
                elif buttons["SELL"]["rect"].collidepoint(mouse_pos) and selected_card:
                    if selected_card.on_board:
                        for i, minion in enumerate(player_board.board_minions):
                            if minion == selected_card:
                                sold_minion = player_board.sell_minion(i)
                                if sold_minion:
                                    economy.sell_minion()
                                    print(f"Sold {sold_minion.name}. Gold: {economy.gold}")
                                    selected_card = None
                                break
                
                else:
                    clicked_minion, location = get_minion_at_position(*mouse_pos)
                    
                    if clicked_minion:
                        if location == "shop":
                            for i, minion in enumerate(shop_system.shop_slots):
                                if minion == clicked_minion:
                                    bought_minion = shop_system.buy_minion(i)
                                    if bought_minion:
                                        player_board.add_to_hand(bought_minion)
                                        print(f"Bought {bought_minion.name}. Gold: {economy.gold}")
                                    else:
                                        print("Not enough gold!")
                                    break
                        
                        elif location == "hand":
                            selected_card = clicked_minion
                            selected_card.selected = True
                            print(f"Selected {clicked_minion.name} from hand")
                        
                        elif location == "board":
                            selected_card = clicked_minion
                            selected_card.selected = True
                            print(f"Selected {clicked_minion.name} from board")
            
            elif event.button == 3:
                clicked_minion, location = get_minion_at_position(*mouse_pos)
                if clicked_minion and location == "board":
                    for i, minion in enumerate(player_board.board_minions):
                        if minion == clicked_minion:
                            sold_minion = player_board.sell_minion(i)
                            if sold_minion:
                                economy.sell_minion()
                                print(f"Sold {sold_minion.name}. Gold: {economy.gold}")
                            break
        
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if selected_card and selected_card.in_hand:
                if len(player_board.board_minions) >= 7:
                    print("Cannot play: Board is full! (7/7 minions)")
                    selected_card.selected = False
                    for i in range(len(player_board.hand_positions)):
                        if i < len(player_board.hand_minions) and player_board.hand_minions[i] == selected_card:
                            x, y = player_board.hand_positions[i]
                            selected_card.x = x
                            selected_card.y = y
                            break
                    selected_card = None
                else:
                    target_slot = None
                    
                    for slot_index, (slot_x, slot_y) in enumerate(player_board.board_positions):
                        slot_rect = pygame.Rect(slot_x, slot_y, 70, 100)
                        
                        if slot_rect.collidepoint(mouse_pos):
                            occupied = any(m.board_slot == slot_index for m in player_board.board_minions)
                            if not occupied:
                                target_slot = slot_index
                            else:
                                print(f"Slot {slot_index} is already occupied!")
                            break
                    
                    if target_slot is not None:
                        for idx, minion in enumerate(player_board.hand_minions):
                            if minion == selected_card:
                                success = player_board.play_to_board(idx, target_slot)
                                if success:
                                    print(f"Played {selected_card.name} to board slot {target_slot}")
                                else:
                                    print(f"Failed to play {selected_card.name}")
                                break
                    else:
                        print("Drop the minion over an empty board slot!")
                        selected_card.selected = False
                        for idx, minion in enumerate(player_board.hand_minions):
                            if minion == selected_card:
                                x, y = player_board.hand_positions[idx]
                                selected_card.x = x
                                selected_card.y = y
                                break
                    
                    selected_card = None
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r:
                if economy.refresh_shop():
                    shop_system.refresh()
                    print(f"Refreshed shop. Gold: {economy.gold}")
            
            elif event.key == pygame.K_u:
                if economy.upgrade_tavern():
                    print(f"Upgraded to Tavern Tier {economy.tavern_tier}! Gold: {economy.gold}")
            
            elif event.key == pygame.K_f:
                frozen = shop_system.toggle_freeze()
                print(f"Shop {'frozen' if frozen else 'unfrozen'}!")
            
            elif event.key == pygame.K_SPACE:
                print("End Turn!")
                turn += 1
                economy.start_new_turn()
                shop_system.refresh()
                print(f"Turn {turn}. Gold: {economy.gold}")
    
    if selected_card and selected_card.in_hand:
        selected_card.x = mouse_pos[0] - selected_card.width // 2
        selected_card.y = mouse_pos[1] - selected_card.height // 2
    
    draw_game_board()
    
    if selected_card and selected_card.in_hand:
        selected_card.draw()
    
    pygame.display.flip()
    clock.tick(60)

pygame.quit()