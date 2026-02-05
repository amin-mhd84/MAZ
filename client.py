# MAW Battlegrounds - Lightweight Frontend
# Optimized for performance, complete single-file implementation

import pygame
import sys
import json
import os
import time
from typing import List, Dict, Optional, Tuple

import asyncio
import websockets
import threading

# ==================== INITIALIZATION ====================
pygame.init()

# Optimized screen dimensions
SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 768
CARD_WIDTH = 100
CARD_HEIGHT = 140

# Game constants
SHOP_SLOTS = 5
BOARD_SLOTS = 7
START_GOLD = 3
MAX_GOLD = 10
TURN_DURATION = 30.0

# Optimized color palette
COLORS = {
    "bg": (15, 20, 35),
    "card_bg": (40, 50, 75),
    "card_border": (80, 130, 200),
    "gold": (255, 215, 0),
    "health": (255, 80, 80),
    "text": (230, 230, 230),
    "shop": (100, 180, 255),
    "board": (220, 160, 100),
    "button": (70, 130, 180),
    "button_hover": (90, 160, 220),
    "taunt": (180, 140, 60),
    "divine_shield": (180, 220, 255),
    "reborn": (200, 100, 200),
    "error": (255, 100, 100),
    "success": (100, 220, 100),
}

# Simple font initialization
pygame.font.init()
FONT_TITLE = pygame.font.SysFont(None, 36)
FONT_NORMAL = pygame.font.SysFont(None, 24)
FONT_SMALL = pygame.font.SysFont(None, 18)

