import pygame
import sys
import json
import threading
import time
import websocket
import uuid
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple, Any
import asyncio
import queue

# Initialize Pygame
pygame.init()
pygame.font.init()

# Constants
SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 800
FPS = 60

# Colors
BACKGROUND_COLOR = (20, 25, 45)
PANEL_COLOR = (40, 45, 70)
BORDER_COLOR = (80, 85, 120)
HIGHLIGHT_COLOR = (100, 180, 255)
GOLD_COLOR = (255, 215, 0)
HEALTH_COLOR = (220, 50, 50)
TEXT_COLOR = (240, 240, 240)
BUTTON_COLOR = (60, 120, 200)
BUTTON_HOVER_COLOR = (80, 140, 230)
SHOP_SLOT_COLOR = (50, 55, 85)
BOARD_SLOT_COLOR = (45, 50, 75)
HAND_SLOT_COLOR = (55, 60, 95)

# Fonts
TITLE_FONT = pygame.font.Font(None, 48)
HEADER_FONT = pygame.font.Font(None, 32)
NORMAL_FONT = pygame.font.Font(None, 24)
SMALL_FONT = pygame.font.Font(None, 18)
TINY_FONT = pygame.font.Font(None, 14)

# Game constants from server
MAX_BOARD_SIZE = 7
MAX_HAND_SIZE = 10
SHOP_SIZE = 5
START_GOLD = 3
START_HEALTH = 40

class GamePhase(Enum):
    LOBBY = "LOBBY"
    HERO_SELECT = "HERO_SELECT"
    RECRUIT = "RECRUIT"
    COMBAT_CALC = "COMBAT_CALC"
    LOG_REPLAY = "LOG_REPLAY"
    GAME_OVER = "GAME_OVER"

class HeroType(Enum):
    SYLVANAS = 0
    LICH_KING = 1
    MILLHOUSE = 2
    YOGG = 3
    PATCHES = 4
    RAGNAROS = 5
    KELTHUZAD = 6
    MALGANIS = 7

    @staticmethod
    def from_int(value: int) -> 'HeroType':
        for hero in HeroType:
            if hero.value == value:
                return hero
        return HeroType.SYLVANAS

@dataclass
class MinionData:
    minion_id: str
    original_id: str
    name: str
    attack: int
    health: int
    tier: int
    abilities: List[str]
    instance_id: str
    player_index: int
    golden: bool
    tribe: str = "NEUTRAL"
    divine_shield: bool = False
    reborn: bool = False
    taunt: bool = False
    windfury: bool = False
    poisonous: bool = False
    
    @classmethod
    def from_json(cls, data: dict) -> 'MinionData':
        abilities = data.get("abilities", [])
        return cls(
            minion_id=data.get("minion_id", ""),
            original_id=data.get("original_id", ""),
            name=data.get("name", "Unknown"),
            attack=data.get("attack", 0),
            health=data.get("health", 0),
            tier=data.get("tier", 1),
            abilities=abilities,
            instance_id=data.get("instance_id", ""),
            player_index=data.get("player_index", -1),
            golden=data.get("golden", False),
            tribe=data.get("tribe", "NEUTRAL"),
            divine_shield="DIVINE_SHIELD" in abilities,
            reborn="REBORN" in abilities,
            taunt="TAUNT" in abilities,
            windfury="WINDFURY" in abilities,
            poisonous="POISONOUS" in abilities
        )

@dataclass
class HeroData:
    type: HeroType
    name: str
    power_cost: int
    power_description: str
    power_used: bool
    passive: bool
    
    @classmethod
    def from_json(cls, data: dict) -> 'HeroData':
        return cls(
            type=HeroType.from_int(data.get("type", 0)),
            name=data.get("name", "Unknown"),
            power_cost=data.get("power_cost", 0),
            power_description=data.get("power_description", ""),
            power_used=data.get("power_used", False),
            passive=data.get("passive", False)
        )

@dataclass
class PlayerData:
    token: str
    name: str
    gold: int
    health: int
    tavern_tier: int
    hero: Optional[HeroData]
    board: List[MinionData]
    hand: List[MinionData]
    shop: List[Optional[MinionData]]
    shop_frozen: bool
    upgrade_cost: int
    is_ready: bool
    is_zombie: bool
    player_index: int
    wins: int
    losses: int
    
    @classmethod
    def from_json(cls, data: dict) -> 'PlayerData':
        hero_data = data.get("hero")
        hero = HeroData.from_json(hero_data) if hero_data else None
        
        board = [MinionData.from_json(m) for m in data.get("board", [])]
        hand = [MinionData.from_json(m) for m in data.get("hand", [])]
        
        shop_data = data.get("shop", {}).get("slots", [])
        shop = []
        for slot in shop_data:
            if slot is None:
                shop.append(None)
            else:
                shop.append(MinionData.from_json(slot))
        
        return cls(
            token=data.get("token", ""),
            name=data.get("name", "Player"),
            gold=data.get("gold", START_GOLD),
            health=data.get("health", START_HEALTH),
            tavern_tier=data.get("tavern_tier", 1),
            hero=hero,
            board=board,
            hand=hand,
            shop=shop,
            shop_frozen=data.get("shop", {}).get("frozen", False),
            upgrade_cost=data.get("shop", {}).get("upgrade_cost", 5),
            is_ready=data.get("is_ready", False),
            is_zombie=data.get("is_zombie", False),
            player_index=data.get("player_index", 0),
            wins=data.get("wins", 0),
            losses=data.get("losses", 0)
        )

