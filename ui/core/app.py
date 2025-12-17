import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import pygame
import time
import random

pygame.init()

screen = pygame.display.set_mode((800, 700))
pygame.display.set_caption("Hearthstone")
icon = pygame.image.load("./image_add/Screenshot 2025-11-27 151541.png")
pygame.display.set_icon(icon)

simple_font = pygame.font.SysFont('Arial', 24)
title_font = pygame.font.SysFont('Arial', 36)
small_font = pygame.font.SysFont('Arial', 16)

entertainment = pygame.transform.smoothscale(
    pygame.image.load("./image_add/IMG_3857.PNG"), (600, 400)
)
loading_img = pygame.transform.smoothscale(
    pygame.image.load("./image_add/IMG_3858.PNG"), (700, 500)
)
game_bg = pygame.transform.scale(
    pygame.image.load(r"C:\Users\Rayanegostar\Downloads\hearthstone_project\MAZ\image_add\Screenshot 2025-12-16 175133.png"),
    (800, 700)
)

hero_images = {
    "sylvanas": pygame.image.load("./bgknowhow-main/images/heroes/BG23_HERO_306_render_80.webp"),
    "lich_king": pygame.image.load("./bgknowhow-main/images/heroes/TB_BaconShop_HERO_22_render_80.webp"),
    "millhouse": pygame.image.load("./bgknowhow-main/images/heroes/TB_BaconShop_HERO_49_render_80.webp"),
    "yogg_saron": pygame.image.load("./bgknowhow-main/images/heroes/TB_BaconShop_HERO_35_render_80.webp")
}

SHOP_X, SHOP_Y, SHOP_W, SHOP_H, SHOP_GAP = 50, 50, 80, 100, 100
HAND_X, HAND_Y, HAND_W, HAND_H, HAND_GAP = 50, 500, 60, 90, 70
BOARD_X, BOARD_Y, BOARD_W, BOARD_H, BOARD_GAP = 50, 250, 80, 100, 100

END_TURN_RECT = pygame.Rect(650, 600, 120, 50)
UPGRADE_BTN_RECT = pygame.Rect(650, 400, 120, 50)
REFRESH_BTN_RECT = pygame.Rect(650, 470, 120, 50)

show_loading = True
show_second_loading = False
show_hero_selection = False
time_start_loading = 0
selected_hero = None
hero_rects = {}
running = True
game_over = False
current_turn = 1
is_discover_active = False
discover_options = []
selected_discover = -1
dragging_card = None
drag_offset_x, drag_offset_y = 0, 0
is_combat_phase = False
combat_log = []
combat_results = []
show_combat_log = False