# ==================== WEB SOCKET MANAGER ====================
class WebSocketManager:
    def __init__(self, game_client):
        self.game = game_client
        self.ws = None
        self.running = False
        self.connected = False
        self.token = None
        self.reconnect_delay = 3
        self.uri = "ws://localhost:8888"
        self.loop = None
        
    def start(self):
        self.running = True
        thread = threading.Thread(target=self._run_async, daemon=True)
        thread.start()
        return thread
    
    def _run_async(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._connect())
    
    async def _connect(self):
        while self.running:
            try:
                print(f"Connecting to {self.uri}...")
                self.ws = await websockets.connect(self.uri, ping_interval=10)
                self.connected = True
                print("Connected to server")
                await self.receive_messages()
            except Exception as e:
                print(f"Connection failed: {e}")
                self.connected = False
                if self.running:
                    print(f"Reconnecting in {self.reconnect_delay} seconds...")
                    await asyncio.sleep(self.reconnect_delay)
    
    async def receive_messages(self):
        try:
            async for message in self.ws:
                await self.handle_message(message)
        except websockets.exceptions.ConnectionClosed:
            print("Connection closed by server")
            self.connected = False
        except Exception as e:
            print(f"Error receiving messages: {e}")
            self.connected = False
    
    async def handle_message(self, message_str):
        try:
            message = json.loads(message_str)
            message_type = message.get("type", "")
            
            print(f"Received: {message_type}")
            
            if message_type == "WELCOME":
                self.token = message.get("token")
                print(f"Token received: {self.token}")
                self.game.offline_mode = False
                self.game._add_log("Connected to server!")
                
            elif message_type == "FULL_STATE":
                await self.game._update_from_server(message)
                
            elif message_type == "SHOP_UPDATE":
                await self.game._update_shop(message)
                
            elif message_type == "phase_change":
                self.game.phase = message.get("phase", "RECRUIT")
                self.game._add_log(f"Phase changed to: {self.game.phase}")
                
            elif message_type == "error":
                error_msg = message.get("message", "Unknown error")
                self.game._add_log(f"Server error: {error_msg}", True)
                
            elif message_type == "combat_log":
                await self.game._start_combat_replay(message)
                
            elif message_type == "game_over":
                winner = message.get("winner", "none")
                self.game._add_log(f"Game Over! Winner: {winner}")
                
        except Exception as e:
            print(f"Error handling message: {e}")
    
    async def send_action(self, action_type, payload=None):
        if not self.connected or not self.ws:
            self.game._add_log("Not connected to server!", True)
            return False
        
        try:
            action = {
                "action": action_type,
                "token": self.token,
                "timestamp": time.time(),
            }
            
            if self.game.current_player and hasattr(self.game.current_player, 'get'):
                action["version"] = self.game.current_player.get("version", 0)
            
            if payload:
                action["payload"] = payload
            
            await self.ws.send(json.dumps(action))
            print(f"Sent: {action_type}")
            return True
            
        except Exception as e:
            print(f"Error sending action: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        self.running = False
        self.connected = False
        if self.ws:
            asyncio.run_coroutine_threadsafe(self.ws.close(), self.loop)

# ==================== CARD CLASS ====================
class Card:
    def __init__(self, data: Dict):
        self.card_id = data.get("card_id", "UNKNOWN")
        self.name = data.get("name", "Unknown")
        self.attack = data.get("attack", 1)
        self.health = data.get("health", 1)
        self.tier = data.get("tier", 1)
        self.cost = data.get("cost", 3)
        self.instance_id = data.get("instance_id", f"inst_{id(self)}")
        self.is_golden = data.get("is_golden", False)
        self.keywords = data.get("keywords", [])
        self.has_divine_shield = data.get("has_divine_shield", False)
        
        self.x = 0
        self.y = 0
        self.width = CARD_WIDTH
        self.height = CARD_HEIGHT
        self.is_dragging = False
        self.drag_offset = (0, 0)
        
        self.color = self._calculate_color()
    
    def _calculate_color(self):
        tier_colors = [
            (100, 100, 100),
            (80, 150, 80),
            (80, 150, 200),
            (180, 120, 220),
            (220, 160, 60),
            (220, 80, 80),
        ]
        tier_idx = min(self.tier, len(tier_colors) - 1)
        return (255, 215, 0) if self.is_golden else tier_colors[tier_idx]
    
    def contains_point(self, point: Tuple[int, int]) -> bool:
        return (self.x <= point[0] <= self.x + self.width and 
                self.y <= point[1] <= self.y + self.height)
    
    def start_drag(self, mouse_pos: Tuple[int, int]):
        self.is_dragging = True
        self.drag_offset = (mouse_pos[0] - self.x, mouse_pos[1] - self.y)
    
    def update_drag(self, mouse_pos: Tuple[int, int]):
        if self.is_dragging:
            self.x = mouse_pos[0] - self.drag_offset[0]
            self.y = mouse_pos[1] - self.drag_offset[1]
    
    def stop_drag(self):
        self.is_dragging = False
    
    def draw(self, surface: pygame.Surface, x: int, y: int, show_cost: bool = False):
        self.x, self.y = x, y
        
        card_rect = pygame.Rect(x, y, self.width, self.height)
        pygame.draw.rect(surface, self.color, card_rect, border_radius=8)
        pygame.draw.rect(surface, COLORS["card_border"], card_rect, 2, border_radius=8)
        
        name = self.name[:12] + "..." if len(self.name) > 12 else self.name
        name_text = FONT_SMALL.render(name, True, COLORS["text"])
        surface.blit(name_text, (x + 5, y + 5))
        
        attack_text = FONT_NORMAL.render(str(self.attack), True, (255, 255, 255))
        attack_bg = pygame.Rect(x + 5, y + self.height - 30, 25, 25)
        pygame.draw.rect(surface, COLORS["health"], attack_bg, border_radius=12)
        surface.blit(attack_text, (x + 10, y + self.height - 27))
        
        health_text = FONT_NORMAL.render(str(self.health), True, (255, 255, 255))
        health_bg = pygame.Rect(x + self.width - 30, y + self.height - 30, 25, 25)
        pygame.draw.rect(surface, (80, 200, 80), health_bg, border_radius=12)
        surface.blit(health_text, (x + self.width - 25, y + self.height - 27))
        
        y_offset = y + 35
        for keyword in self.keywords[:2]:
            if keyword == "Taunt":
                color = COLORS["taunt"]
            elif keyword == "Divine Shield":
                color = COLORS["divine_shield"]
            elif keyword == "Reborn":
                color = COLORS["reborn"]
            else:
                color = (180, 180, 180)
            
            kw_text = FONT_SMALL.render(keyword[:8], True, color)
            surface.blit(kw_text, (x + 5, y_offset))
            y_offset += 18
        
        if self.has_divine_shield:
            shield_text = FONT_SMALL.render("S", True, COLORS["divine_shield"])
            surface.blit(shield_text, (x + self.width - 15, y + 5))
        
        if show_cost:
            cost_text = FONT_NORMAL.render(str(self.cost), True, COLORS["gold"])
            surface.blit(cost_text, (x + self.width - 25, y + 5))

# ==================== PLAYER CLASS ====================
class Player:
    def __init__(self, data: Dict):
        self.player_id = data.get("player_id", "p1")
        
        hero_data = data.get("hero", {})
        if isinstance(hero_data, dict):
            self.hero_name = hero_data.get("name", "Sylvanas")
            self.health = hero_data.get("health", 40)
            self.hero_power_cost = hero_data.get("hero_power_cost", 1)
            self.hero_power_used = hero_data.get("hero_power_used", False)
        else:
            self.hero_name = str(hero_data)
            self.health = data.get("health", 40)
            self.hero_power_cost = 1
            self.hero_power_used = False
        
        self.gold = data.get("gold", START_GOLD)
        self.tavern_tier = data.get("tavern_tier", 1)
        
        self.shop = self._parse_cards(data.get("shop", []), is_shop=True)
        self.board = self._parse_cards(data.get("board", []))
        
        self.shop_frozen = data.get("flags", {}).get("shop_frozen", False)
        
        self.shop_pos = (30, 120)
        self.board_pos = (30, 400)
    
    def _parse_cards(self, card_list: List, is_shop: bool = False) -> List:
        cards = []
        for item in card_list:
            if item:
                cards.append(Card(item))
            elif is_shop:
                cards.append(None)
        return cards

    def _find_empty_board_slot(self):
        for i, card in enumerate(self.board):
            if card is None:
                return i
        if len(self.board) < BOARD_SLOTS:
            return len(self.board)
        return -1

# ==================== BUTTON CLASS ====================
class Button:
    def __init__(self, x: int, y: int, width: int, height: int, 
                 text: str, action: str = ""):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.action = action
        self.is_hovered = False
        self.enabled = True
    
    def draw(self, surface: pygame.Surface):
        color = COLORS["button_hover"] if self.is_hovered else COLORS["button"]
        if not self.enabled:
            color = (100, 100, 120)
        
        pygame.draw.rect(surface, color, self.rect, border_radius=6)
        pygame.draw.rect(surface, (255, 255, 255), self.rect, 1, border_radius=6)
        
        text_color = (255, 255, 255) if self.enabled else (150, 150, 150)
        text_surf = FONT_NORMAL.render(self.text, True, text_color)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)
    
    def check_hover(self, mouse_pos: Tuple[int, int]) -> bool:
        self.is_hovered = self.rect.collidepoint(mouse_pos) and self.enabled
        return self.is_hovered

