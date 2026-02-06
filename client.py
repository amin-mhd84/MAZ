# client.py - Hearthstone Battlegrounds Client
import pygame
import sys
import os
import json
import asyncio
import websockets
import threading
import queue
import uuid
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import random
import math

# Local imports
from assets.minions.minions import create_minion, MinionManager

# Initialize pygame
pygame.init()

# Screen setup
screen = pygame.display.set_mode((800, 700))
pygame.display.set_caption("Hearthstone Battlegrounds - Client")
icon = pygame.image.load("./image_add/Screenshot 2025-11-27 151541.png")
pygame.display.set_icon(icon)

# Load background
game_bg = pygame.transform.scale(
    pygame.image.load(r"./image_add/Screenshot 2025-12-16 175133.png"),
    (800, 700)
)

clock = pygame.time.Clock()

# ============================================================================
# NETWORK MANAGER - WebSocket Communication
# ============================================================================

class NetworkManager:
    def __init__(self, server_url="ws://localhost:8888"):
        self.server_url = server_url
        self.ws = None
        self.connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.token = None
        self.player_id = None
        
        # Message queues
        self.incoming_queue = queue.Queue()
        self.outgoing_queue = queue.Queue()
        
        # Thread control
        self.network_thread = None
        self.running = False
        
    def start(self):
        """Start network thread"""
        self.running = True
        self.network_thread = threading.Thread(target=self._network_loop, daemon=True)
        self.network_thread.start()
        
    def stop(self):
        """Stop network thread"""
        self.running = False
        if self.ws:
            asyncio.run(self._close_connection())
            
    async def _close_connection(self):
        try:
            await self.ws.close()
        except:
            pass
            
    def _network_loop(self):
        """Main network loop running in separate thread"""
        asyncio.run(self._async_network_loop())
        
    async def _async_network_loop(self):
        """Async network loop"""
        while self.running:
            try:
                async with websockets.connect(self.server_url) as websocket:
                    self.ws = websocket
                    self.connected = True
                    self.reconnect_attempts = 0
                    
                    print(f"Connected to server at {self.server_url}")
                    
                    # Send initial handshake if we have token
                    if self.token:
                        await self._send_message({
                            "action": "RECONNECT",
                            "token": self.token
                        })
                    
                    # Start send/receive tasks
                    receive_task = asyncio.create_task(self._receive_messages())
                    send_task = asyncio.create_task(self._send_messages())
                    
                    # Wait for tasks to complete
                    await asyncio.gather(receive_task, send_task)
                    
            except Exception as e:
                self.connected = False
                self.reconnect_attempts += 1
                
                if self.reconnect_attempts <= self.max_reconnect_attempts:
                    print(f"Connection failed ({e}), retrying in 3 seconds...")
                    await asyncio.sleep(3)
                else:
                    print("Max reconnection attempts reached.")
                    self.incoming_queue.put({
                        "type": "error",
                        "code": "CONNECTION_LOST",
                        "message": "Lost connection to server"
                    })
                    break
                    
    async def _receive_messages(self):
        """Receive messages from server"""
        try:
            async for message in self.ws:
                try:
                    data = json.loads(message)
                    self.incoming_queue.put(data)
                except json.JSONDecodeError as e:
                    print(f"Failed to parse message: {e}")
        except websockets.exceptions.ConnectionClosed:
            print("WebSocket connection closed")
            self.connected = False
            
    async def _send_messages(self):
        """Send messages to server"""
        while self.connected:
            try:
                if not self.outgoing_queue.empty():
                    message = self.outgoing_queue.get_nowait()
                    await self.ws.send(json.dumps(message))
                await asyncio.sleep(0.01)  # Small delay to prevent busy waiting
            except Exception as e:
                print(f"Error sending message: {e}")
                break
                
    async def _send_message(self, message):
        """Send a message (internal async version)"""
        if self.ws and self.connected:
            await self.ws.send(json.dumps(message))
            
    def send(self, message):
        """Send a message (thread-safe)"""
        if self.connected:
            self.outgoing_queue.put(message)
        else:
            print("Cannot send: Not connected to server")
            
    def has_messages(self):
        """Check if there are pending messages"""
        return not self.incoming_queue.empty()
        
    def get_message(self):
        """Get next message from queue"""
        try:
            return self.incoming_queue.get_nowait()
        except queue.Empty:
            return None
            
    def is_connected(self):
        """Check connection status"""
        return self.connected
        
    def set_token(self, token):
        """Set authentication token"""
        self.token = token
        
    def set_player_id(self, player_id):
        """Set player ID"""
        self.player_id = player_id

# ============================================================================
# GAME STATE MANAGER
# ============================================================================