class WebSocketClient:
    def __init__(self, server_url: str, token: str, name: str):
        self.server_url = server_url
        self.token = token
        self.name = name
        self.ws = None
        self.connected = False
        self.message_queue = queue.Queue()
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        
    def connect(self):
        try:
            self.ws = websocket.WebSocket()
            self.ws.connect(self.server_url)
            self.connected = True
            self.reconnect_attempts = 0
            
            # Send join message
            join_message = {
                "type": "JOIN",
                "token": self.token,
                "name": self.name
            }
            self.send(join_message)
            
            # Start receive thread
            self.receive_thread = threading.Thread(target=self._receive_messages, daemon=True)
            self.receive_thread.start()
            
            print(f"Connected to server as {self.name}")
            return True
            
        except Exception as e:
            print(f"Connection error: {e}")
            return False
    
    def reconnect(self):
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            return False
        
        self.reconnect_attempts += 1
        print(f"Reconnecting... Attempt {self.reconnect_attempts}")
        time.sleep(2 ** self.reconnect_attempts)  # Exponential backoff
        
        try:
            self.ws = websocket.WebSocket()
            self.ws.connect(self.server_url)
            
            reconnect_message = {
                "type": "RECONNECT",
                "token": self.token,
                "name": self.name
            }
            self.send(reconnect_message)
            
            self.connected = True
            print("Reconnected successfully")
            return True
            
        except Exception as e:
            print(f"Reconnect failed: {e}")
            return False
    
    def _receive_messages(self):
        while self.connected:
            try:
                message = self.ws.recv()
                if message:
                    data = json.loads(message)
                    self.message_queue.put(data)
            except websocket.WebSocketConnectionClosedException:
                print("WebSocket connection closed")
                self.connected = False
                break
            except Exception as e:
                print(f"Error receiving message: {e}")
                self.connected = False
                break
    
    def send(self, data: dict):
        if self.connected and self.ws:
            try:
                self.ws.send(json.dumps(data))
                return True
            except Exception as e:
                print(f"Error sending message: {e}")
                self.connected = False
                return False
        return False
    
    def get_message(self):
        try:
            return self.message_queue.get_nowait()
        except queue.Empty:
            return None
    
    def close(self):
        self.connected = False
        if self.ws:
            self.ws.close()