# ==================== TIMER CLASS ====================
class Timer:
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y
        self.time_left = TURN_DURATION
        self.grace_time = 2.0
        self.in_grace = False
        self.active = True
    
    def update(self, dt: float):
        if not self.active:
            return
            
        if self.time_left > 0:
            self.time_left -= dt
        elif not self.in_grace:
            self.in_grace = True
            self.grace_time = 2.0
        elif self.in_grace:
            self.grace_time -= dt
            if self.grace_time <= 0:
                self.active = False
    
    def draw(self, surface: pygame.Surface):
        bar_width = 250
        bar_height = 20
        
        bg_rect = pygame.Rect(self.x, self.y, bar_width, bar_height)
        pygame.draw.rect(surface, (40, 50, 70), bg_rect, border_radius=3)
        
        if self.in_grace:
            progress = self.grace_time / 2.0
            color = (255, 200, 50)
            label = "GRACE"
        else:
            progress = self.time_left / TURN_DURATION
            if progress > 0.5:
                color = (80, 200, 100)
            elif progress > 0.2:
                color = (255, 200, 50)
            else:
                color = (255, 80, 80)
            label = "RECRUIT"
        
        fill_width = int(bar_width * progress)
        fill_rect = pygame.Rect(self.x, self.y, fill_width, bar_height)
        pygame.draw.rect(surface, color, fill_rect, border_radius=3)
        
        pygame.draw.rect(surface, (180, 180, 200), bg_rect, 1, border_radius=3)
        
        time_text = f"{label}: {self.grace_time:.1f}s" if self.in_grace else f"{label}: {self.time_left:.1f}s"
        text_surf = FONT_SMALL.render(time_text, True, (255, 255, 255))
        text_rect = text_surf.get_rect(center=bg_rect.center)
        surface.blit(text_surf, text_rect)