class GameState:
    def __init__(self):
        self.phase = "LOBBY"  # LOBBY, HERO_SELECT, RECRUIT, COMBAT, GAME_OVER
        self.turn = 0
        self.players = {}
        self.current_player_id = None
        self.match_id = None
        
        # Local player state
        self.gold = 0
        self.max_gold = 10
        self.health = 40
        self.armor = 0
        self.tavern_tier = 1
        self.upgrade_cost = 5
        self.refresh_cost = 1
        self.tavern_upgrade_discount = 0
        
        # Collections
        self.board = []  # Minions on board
        self.hand = []   # Minions in hand
        self.shop = []   # Shop minions
        self.graveyard = []  # Minions that died last combat
        
        # Flags
        self.shop_frozen = False
        self.hero_power_used = False
        self.ready = False
        self.combat_result = None
        
        # UI state
        self.selected_minion = None
        self.dragging_minion = None
        self.hovered_slot = None
        
        # Timer
        self.timer_ms = 0
        self.last_timer_update = pygame.time.get_ticks()
        
    def update_from_server(self, server_state):
        """Update state from server message"""
        if "phase" in server_state:
            self.phase = server_state["phase"]
            
        if "turn" in server_state:
            self.turn = server_state["turn"]
            
        if "players" in server_state:
            self.players = server_state["players"]
            
        # Update local player if exists
        if self.current_player_id and self.current_player_id in self.players:
            player_data = self.players[self.current_player_id]
            
            self.gold = player_data.get("gold", self.gold)
            self.max_gold = player_data.get("max_gold", self.max_gold)
            self.health = player_data.get("health", self.health)
            self.armor = player_data.get("armor", self.armor)
            self.tavern_tier = player_data.get("tavern_tier", self.tavern_tier)
            self.upgrade_cost = player_data.get("upgrade_cost", self.upgrade_cost)
            self.refresh_cost = player_data.get("refresh_cost", self.refresh_cost)
            self.tavern_upgrade_discount = player_data.get("tavern_upgrade_discount", 0)
            
            # Shop
            if "shop" in player_data:
                self.shop = player_data["shop"]
                
            # Board
            if "board" in player_data:
                self.board = player_data["board"]
                
            # Hand
            if "hand" in player_data:
                self.hand = player_data["hand"]
                
            # Flags
            if "flags" in player_data:
                flags = player_data["flags"]
                self.shop_frozen = flags.get("shop_frozen", self.shop_frozen)
                self.hero_power_used = flags.get("hero_power_used", self.hero_power_used)
                self.ready = flags.get("ready", self.ready)
                
            # Timer
            if "timer_ms" in player_data:
                self.timer_ms = player_data["timer_ms"]
                self.last_timer_update = pygame.time.get_ticks()
                
    def update_timer(self):
        """Update timer based on elapsed time"""
        if self.timer_ms > 0:
            current_time = pygame.time.get_ticks()
            elapsed = current_time - self.last_timer_update
            self.timer_ms = max(0, self.timer_ms - elapsed)
            self.last_timer_update = current_time
            
    def get_minion_by_instance_id(self, instance_id):
        """Find minion by instance ID in board, hand, or shop"""
        # Check board
        for minion in self.board:
            if minion.get("instance_id") == instance_id:
                return minion, "board"
                
        # Check hand
        for minion in self.hand:
            if minion.get("instance_id") == instance_id:
                return minion, "hand"
                
        # Check shop
        for minion in self.shop:
            if minion and minion.get("instance_id") == instance_id:
                return minion, "shop"
                
        return None, None
        
    def can_buy_minion(self):
        """Check if player can buy a minion"""
        return self.gold >= 3 and len(self.hand) < 10
        
    def can_refresh_shop(self):
        """Check if player can refresh shop"""
        return self.gold >= self.refresh_cost
        
    def can_upgrade_tavern(self):
        """Check if player can upgrade tavern"""
        actual_cost = max(self.upgrade_cost - self.tavern_upgrade_discount, 2)
        return self.gold >= actual_cost and self.tavern_tier < 6
        
    def get_upgrade_cost(self):
        """Get actual upgrade cost with discount"""
        return max(self.upgrade_cost - self.tavern_upgrade_discount, 2)

# ============================================================================
# UI COMPONENTS
# ============================================================================

class Button:
    def __init__(self, rect, text, color, hover_color=None, text_color=(255, 255, 255)):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.color = color
        self.hover_color = hover_color or color
        self.text_color = text_color
        self.font = pygame.font.Font(None, 24)
        self.enabled = True
        
    def draw(self, surface, mouse_pos):
        color = self.hover_color if self.rect.collidepoint(mouse_pos) and self.enabled else self.color
        alpha = 150 if not self.enabled else 255
        
        # Draw button with transparency if disabled
        button_surface = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
        pygame.draw.rect(button_surface, (*color, alpha), (0, 0, self.rect.width, self.rect.height), border_radius=8)
        pygame.draw.rect(button_surface, (255, 255, 255, alpha), (0, 0, self.rect.width, self.rect.height), 2, border_radius=8)
        
        surface.blit(button_surface, self.rect)
        
        # Draw text
        text_surface = self.font.render(self.text, True, (*self.text_color, alpha))
        text_rect = text_surface.get_rect(center=self.rect.center)
        surface.blit(text_surface, text_rect)
        
    def is_clicked(self, mouse_pos, mouse_pressed):
        return (self.rect.collidepoint(mouse_pos) and mouse_pressed[0] and self.enabled)

class GoldDisplay:
    def __init__(self, x, y, max_gold=10):
        self.x = x
        self.y = y
        self.max_gold = max_gold
        self.crystal_size = 25
        self.spacing = 30
        
    def draw(self, surface, current_gold, max_gold):
        for i in range(self.max_gold):
            crystal_rect = pygame.Rect(
                self.x + i * self.spacing,
                self.y,
                self.crystal_size,
                self.crystal_size
            )
            
            if i < max_gold:
                if i < current_gold:
                    # Full gold crystal
                    pygame.draw.rect(surface, (255, 215, 0), crystal_rect, border_radius=5)
                    pygame.draw.rect(surface, (255, 215, 200), crystal_rect, 2, border_radius=5)
                    
                    # Number
                    font = pygame.font.Font(None, 16)
                    number = font.render(str(i + 1), True, (255, 255, 255))
                    number_rect = number.get_rect(center=crystal_rect.center)
                    surface.blit(number, number_rect)
                else:
                    # Empty crystal (available)
                    pygame.draw.rect(surface, (150, 150, 0), crystal_rect, border_radius=5)
                    pygame.draw.rect(surface, (200, 200, 100), crystal_rect, 2, border_radius=5)
            else:
                # Locked crystal
                pygame.draw.rect(surface, (100, 100, 0), crystal_rect, border_radius=5)
                pygame.draw.rect(surface, (150, 150, 50), crystal_rect, 2, border_radius=5)
                
        # Gold text
        font = pygame.font.Font(None, 32)
        gold_text = font.render(f"GOLD: {current_gold}/{max_gold}", True, (255, 215, 0))
        surface.blit(gold_text, (self.x, self.y - 40))