class DeterministicRNG:
    def __init__(self, seed):
        self.seed = seed
        self.state = seed & 0xFFFFFFFFFFFFFFFF
        
    def next(self):
        self.state = (self.state * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        return self.state
        
    def randint(self, min_val, max_val):
        rand_val = self.next()
        return min_val + (rand_val % (max_val - min_val + 1))
        
    def choice(self, seq):
        if not seq:
            return None
        idx = self.randint(0, len(seq) - 1)
        return seq[idx]

class Minion:
    def __init__(self, name, tier, attack, health, battlecry=None, is_golden=False):
        self.name = name
        self.tier = tier
        self.attack = attack
        self.health = health
        self.battlecry = battlecry
        self.is_golden = is_golden
        self.count_in_collection = 0
        self.position = None
        self.is_frozen = False
        self.has_divine_shield = False
        self.has_taunt = False
        self.has_poison = False
        self.is_reborn = False
        
    def apply_golden_bonus(self):
        self.attack *= 2
        self.health *= 2
        self.is_golden = True
        return self
        
    def execute_battlecry(self, player_state):
        if self.battlecry:
            self.battlecry(player_state)
            return f"Battlecry of {self.name} activated!"
        return None
        
    def draw(self, screen, x, y, width, height, is_shop=False):
        color = (255, 215, 0) if self.is_golden else (120, 50, 50) if is_shop else (80, 80, 80)
        pygame.draw.rect(screen, color, (x, y, width, height), 0, 10)
        
        if self.is_golden:
            pygame.draw.rect(screen, (255, 215, 0), (x, y, width, height), 3, 10)
        
        name_color = (255, 215, 0) if self.is_golden else (255, 255, 255)
        name_text = small_font.render(self.name, True, name_color)
        screen.blit(name_text, (x + 5, y + 5))
        
        stats_color = (0, 255, 0) if self.is_golden else (255, 200, 200)
        stats_text = small_font.render(f"{self.attack}/{self.health}", True, stats_color)
        screen.blit(stats_text, (x + 5, y + height - 20))
        
        tier_text = small_font.render(f"T{self.tier}", True, (200, 200, 255))
        screen.blit(tier_text, (x + width - 20, y + 5))
        
        if self.has_divine_shield:
            shield_text = small_font.render("D", True, (100, 200, 255))
            screen.blit(shield_text, (x + width - 35, y + 5))
        
        if is_shop and self.is_frozen:
            freeze_text = small_font.render("FROZEN", True, (100, 200, 255))
            screen.blit(freeze_text, (x + 5, y + height - 40))

class CombatMinion:
    def __init__(self, base_minion, position, is_player1=True):
        self.name = base_minion.name
        self.base = base_minion
        self.attack = base_minion.attack
        self.health = base_minion.health
        self.position = position
        self.has_divine_shield = base_minion.has_divine_shield
        self.has_taunt = base_minion.has_taunt
        self.has_poison = base_minion.has_poison
        self.is_reborn = base_minion.is_reborn
        self.is_alive = True
        self.has_attacked = False
        self.is_player1 = is_player1
        self.tier = base_minion.tier
        
    def take_damage(self, damage):
        if self.has_divine_shield:
            self.has_divine_shield = False
            return False
            
        self.health -= damage
        return self.health <= 0
        
    def attack_target(self, target):
        if not self.is_alive or not target.is_alive:
            return False, False
            
        target_died = target.take_damage(self.attack)
        
        attacker_died = False
        if target.is_alive:
            attacker_died = self.take_damage(target.attack)
            
        self.has_attacked = True
        return target_died, attacker_died

class CombatSystem:
    def __init__(self, seed, player1_board, player2_board):
        self.seed = seed
        self.rng = DeterministicRNG(seed)
        self.combat_log = []
        self.round = 0
        
        self.player1_minions = []
        self.player2_minions = []
        
        for i, minion in enumerate(player1_board):
            combat_minion = CombatMinion(minion, i, True)
            self.player1_minions.append(combat_minion)
            
        for i, minion in enumerate(player2_board):
            combat_minion = CombatMinion(minion, i, False)
            self.player2_minions.append(combat_minion)
            
        self.determine_first_attacker()
        
    def determine_first_attacker(self):
        if len(self.player1_minions) > len(self.player2_minions):
            self.current_attacker = 1
            self.combat_log.append("Player 1 attacks first (more minions)")
        elif len(self.player2_minions) > len(self.player1_minions):
            self.current_attacker = 2
            self.combat_log.append("Player 2 attacks first (more minions)")
        else:
            self.current_attacker = self.rng.choice([1, 2])
            self.combat_log.append(f"Player {self.current_attacker} attacks first (random)")
            
    def get_attacker_minions(self):
        return self.player1_minions if self.current_attacker == 1 else self.player2_minions
        
    def get_defender_minions(self):
        return self.player2_minions if self.current_attacker == 1 else self.player1_minions
        
    def get_next_attacker(self):
        attackers = self.get_attacker_minions()
        alive_attackers = [m for m in attackers if m.is_alive and not m.has_attacked]
        
        if not alive_attackers:
            for m in attackers:
                if m.is_alive:
                    m.has_attacked = False
            alive_attackers = [m for m in attackers if m.is_alive]
            
        if not alive_attackers:
            return None
            
        return min(alive_attackers, key=lambda m: m.position)
        
    def get_random_defender(self):
        defenders = self.get_defender_minions()
        alive_defenders = [m for m in defenders if m.is_alive]
        
        if not alive_defenders:
            return None
            
        return self.rng.choice(alive_defenders)
        
    def cleanup_dead_minions(self):
        self.player1_minions = [m for m in self.player1_minions if m.is_alive]
        self.player2_minions = [m for m in self.player2_minions if m.is_alive]
        
        for i, minion in enumerate(self.player1_minions):
            minion.position = i
        for i, minion in enumerate(self.player2_minions):
            minion.position = i
            
    def execute_combat_round(self):
        attacker = self.get_next_attacker()
        if not attacker:
            return False
            
        defender = self.get_random_defender()
        if not defender:
            return False
            
        attacker_name = f"P1[{attacker.position}]" if attacker.is_player1 else f"P2[{attacker.position}]"
        defender_name = f"P1[{defender.position}]" if defender.is_player1 else f"P2[{defender.position}]"
        
        self.combat_log.append(f"Round {self.round}: {attacker_name} {attacker.name} attacks {defender_name} {defender.name}")
        
        if attacker.has_divine_shield:
            self.combat_log.append(f"  {attacker.name} has Divine Shield")
        if defender.has_divine_shield:
            self.combat_log.append(f"  {defender.name} has Divine Shield")
            
        target_died, attacker_died = attacker.attack_target(defender)
        
        if attacker.has_divine_shield and not attacker.has_divine_shield:
            self.combat_log.append(f"  {attacker.name}'s Divine Shield breaks!")
        if defender.has_divine_shield and not defender.has_divine_shield:
            self.combat_log.append(f"  {defender.name}'s Divine Shield breaks!")
            
        if target_died:
            self.combat_log.append(f"  {defender.name} dies!")
        if attacker_died:
            self.combat_log.append(f"  {attacker.name} dies!")
            
        self.cleanup_dead_minions()
        
        self.current_attacker = 3 - self.current_attacker
        
        return True
        
    def run_combat(self):
        self.combat_log = ["=== COMBAT START ==="]
        self.combat_log.append(f"Combat Seed: {self.seed}")
        self.combat_log.append(f"Player 1: {len(self.player1_minions)} minions")
        self.combat_log.append(f"Player 2: {len(self.player2_minions)} minions")
        
        max_rounds = 100
        for round_num in range(max_rounds):
            self.round = round_num + 1
            
            player1_alive = any(m.is_alive for m in self.player1_minions)
            player2_alive = any(m.is_alive for m in self.player2_minions)
            
            if not player1_alive or not player2_alive:
                break
                
            if not self.execute_combat_round():
                break
                
        return self.get_combat_result()
        
    def get_combat_result(self):
        player1_alive = any(m.is_alive for m in self.player1_minions)
        player2_alive = any(m.is_alive for m in self.player2_minions)
        
        if player1_alive and not player2_alive:
            winner = 1
            loser = 2
        elif player2_alive and not player1_alive:
            winner = 2
            loser = 1
        else:
            self.combat_log.append("\nCombat ended in a draw!")
            return {
                "draw": True,
                "damage": 0,
                "winner": None,
                "loser": None,
                "log": self.combat_log
            }
            
        if winner == 1:
            damage = sum(m.tier for m in self.player1_minions if m.is_alive)
        else:
            damage = sum(m.tier for m in self.player2_minions if m.is_alive)
            
        self.combat_log.append(f"\nPlayer {winner} wins!")
        self.combat_log.append(f"Player {loser} takes {damage} damage")
        
        return {
            "draw": False,
            "damage": damage,
            "winner": winner,
            "loser": loser,
            "log": self.combat_log
        }

class MultiplayerCombatManager:
    def __init__(self):
        self.players = []
        self.current_turn = 1
        self.combat_results = []
        
    def add_player(self, name, board, hp=30):
        player = {
            "id": len(self.players) + 1,
            "name": name,
            "board": board,
            "hp": hp,
            "wins": 0,
            "losses": 0
        }
        self.players.append(player)
        
    def start_simultaneous_combats(self):
        if len(self.players) < 4:
            if len(self.players) >= 2:
                self.run_single_combat(0, 1)
            return
            
        self.run_single_combat(0, 3)
        
        self.run_single_combat(1, 2)
        
        self.current_turn += 1
        
    def run_single_combat(self, idx1, idx2):
        if idx1 >= len(self.players) or idx2 >= len(self.players):
            return
            
        p1 = self.players[idx1]
        p2 = self.players[idx2]
        
        seed = (p1["id"] * 1000 + p2["id"]) * 100 + self.current_turn
        
        combat = CombatSystem(seed, p1["board"], p2["board"])
        result = combat.run_combat()
        
        result["player1"] = p1["id"]
        result["player2"] = p2["id"]
        self.combat_results.append(result)
        
        if not result["draw"]:
            loser_id = result["loser"]
            loser = p1 if loser_id == 1 else p2
            
            self.players[idx1 if loser_id == 1 else idx2]["hp"] -= result["damage"]
            
            if result["winner"] == 1:
                self.players[idx1]["wins"] += 1
                self.players[idx2]["losses"] += 1
            else:
                self.players[idx2]["wins"] += 1
                self.players[idx1]["losses"] += 1
                
        self.players = [p for p in self.players if p["hp"] > 0]
        
    def get_leaderboard(self):
        return sorted(self.players, key=lambda p: (-p["hp"], -p["wins"]))

class Economy:
    def __init__(self):
        self.gold = 3
        self.max_gold = 10
        self.turn = 1
        self.tavern_tier = 1
        self.upgrade_cost_base = 5
        self.refresh_cost = 1
        self.minion_cost_base = 3
        
    def start_new_turn(self):
        self.turn += 1
        if self.turn <= 3:
            gold_gain = self.turn
        else:
            gold_gain = 3
        
        old_gold = self.gold
        self.gold = min(self.max_gold, self.gold + gold_gain)
        
        if old_gold == self.max_gold:
            return "Gold is full! Use your gold!"
        return f"Turn {self.turn}: Gained {gold_gain} gold"
    
    def can_buy(self):
        return self.gold >= self.minion_cost_base
        
    def buy_minion(self):
        if self.can_buy():
            self.gold -= self.minion_cost_base
            return True
        return False
        
    def sell_minion(self):
        self.gold += 1
        self.gold = min(self.gold, self.max_gold)
        
    def can_refresh(self):
        return self.gold >= self.refresh_cost
        
    def refresh_shop(self):
        if self.can_refresh():
            self.gold -= self.refresh_cost
            return True
        return False
        
    def can_upgrade(self):
        return self.gold >= self.upgrade_cost_base and self.tavern_tier < 6
        
    def upgrade_tavern(self):
        if self.can_upgrade():
            self.gold -= self.upgrade_cost_base
            self.tavern_tier += 1
            self.upgrade_cost_base = self.get_upgrade_cost_for_tier(self.tavern_tier)
            return True
        return False
        
    def get_upgrade_cost_for_tier(self, tier):
        costs = {1: 5, 2: 7, 3: 8, 4: 9, 5: 10, 6: 0}
        return costs.get(tier, 0)

class ShopSystem:
    def __init__(self, economy):
        self.economy = economy
        self.shop_slots = []
        self.frozen_slots = []
        self.refresh_shop()
        
    def refresh_shop(self):
        self.shop_slots = []
        slots_count = 3 if self.economy.tavern_tier == 1 else 4
        
        for _ in range(slots_count):
            tier = self.economy.tavern_tier
            tier_weights = self.get_tier_weights(tier)
            selected_tier = random.choices(
                list(tier_weights.keys()), 
                weights=list(tier_weights.values())
            )[0]
            
            minion = self.generate_minion(selected_tier)
            self.shop_slots.append(minion)
    
    def get_tier_weights(self, current_tier):
        weights = {
            1: {1: 100, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0},
            2: {1: 70, 2: 30, 3: 0, 4: 0, 5: 0, 6: 0},
            3: {1: 55, 2: 33, 3: 12, 4: 0, 5: 0, 6: 0},
            4: {1: 45, 2: 35, 3: 20, 4: 0, 5: 0, 6: 0}
        }
        return weights.get(current_tier, {current_tier: 100})
    
    def generate_minion(self, tier):
        minions_by_tier = {
            1: [
                Minion("Alleycat", 1, 1, 1),
                Minion("Murloc Tidehunter", 1, 2, 1),
                Minion("Rockpool Hunter", 1, 2, 3),
                Minion("Selfless Hero", 1, 2, 1)
            ],
            2: [
                Minion("Glyph Guardian", 2, 2, 4),
                Minion("Kaboom Bot", 2, 2, 2),
                Minion("Murloc Warleader", 2, 3, 3),
                Minion("Old Murk-Eye", 2, 2, 4)
            ],
            3: [
                Minion("Crackling Cyclone", 3, 4, 4),
                Minion("Floating Watcher", 3, 4, 4),
                Minion("Houndmaster", 3, 4, 3),
                Minion("Imp Gang Boss", 3, 2, 4)
            ]
        }
        
        tier_minions = minions_by_tier.get(tier, [Minion("Unknown", tier, 1, 1)])
        minion = random.choice(tier_minions)
        minion.count_in_collection = 1
        return minion
    
    def buy_minion(self, slot_index):
        if 0 <= slot_index < len(self.shop_slots):
            minion = self.shop_slots[slot_index]
            if minion and self.economy.buy_minion():
                self.shop_slots[slot_index] = None
                return minion
        return None
    
    def toggle_freeze(self, slot_index):
        if 0 <= slot_index < len(self.shop_slots):
            minion = self.shop_slots[slot_index]
            if minion:
                minion.is_frozen = not minion.is_frozen
                return minion.is_frozen
        return False

class GoldenSystem:
    def __init__(self):
        self.minion_collection = {}
        self.discover_active = False
        self.discover_options = []
        
    def add_minion_to_collection(self, minion):
        if minion.name not in self.minion_collection:
            self.minion_collection[minion.name] = []
        
        self.minion_collection[minion.name].append(minion)
        
        if len(self.minion_collection[minion.name]) == 3:
            return self.create_golden(minion.name)
        return None
    
    def create_golden(self, minion_name):
        if minion_name in self.minion_collection and len(self.minion_collection[minion_name]) >= 2:
            normal1 = self.minion_collection[minion_name].pop(0)
            normal2 = self.minion_collection[minion_name].pop(0)
            
            golden_minion = Minion(
                minion_name,
                normal1.tier,
                normal1.attack,
                normal1.health,
                normal1.battlecry,
                True
            )
            golden_minion.apply_golden_bonus()
            
            self.minion_collection[minion_name].append(golden_minion)
            
            self.discover_active = True
            self.discover_options = self.generate_discover_options(golden_minion.tier)
            
            return golden_minion
        return None
    
    def generate_discover_options(self, tier):
        options = []
        minion_pool = self.get_discover_minions(tier)
        
        for _ in range(3):
            if minion_pool:
                minion = random.choice(minion_pool)
                options.append(minion)
                minion_pool.remove(minion)
        
        return options
    
    def get_discover_minions(self, tier):
        discover_minions = []
        
        for i in range(3):
            discover_minions.append(Minion(
                f"Discover Minion {i+1}",
                tier,
                random.randint(2, 5),
                random.randint(2, 5)
            ))
        
        return discover_minions

class DragDropSystem:
    def __init__(self):
        self.dragging = False
        self.drag_card = None
        self.drag_source = None
        self.drag_source_index = -1
        self.drag_offset = (0, 0)
        self.drop_target = None
        self.drop_target_type = None
        
    def start_drag(self, card, source, index, mouse_pos, card_rect):
        self.dragging = True
        self.drag_card = card
        self.drag_source = source
        self.drag_source_index = index
        self.drag_offset = (mouse_pos[0] - card_rect.x, mouse_pos[1] - card_rect.y)
        
    def update_drag(self, mouse_pos):
        if self.dragging and self.drag_card:
            self.drag_card.position = (
                mouse_pos[0] - self.drag_offset[0],
                mouse_pos[1] - self.drag_offset[1]
            )
            
    def stop_drag(self, mouse_pos, player_state, shop_system):
        if not self.dragging:
            return
        
        target_info = self.get_drop_target(mouse_pos)
        
        if target_info:
            target_type, target_index = target_info
            
            event_data = {
                "source": self.drag_source,
                "source_index": self.drag_source_index,
                "target": target_type,
                "target_index": target_index,
                "action": "DRAG_DROP"
            }
            print(f"EventBus Message: {event_data}")
            
            if self.drag_source == 'shop' and target_type == 'hand':
                if shop_system and player_state["gold"] >= 3:
                    bought_minion = shop_system.buy_minion(self.drag_source_index)
                    if bought_minion:
                        player_state["hand"].append(bought_minion)
                        player_state["gold"] -= 3
                        
            elif self.drag_source == 'hand' and target_type == 'board':
                if len(player_state["board"]) < 7 and self.drag_source_index < len(player_state["hand"]):
                    card = player_state["hand"].pop(self.drag_source_index)
                    player_state["board"].append(card)
                    
                    if hasattr(card, 'battlecry') and card.battlecry:
                        card.execute_battlecry(player_state)
                        
            elif self.drag_source == 'board' and target_type == 'hand':
                if self.drag_source_index < len(player_state["board"]):
                    player_state["board"].pop(self.drag_source_index)
                    player_state["gold"] = min(10, player_state["gold"] + 1)
        
        self.reset_drag()
    
    def get_drop_target(self, mouse_pos):
        for i in range(7):
            rect = pygame.Rect(BOARD_X + i*BOARD_GAP, BOARD_Y, BOARD_W, BOARD_H)
            if rect.collidepoint(mouse_pos):
                return ('board', i)
        
        for i in range(10):
            rect = pygame.Rect(HAND_X + i*HAND_GAP, HAND_Y, HAND_W, HAND_H)
            if rect.collidepoint(mouse_pos):
                return ('hand', i)
        
        return None
    
    def reset_drag(self):
        self.dragging = False
        self.drag_card = None
        self.drag_source = None
        self.drag_source_index = -1
        self.drag_offset = (0, 0)
        
    def draw_dragging_card(self, screen):
        if self.dragging and self.drag_card:
            x, y = self.drag_card.position if self.drag_card.position else pygame.mouse.get_pos()
            self.drag_card.draw(screen, x, y, SHOP_W, SHOP_H)

economy = Economy()
shop_system = ShopSystem(economy)
golden_system = GoldenSystem()
drag_drop = DragDropSystem()
combat_manager = MultiplayerCombatManager()

player_state = {
    "gold": economy.gold,
    "hp": 30,
    "board": [],
    "hand": [],
    "hero": None,
    "tavern_tier": 1
}

combat_state = {
    "is_active": False,
    "current_combat": None,
    "log": [],
    "results": []
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

def draw_combat_log_screen():
    overlay = pygame.Surface((800, 700), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 220))
    screen.blit(overlay, (0, 0))
    
    title = title_font.render("COMBAT LOG", True, (255, 50, 50))
    screen.blit(title, (400 - title.get_width() // 2, 50))
    
    y_offset = 100
    for line in combat_log[-20:]:
        log_text = small_font.render(line, True, (220, 220, 180))
        screen.blit(log_text, (50, y_offset))
        y_offset += 25
        
        if y_offset > 650:
            break
    
    close_rect = pygame.Rect(350, 650, 100, 40)
    pygame.draw.rect(screen, (180, 50, 50), close_rect, 0, 5)
    close_text = simple_font.render("Close", True, (255, 255, 255))
    screen.blit(close_text, (400 - close_text.get_width() // 2, 665))
    
    return close_rect

def draw_game_board():
    screen.blit(game_bg, (0, 0))
    
    for i, minion in enumerate(shop_system.shop_slots):
        rect = pygame.Rect(SHOP_X + i*SHOP_GAP, SHOP_Y, SHOP_W, SHOP_H)
        
        if minion:
            minion.draw(screen, rect.x, rect.y, rect.width, rect.height, is_shop=True)
            
            freeze_rect = pygame.Rect(rect.x + rect.width - 25, rect.y + 5, 20, 20)
            freeze_color = (100, 200, 255) if minion.is_frozen else (200, 200, 200)
            pygame.draw.rect(screen, freeze_color, freeze_rect, 0, 3)
            
            freeze_text = small_font.render("F", True, (0, 0, 0))
            screen.blit(freeze_text, (freeze_rect.x + 6, freeze_rect.y + 3))
        else:
            pygame.draw.rect(screen, (60, 30, 30), rect, 0, 10)
            empty_text = small_font.render("Empty", True, (150, 150, 150))
            screen.blit(empty_text, (rect.x + 10, rect.y + 40))
    
    for i, card in enumerate(player_state["board"]):
        rect = pygame.Rect(BOARD_X + i*BOARD_GAP, BOARD_Y, BOARD_W, BOARD_H)
        if isinstance(card, Minion):
            card.draw(screen, rect.x, rect.y, rect.width, rect.height)
        else:
            pygame.draw.rect(screen, (50, 50, 50), rect, 0, 10)
    
    for i, card in enumerate(player_state["hand"]):
        rect = pygame.Rect(HAND_X + i*HAND_GAP, HAND_Y, HAND_W, HAND_H)
        if isinstance(card, Minion):
            card.draw(screen, rect.x, rect.y, rect.width, rect.height)
        else:
            pygame.draw.rect(screen, (80, 80, 80), rect, 0, 10)
    
    gold_text = simple_font.render(f"Gold: {player_state['gold']}/{economy.max_gold}", True, (255, 255, 0))
    hp_text = simple_font.render(f"HP: {player_state['hp']}", True, (255, 80, 80))
    turn_text = simple_font.render(f"Turn: {economy.turn}", True, (200, 200, 255))
    tier_text = simple_font.render(f"Tavern Tier: {economy.tavern_tier}", True, (150, 255, 150))
    
    screen.blit(gold_text, (650, 10))
    screen.blit(hp_text, (650, 40))
    screen.blit(turn_text, (650, 70))
    screen.blit(tier_text, (650, 100))
    
    pygame.draw.rect(screen, (180, 50, 50), END_TURN_RECT, 0, 10)
    end_text = simple_font.render("End Turn", True, (255, 255, 255))
    screen.blit(end_text, (END_TURN_RECT.x + 20, END_TURN_RECT.y + 15))
    
    upgrade_color = (50, 180, 50) if economy.can_upgrade() else (100, 100, 100)
    pygame.draw.rect(screen, upgrade_color, UPGRADE_BTN_RECT, 0, 10)
    upgrade_cost = economy.get_upgrade_cost_for_tier(economy.tavern_tier)
    upgrade_text = simple_font.render(f"Upgrade ({upgrade_cost})", True, (255, 255, 255))
    screen.blit(upgrade_text, (UPGRADE_BTN_RECT.x + 10, UPGRADE_BTN_RECT.y + 15))
    
    refresh_color = (50, 100, 200) if economy.can_refresh() else (100, 100, 100)
    pygame.draw.rect(screen, refresh_color, REFRESH_BTN_RECT, 0, 10)
    refresh_text = simple_font.render(f"Refresh ({economy.refresh_cost})", True, (255, 255, 255))
    screen.blit(refresh_text, (REFRESH_BTN_RECT.x + 15, REFRESH_BTN_RECT.y + 15))
    
    combat_log_rect = pygame.Rect(650, 300, 120, 50)
    pygame.draw.rect(screen, (100, 100, 200), combat_log_rect, 0, 10)
    combat_log_text = simple_font.render("Combat Log", True, (255, 255, 255))
    screen.blit(combat_log_text, (combat_log_rect.x + 15, combat_log_rect.y + 15))
    
    if selected_hero:
        hero_img = pygame.transform.scale(hero_images[selected_hero], (120, 177))
        screen.blit(hero_img, (316, 520))
    
    drag_drop.draw_dragging_card(screen)
    
    if golden_system.discover_active:
        draw_discover_overlay()
    
    if show_combat_log:
        return draw_combat_log_screen()
    
    return combat_log_rect

def draw_discover_overlay():
    overlay = pygame.Surface((800, 700), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 200))
    screen.blit(overlay, (0, 0))
    
    title = title_font.render("DISCOVER A MINION!", True, (255, 215, 0))
    screen.blit(title, (400 - title.get_width() // 2, 100))
    
    instruction = simple_font.render("Choose one minion to add to your hand", True, (255, 255, 255))
    screen.blit(instruction, (400 - instruction.get_width() // 2, 150))
    
    for i, minion in enumerate(golden_system.discover_options):
        x = 150 + i * 200
        y = 300
        
        minion.draw(screen, x, y, SHOP_W, SHOP_H)
        
        num_text = simple_font.render(str(i+1), True, (255, 255, 255))
        screen.blit(num_text, (x + SHOP_W // 2 - 5, y + SHOP_H + 10))

def draw_game_over():
    screen.fill((0, 0, 0))
    text = title_font.render("GAME OVER", True, (255, 0, 0))
    screen.blit(text, text.get_rect(center=(400, 300)))

def initialize_multiplayer():
    combat_manager.add_player("Player", player_state["board"], player_state["hp"])
    
    for i in range(3):
        bot_board = [Minion(f"Bot{i+1}_Minion{j}", random.randint(1, 3), 
                          random.randint(1, 5), random.randint(1, 5)) 
                    for j in range(random.randint(1, 5))]
        combat_manager.add_player(f"Bot {i+1}", bot_board, 30)

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
                    initialize_multiplayer()

        elif not show_hero_selection and not show_loading and not show_second_loading:
            mouse_pos = pygame.mouse.get_pos()
            
            if golden_system.discover_active:
                if event.type == pygame.KEYDOWN:
                    if event.key in [pygame.K_1, pygame.K_2, pygame.K_3]:
                        choice = event.key - pygame.K_1
                        if choice < len(golden_system.discover_options):
                            selected_minion = golden_system.discover_options[choice]
                            player_state["hand"].append(selected_minion)
                            golden_system.discover_active = False
                            golden_system.discover_options = []
                            print(f"Discover choice: {selected_minion.name}")
                continue
            
            if show_combat_log:
                if event.type == pygame.MOUSEBUTTONDOWN:
                    close_rect = draw_combat_log_screen()
                    if close_rect.collidepoint(mouse_pos):
                        show_combat_log = False
                continue
            
            if event.type == pygame.MOUSEBUTTONDOWN:
                combat_log_rect = pygame.Rect(650, 300, 120, 50)
                if combat_log_rect.collidepoint(mouse_pos):
                    show_combat_log = True
                    continue
                
                for i, minion in enumerate(shop_system.shop_slots):
                    if minion:
                        rect = pygame.Rect(SHOP_X + i*SHOP_GAP, SHOP_Y, SHOP_W, SHOP_H)
                        if rect.collidepoint(mouse_pos):
                            freeze_rect = pygame.Rect(rect.x + rect.width - 25, rect.y + 5, 20, 20)
                            if freeze_rect.collidepoint(mouse_pos):
                                shop_system.toggle_freeze(i)
                            else:
                                drag_drop.start_drag(minion, 'shop', i, mouse_pos, rect)
                            break
                
                for i, card in enumerate(player_state["hand"]):
                    rect = pygame.Rect(HAND_X + i*HAND_GAP, HAND_Y, HAND_W, HAND_H)
                    if rect.collidepoint(mouse_pos):
                        drag_drop.start_drag(card, 'hand', i, mouse_pos, rect)
                        break
                
                for i, card in enumerate(player_state["board"]):
                    rect = pygame.Rect(BOARD_X + i*BOARD_GAP, BOARD_Y, BOARD_W, BOARD_H)
                    if rect.collidepoint(mouse_pos):
                        drag_drop.start_drag(card, 'board', i, mouse_pos, rect)
                        break
                
                if END_TURN_RECT.collidepoint(mouse_pos):
                    combat_log.append(f"=== Turn {economy.turn} Combat ===")
                    
                    combat_manager.players[0]["board"] = player_state["board"].copy()
                    combat_manager.players[0]["hp"] = player_state["hp"]
                    
                    combat_manager.start_simultaneous_combats()
                    
                    if len(combat_manager.players) > 0:
                        player_state["hp"] = combat_manager.players[0]["hp"]
                    
                    for result in combat_manager.combat_results:
                        combat_log.extend(result["log"])
                    
                    message = economy.start_new_turn()
                    player_state["gold"] = economy.gold
                    combat_log.append(message)
                    
                    new_shop = []
                    for minion in shop_system.shop_slots:
                        if minion and minion.is_frozen:
                            new_shop.append(minion)
                        else:
                            new_shop.append(None)
                    
                    shop_system.shop_slots = new_shop
                    shop_system.refresh_shop()
                    
                    for i in range(len(shop_system.shop_slots)):
                        if shop_system.shop_slots[i] is None:
                            shop_system.shop_slots[i] = shop_system.generate_minion(economy.tavern_tier)
                    
                    if player_state["hp"] <= 0:
                        game_over = True
                        combat_log.append("GAME OVER!")
                
                elif UPGRADE_BTN_RECT.collidepoint(mouse_pos) and economy.can_upgrade():
                    if economy.upgrade_tavern():
                        player_state["gold"] = economy.gold
                        player_state["tavern_tier"] = economy.tavern_tier
                        combat_log.append(f"Upgraded to Tavern Tier {economy.tavern_tier}")
                
                elif REFRESH_BTN_RECT.collidepoint(mouse_pos) and economy.can_refresh():
                    if economy.refresh_shop():
                        player_state["gold"] = economy.gold
                        shop_system.refresh_shop()
                        combat_log.append("Shop refreshed")
            
            elif event.type == pygame.MOUSEBUTTONUP:
                drag_drop.stop_drag(mouse_pos, player_state, shop_system)
            
            elif event.type == pygame.MOUSEMOTION:
                drag_drop.update_drag(mouse_pos)

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