class GameClient:
    def __init__(self, server_url: str, player_name: str):
        self.server_url = server_url
        self.player_name = player_name
        self.token = str(uuid.uuid4())
        
        self.ws_client = WebSocketClient(server_url, self.token, player_name)
        self.game_state = None
        self.current_phase = GamePhase.LOBBY
        self.selected_minion = None
        self.dragging_minion = None
        self.drag_offset = (0, 0)
        self.hovered_slot = None
        self.hovered_button = None
        self.hero_offer = []
        self.selected_hero = None
        self.combat_log = []
        self.game_over_data = None
        
        # UI elements
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption(f"Hearthstone Battlegrounds - {player_name}")
        
        # Load images
        self.load_images()
        
        # Timer
        self.phase_timer = 0
        self.last_update = time.time()
        
        # Game state
        self.player_data = None
        self.opponents = []
        
        # Initialize
        self.connect_to_server()
    
    def load_images(self):
        """Load game images"""
        try:
            # Load hero images
            self.hero_images = {}
            hero_files = {
                HeroType.SYLVANAS: "../bgknowhow-main/images/heroes/BG23_HERO_306_render_80.webp",
                HeroType.LICH_KING: "../bgknowhow-main/images/heroes/TB_BaconShop_HERO_22_render_80.webp",
                HeroType.MILLHOUSE: "../bgknowhow-main/images/heroes/TB_BaconShop_HERO_49_render_80.webp",
                HeroType.YOGG: "../bgknowhow-main/images/heroes/TB_BaconShop_HERO_35_render_80.webp",
                HeroType.PATCHES: "../bgknowhow-main/images/heroes/BG26_HERO_102_render_80.webp",
                HeroType.RAGNAROS: "../bgknowhow-main/images/heroes/BG26_HERO_103_render_80.webp",
                HeroType.KELTHUZAD: "../bgknowhow-main/images/heroes/BG26_HERO_104_render_80.webp",
                HeroType.MALGANIS: "../bgknowhow-main/images/heroes/BG26_HERO_105_render_80.webp"
            }
            
            for hero_type, filepath in hero_files.items():
                try:
                    image = pygame.image.load(filepath)
                    self.hero_images[hero_type] = pygame.transform.scale(image, (100, 140))
                except:
                    # Create placeholder if image not found
                    surface = pygame.Surface((100, 140))
                    surface.fill((100, 100, 150))
                    pygame.draw.rect(surface, (200, 200, 200), (0, 0, 100, 140), 2)
                    self.hero_images[hero_type] = surface
            
            # Load minion images (placeholder - you should load actual images)
            self.minion_images = {}
            
            # Load icons
            self.icons = {
                "taunt": self.create_icon("T", (100, 200, 100)),
                "divine_shield": self.create_icon("D", (200, 200, 100)),
                "reborn": self.create_icon("R", (150, 100, 200)),
                "windfury": self.create_icon("W", (100, 150, 200)),
                "poisonous": self.create_icon("P", (150, 50, 50)),
                "deathrattle": self.create_icon("DR", (200, 150, 50)),
                "battlecry": self.create_icon("BC", (50, 150, 200)),
                "aura": self.create_icon("A", (200, 100, 150))
            }
            
            # Load background
            try:
                self.background = pygame.image.load("./image_add/Screenshot 2025-12-16 175133.png")
                self.background = pygame.transform.scale(self.background, (SCREEN_WIDTH, SCREEN_HEIGHT))
            except:
                self.background = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
                self.background.fill(BACKGROUND_COLOR)
                
        except Exception as e:
            print(f"Error loading images: {e}")
    
    def create_icon(self, text, color):
        """Create a simple icon for abilities"""
        surface = pygame.Surface((20, 20), pygame.SRCALPHA)
        pygame.draw.circle(surface, color, (10, 10), 9)
        pygame.draw.circle(surface, (255, 255, 255), (10, 10), 9, 1)
        
        font = pygame.font.Font(None, 14)
        text_surf = font.render(text, True, (255, 255, 255))
        text_rect = text_surf.get_rect(center=(10, 10))
        surface.blit(text_surf, text_rect)
        
        return surface
    
    def connect_to_server(self):
        """Connect to the game server"""
        if self.ws_client.connect():
            print(f"Connected to server as {self.player_name}")
            return True
        else:
            print("Failed to connect to server")
            return False
    
    def handle_message(self, message):
        """Handle incoming WebSocket messages"""
        msg_type = message.get("type")
        
        if msg_type == "WELCOME":
            print("Connected to game server")
            
        elif msg_type == "JOIN_SUCCESS":
            print(f"Joined successfully as {self.player_name}")
            
        elif msg_type == "PLAYER_JOINED":
            player_name = message.get("name")
            player_count = message.get("player_count")
            print(f"{player_name} joined the game ({player_count}/4)")
            
        elif msg_type == "PLAYER_READY":
            player_name = message.get("name")
            ready = message.get("ready")
            status = "ready" if ready else "not ready"
            print(f"{player_name} is {status}")
            
        elif msg_type == "HERO_OFFER":
            self.hero_offer = [HeroType.from_int(h) for h in message.get("heroes", [])]
            self.current_phase = GamePhase.HERO_SELECT
            self.phase_timer = message.get("time", 15)
            print("Hero selection started")
            
        elif msg_type == "HERO_SELECTED":
            hero_type = HeroType.from_int(message.get("hero"))
            print(f"Hero selected: {hero_type.name}")
            
        elif msg_type == "PLAYER_HERO_SELECTED":
            player_name = message.get("name")
            hero_type = HeroType.from_int(message.get("hero"))
            print(f"{player_name} selected {hero_type.name}")
            
        elif msg_type == "FULL_STATE":
            self.update_game_state(message.get("data", {}))
            
        elif msg_type == "PHASE_CHANGE":
            phase = message.get("phase")
            self.current_phase = GamePhase(phase)
            self.phase_timer = message.get("time", 30)
            print(f"Phase changed to: {phase}")
            
        elif msg_type == "BUY_SUCCESS":
            print("Minion bought successfully")
            
        elif msg_type == "SELL_SUCCESS":
            print("Minion sold successfully")
            
        elif msg_type == "PLAY_SUCCESS":
            print("Minion played successfully")
            
        elif msg_type == "REFRESH_SUCCESS":
            print("Shop refreshed")
            
        elif msg_type == "UPGRADE_SUCCESS":
            print("Tavern upgraded")
            
        elif msg_type == "FREEZE_SUCCESS":
            frozen = message.get("frozen")
            print(f"Shop {'frozen' if frozen else 'unfrozen'}")
            
        elif msg_type == "TURN_ENDED":
            print("Turn ended")
            
        elif msg_type == "HERO_POWER_USED":
            print("Hero power used")
            
        elif msg_type == "COMBAT_RESULT":
            result = message.get("result")
            if result == "WIN":
                print("You won the combat!")
            elif result == "LOSE":
                print("You lost the combat")
            elif result == "BYE":
                print("No opponent this round")
            
        elif msg_type == "GAME_OVER":
            self.game_over_data = message
            self.current_phase = GamePhase.GAME_OVER
            print("Game Over!")
            
        elif msg_type == "ERROR":
            error_msg = message.get("message", "Unknown error")
            print(f"Error: {error_msg}")
            
        elif msg_type == "GRACE_PERIOD":
            print("Grace period started - finish your actions!")
            
        elif msg_type == "RECONNECT_SUCCESS":
            print("Reconnected successfully")
            self.update_game_state(message.get("full_state", {}))
            
        else:
            print(f"Unknown message type: {msg_type}")
    
    def update_game_state(self, state_data):
        """Update the game state from server data"""
        try:
            # Update phase
            phase_str = state_data.get("phase", "LOBBY")
            self.current_phase = GamePhase(phase_str)
            
            # Update timer
            self.phase_timer = state_data.get("phase_timer", 0)
            
            # Parse players
            players_data = state_data.get("players", [])
            for player_data in players_data:
                player = PlayerData.from_json(player_data)
                
                if player.token == self.token:
                    self.player_data = player
                else:
                    # Update or add opponent
                    found = False
                    for i, opp in enumerate(self.opponents):
                        if opp.token == player.token:
                            self.opponents[i] = player
                            found = True
                            break
                    if not found and not player.is_zombie:
                        self.opponents.append(player)
            
            # Remove disconnected opponents
            self.opponents = [p for p in self.opponents if not p.is_zombie]
            
        except Exception as e:
            print(f"Error updating game state: {e}")
    
    def send_action(self, action_type: str, **kwargs):
        """Send an action to the server"""
        action = {
            "type": action_type,
            "token": self.token,
            **kwargs
        }
        return self.ws_client.send(action)
    
    def handle_events(self):
        """Handle pygame events"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.handle_mouse_down(event)
                
            elif event.type == pygame.MOUSEBUTTONUP:
                self.handle_mouse_up(event)
                
            elif event.type == pygame.MOUSEMOTION:
                self.handle_mouse_motion(event)
                
            elif event.type == pygame.KEYDOWN:
                self.handle_key_down(event)
        
        return True
    
    def handle_mouse_down(self, event):
        """Handle mouse button down events"""
        mouse_pos = pygame.mouse.get_pos()
        
        if event.button == 1:  # Left click
            # Check UI buttons first
            if self.handle_button_click(mouse_pos):
                return
            
            # Handle hero selection
            if self.current_phase == GamePhase.HERO_SELECT:
                self.handle_hero_selection_click(mouse_pos)
                return
            
            # Handle shop minion click
            if self.current_phase == GamePhase.RECRUIT and self.player_data:
                # Check shop
                for i, minion in enumerate(self.player_data.shop):
                    if minion and self.is_point_in_shop_slot(mouse_pos, i):
                        self.send_action("BUY_MINION", slot=i)
                        return
                
                # Check hand
                for i, minion in enumerate(self.player_data.hand):
                    if self.is_point_in_hand_slot(mouse_pos, i):
                        self.start_dragging_minion(minion, mouse_pos)
                        return
                
                # Check board
                for i, minion in enumerate(self.player_data.board):
                    if self.is_point_in_board_slot(mouse_pos, i):
                        # Could select for selling or hero power target
                        self.selected_minion = minion
                        return
        
        elif event.button == 3:  # Right click
            # Sell minion
            if self.current_phase == GamePhase.RECRUIT and self.selected_minion:
                self.send_action("SELL_MINION", instance_id=self.selected_minion.instance_id)
                self.selected_minion = None
    
    def handle_mouse_up(self, event):
        """Handle mouse button up events"""
        if event.button == 1 and self.dragging_minion:
            mouse_pos = pygame.mouse.get_pos()
            
            # Check if dropped on board
            for i in range(MAX_BOARD_SIZE):
                if self.is_point_in_board_slot(mouse_pos, i):
                    # Check if slot is empty
                    occupied = any(m.board_slot == i for m in self.player_data.board)
                    if not occupied:
                        self.send_action("PLAY_MINION", 
                                       instance_id=self.dragging_minion.instance_id,
                                       position=i)
                        break
            
            self.dragging_minion = None
    
    def handle_mouse_motion(self, event):
        """Handle mouse motion events"""
        mouse_pos = pygame.mouse.get_pos()
        
        # Update hovered button
        self.hovered_button = None
        for button_name, button_rect in self.get_ui_buttons().items():
            if button_rect.collidepoint(mouse_pos):
                self.hovered_button = button_name
                break
        
        # Update hovered slot
        self.hovered_slot = None
        if self.current_phase == GamePhase.RECRUIT:
            for i in range(MAX_BOARD_SIZE):
                if self.is_point_in_board_slot(mouse_pos, i):
                    self.hovered_slot = ("board", i)
                    break
        
        # Update dragging
        if self.dragging_minion:
            self.dragging_minion.x = mouse_pos[0] - self.drag_offset[0]
            self.dragging_minion.y = mouse_pos[1] - self.drag_offset[1]
    
    def handle_key_down(self, event):
        """Handle key press events"""
        if event.key == pygame.K_ESCAPE:
            return False
        
        elif event.key == pygame.K_SPACE and self.current_phase == GamePhase.RECRUIT:
            self.send_action("END_TURN")
        
        elif event.key == pygame.K_r and self.current_phase == GamePhase.RECRUIT:
            self.send_action("REFRESH_SHOP")
        
        elif event.key == pygame.K_u and self.current_phase == GamePhase.RECRUIT:
            self.send_action("UPGRADE_TAVERN")
        
        elif event.key == pygame.K_f and self.current_phase == GamePhase.RECRUIT:
            self.send_action("FREEZE_SHOP")
        
        elif event.key == pygame.K_h and self.current_phase == GamePhase.RECRUIT:
            self.send_action("USE_HERO_POWER")
        
        return True
    
    def handle_button_click(self, mouse_pos):
        """Handle UI button clicks"""
        buttons = self.get_ui_buttons()
        
        for button_name, button_rect in buttons.items():
            if button_rect.collidepoint(mouse_pos):
                if button_name == "ready" and self.current_phase == GamePhase.LOBBY:
                    self.send_action("READY", ready=True)
                    return True
                
                elif button_name == "refresh" and self.current_phase == GamePhase.RECRUIT:
                    self.send_action("REFRESH_SHOP")
                    return True
                
                elif button_name == "upgrade" and self.current_phase == GamePhase.RECRUIT:
                    self.send_action("UPGRADE_TAVERN")
                    return True
                
                elif button_name == "freeze" and self.current_phase == GamePhase.RECRUIT:
                    self.send_action("FREEZE_SHOP")
                    return True
                
                elif button_name == "end_turn" and self.current_phase == GamePhase.RECRUIT:
                    self.send_action("END_TURN")
                    return True
                
                elif button_name == "hero_power" and self.current_phase == GamePhase.RECRUIT:
                    self.send_action("USE_HERO_POWER")
                    return True
                
                elif button_name == "sell" and self.current_phase == GamePhase.RECRUIT and self.selected_minion:
                    self.send_action("SELL_MINION", instance_id=self.selected_minion.instance_id)
                    self.selected_minion = None
                    return True
        
        return False
    
    def handle_hero_selection_click(self, mouse_pos):
        """Handle hero selection clicks"""
        hero_rects = self.get_hero_selection_rects()
        
        for i, hero_rect in enumerate(hero_rects):
            if i < len(self.hero_offer) and hero_rect.collidepoint(mouse_pos):
                hero_type = self.hero_offer[i]
                self.send_action("SELECT_HERO", hero=hero_type.value)
                self.selected_hero = hero_type
                return True
        
        return False
    
    def start_dragging_minion(self, minion, mouse_pos):
        """Start dragging a minion"""
        self.dragging_minion = minion
        self.drag_offset = (mouse_pos[0] - minion.x, mouse_pos[1] - minion.y)
    
    def get_ui_buttons(self):
        """Get UI button rectangles based on current phase"""
        buttons = {}
        
        if self.current_phase == GamePhase.LOBBY:
            buttons["ready"] = pygame.Rect(SCREEN_WIDTH - 150, SCREEN_HEIGHT - 80, 120, 50)
        
        elif self.current_phase == GamePhase.RECRUIT:
            buttons["refresh"] = pygame.Rect(SCREEN_WIDTH - 300, 100, 120, 40)
            buttons["upgrade"] = pygame.Rect(SCREEN_WIDTH - 300, 150, 120, 40)
            buttons["freeze"] = pygame.Rect(SCREEN_WIDTH - 300, 200, 120, 40)
            buttons["hero_power"] = pygame.Rect(SCREEN_WIDTH - 300, 250, 120, 40)
            buttons["end_turn"] = pygame.Rect(SCREEN_WIDTH - 300, 300, 120, 40)
            
            if self.selected_minion:
                buttons["sell"] = pygame.Rect(SCREEN_WIDTH - 300, 350, 120, 40)
        
        return buttons
    
    def get_hero_selection_rects(self):
        """Get rectangles for hero selection"""
        rects = []
        start_x = SCREEN_WIDTH // 2 - 200
        for i in range(3):
            rects.append(pygame.Rect(start_x + i * 150, SCREEN_HEIGHT // 2, 140, 180))
        return rects
    
    def is_point_in_shop_slot(self, point, slot_index):
        """Check if point is in a shop slot"""
        shop_rects = self.get_shop_slot_rects()
        if 0 <= slot_index < len(shop_rects):
            return shop_rects[slot_index].collidepoint(point)
        return False
    
    def is_point_in_hand_slot(self, point, slot_index):
        """Check if point is in a hand slot"""
        hand_rects = self.get_hand_slot_rects()
        if 0 <= slot_index < len(hand_rects):
            return hand_rects[slot_index].collidepoint(point)
        return False
    
    def is_point_in_board_slot(self, point, slot_index):
        """Check if point is in a board slot"""
        board_rects = self.get_board_slot_rects()
        if 0 <= slot_index < len(board_rects):
            return board_rects[slot_index].collidepoint(point)
        return False
    
    def get_shop_slot_rects(self):
        """Get rectangles for shop slots"""
        rects = []
        start_x = 150
        start_y = 150
        slot_width = 100
        slot_height = 140
        spacing = 20
        
        for i in range(SHOP_SIZE):
            rects.append(pygame.Rect(
                start_x + i * (slot_width + spacing),
                start_y,
                slot_width,
                slot_height
            ))
        
        return rects
    
    def get_board_slot_rects(self):
        """Get rectangles for board slots"""
        rects = []
        start_x = 150
        start_y = 350
        slot_width = 100
        slot_height = 140
        spacing = 20
        
        for i in range(MAX_BOARD_SIZE):
            rects.append(pygame.Rect(
                start_x + i * (slot_width + spacing),
                start_y,
                slot_width,
                slot_height
            ))
        
        return rects
    
    def get_hand_slot_rects(self):
        """Get rectangles for hand slots"""
        rects = []
        start_x = 150
        start_y = 550
        slot_width = 100
        slot_height = 140
        spacing = 20
        
        for i in range(MAX_HAND_SIZE):
            rects.append(pygame.Rect(
                start_x + i * (slot_width + spacing),
                start_y,
                slot_width,
                slot_height
            ))
        
        return rects
    
    def draw(self):
        """Draw the entire game screen"""
        # Draw background
        self.screen.blit(self.background, (0, 0))
        
        # Draw based on current phase
        if self.current_phase == GamePhase.LOBBY:
            self.draw_lobby_screen()
        elif self.current_phase == GamePhase.HERO_SELECT:
            self.draw_hero_selection_screen()
        elif self.current_phase == GamePhase.RECRUIT:
            self.draw_recruit_screen()
        elif self.current_phase == GamePhase.COMBAT_CALC:
            self.draw_combat_screen()
        elif self.current_phase == GamePhase.LOG_REPLAY:
            self.draw_log_replay_screen()
        elif self.current_phase == GamePhase.GAME_OVER:
            self.draw_game_over_screen()
        
        # Draw dragging minion on top
        if self.dragging_minion:
            self.draw_minion(self.dragging_minion)
        
        # Update display
        pygame.display.flip()
    
    def draw_lobby_screen(self):
        """Draw lobby screen"""
        # Title
        title = TITLE_FONT.render("Hearthstone Battlegrounds", True, TEXT_COLOR)
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 50))
        
        # Player info
        player_text = HEADER_FONT.render(f"Player: {self.player_name}", True, TEXT_COLOR)
        self.screen.blit(player_text, (50, 150))
        
        # Connected players
        y = 200
        player_count = 1
        if self.player_data:
            status = "Ready" if self.player_data.is_ready else "Not Ready"
            player_text = NORMAL_FONT.render(f"1. {self.player_data.name} - {status}", True, TEXT_COLOR)
            self.screen.blit(player_text, (50, y))
            y += 40
            player_count += 1
        
        for i, opponent in enumerate(self.opponents):
            status = "Ready" if opponent.is_ready else "Not Ready"
            player_text = NORMAL_FONT.render(f"{player_count}. {opponent.name} - {status}", True, TEXT_COLOR)
            self.screen.blit(player_text, (50, y))
            y += 40
            player_count += 1
        
        # Waiting message
        if player_count < 4:
            waiting_text = HEADER_FONT.render(f"Waiting for {4 - player_count} more players...", True, TEXT_COLOR)
            self.screen.blit(waiting_text, (SCREEN_WIDTH // 2 - waiting_text.get_width() // 2, 400))
        
        # Ready button
        self.draw_button("READY", "ready", SCREEN_WIDTH - 150, SCREEN_HEIGHT - 80, 120, 50)
    
    def draw_hero_selection_screen(self):
        """Draw hero selection screen"""
        # Title
        title = TITLE_FONT.render("Choose Your Hero", True, TEXT_COLOR)
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 50))
        
        # Timer
        timer_text = HEADER_FONT.render(f"Time: {int(self.phase_timer)}s", True, TEXT_COLOR)
        self.screen.blit(timer_text, (SCREEN_WIDTH - 150, 50))
        
        # Hero offers
        hero_rects = self.get_hero_selection_rects()
        
        for i, hero_type in enumerate(self.hero_offer):
            if i < len(hero_rects):
                rect = hero_rects[i]
                
                # Draw hero card
                self.draw_hero_card(hero_type, rect.x, rect.y, rect.width, rect.height)
                
                # Highlight if selected
                if self.selected_hero == hero_type:
                    pygame.draw.rect(self.screen, HIGHLIGHT_COLOR, rect, 4)
    
    def draw_recruit_screen(self):
        """Draw recruit phase screen"""
        if not self.player_data:
            return
        
        # Draw player info panel
        self.draw_player_info_panel()
        
        # Draw opponents panel
        self.draw_opponents_panel()
        
        # Draw shop
        self.draw_shop()
        
        # Draw board
        self.draw_board()
        
        # Draw hand
        self.draw_hand()
        
        # Draw UI buttons
        self.draw_ui_buttons()
        
        # Draw timer
        self.draw_timer()
        
        # Draw selected minion info
        if self.selected_minion:
            self.draw_minion_info(self.selected_minion)
    
    def draw_player_info_panel(self):
        """Draw player information panel"""
        panel_rect = pygame.Rect(20, 20, 350, 100)
        pygame.draw.rect(self.screen, PANEL_COLOR, panel_rect, border_radius=10)
        pygame.draw.rect(self.screen, BORDER_COLOR, panel_rect, 2, border_radius=10)
        
        # Player name
        name_text = HEADER_FONT.render(self.player_data.name, True, TEXT_COLOR)
        self.screen.blit(name_text, (40, 30))
        
        # Health
        health_text = NORMAL_FONT.render(f"Health: {self.player_data.health}", True, HEALTH_COLOR)
        self.screen.blit(health_text, (40, 60))
        
        # Gold
        gold_text = NORMAL_FONT.render(f"Gold: {self.player_data.gold}", True, GOLD_COLOR)
        self.screen.blit(gold_text, (40, 85))
        
        # Tavern tier
        tier_text = NORMAL_FONT.render(f"Tavern Tier: {self.player_data.tavern_tier}", True, (100, 200, 255))
        self.screen.blit(tier_text, (180, 60))
        
        # Wins/Losses
        stats_text = NORMAL_FONT.render(f"Wins: {self.player_data.wins} Losses: {self.player_data.losses}", True, TEXT_COLOR)
        self.screen.blit(stats_text, (180, 85))
        
        # Hero
        if self.player_data.hero:
            hero_name = SMALL_FONT.render(self.player_data.hero.name, True, TEXT_COLOR)
            self.screen.blit(hero_name, (300, 30))
            
            power_text = TINY_FONT.render(f"Power ({self.player_data.hero.power_cost}G): {self.player_data.hero.power_description}", True, (200, 200, 100))
            self.screen.blit(power_text, (300, 50))
    
    def draw_opponents_panel(self):
        """Draw opponents panel"""
        panel_rect = pygame.Rect(SCREEN_WIDTH - 370, 20, 350, 150)
        pygame.draw.rect(self.screen, PANEL_COLOR, panel_rect, border_radius=10)
        pygame.draw.rect(self.screen, BORDER_COLOR, panel_rect, 2, border_radius=10)
        
        title = NORMAL_FONT.render("Opponents", True, TEXT_COLOR)
        self.screen.blit(title, (SCREEN_WIDTH - 360, 30))
        
        y = 60
        for opponent in self.opponents[:3]:  # Show up to 3 opponents
            if opponent.is_zombie:
                continue
                
            name_text = SMALL_FONT.render(f"{opponent.name}", True, TEXT_COLOR)
            self.screen.blit(name_text, (SCREEN_WIDTH - 360, y))
            
            health_text = TINY_FONT.render(f"HP: {opponent.health}", True, HEALTH_COLOR)
            self.screen.blit(health_text, (SCREEN_WIDTH - 260, y))
            
            tier_text = TINY_FONT.render(f"Tier: {opponent.tavern_tier}", True, (100, 200, 255))
            self.screen.blit(tier_text, (SCREEN_WIDTH - 200, y))
            
            if opponent.hero:
                hero_text = TINY_FONT.render(f"Hero: {opponent.hero.name[:10]}", True, (200, 200, 100))
                self.screen.blit(hero_text, (SCREEN_WIDTH - 140, y))
            
            y += 30
    
    def draw_shop(self):
        """Draw the shop"""
        # Shop title
        shop_title = HEADER_FONT.render("SHOP", True, TEXT_COLOR)
        self.screen.blit(shop_title, (150, 100))
        
        # Frozen indicator
        if self.player_data and self.player_data.shop_frozen:
            frozen_text = NORMAL_FONT.render("FROZEN", True, (100, 200, 255))
            self.screen.blit(frozen_text, (250, 100))
        
        # Shop slots
        shop_rects = self.get_shop_slot_rects()
        
        for i, rect in enumerate(shop_rects):
            # Draw slot background
            color = SHOP_SLOT_COLOR
            if self.hovered_slot == ("shop", i):
                color = (70, 75, 105)
            
            pygame.draw.rect(self.screen, color, rect, border_radius=5)
            pygame.draw.rect(self.screen, BORDER_COLOR, rect, 2, border_radius=5)
            
            # Draw minion if present
            if i < len(self.player_data.shop) and self.player_data.shop[i]:
                minion = self.player_data.shop[i]
                self.draw_minion_in_rect(minion, rect)
                
                # Draw cost
                cost_text = SMALL_FONT.render("3G", True, GOLD_COLOR)
                cost_rect = cost_text.get_rect(center=(rect.centerx, rect.top - 10))
                self.screen.blit(cost_text, cost_rect)
    
    def draw_board(self):
        """Draw the board"""
        # Board title
        board_title = HEADER_FONT.render("BOARD", True, TEXT_COLOR)
        self.screen.blit(board_title, (150, 300))
        
        # Board slots
        board_rects = self.get_board_slot_rects()
        
        for i, rect in enumerate(board_rects):
            # Draw slot background
            color = BOARD_SLOT_COLOR
            if self.hovered_slot == ("board", i):
                color = (65, 70, 95)
            
            pygame.draw.rect(self.screen, color, rect, border_radius=5)
            pygame.draw.rect(self.screen, BORDER_COLOR, rect, 2, border_radius=5)
            
            # Draw slot number
            slot_text = TINY_FONT.render(str(i + 1), True, (150, 150, 150))
            self.screen.blit(slot_text, (rect.x + 5, rect.y + 5))
            
            # Draw minion if present
            for minion in self.player_data.board:
                if minion.board_slot == i:
                    self.draw_minion_in_rect(minion, rect)
                    break
        
        # Board size indicator
        size_text = NORMAL_FONT.render(f"{len(self.player_data.board)}/{MAX_BOARD_SIZE}", True, TEXT_COLOR)
        self.screen.blit(size_text, (150 + MAX_BOARD_SIZE * 120 + 20, 300))
    
    def draw_hand(self):
        """Draw the hand"""
        # Hand title
        hand_title = HEADER_FONT.render("HAND", True, TEXT_COLOR)
        self.screen.blit(hand_title, (150, 500))
        
        # Hand slots
        hand_rects = self.get_hand_slot_rects()
        
        for i, rect in enumerate(hand_rects):
            # Draw slot background
            color = HAND_SLOT_COLOR
            pygame.draw.rect(self.screen, color, rect, border_radius=5)
            pygame.draw.rect(self.screen, BORDER_COLOR, rect, 2, border_radius=5)
            
            # Draw minion if present
            if i < len(self.player_data.hand):
                minion = self.player_data.hand[i]
                self.draw_minion_in_rect(minion, rect)
        
        # Hand size indicator
        size_text = NORMAL_FONT.render(f"{len(self.player_data.hand)}/{MAX_HAND_SIZE}", True, TEXT_COLOR)
        self.screen.blit(size_text, (150 + MAX_HAND_SIZE * 120 + 20, 500))
    
    def draw_ui_buttons(self):
        """Draw UI buttons"""
        buttons = self.get_ui_buttons()
        
        for button_name, rect in buttons.items():
            self.draw_button(button_name.upper().replace("_", " "), button_name, 
                           rect.x, rect.y, rect.width, rect.height)
    
    def draw_button(self, text, button_name, x, y, width, height):
        """Draw a button"""
        rect = pygame.Rect(x, y, width, height)
        
        # Determine color
        if self.hovered_button == button_name:
            color = BUTTON_HOVER_COLOR
        else:
            color = BUTTON_COLOR
        
        # Draw button
        pygame.draw.rect(self.screen, color, rect, border_radius=8)
        pygame.draw.rect(self.screen, (255, 255, 255), rect, 2, border_radius=8)
        
        # Draw text
        button_text = SMALL_FONT.render(text, True, TEXT_COLOR)
        text_rect = button_text.get_rect(center=rect.center)
        self.screen.blit(button_text, text_rect)
    
    def draw_timer(self):
        """Draw phase timer"""
        timer_text = HEADER_FONT.render(f"Time: {int(self.phase_timer)}s", True, TEXT_COLOR)
        self.screen.blit(timer_text, (SCREEN_WIDTH // 2 - timer_text.get_width() // 2, 20))
    
    def draw_minion_info(self, minion):
        """Draw detailed information about a minion"""
        # Create info panel
        panel_rect = pygame.Rect(SCREEN_WIDTH - 250, SCREEN_HEIGHT - 200, 230, 180)
        pygame.draw.rect(self.screen, PANEL_COLOR, panel_rect, border_radius=10)
        pygame.draw.rect(self.screen, BORDER_COLOR, panel_rect, 2, border_radius=10)
        
        # Minion name
        name_text = NORMAL_FONT.render(minion.name, True, TEXT_COLOR)
        self.screen.blit(name_text, (panel_rect.x + 10, panel_rect.y + 10))
        
        # Stats
        stats_text = SMALL_FONT.render(f"Attack: {minion.attack} Health: {minion.health}", True, TEXT_COLOR)
        self.screen.blit(stats_text, (panel_rect.x + 10, panel_rect.y + 40))
        
        # Tier and tribe
        tier_text = SMALL_FONT.render(f"Tier: {minion.tier} Tribe: {minion.tribe}", True, TEXT_COLOR)
        self.screen.blit(tier_text, (panel_rect.x + 10, panel_rect.y + 60))
        
        # Golden indicator
        if minion.golden:
            golden_text = SMALL_FONT.render("GOLDEN", True, GOLD_COLOR)
            self.screen.blit(golden_text, (panel_rect.x + 10, panel_rect.y + 80))
        
        # Abilities
        y = panel_rect.y + 100
        for ability in minion.abilities:
            ability_text = TINY_FONT.render(ability, True, (200, 200, 100))
            self.screen.blit(ability_text, (panel_rect.x + 10, y))
            y += 20
    
    def draw_minion(self, minion):
        """Draw a minion at its current position"""
        # Create minion surface
        surface = pygame.Surface((100, 140), pygame.SRCALPHA)
        
        # Draw minion background
        color = (70, 75, 105) if minion.golden else (50, 55, 85)
        pygame.draw.rect(surface, color, (0, 0, 100, 140), border_radius=8)
        pygame.draw.rect(surface, BORDER_COLOR, (0, 0, 100, 140), 2, border_radius=8)
        
        # Draw minion image (placeholder)
        pygame.draw.rect(surface, (100, 100, 150), (10, 10, 80, 80), border_radius=5)
        
        # Draw name
        name_text = TINY_FONT.render(minion.name[:12], True, TEXT_COLOR)
        surface.blit(name_text, (50 - name_text.get_width() // 2, 95))
        
        # Draw stats
        # Attack
        attack_bg = pygame.Surface((25, 25), pygame.SRCALPHA)
        pygame.draw.circle(attack_bg, (150, 50, 50), (12, 12), 12)
        pygame.draw.circle(attack_bg, (255, 100, 100), (12, 12), 12, 2)
        attack_text = TINY_FONT.render(str(minion.attack), True, TEXT_COLOR)
        attack_rect = attack_text.get_rect(center=(12, 12))
        attack_bg.blit(attack_text, attack_rect)
        surface.blit(attack_bg, (10, 110))
        
        # Health
        health_bg = pygame.Surface((25, 25), pygame.SRCALPHA)
        pygame.draw.circle(health_bg, (50, 150, 50), (12, 12), 12)
        pygame.draw.circle(health_bg, (100, 255, 100), (12, 12), 12, 2)
        health_text = TINY_FONT.render(str(minion.health), True, TEXT_COLOR)
        health_rect = health_text.get_rect(center=(12, 12))
        health_bg.blit(health_text, health_rect)
        surface.blit(health_bg, (65, 110))
        
        # Draw abilities icons
        x_offset = 35
        for ability in minion.abilities[:3]:  # Show up to 3 abilities
            if ability in self.icons:
                surface.blit(self.icons[ability], (x_offset, 120))
                x_offset += 25
        
        # Draw to screen
        self.screen.blit(surface, (minion.x, minion.y))
        
        # Highlight if selected
        if minion == self.selected_minion:
            highlight_rect = pygame.Rect(minion.x - 2, minion.y - 2, 104, 144)
            pygame.draw.rect(self.screen, HIGHLIGHT_COLOR, highlight_rect, 3, border_radius=10)
    
    def draw_minion_in_rect(self, minion, rect):
        """Draw a minion inside a rectangle"""
        # Temporarily set minion position to rect
        original_x, original_y = minion.x, minion.y
        minion.x, minion.y = rect.x, rect.y
        self.draw_minion(minion)
        minion.x, minion.y = original_x, original_y
    
    def draw_hero_card(self, hero_type, x, y, width, height):
        """Draw a hero selection card"""
        # Card background
        card_rect = pygame.Rect(x, y, width, height)
        pygame.draw.rect(self.screen, PANEL_COLOR, card_rect, border_radius=10)
        pygame.draw.rect(self.screen, BORDER_COLOR, card_rect, 3, border_radius=10)
        
        # Hero image
        if hero_type in self.hero_images:
            hero_img = self.hero_images[hero_type]
            img_rect = hero_img.get_rect(center=(x + width // 2, y + 70))
            self.screen.blit(hero_img, img_rect)
        
        # Hero name
        name_text = NORMAL_FONT.render(hero_type.name.replace("_", " "), True, TEXT_COLOR)
        name_rect = name_text.get_rect(center=(x + width // 2, y + height - 50))
        self.screen.blit(name_text, name_rect)
        
        # Hero type
        type_text = SMALL_FONT.render("HERO", True, (200, 200, 100))
        type_rect = type_text.get_rect(center=(x + width // 2, y + height - 30))
        self.screen.blit(type_text, type_rect)
    
    def draw_combat_screen(self):
        """Draw combat calculation screen"""
        # Background
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        self.screen.blit(overlay, (0, 0))
        
        # Title
        title = TITLE_FONT.render("COMBAT IN PROGRESS", True, TEXT_COLOR)
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, SCREEN_HEIGHT // 2 - 100))
        
        # Loading animation
        dots = "." * (int(pygame.time.get_ticks() / 500) % 4)
        loading_text = HEADER_FONT.render(f"Calculating combat{dots}", True, TEXT_COLOR)
        self.screen.blit(loading_text, (SCREEN_WIDTH // 2 - loading_text.get_width() // 2, SCREEN_HEIGHT // 2))
    
    def draw_log_replay_screen(self):
        """Draw log replay screen"""
        # Similar to combat screen
        self.draw_combat_screen()
        
        # Add log replay specific text
        replay_text = HEADER_FONT.render("Replaying combat log...", True, TEXT_COLOR)
        self.screen.blit(replay_text, (SCREEN_WIDTH // 2 - replay_text.get_width() // 2, SCREEN_HEIGHT // 2 + 50))
    
    def draw_game_over_screen(self):
        """Draw game over screen"""
        if not self.game_over_data:
            return
        
        # Background
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 220))
        self.screen.blit(overlay, (0, 0))
        
        # Title
        winner = self.game_over_data.get("winner", "Unknown")
        title = TITLE_FONT.render("GAME OVER", True, TEXT_COLOR)
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 50))
        
        # Winner
        winner_text = HEADER_FONT.render(f"Winner: {winner}", True, GOLD_COLOR)
        self.screen.blit(winner_text, (SCREEN_WIDTH // 2 - winner_text.get_width() // 2, 120))
        
        # Player standings
        players = self.game_over_data.get("players", [])
        y = 200
        
        for i, player in enumerate(players):
            player_name = player.get("name", f"Player {i+1}")
            player_health = player.get("health", 0)
            player_wins = player.get("wins", 0)
            player_losses = player.get("losses", 0)
            player_damage = player.get("damage_dealt", 0)
            player_hero = player.get("hero", "Unknown")
            
            # Player card
            card_rect = pygame.Rect(SCREEN_WIDTH // 2 - 200, y, 400, 80)
            color = (60, 120, 200) if player_name == winner else PANEL_COLOR
            pygame.draw.rect(self.screen, color, card_rect, border_radius=10)
            pygame.draw.rect(self.screen, BORDER_COLOR, card_rect, 2, border_radius=10)
            
            # Player info
            name_text = NORMAL_FONT.render(f"{i+1}. {player_name}", True, TEXT_COLOR)
            self.screen.blit(name_text, (card_rect.x + 20, card_rect.y + 15))
            
            stats_text = SMALL_FONT.render(f"HP: {player_health} | W: {player_wins} L: {player_losses} | Dmg: {player_damage}", True, TEXT_COLOR)
            self.screen.blit(stats_text, (card_rect.x + 20, card_rect.y + 45))
            
            hero_text = SMALL_FONT.render(f"Hero: {player_hero}", True, (200, 200, 100))
            self.screen.blit(hero_text, (card_rect.x + 250, card_rect.y + 30))
            
            y += 100
        
        # Restart button
        restart_rect = pygame.Rect(SCREEN_WIDTH // 2 - 100, y + 20, 200, 50)
        self.draw_button("EXIT GAME", "exit", restart_rect.x, restart_rect.y, restart_rect.width, restart_rect.height)
    
    def update_timer(self):
        """Update the phase timer"""
        current_time = time.time()
        delta = current_time - self.last_update
        self.last_update = current_time
        
        if self.phase_timer > 0:
            self.phase_timer -= delta
    
    def run(self):
        """Main game loop"""
        clock = pygame.time.Clock()
        
        print(f"Starting game client for {self.player_name}")
        print("Controls:")
        print("  SPACE - End turn")
        print("  R - Refresh shop")
        print("  U - Upgrade tavern")
        print("  F - Freeze shop")
        print("  H - Use hero power")
        print("  Right-click - Sell selected minion")
        
        running = True
        while running:
            # Handle events
            running = self.handle_events()
            
            # Process WebSocket messages
            while True:
                message = self.ws_client.get_message()
                if not message:
                    break
                self.handle_message(message)
            
            # Reconnect if disconnected
            if not self.ws_client.connected and self.current_phase != GamePhase.GAME_OVER:
                if not self.ws_client.reconnect():
                    print("Lost connection to server")
                    running = False
                    break
            
            # Update timer
            self.update_timer()
            
            # Draw everything
            self.draw()
            
            # Cap the frame rate
            clock.tick(FPS)
        
        # Cleanup
        self.ws_client.close()
        pygame.quit()
        sys.exit()

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Hearthstone Battlegrounds Client')
    parser.add_argument('--name', type=str, required=True, help='Player name')
    parser.add_argument('--server', type=str, default='ws://localhost:8888', help='Server URL')
    
    args = parser.parse_args()
    
    # Create and run the client
    client = GameClient(args.server, args.name)
    client.run()

if __name__ == "__main__":
    main()