class TimerDisplay:
    def __init__(self, x, y, width=200, height=20):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.font = pygame.font.Font(None, 20)
        
    def draw(self, surface, time_ms):
        # Convert ms to seconds
        seconds = max(0, time_ms // 1000)
        
        # Calculate percentage for bar
        total_time = 30000  # 30 seconds default
        percentage = time_ms / total_time if total_time > 0 else 0
        
        # Draw background bar
        bg_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        pygame.draw.rect(surface, (50, 50, 50), bg_rect, border_radius=3)
        
        # Draw progress bar
        progress_width = int(self.width * percentage)
        progress_rect = pygame.Rect(self.x, self.y, progress_width, self.height)
        
        # Color based on time remaining
        if percentage > 0.5:
            color = (100, 255, 100)  # Green
        elif percentage > 0.25:
            color = (255, 255, 100)  # Yellow
        else:
            color = (255, 100, 100)  # Red
            
        pygame.draw.rect(surface, color, progress_rect, border_radius=3)
        pygame.draw.rect(surface, (200, 200, 200), bg_rect, 2, border_radius=3)
        
        # Draw time text
        time_text = self.font.render(f"Time: {seconds}s", True, (255, 255, 255))
        surface.blit(time_text, (self.x + self.width + 10, self.y))

class PlayerInfoPanel:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.font = pygame.font.Font(None, 28)
        self.small_font = pygame.font.Font(None, 22)
        
    def draw(self, surface, player_state, opponent_state=None):
        # Player info
        player_text = self.font.render(f"Player", True, (100, 200, 255))
        surface.blit(player_text, (self.x, self.y))
        
        health_text = self.small_font.render(f"Health: {player_state['health']}", True, (255, 50, 50))
        surface.blit(health_text, (self.x, self.y + 30))
        
        if player_state.get('armor', 0) > 0:
            armor_text = self.small_font.render(f"Armor: {player_state['armor']}", True, (100, 150, 255))
            surface.blit(armor_text, (self.x, self.y + 55))
            
        tier_text = self.small_font.render(f"Tavern Tier: {player_state['tavern_tier']}", True, (100, 200, 255))
        surface.blit(tier_text, (self.x, self.y + 80))
        
        # Turn info
        turn_text = self.small_font.render(f"Turn: {player_state.get('turn', 1)}", True, (255, 255, 200))
        surface.blit(turn_text, (self.x, self.y + 105))
        
        # Opponent info (if available)
        if opponent_state:
            opponent_text = self.font.render(f"Opponent", True, (255, 100, 100))
            surface.blit(opponent_text, (self.x, self.y + 140))
            
            opp_health_text = self.small_font.render(f"Health: {opponent_state['health']}", True, (255, 50, 50))
            surface.blit(opp_health_text, (self.x, self.y + 170))

# ============================================================================
# MAIN GAME CLIENT
# ============================================================================

class HearthstoneBattlegroundsClient:
    def __init__(self):
        self.screen = screen
        self.running = True
        
        # Game state
        self.game_state = GameState()
        self.network = NetworkManager()
        
        # UI Components
        self.minion_manager = MinionManager(screen)
        
        # Buttons
        self.buttons = {
            "END_TURN": Button((660, 300, 100, 50), "END TURN", (255, 100, 100), (230, 70, 70)),
            "UPGRADE": Button((230, 110, 80, 70), "UPGRADE", (50, 150, 50), (30, 130, 30)),
            "FREEZE": Button((450, 80, 80, 50), "FREEZE", (100, 100, 255), (70, 70, 230)),
            "REFRESH": Button((450, 140, 100, 50), "REFRESH", (255, 200, 50), (230, 180, 30)),
            "SELL": Button((660, 370, 80, 40), "SELL", (200, 50, 50), (180, 30, 30)),
            "HERO_POWER": Button((570, 110, 100, 50), "HERO POWER", (150, 50, 150), (130, 30, 130))
        }
        
        # Displays
        self.gold_display = GoldDisplay(30, 50)
        self.timer_display = TimerDisplay(250, 20)
        self.player_info = PlayerInfoPanel(650, 20)
        
        # Placeholders (from original code)
        self.placeholders = {
            "hero": {"rect": pygame.Rect(330, 465, 90, 120), "color": (50, 50, 100, 180), "label": "Hero"},
            "opponent_hero": {"rect": pygame.Rect(330, 70, 90, 120), "color": (100, 50, 50, 180), "label": "Opponent"},
            "players": {"rect": pygame.Rect(30, 250, 50, 200), "color": (100, 50, 50, 180), "label": "players"},
        }
        
        # Game phase specific
        self.combat_log = []
        self.combat_events = []
        self.current_combat_step = 0
        
        # Popup states
        self.discover_popup = None
        self.choose_one_popup = None
        self.error_popup = None
        
        # Start network
        self.network.start()
        
    def handle_network_messages(self):
        """Process incoming network messages"""
        while self.network.has_messages():
            message = self.network.get_message()
            if message:
                self.process_server_message(message)
                
    def process_server_message(self, message):
        """Process a message from server"""
        msg_type = message.get("type")
        
        print(f"Received message type: {msg_type}")
        
        if msg_type == "state_delta":
            self.handle_state_delta(message)
        elif msg_type == "combat_start":
            self.handle_combat_start(message)
        elif msg_type == "combat_event":
            self.handle_combat_event(message)
        elif msg_type == "combat_result":
            self.handle_combat_result(message)
        elif msg_type == "discover_offer":
            self.handle_discover_offer(message)
        elif msg_type == "choose_one_offer":
            self.handle_choose_one_offer(message)
        elif msg_type == "leaderboard_update":
            self.handle_leaderboard_update(message)
        elif msg_type == "error":
            self.handle_error(message)
        elif msg_type == "session_closed":
            self.handle_session_closed(message)
        elif msg_type == "full_game_state":
            self.handle_full_game_state(message)
        elif msg_type == "lobby_update":
            self.handle_lobby_update(message)
        elif msg_type == "hero_selection":
            self.handle_hero_selection(message)
        elif msg_type == "phase_change":
            self.handle_phase_change(message)
            
    def handle_state_delta(self, message):
        """Handle state updates from server"""
        events = message.get("events", [])
        
        for event in events:
            op = event.get("op")
            player_id = event.get("player_id")
            
            if player_id != self.game_state.current_player_id:
                continue  # Only process events for local player
                
            if op == "gold":
                self.game_state.gold = event.get("value", self.game_state.gold)
            elif op == "shop_update":
                self.update_shop(event.get("slots", []))
            elif op == "hand_add":
                self.add_to_hand(event.get("card"))
            elif op == "hand_remove":
                self.remove_from_hand(event.get("hand_index"))
            elif op == "board_insert":
                self.add_to_board(event.get("slot"), event.get("minion_data"))
            elif op == "board_update":
                self.update_board_minion(event.get("slot"), event.get("minion_data"))
            elif op == "board_remove":
                self.remove_from_board(event.get("slot"))
            elif op == "freeze_state":
                self.game_state.shop_frozen = event.get("frozen", False)
            elif op == "hero_health":
                self.game_state.health = event.get("value", self.game_state.health)
            elif op == "armor":
                self.game_state.armor = event.get("value", self.game_state.armor)
            elif op == "tavern_tier":
                self.game_state.tavern_tier = event.get("value", self.game_state.tavern_tier)
            elif op == "upgrade_cost":
                self.game_state.upgrade_cost = event.get("value", self.game_state.upgrade_cost)
            elif op == "discount":
                self.game_state.tavern_upgrade_discount = event.get("value", 0)
            elif op == "log":
                self.add_to_log(event.get("level", "info"), event.get("message", ""))
            elif op == "timer_tick":
                self.game_state.timer_ms = event.get("value", self.game_state.timer_ms)
                
    def handle_combat_start(self, message):
        """Handle combat start"""
        self.game_state.phase = "COMBAT"
        self.combat_log = []
        self.combat_events = message.get("boards", {})
        self.current_combat_step = 0
        
        # Extract boards for visualization
        player_board = self.combat_events.get(self.game_state.current_player_id, [])
        opponent_id = next((pid for pid in self.combat_events if pid != self.game_state.current_player_id), None)
        opponent_board = self.combat_events.get(opponent_id, []) if opponent_id else []
        
        print(f"Combat started! Player board: {len(player_board)}, Opponent board: {len(opponent_board)}")
        
    def handle_combat_event(self, message):
        """Handle combat events for animation"""
        self.combat_log.append(message)
        
    def handle_combat_result(self, message):
        """Handle combat result"""
        self.game_state.combat_result = message
        damage = message.get("damage", {})
        
        if self.game_state.current_player_id in damage:
            damage_taken = damage[self.game_state.current_player_id]
            self.game_state.health -= damage_taken
            
        # Transition back to recruit phase after showing results
        # In full implementation, this would trigger a timer
        self.game_state.phase = "RECRUIT"
        
    def handle_discover_offer(self, message):
        """Show discover popup"""
        self.discover_popup = {
            "request_id": message.get("request_id"),
            "options": message.get("options", []),
            "source": message.get("source")
        }
        
    def handle_choose_one_offer(self, message):
        """Show choose one popup"""
        self.choose_one_popup = {
            "request_id": message.get("request_id"),
            "options": message.get("options", []),
            "minion_id": message.get("minion_id")
        }
        
    def handle_error(self, message):
        """Show error popup"""
        self.error_popup = {
            "code": message.get("code", "UNKNOWN_ERROR"),
            "message": message.get("message", "An error occurred"),
            "retryable": message.get("retryable", False)
        }
        
        print(f"Error from server: {self.error_popup['code']} - {self.error_popup['message']}")
        
    def handle_full_game_state(self, message):
        """Handle full game state sync"""
        self.game_state.update_from_server(message)
        self.game_state.current_player_id = message.get("player_id")
        
    def handle_phase_change(self, message):
        """Handle phase changes"""
        new_phase = message.get("phase")
        self.game_state.phase = new_phase
        
        if new_phase == "RECRUIT":
            # Reset ready flag
            self.game_state.ready = False
            
    # ========================================================================
    # GAME ACTIONS - Send to Server
    # ========================================================================
    
    def send_action(self, action_type, payload=None):
        """Send action to server"""
        if not self.network.is_connected():
            print("Cannot send action: Not connected")
            return
            
        message = {
            "action": action_type,
            "token": self.network.token,
            "timestamp": int(pygame.time.get_ticks() / 1000)
        }
        
        if payload:
            message["payload"] = payload
            
        self.network.send(message)
        
    def buy_minion(self, shop_slot):
        """Buy minion from shop"""
        self.send_action("BUY", {
            "shop_slot": shop_slot
        })
        
    def sell_minion(self, board_slot):
        """Sell minion from board"""
        self.send_action("SELL", {
            "board_slot": board_slot
        })
        
    def play_minion(self, hand_index, board_slot):
        """Play minion from hand to board"""
        self.send_action("PLAY", {
            "hand_index": hand_index,
            "board_slot": board_slot
        })
        
    def refresh_shop(self):
        """Refresh shop"""
        self.send_action("REFRESH")
        
    def freeze_shop(self):
        """Toggle shop freeze"""
        self.send_action("FREEZE")
        
    def upgrade_tavern(self):
        """Upgrade tavern tier"""
        self.send_action("UPGRADE")
        
    def use_hero_power(self, target_slot=None):
        """Use hero power"""
        payload = {}
        if target_slot is not None:
            payload["target_slot"] = target_slot
        self.send_action("HERO_POWER", payload)
        
    def end_turn(self):
        """End current turn"""
        self.send_action("END_TURN")
        
    def discover_choice(self, request_id, card_id):
        """Send discover choice"""
        self.send_action("DISCOVER_CHOICE", {
            "request_id": request_id,
            "card_id": card_id
        })
        
    def choose_one_choice(self, request_id, option):
        """Send choose one choice"""
        self.send_action("CHOOSE_ONE", {
            "request_id": request_id,
            "option": option
        })
        
    def ready_up(self):
        """Mark player as ready"""
        self.send_action("READY")
        
    # ========================================================================
    # UI HELPER METHODS
    # ========================================================================
    
    def update_shop(self, shop_slots):
        """Update shop from server data"""
        self.game_state.shop = []
        
        for slot_data in shop_slots:
            if slot_data is None:
                self.game_state.shop.append(None)
            else:
                # Create minion object from data
                minion_data = {
                    "card_id": slot_data.get("card_id"),
                    "instance_id": slot_data.get("instance_id", f"shop_{uuid.uuid4().hex[:8]}"),
                    "attack": slot_data.get("attack", 1),
                    "health": slot_data.get("health", 1),
                    "keywords": slot_data.get("keywords", []),
                    "tier": slot_data.get("tier", 1),
                    "name": slot_data.get("name", "Unknown"),
                    "cost": slot_data.get("cost", 3)
                }
                self.game_state.shop.append(minion_data)
                
    def add_to_hand(self, card_data):
        """Add minion to hand"""
        if len(self.game_state.hand) < 10:
            self.game_state.hand.append(card_data)
            
    def add_to_board(self, slot, minion_data):
        """Add minion to board"""
        if len(self.game_state.board) < 7 and 0 <= slot < 7:
            # Make sure slot is not occupied
            occupied = any(m.get("board_slot") == slot for m in self.game_state.board)
            if not occupied:
                minion_data["board_slot"] = slot
                self.game_state.board.append(minion_data)
                
    def update_board_minion(self, slot, minion_data):
        """Update board minion stats"""
        for i, minion in enumerate(self.game_state.board):
            if minion.get("board_slot") == slot:
                self.game_state.board[i].update(minion_data)
                break
                
    def add_to_log(self, level, message):
        """Add message to game log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {level.upper()}: {message}"
        print(log_entry)
        
    def draw_placeholder(self, ph_data):
        """Draw placeholder from original code"""
        ph_surface = pygame.Surface((ph_data["rect"].width, ph_data["rect"].height), pygame.SRCALPHA)
        pygame.draw.rect(ph_surface, ph_data["color"], 
                        (0, 0, ph_data["rect"].width, ph_data["rect"].height), 
                        border_radius=5)
        pygame.draw.rect(ph_surface, (255, 255, 255), 
                        (0, 0, ph_data["rect"].width, ph_data["rect"].height), 
                        2, border_radius=5)
        
        self.screen.blit(ph_surface, ph_data["rect"])
        
        font = pygame.font.Font(None, 20)
        label = font.render(ph_data["label"], True, (255, 255, 255))
        label_rect = label.get_rect(center=ph_data["rect"].center)
        self.screen.blit(label, label_rect)
        
    def draw_shop(self):
        """Draw shop minions"""
        shop_positions = [(130, 200), (230, 200), (330, 200), (430, 200), (530, 200)]
        
        for i, slot_data in enumerate(self.game_state.shop):
            if i < len(shop_positions) and slot_data is not None:
                x, y = shop_positions[i]
                
                # Draw slot background
                slot_rect = pygame.Rect(x, y, 70, 100)
                pygame.draw.rect(self.screen, (40, 40, 60, 150), slot_rect)
                pygame.draw.rect(self.screen, (100, 100, 150), slot_rect, 2)
                
                # Try to load and draw minion image
                try:
                    card_id = slot_data.get("card_id", "unknown")
                    image = pygame.image.load(f"./bgknowhow-main/images/minions/{card_id}_render_80.webp")
                    image = pygame.transform.scale(image, (100, 140))
                    img_rect = image.get_rect(center=(x + 35, y + 50))
                    self.screen.blit(image, img_rect)
                except:
                    # Fallback rectangle
                    pygame.draw.rect(self.screen, (100, 100, 150), 
                                    pygame.Rect(x + 10, y + 10, 50, 80))
                    
                # Draw cost
                font = pygame.font.Font(None, 20)
                cost_text = font.render(f"{slot_data.get('cost', 3)}G", True, (255, 215, 0))
                cost_rect = cost_text.get_rect(center=(x + 35, y - 10))
                self.screen.blit(cost_text, cost_rect)
                
                # Draw frozen indicator
                if self.game_state.shop_frozen:
                    freeze_font = pygame.font.Font(None, 24)
                    freeze_text = freeze_font.render("FROZEN", True, (100, 200, 255))
                    self.screen.blit(freeze_text, (350, 280))
                    
    def draw_board(self):
        """Draw board minions"""
        board_positions = [
            (105, 340), (185, 340), (265, 340), (345, 340),
            (425, 340), (505, 340), (585, 340)
        ]
        
        for minion_data in self.game_state.board:
            slot = minion_data.get("board_slot", 0)
            if 0 <= slot < len(board_positions):
                x, y = board_positions[slot]
                
                # Draw minion using minion_manager or custom drawing
                try:
                    # Try to create minion object
                    minion = create_minion(
                        self.screen, x, y,
                        minion_data.get("card_id", "unknown"),
                        minion_data.get("golden", False)
                    )
                    
                    # Update stats
                    minion.current_attack = minion_data.get("attack", minion.base_attack)
                    minion.current_health = minion_data.get("health", minion.base_health)
                    minion.keywords = minion_data.get("keywords", [])
                    
                    minion.draw()
                except Exception as e:
                    print(f"Error drawing minion: {e}")
                    # Draw fallback
                    pygame.draw.rect(self.screen, (150, 150, 200), 
                                    pygame.Rect(x, y, 70, 100))
                    
    def draw_hand(self):
        """Draw hand minions"""
        hand_positions = [
            (180, 580), (270, 580), (360, 580), (450, 580), (540, 580),
        ]
        
        for i, minion_data in enumerate(self.game_state.hand):
            if i < len(hand_positions):
                x, y = hand_positions[i]
                
                try:
                    minion = create_minion(
                        self.screen, x, y,
                        minion_data.get("card_id", "unknown"),
                        minion_data.get("golden", False)
                    )
                    
                    minion.current_attack = minion_data.get("attack", minion.base_attack)
                    minion.current_health = minion_data.get("health", minion.base_health)
                    minion.keywords = minion_data.get("keywords", [])
                    
                    minion.draw()
                except Exception as e:
                    print(f"Error drawing hand minion: {e}")
                    pygame.draw.rect(self.screen, (200, 150, 150), 
                                    pygame.Rect(x, y, 70, 100))
                    
    def update_button_states(self):
        """Update button enabled states based on game state"""
        # End Turn button - always enabled in recruit phase
        self.buttons["END_TURN"].enabled = (self.game_state.phase == "RECRUIT")
        
        # Upgrade button
        self.buttons["UPGRADE"].enabled = self.game_state.can_upgrade_tavern()
        
        # Freeze button - always enabled
        self.buttons["FREEZE"].enabled = True
        
        # Refresh button
        self.buttons["REFRESH"].enabled = self.game_state.can_refresh_shop()
        
        # Sell button - only enabled if minion selected
        self.buttons["SELL"].enabled = (self.game_state.selected_minion is not None)
        
        # Hero Power button - depends on hero and gold
        hero_power_cost = 1  # Default cost, should come from game state
        self.buttons["HERO_POWER"].enabled = (
            self.game_state.phase == "RECRUIT" and
            not self.game_state.hero_power_used and
            self.game_state.gold >= hero_power_cost
        )
        
    def draw_phase_indicator(self):
        """Draw current phase indicator"""
        phase_colors = {
            "LOBBY": (100, 100, 255),
            "HERO_SELECT": (150, 100, 255),
            "RECRUIT": (100, 255, 100),
            "COMBAT": (255, 100, 100),
            "GAME_OVER": (100, 100, 100)
        }
        
        color = phase_colors.get(self.game_state.phase, (255, 255, 255))
        
        # Draw phase bar at top
        phase_bar = pygame.Rect(0, 0, 800, 5)
        pygame.draw.rect(self.screen, color, phase_bar)
        
        # Draw phase text
        font = pygame.font.Font(None, 32)
        phase_text = font.render(f"Phase: {self.game_state.phase}", True, color)
        self.screen.blit(phase_text, (300, 10))
        
    def draw(self):
        """Draw everything"""
        # Draw background
        self.screen.blit(game_bg, (0, 0))
        
        # Draw phase indicator
        self.draw_phase_indicator()
        
        # Draw placeholders
        for ph_key in self.placeholders:
            self.draw_placeholder(self.placeholders[ph_key])
            
        # Draw game elements based on phase
        if self.game_state.phase == "RECRUIT":
            self.draw_shop()
            self.draw_board()
            self.draw_hand()
            
            # Update and draw buttons
            mouse_pos = pygame.mouse.get_pos()
            self.update_button_states()
            for button in self.buttons.values():
                button.draw(self.screen, mouse_pos)
                
            # Draw displays
            self.gold_display.draw(self.screen, self.game_state.gold, self.game_state.max_gold)
            self.timer_display.draw(self.screen, self.game_state.timer_ms)
            
            # Draw player info
            player_info = {
                "health": self.game_state.health,
                "armor": self.game_state.armor,
                "tavern_tier": self.game_state.tavern_tier,
                "turn": self.game_state.turn
            }
            self.player_info.draw(self.screen, player_info)
            
        elif self.game_state.phase == "COMBAT":
            # Draw combat view
            self.draw_combat_view()
            
        elif self.game_state.phase == "LOBBY":
            self.draw_lobby_view()
            
        elif self.game_state.phase == "HERO_SELECT":
            self.draw_hero_selection()
            
        # Draw popups if any
        if self.discover_popup:
            self.draw_discover_popup()
        if self.choose_one_popup:
            self.draw_choose_one_popup()
        if self.error_popup:
            self.draw_error_popup()
            
        # Draw help text
        help_font = pygame.font.Font(None, 18)
        help_text = help_font.render("Click minions to buy, drag to board, right-click to sell", 
                                    True, (200, 200, 255))
        self.screen.blit(help_text, (200, 680))
        
    def draw_combat_view(self):
        """Draw combat animation"""
        # This would be expanded to show combat animations
        font = pygame.font.Font(None, 48)
        combat_text = font.render("COMBAT IN PROGRESS", True, (255, 50, 50))
        text_rect = combat_text.get_rect(center=(400, 350))
        self.screen.blit(combat_text, text_rect)
        
        if self.game_state.combat_result:
            result_font = pygame.font.Font(None, 36)
            damage = self.game_state.combat_result.get("damage", {})
            if self.game_state.current_player_id in damage:
                result_text = result_font.render(
                    f"You took {damage[self.game_state.current_player_id]} damage!", 
                    True, (255, 100, 100)
                )
                result_rect = result_text.get_rect(center=(400, 420))
                self.screen.blit(result_text, result_rect)
                
    def draw_lobby_view(self):
        """Draw lobby screen"""
        font = pygame.font.Font(None, 48)
        lobby_text = font.render("WAITING FOR PLAYERS...", True, (100, 200, 255))
        text_rect = lobby_text.get_rect(center=(400, 300))
        self.screen.blit(lobby_text, text_rect)
        
        small_font = pygame.font.Font(None, 24)
        info_text = small_font.render("4 players needed to start", True, (200, 200, 255))
        info_rect = info_text.get_rect(center=(400, 360))
        self.screen.blit(info_text, info_rect)
        
    def draw_hero_selection(self):
        """Draw hero selection screen"""
        font = pygame.font.Font(None, 48)
        title_text = font.render("SELECT YOUR HERO", True, (255, 215, 0))
        title_rect = title_text.get_rect(center=(400, 100))
        self.screen.blit(title_text, title_rect)
        
        # This would be expanded to show hero options
        heroes = ["Sylvanas", "Lich King", "Millhouse", "Yogg-Saron"]
        for i, hero in enumerate(heroes):
            hero_font = pygame.font.Font(None, 36)
            hero_text = hero_font.render(hero, True, (200, 200, 255))
            hero_rect = hero_text.get_rect(center=(200 + i * 150, 300))
            self.screen.blit(hero_text, hero_rect)
            
    def draw_discover_popup(self):
        """Draw discover popup"""
        if not self.discover_popup:
            return
            
        # Draw semi-transparent overlay
        overlay = pygame.Surface((800, 700), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        self.screen.blit(overlay, (0, 0))
        
        # Draw popup box
        popup_rect = pygame.Rect(200, 200, 400, 300)
        pygame.draw.rect(self.screen, (50, 50, 80), popup_rect, border_radius=10)
        pygame.draw.rect(self.screen, (100, 100, 200), popup_rect, 3, border_radius=10)
        
        # Draw title
        font = pygame.font.Font(None, 36)
        title_text = font.render("DISCOVER A CARD", True, (255, 215, 0))
        title_rect = title_text.get_rect(center=(400, 230))
        self.screen.blit(title_text, title_rect)
        
        # Draw options
        options = self.discover_popup["options"]
        for i, option in enumerate(options[:3]):  # Max 3 options
            option_rect = pygame.Rect(250 + i * 100, 300, 80, 120)
            pygame.draw.rect(self.screen, (100, 100, 150), option_rect)
            pygame.draw.rect(self.screen, (200, 200, 255), option_rect, 2)
            
            # Draw card name
            small_font = pygame.font.Font(None, 16)
            name_text = small_font.render(option.get("card_id", "Unknown"), True, (255, 255, 255))
            name_rect = name_text.get_rect(center=option_rect.center)
            self.screen.blit(name_text, name_rect)
            
    def draw_error_popup(self):
        """Draw error popup"""
        if not self.error_popup:
            return
            
        # Draw error box
        error_rect = pygame.Rect(250, 300, 300, 150)
        pygame.draw.rect(self.screen, (80, 50, 50), error_rect, border_radius=10)
        pygame.draw.rect(self.screen, (200, 100, 100), error_rect, 3, border_radius=10)
        
        # Draw error text
        font = pygame.font.Font(None, 24)
        error_text = font.render(f"Error: {self.error_popup['code']}", True, (255, 150, 150))
        error_rect_text = error_text.get_rect(center=(400, 330))
        self.screen.blit(error_text, error_rect_text)
        
        message_font = pygame.font.Font(None, 20)
        message_text = message_font.render(self.error_popup['message'], True, (255, 200, 200))
        message_rect = message_text.get_rect(center=(400, 370))
        self.screen.blit(message_text, message_rect)
        
    def get_minion_at_position(self, x, y):
        """Get minion at mouse position"""
        # Check shop
        shop_positions = [(130, 200), (230, 200), (330, 200), (430, 200), (530, 200)]
        for i, (sx, sy) in enumerate(shop_positions):
            if i < len(self.game_state.shop) and self.game_state.shop[i] is not None:
                shop_rect = pygame.Rect(sx, sy, 70, 100)
                if shop_rect.collidepoint(x, y):
                    return self.game_state.shop[i], "shop", i
                    
        # Check board
        board_positions = [
            (105, 340), (185, 340), (265, 340), (345, 340),
            (425, 340), (505, 340), (585, 340)
        ]
        for minion in self.game_state.board:
            slot = minion.get("board_slot", 0)
            if 0 <= slot < len(board_positions):
                bx, by = board_positions[slot]
                board_rect = pygame.Rect(bx, by, 70, 100)
                if board_rect.collidepoint(x, y):
                    return minion, "board", slot
                    
        # Check hand
        hand_positions = [
            (180, 580), (270, 580), (360, 580), (450, 580), (540, 580),
        ]
        for i, minion in enumerate(self.game_state.hand):
            if i < len(hand_positions):
                hx, hy = hand_positions[i]
                hand_rect = pygame.Rect(hx, hy, 70, 100)
                if hand_rect.collidepoint(x, y):
                    return minion, "hand", i
                    
        return None, None, None
        
    def run(self):
        """Main game loop"""
        while self.running:
            # Handle network messages
            self.handle_network_messages()
            
            # Update game state
            self.game_state.update_timer()
            
            # Process events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    self.network.stop()
                    
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    mouse_pos = pygame.mouse.get_pos()
                    mouse_pressed = pygame.mouse.get_pressed()
                    
                    # Handle button clicks
                    if self.buttons["END_TURN"].is_clicked(mouse_pos, mouse_pressed):
                        self.end_turn()
                    elif self.buttons["UPGRADE"].is_clicked(mouse_pos, mouse_pressed):
                        self.upgrade_tavern()
                    elif self.buttons["FREEZE"].is_clicked(mouse_pos, mouse_pressed):
                        self.freeze_shop()
                    elif self.buttons["REFRESH"].is_clicked(mouse_pos, mouse_pressed):
                        self.refresh_shop()
                    elif self.buttons["SELL"].is_clicked(mouse_pos, mouse_pressed):
                        if self.game_state.selected_minion:
                            # Find selected minion slot
                            for i, minion in enumerate(self.game_state.board):
                                if minion.get("instance_id") == self.game_state.selected_minion.get("instance_id"):
                                    self.sell_minion(i)
                                    break
                    elif self.buttons["HERO_POWER"].is_clicked(mouse_pos, mouse_pressed):
                        self.use_hero_power()
                        
                    # Handle minion clicks
                    elif event.button == 1:  # Left click
                        minion, location, index = self.get_minion_at_position(*mouse_pos)
                        if minion:
                            if location == "shop":
                                self.buy_minion(index)
                            elif location == "hand":
                                self.game_state.selected_minion = minion
                            elif location == "board":
                                self.game_state.selected_minion = minion
                                
                    elif event.button == 3:  # Right click
                        minion, location, index = self.get_minion_at_position(*mouse_pos)
                        if minion and location == "board":
                            self.sell_minion(index)
                            
                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    # Handle drag and drop
                    if (self.game_state.selected_minion and 
                        self.game_state.selected_minion.get("location") == "hand"):
                        
                        mouse_pos = pygame.mouse.get_pos()
                        
                        # Check if dropped on board slot
                        board_positions = [
                            (105, 340), (185, 340), (265, 340), (345, 340),
                            (425, 340), (505, 340), (585, 340)
                        ]
                        
                        target_slot = None
                        for slot_index, (sx, sy) in enumerate(board_positions):
                            slot_rect = pygame.Rect(sx, sy, 70, 100)
                            if slot_rect.collidepoint(mouse_pos):
                                # Check if slot is empty
                                occupied = any(
                                    m.get("board_slot") == slot_index 
                                    for m in self.game_state.board
                                )
                                if not occupied:
                                    target_slot = slot_index
                                break
                                
                        if target_slot is not None:
                            # Find hand index
                            for i, minion in enumerate(self.game_state.hand):
                                if minion.get("instance_id") == self.game_state.selected_minion.get("instance_id"):
                                    self.play_minion(i, target_slot)
                                    break
                                    
                        self.game_state.selected_minion = None
                        
                elif event.type == pygame.KEYDOWN:
                    # Keyboard shortcuts
                    if event.key == pygame.K_r:
                        self.refresh_shop()
                    elif event.key == pygame.K_u:
                        self.upgrade_tavern()
                    elif event.key == pygame.K_f:
                        self.freeze_shop()
                    elif event.key == pygame.K_SPACE:
                        self.end_turn()
                    elif event.key == pygame.K_ESCAPE:
                        self.game_state.selected_minion = None
                        
            # Draw everything
            self.draw()
            
            # Update display
            pygame.display.flip()
            clock.tick(60)
            
        pygame.quit()
        sys.exit()

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    # Parse command line arguments
    import argparse
    
    parser = argparse.ArgumentParser(description="Hearthstone Battlegrounds Client")
    parser.add_argument("--server", default="ws://localhost:8888", help="WebSocket server URL")
    parser.add_argument("--offline", action="store_true", help="Run in offline mode")
    parser.add_argument("--token", help="Authentication token for reconnection")
    
    args = parser.parse_args()
    
    # Create and run client
    client = HearthstoneBattlegroundsClient()
    
    if args.token:
        client.network.set_token(args.token)
        
    if not args.offline:
        client.network.server_url = args.server
        
    print("Starting Hearthstone Battlegrounds Client...")
    print(f"Server: {args.server}")
    print(f"Offline mode: {args.offline}")
    
    client.run()