# ==================== GAME CLIENT CLASS ====================
class GameClient:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("MAW Battlegrounds - Lightweight")
        
        self.clock = pygame.time.Clock()
        self.running = True
        self.offline_mode = True
        
        self.ws_manager = WebSocketManager(self)
        self.ws_thread = None
        
        self.phase = "RECRUIT"
        self.players = self._load_game_data()
        self.current_player = self.players[0] if self.players else None
        
        self.timer = Timer(SCREEN_WIDTH - 280, 20)
        self.buttons = self._create_buttons()
        
        self.dragging_card = None
        self.drag_source = ""
        
        self.log = [
            "Game started in lightweight mode",
            "Drag shop cards to board to buy",
            "Right-click board cards to sell"
        ]
        
        self.start_websocket()
    
    def start_websocket(self):
        print("Starting WebSocket connection...")
        self.ws_thread = self.ws_manager.start()
    
    def _load_game_data(self) -> List[Player]:
        try:
            if os.path.exists('data/mock_state.json'):
                with open('data/mock_state.json', 'r') as f:
                    data = json.load(f)
                players_data = data.get("players", [])
                return [Player(p) for p in players_data]
        except:
            pass
        
        return [Player({
            "player_id": "p1",
            "hero": {"name": "Sylvanas", "health": 40},
            "gold": 7,
            "tavern_tier": 2,
            "shop": [
                {"name": "Buzzing Vermin", "attack": 2, "health": 3, "tier": 1, 
                 "cost": 3, "keywords": ["Taunt", "Deathrattle"]},
                {"name": "Forest Rover", "attack": 3, "health": 2, "tier": 1,
                 "cost": 3, "keywords": ["Battlecry"]},
                {"name": "Scarab", "attack": 2, "health": 2, "tier": 2,
                 "cost": 3, "keywords": ["Choose One"]},
                None,
                None
            ],
            "board": [
                {"name": "Defender", "attack": 2, "health": 4, "tier": 2,
                 "keywords": ["Taunt"]},
                None, None, None, None, None, None
            ],
            "flags": {"shop_frozen": False}
        })]
    
    def _create_buttons(self) -> List[Button]:
        buttons = []
        x_start = SCREEN_WIDTH - 150
        y_start = 100
        btn_width = 140
        btn_height = 40
        spacing = 50
        
        button_data = [
            ("Refresh (1g)", "refresh"),
            ("Freeze", "freeze"),
            ("End Turn", "end_turn"),
            ("Upgrade (5g)", "upgrade"),
            ("Hero Power", "hero_power"),
        ]
        
        for i, (text, action) in enumerate(button_data):
            buttons.append(Button(
                x_start, y_start + i * spacing,
                btn_width, btn_height,
                text, action
            ))
        
        return buttons
    
    def _add_log(self, message: str, is_error: bool = False):
        color = "error" if is_error else "success"
        self.log.append(message)
        if len(self.log) > 8:
            self.log.pop(0)
        print(f"[LOG] {message}")
    
    async def _send_to_server(self, action_type, payload=None):
        if self.ws_manager.connected:
            await self.ws_manager.send_action(action_type, payload)
        else:
            self._add_log("Not connected to server", True)
    
    def _run_async_in_thread(self, coro):
        if hasattr(self.ws_manager, 'loop') and self.ws_manager.loop:
            asyncio.run_coroutine_threadsafe(coro, self.ws_manager.loop)
        else:
            print("Warning: No event loop available")
    
    def handle_events(self):
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            elif event.type == pygame.KEYDOWN:
                # فقط در لحظه فشرده شدن کلید
                self._handle_keyboard(event)
            
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    mouse_handled = False
                    
                    # ابتدا کارت‌های shop را بررسی کن
                    if self.current_player:
                        for card in self.current_player.shop:
                            if card and card.contains_point(mouse_pos):
                                self.dragging_card = card
                                self.drag_source = "shop"
                                card.start_drag(mouse_pos)
                                mouse_handled = True
                                break
                        
                        # اگر روی shop نبود، board را بررسی کن
                        if not mouse_handled:
                            for card in self.current_player.board:
                                if card and card.contains_point(mouse_pos):
                                    self.dragging_card = card
                                    self.drag_source = "board"
                                    card.start_drag(mouse_pos)
                                    mouse_handled = True
                                    break
                    
                    # اگر روی کارتی نبود، دکمه‌ها را بررسی کن
                    if not mouse_handled:
                        for button in self.buttons:
                            if button.rect.collidepoint(mouse_pos) and button.enabled:
                                print(f"Button clicked: {button.action}")  # برای دیباگ
                                self._handle_button_click(button.action)
                                break
                
                elif event.button == 3:  # Right click
                    self._handle_right_click(mouse_pos)
            
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1 and self.dragging_card:
                    self._handle_card_drop(mouse_pos)

        # فقط برای hover کردن دکمه‌ها (نه برای کلیک)
        for button in self.buttons:
            button.check_hover(mouse_pos)

        # Update dragging
        if self.dragging_card:
            self.dragging_card.update_drag(mouse_pos)    
    def _handle_keyboard(self, event):
        if event.key == pygame.K_ESCAPE:
            self.running = False
        elif event.key == pygame.K_r:
            self._handle_refresh()
        elif event.key == pygame.K_f:
            self._handle_freeze()
        elif event.key == pygame.K_SPACE:
            self._handle_end_turn()
    
    def _handle_left_click(self, mouse_pos: Tuple[int, int]):
        if not self.current_player:
            return
            
        for card in self.current_player.shop:
            if card and card.contains_point(mouse_pos):
                self.dragging_card = card
                self.drag_source = "shop"
                card.start_drag(mouse_pos)
                return
        
        for card in self.current_player.board:
            if card and card.contains_point(mouse_pos):
                self.dragging_card = card
                self.drag_source = "board"
                card.start_drag(mouse_pos)
                return
    
    def _handle_right_click(self, mouse_pos: Tuple[int, int]):
        if not self.current_player:
            return
            
        for i, card in enumerate(self.current_player.board):
            if card and card.contains_point(mouse_pos):
                if self.offline_mode:
                    self.current_player.gold += 1
                    self.current_player.board[i] = None
                    self._add_log(f"Sold {card.name} (+1 gold)")
                else:
                    payload = {
                        "instance_id": card.instance_id,
                        "slot": i
                    }
                    self._run_async_in_thread(self._send_to_server("SELL_MINION", payload))
                return
    
    def _handle_card_drop(self, mouse_pos: Tuple[int, int]):
        if not self.dragging_card or not self.current_player:
            return
        
        board_rect = pygame.Rect(
            self.current_player.board_pos[0] - 10,
            self.current_player.board_pos[1] - 10,
            BOARD_SLOTS * (CARD_WIDTH + 5) + 20,
            CARD_HEIGHT + 20
        )
        
        if self.drag_source == "shop" and board_rect.collidepoint(mouse_pos):
            self._buy_card()
        elif self.drag_source == "board" and not board_rect.collidepoint(mouse_pos):
            self._sell_card()
        
        if self.dragging_card:
            self.dragging_card.stop_drag()
            self.dragging_card = None
            self.drag_source = ""
    
    def _buy_card(self):
        if not self.dragging_card or not self.current_player:
            return
            
        if self.offline_mode:
            if self.current_player.gold < self.dragging_card.cost:
                self._add_log("Not enough gold!", True)
                return
            
            empty_slot = self.current_player._find_empty_board_slot()
            if empty_slot == -1:
                self._add_log("Board is full!", True)
                return
            
            for i, card in enumerate(self.current_player.shop):
                if card and card.instance_id == self.dragging_card.instance_id:
                    self.current_player.shop[i] = None
                    break
            
            if empty_slot < len(self.current_player.board):
                self.current_player.board[empty_slot] = self.dragging_card
            else:
                self.current_player.board.append(self.dragging_card)
            
            self.current_player.gold -= self.dragging_card.cost
            self._add_log(f"Bought {self.dragging_card.name} (-{self.dragging_card.cost}g)")
        else:
            shop_slot = self._find_card_slot(self.dragging_card, "shop")
            if shop_slot >= 0:
                payload = {
                    "shop_slot": shop_slot,
                    "card_id": self.dragging_card.card_id,
                    "expected_cost": self.dragging_card.cost
                }
                self._run_async_in_thread(self._send_to_server("BUY_MINION", payload))
    
    def _sell_card(self):
        if not self.dragging_card or not self.current_player:
            return
            
        if self.offline_mode:
            for i, card in enumerate(self.current_player.board):
                if card and card.instance_id == self.dragging_card.instance_id:
                    self.current_player.board[i] = None
                    self.current_player.gold += 1
                    self._add_log(f"Sold {card.name} (+1 gold)")
                    return
        else:
            board_slot = self._find_card_slot(self.dragging_card, "board")
            if board_slot >= 0:
                payload = {
                    "instance_id": self.dragging_card.instance_id,
                    "slot": board_slot
                }
                self._run_async_in_thread(self._send_to_server("SELL_MINION", payload))
    
    def _handle_button_click(self, action: str):
        """Handle button clicks - فقط یک بار اجرا می‌شود"""
        print(f"Processing button action: {action}")
        
        if action == "refresh":
            self._handle_refresh()
        elif action == "freeze":
            self._handle_freeze()
        elif action == "end_turn":
            self._handle_end_turn()
        elif action == "upgrade":
            self._handle_upgrade()
        elif action == "hero_power":
            self._handle_hero_power()    
    def _handle_refresh(self):
        if self.offline_mode:
            if self.current_player.gold >= 1:
                self.current_player.gold -= 1
                self._add_log("Shop refreshed (-1 gold)")
            else:
                self._add_log("Not enough gold to refresh!", True)
        else:
            self._run_async_in_thread(self._send_to_server("REFRESH_SHOP"))
    
    def _handle_freeze(self):
        if self.offline_mode:
            self.current_player.shop_frozen = not self.current_player.shop_frozen
            status = "frozen" if self.current_player.shop_frozen else "unfrozen"
            self._add_log(f"Shop {status}")
        else:
            self._run_async_in_thread(self._send_to_server("TOGGLE_FREEZE"))
    
    def _handle_end_turn(self):
        if self.offline_mode:
            self.timer.time_left = 0
            self._add_log("Turn ended")
        else:
            self._run_async_in_thread(self._send_to_server("END_TURN"))
    
    def _handle_upgrade(self):
        cost = 5
        if self.offline_mode:
            if self.current_player.gold >= cost:
                self.current_player.gold -= cost
                self.current_player.tavern_tier += 1
                self._add_log(f"Tavern upgraded to tier {self.current_player.tavern_tier} (-{cost}g)")
            else:
                self._add_log("Not enough gold to upgrade!", True)
        else:
            payload = {
                "current_tier": self.current_player.tavern_tier,
                "expected_cost": cost
            }
            self._run_async_in_thread(self._send_to_server("UPGRADE_TAVERN", payload))
    
    def _handle_hero_power(self):
        if self.offline_mode:
            if not self.current_player.hero_power_used:
                self.current_player.hero_power_used = True
                self._add_log(f"{self.current_player.hero_name} hero power used")
            else:
                self._add_log("Hero power already used this turn", True)
        else:
            self._run_async_in_thread(self._send_to_server("USE_HERO_POWER"))
    
    def update(self, dt: float):
        self.timer.update(dt)
        
        if not self.timer.active and self.phase == "RECRUIT":
            self.phase = "COMBAT"
            self._add_log("Entering combat phase!")
    
    def draw(self):
        self.screen.fill(COLORS["bg"])
        
        title = FONT_TITLE.render("MAW BATTLEGROUNDS", True, COLORS["gold"])
        self.screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 10))
        
        status = "Connected" if self.ws_manager.connected else "Offline"
        status_color = (100, 220, 100) if self.ws_manager.connected else (255, 100, 100)
        status_text = FONT_SMALL.render(status, True, status_color)
        self.screen.blit(status_text, (SCREEN_WIDTH - 150, 10))
        
        self._draw_player_info()
        
        self._draw_shop()
        self._draw_board()
        
        self.timer.draw(self.screen)
        for button in self.buttons:
            button.draw(self.screen)
        
        self._draw_log()
        
        if self.dragging_card:
            self.dragging_card.draw(self.screen, 
                                   self.dragging_card.x, 
                                   self.dragging_card.y,
                                   show_cost=(self.drag_source == "shop"))
        
        phase_text = FONT_NORMAL.render(f"Phase: {self.phase}", True, COLORS["text"])
        self.screen.blit(phase_text, (20, SCREEN_HEIGHT - 30))
    
    def _draw_player_info(self):
        if not self.current_player:
            return
        
        hero_text = FONT_NORMAL.render(self.current_player.hero_name, True, (255, 255, 200))
        self.screen.blit(hero_text, (20, 20))
        
        stats = f"Health: {self.current_player.health}   Gold: {self.current_player.gold}   Tier: {self.current_player.tavern_tier}"
        stats_text = FONT_NORMAL.render(stats, True, COLORS["text"])
        self.screen.blit(stats_text, (20, 50))
        
        if self.current_player.shop_frozen:
            freeze_text = FONT_SMALL.render("FROZEN", True, COLORS["shop"])
            self.screen.blit(freeze_text, (200, 50))
    
    def _draw_shop(self):
        if not self.current_player:
            return
            
        title = FONT_NORMAL.render("SHOP", True, COLORS["shop"])
        self.screen.blit(title, (self.current_player.shop_pos[0], 
                                self.current_player.shop_pos[1] - 25))
        
        for i, card in enumerate(self.current_player.shop):
            x = self.current_player.shop_pos[0] + i * (CARD_WIDTH + 10)
            y = self.current_player.shop_pos[1]
            
            if card and card != self.dragging_card:
                card.draw(self.screen, x, y, show_cost=True)
            elif card is None:
                slot = pygame.Rect(x, y, CARD_WIDTH, CARD_HEIGHT)
                pygame.draw.rect(self.screen, (30, 40, 60), slot, border_radius=6)
                pygame.draw.rect(self.screen, (60, 80, 100), slot, 1, border_radius=6)
    
    def _draw_board(self):
        if not self.current_player:
            return
            
        title = FONT_NORMAL.render("BOARD", True, COLORS["board"])
        self.screen.blit(title, (self.current_player.board_pos[0],
                                self.current_player.board_pos[1] - 25))
        
        board_bg = pygame.Rect(
            self.current_player.board_pos[0] - 5,
            self.current_player.board_pos[1] - 5,
            BOARD_SLOTS * (CARD_WIDTH + 5) + 10,
            CARD_HEIGHT + 10
        )
        pygame.draw.rect(self.screen, (35, 45, 65), board_bg, border_radius=8)
        pygame.draw.rect(self.screen, (70, 100, 140), board_bg, 1, border_radius=8)
        
        for i in range(BOARD_SLOTS):
            x = self.current_player.board_pos[0] + i * (CARD_WIDTH + 5)
            y = self.current_player.board_pos[1]
            
            if i < len(self.current_player.board):
                card = self.current_player.board[i]
                if card and card != self.dragging_card:
                    card.draw(self.screen, x, y)
                elif card is None:
                    pygame.draw.rect(self.screen, (50, 60, 80), 
                                    (x, y, CARD_WIDTH, CARD_HEIGHT), 1, border_radius=6)
    
    def _draw_log(self):
        log_bg = pygame.Rect(SCREEN_WIDTH - 300, SCREEN_HEIGHT - 180, 280, 160)
        pygame.draw.rect(self.screen, (25, 35, 55), log_bg, border_radius=6)
        pygame.draw.rect(self.screen, (60, 80, 110), log_bg, 1, border_radius=6)
        
        log_title = FONT_SMALL.render("EVENT LOG", True, COLORS["text"])
        self.screen.blit(log_title, (SCREEN_WIDTH - 290, SCREEN_HEIGHT - 170))
        
        y_offset = SCREEN_HEIGHT - 145
        for message in self.log[-6:]:
            text = FONT_SMALL.render(message, True, (200, 220, 255))
            self.screen.blit(text, (SCREEN_WIDTH - 290, y_offset))
            y_offset += 22
    
    async def _update_from_server(self, message):
        try:
            players_data = message.get("players", [])
            if players_data:
                self.players = [Player(p) for p in players_data]
                self.current_player = self.players[0]
            
            phase = message.get("phase", "RECRUIT")
            self.phase = phase
            
            self._add_log(f"Game state updated from server (Phase: {phase})")
            
        except Exception as e:
            print(f"Error updating from server: {e}")
    
    async def _update_shop(self, message):
        if not self.current_player:
            return
            
        shop_data = message.get("shop", {})
        gold = message.get("gold", self.current_player.gold)
        
        self.current_player.gold = gold
        self._add_log("Shop updated from server")
    
    async def _start_combat_replay(self, message):
        combat_log = message.get("log", [])
        seed = message.get("seed", 0)
        
        self.phase = "COMBAT"
        self._add_log(f"Starting combat replay (Seed: {seed})")
        
        for entry in combat_log:
            p1 = entry.get("p1", "Player1")
            p2 = entry.get("p2", "Player2")
            damage = entry.get("damage", 0)
            self._add_log(f"{p1} vs {p2}: {damage} damage")
    
    def _find_card_slot(self, card, location):
        if not self.current_player:
            return -1
            
        if location == "shop":
            for i, c in enumerate(self.current_player.shop):
                if c and c.instance_id == card.instance_id:
                    return i
        elif location == "board":
            for i, c in enumerate(self.current_player.board):
                if c and c.instance_id == card.instance_id:
                    return i
        return -1
    
    def run(self):
        print("=" * 50)
        print("MAW BATTLEGROUNDS - Lightweight Frontend")
        print("=" * 50)
        print("Controls:")
        print("• Drag SHOP cards to BOARD to buy")
        print("• Drag BOARD cards away to sell")
        print("• Right-click BOARD cards to quick sell")
        print("• R: Refresh shop | F: Freeze shop")
        print("• SPACE: End turn | ESC: Exit")
        print("=" * 50)
        
        while self.running:
            dt = self.clock.tick(30) / 1000.0
            
            self.handle_events()
            self.update(dt)
            self.draw()
            
            pygame.display.flip()
        
        self.ws_manager.disconnect()
        pygame.quit()
        sys.exit()

# ==================== MAIN EXECUTION ====================
if __name__ == "__main__":
    if not os.path.exists('data'):
        os.makedirs('data')
        print("Created 'data' directory")
    
    try:
        game = GameClient()
        game.run()
    except pygame.error as e:
        print(f"PyGame Error: {e}")
        print("Try running with software rendering:")
        print("  Set environment variable: SDL_VIDEODRIVER=windib")
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")