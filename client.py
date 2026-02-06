# client_fixed.py - Hearthstone Battlegrounds Client (Fixed for Server Compatibility)
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

# Initialize pygame
pygame.init()

# Screen setup
screen = pygame.display.set_mode((800, 700))
pygame.display.set_caption("Hearthstone Battlegrounds - Client")
icon = pygame.image.load("./image_add/Screenshot 2025-11-27 151541.png")
pygame.display.set_icon(icon)

# Load background
try:
    game_bg = pygame.transform.scale(
        pygame.image.load(r"./image_add/Screenshot 2025-12-16 175133.png"),
        (800, 700)
    )
except:
    # Fallback background
    game_bg = pygame.Surface((800, 700))
    game_bg.fill((30, 30, 50))

clock = pygame.time.Clock()

# ============================================================================
# NETWORK MANAGER - Fixed for Server Compatibility
# ============================================================================

class NetworkManager:
    def __init__(self, server_url="ws://localhost:8888"):
        self.server_url = server_url
        self.ws = None
        self.connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.token = None
        self.player_name = "Player"
        
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
                    
                    print(f"✅ Connected to server at {self.server_url}")
                    
                    # Send initial handshake if we have token
                    if self.token:
                        await self._send_message({
                            "type": "RECONNECT",
                            "token": self.token,
                            "name": self.player_name
                        })
                    else:
                        # Request to join
                        await self._send_message({
                            "type": "JOIN",
                            "token": str(uuid.uuid4()),
                            "name": self.player_name
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
                    print(f"❌ Connection failed ({e}), retrying in 3 seconds...")
                    await asyncio.sleep(3)
                else:
                    print("❌ Max reconnection attempts reached.")
                    self.incoming_queue.put({
                        "type": "ERROR",
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
                    print(f"❌ Failed to parse message: {e}")
        except websockets.exceptions.ConnectionClosed:
            print("❌ WebSocket connection closed")
            self.connected = False
            
    async def _send_messages(self):
        """Send messages to server"""
        while self.connected:
            try:
                if not self.outgoing_queue.empty():
                    message = self.outgoing_queue.get_nowait()
                    await self.ws.send(json.dumps(message))
                await asyncio.sleep(0.01)
            except Exception as e:
                print(f"❌ Error sending message: {e}")
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
            print("❌ Cannot send: Not connected to server")
            
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
        
    def set_player_name(self, name):
        """Set player name"""
        self.player_name = name

# ============================================================================
# GAME STATE MANAGER - Fixed for Server Compatibility
# ============================================================================

class GameState:
    def __init__(self):
        self.phase = "LOBBY"  # LOBBY, HERO_SELECT, RECRUIT, COMBAT_CALC, LOG_REPLAY, GAME_OVER
        self.turn_number = 0
        self.players = []
        self.my_player = None
        self.my_token = None
        
        # Local player state
        self.gold = 3
        self.health = 40
        self.tavern_tier = 1
        self.upgrade_cost = 5
        self.refresh_cost = 1
        
        # Collections
        self.board = []  # Minions on board
        self.hand = []   # Minions in hand
        self.shop = []   # Shop minions (5 slots)
        self.graveyard = []  # Minions that died last combat
        
        # Hero
        self.hero = None
        self.hero_offers = []
        
        # Flags
        self.shop_frozen = False
        self.hero_power_used = False
        self.ready = False
        self.is_zombie = False
        
        # Combat
        self.combat_log = None
        self.combat_result = None
        
        # UI state
        self.selected_minion = None
        self.dragging_minion = None
        
        # Timer
        self.phase_timer = 0
        self.grace_timer = 0
        self.in_grace_period = False
        
    def update_from_server(self, server_data):
        """Update state from server full_state message"""
        try:
            # Update phase
            if "phase" in server_data:
                self.phase = server_data["phase"]
                
            if "turn_number" in server_data:
                self.turn_number = server_data["turn_number"]
                
            if "phase_timer" in server_data:
                self.phase_timer = server_data["phase_timer"]
                
            if "grace_timer" in server_data:
                self.grace_timer = server_data["grace_timer"]
                
            if "in_grace_period" in server_data:
                self.in_grace_period = server_data["in_grace_period"]
            
            # Update players
            if "players" in server_data:
                self.players = server_data["players"]
                
                # Find my player
                for player in self.players:
                    if player.get("token") == self.my_token:
                        self.my_player = player
                        self.update_my_state(player)
                        break
                        
        except Exception as e:
            print(f"❌ Error updating from server: {e}")
            
    def update_my_state(self, player_data):
        """Update my player's specific state"""
        self.gold = player_data.get("gold", self.gold)
        self.health = player_data.get("health", self.health)
        self.ready = player_data.get("is_ready", self.ready)
        self.is_zombie = player_data.get("is_zombie", self.is_zombie)
        
        # Hero
        if "hero" in player_data:
            self.hero = player_data["hero"]
            
        # Shop, Board, Hand (only if full state)
        if "shop" in player_data:
            self.shop = self.parse_minions(player_data["shop"])
            
        if "board" in player_data:
            self.board = self.parse_minions(player_data["board"])
            
        if "hand" in player_data:
            self.hand = self.parse_minions(player_data["hand"])
            
        # Shop state
        if "tavern_tier" in player_data:
            self.tavern_tier = player_data["tavern_tier"]
            
    def parse_minions(self, minions_data):
        """Parse minions from server data"""
        minions = []
        for item in minions_data:
            if item is not None:
                minions.append(item)
        return minions
        
    def set_token(self, token):
        """Set my token"""
        self.my_token = token
        
    def get_minion_at_position(self, x, y, location):
        """Get minion at mouse position in specific location"""
        positions = []
        
        if location == "shop":
            positions = [(130, 200), (230, 200), (330, 200), (430, 200), (530, 200)]
            collection = self.shop
        elif location == "board":
            positions = [(105, 340), (185, 340), (265, 340), (345, 340),
                        (425, 340), (505, 340), (585, 340)]
            collection = self.board
        elif location == "hand":
            positions = [(180, 580), (270, 580), (360, 580), (450, 580), (540, 580)]
            collection = self.hand
            
        for i, (pos_x, pos_y) in enumerate(positions):
            if i < len(collection) and collection[i] is not None:
                rect = pygame.Rect(pos_x, pos_y, 70, 100)
                if rect.collidepoint(x, y):
                    return collection[i], i
                    
        return None, -1
        
    def can_buy_minion(self):
        """Check if player can buy a minion"""
        return self.gold >= 3 and len(self.hand) < 10
        
    def can_refresh_shop(self):
        """Check if player can refresh shop"""
        return self.gold >= self.refresh_cost
        
    def can_upgrade_tavern(self):
        """Check if player can upgrade tavern"""
        return self.gold >= self.upgrade_cost and self.tavern_tier < 6

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
        
    def draw(self, surface, current_gold):
        for i in range(self.max_gold):
            crystal_rect = pygame.Rect(
                self.x + i * self.spacing,
                self.y,
                self.crystal_size,
                self.crystal_size
            )
            
            if i < current_gold:
                # Full gold crystal
                pygame.draw.rect(surface, (255, 215, 0), crystal_rect, border_radius=5)
                pygame.draw.rect(surface, (255, 215, 200), crystal_rect, 2, border_radius=5)
            else:
                # Empty crystal
                pygame.draw.rect(surface, (150, 150, 0), crystal_rect, border_radius=5)
                pygame.draw.rect(surface, (200, 200, 100), crystal_rect, 2, border_radius=5)
                
        # Gold text
        font = pygame.font.Font(None, 32)
        gold_text = font.render(f"GOLD: {current_gold}", True, (255, 215, 0))
        surface.blit(gold_text, (self.x, self.y - 40))

class TimerDisplay:
    def __init__(self, x, y, width=200, height=20):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.font = pygame.font.Font(None, 20)
        
    def draw(self, surface, time_seconds):
        # Calculate percentage for bar
        total_time = 30  # 30 seconds default
        percentage = min(1.0, time_seconds / total_time)
        
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
        time_text = self.font.render(f"Time: {int(time_seconds)}s", True, (255, 255, 255))
        surface.blit(time_text, (self.x + self.width + 10, self.y))

class MinionCard:
    def __init__(self, screen, x, y, minion_data):
        self.screen = screen
        self.x = x
        self.y = y
        self.data = minion_data
        self.width = 70
        self.height = 100
        
    def draw(self):
        # Draw card background
        card_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        
        # Color based on tier
        tier_colors = {
            1: (100, 100, 150),
            2: (100, 150, 100),
            3: (150, 150, 100),
            4: (150, 100, 150),
            5: (200, 150, 100),
            6: (200, 100, 100)
        }
        
        tier = self.data.get("tier", 1)
        color = tier_colors.get(tier, (100, 100, 100))
        
        pygame.draw.rect(self.screen, color, card_rect)
        pygame.draw.rect(self.screen, (255, 255, 255), card_rect, 2)
        
        # Draw minion info
        font_small = pygame.font.Font(None, 14)
        font_large = pygame.font.Font(None, 20)
        
        # Name (truncated)
        name = self.data.get("name", "Minion")
        if len(name) > 10:
            name = name[:10] + "..."
        name_text = font_small.render(name, True, (255, 255, 255))
        self.screen.blit(name_text, (self.x + 5, self.y + 5))
        
        # Attack/Health
        attack = self.data.get("attack", 1)
        health = self.data.get("health", 1)
        
        # Attack (red circle on left)
        attack_rect = pygame.Rect(self.x + 5, self.y + self.height - 25, 20, 20)
        pygame.draw.rect(self.screen, (200, 50, 50), attack_rect, border_radius=10)
        attack_text = font_large.render(str(attack), True, (255, 255, 255))
        attack_text_rect = attack_text.get_rect(center=attack_rect.center)
        self.screen.blit(attack_text, attack_text_rect)
        
        # Health (green circle on right)
        health_rect = pygame.Rect(self.x + self.width - 25, self.y + self.height - 25, 20, 20)
        pygame.draw.rect(self.screen, (50, 200, 50), health_rect, border_radius=10)
        health_text = font_large.render(str(health), True, (255, 255, 255))
        health_text_rect = health_text.get_rect(center=health_rect.center)
        self.screen.blit(health_text, health_text_rect)
        
        # Golden indicator
        if self.data.get("golden", False):
            golden_text = font_small.render("GOLD", True, (255, 215, 0))
            self.screen.blit(golden_text, (self.x + 5, self.y + 25))

# ============================================================================
# MAIN GAME CLIENT - Fixed for Server Compatibility
# ============================================================================

class HearthstoneBattlegroundsClient:
    def __init__(self):
        self.screen = screen
        self.running = True
        
        # Game state
        self.game_state = GameState()
        self.network = NetworkManager()
        
        # UI Components
        self.buttons = {
            "END_TURN": Button((660, 300, 100, 50), "END TURN", (255, 100, 100), (230, 70, 70)),
            "UPGRADE": Button((230, 110, 80, 70), "UPGRADE", (50, 150, 50), (30, 130, 30)),
            "FREEZE": Button((450, 80, 80, 50), "FREEZE", (100, 100, 255), (70, 70, 230)),
            "REFRESH": Button((450, 140, 100, 50), "REFRESH", (255, 200, 50), (230, 180, 30)),
            "SELL": Button((660, 370, 80, 40), "SELL", (200, 50, 50), (180, 30, 30)),
            "HERO_POWER": Button((570, 110, 100, 50), "HERO POWER", (150, 50, 150), (130, 30, 130)),
            "READY": Button((350, 600, 100, 50), "READY", (100, 200, 100), (80, 180, 80))
        }
        
        # Displays
        self.gold_display = GoldDisplay(30, 50)
        self.timer_display = TimerDisplay(250, 20)
        
        # Input
        self.input_box = pygame.Rect(300, 500, 200, 40)
        self.input_text = ""
        self.input_active = False
        
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
        msg_type = message.get("type", "")
        
        print(f"📥 Received: {msg_type}")
        
        if msg_type == "WELCOME":
            self.handle_welcome(message)
        elif msg_type == "JOIN_SUCCESS":
            self.handle_join_success(message)
        elif msg_type == "PLAYER_JOINED":
            self.handle_player_joined(message)
        elif msg_type == "FULL_STATE":
            self.handle_full_state(message)
        elif msg_type == "PHASE_CHANGE":
            self.handle_phase_change(message)
        elif msg_type == "PLAYER_READY":
            self.handle_player_ready(message)
        elif msg_type == "HERO_OFFER":
            self.handle_hero_offer(message)
        elif msg_type == "PLAYER_HERO_SELECTED":
            self.handle_player_hero_selected(message)
        elif msg_type == "HERO_SELECTED":
            self.handle_hero_selected(message)
        elif msg_type == "BUY_SUCCESS":
            self.handle_buy_success(message)
        elif msg_type == "SELL_SUCCESS":
            self.handle_sell_success(message)
        elif msg_type == "PLAY_SUCCESS":
            self.handle_play_success(message)
        elif msg_type == "REFRESH_SUCCESS":
            self.handle_refresh_success(message)
        elif msg_type == "UPGRADE_SUCCESS":
            self.handle_upgrade_success(message)
        elif msg_type == "FREEZE_SUCCESS":
            self.handle_freeze_success(message)
        elif msg_type == "GRACE_PERIOD":
            self.handle_grace_period(message)
        elif msg_type == "COMBAT_RESULT":
            self.handle_combat_result(message)
        elif msg_type == "GAME_OVER":
            self.handle_game_over(message)
        elif msg_type == "ERROR":
            self.handle_error(message)
        elif msg_type == "RECONNECT_SUCCESS":
            self.handle_reconnect_success(message)
            
    def handle_welcome(self, message):
        """Handle welcome message"""
        token = message.get("token")
        if token:
            self.game_state.set_token(token)
            self.network.set_token(token)
            print(f"🔑 Token received: {token}")
            
    def handle_join_success(self, message):
        """Handle join success"""
        token = message.get("token")
        name = message.get("name")
        print(f"✅ Joined as {name} (token: {token})")
        
    def handle_player_joined(self, message):
        """Handle player joined notification"""
        name = message.get("name", "Unknown")
        count = message.get("player_count", 0)
        print(f"👤 {name} joined ({count} players)")
        
    def handle_full_state(self, message):
        """Handle full game state"""
        data = message.get("data", {})
        self.game_state.update_from_server(data)
        print(f"🔄 Game state updated - Phase: {self.game_state.phase}")
        
    def handle_phase_change(self, message):
        """Handle phase change"""
        phase = message.get("phase", "")
        time_left = message.get("time", 0)
        print(f"🔄 Phase changed to: {phase} (Time: {time_left}s)")
        
    def handle_hero_offer(self, message):
        """Handle hero offer"""
        heroes = message.get("heroes", [])
        self.game_state.hero_offers = heroes
        print(f"🎭 Hero offers: {heroes}")
        
    # ========================================================================
    # ACTION HANDLERS
    # ========================================================================
    
    def send_join(self, name):
        """Send join request"""
        token = str(uuid.uuid4())
        self.network.send({
            "type": "JOIN",
            "token": token,
            "name": name
        })
        self.game_state.set_token(token)
        self.network.set_token(token)
        
    def send_ready(self, ready=True):
        """Send ready status"""
        self.network.send({
            "type": "READY",
            "ready": ready
        })
        
    def send_select_hero(self, hero_type):
        """Select hero"""
        self.network.send({
            "type": "SELECT_HERO",
            "hero": hero_type
        })
        
    def send_buy_minion(self, slot):
        """Buy minion from shop"""
        self.network.send({
            "type": "BUY_MINION",
            "slot": slot
        })
        
    def send_sell_minion(self, instance_id):
        """Sell minion"""
        self.network.send({
            "type": "SELL_MINION",
            "instance_id": instance_id
        })
        
    def send_play_minion(self, instance_id, position=-1):
        """Play minion from hand"""
        self.network.send({
            "type": "PLAY_MINION",
            "instance_id": instance_id,
            "position": position
        })
        
    def send_refresh_shop(self):
        """Refresh shop"""
        self.network.send({
            "type": "REFRESH_SHOP"
        })
        
    def send_freeze_shop(self):
        """Freeze shop"""
        self.network.send({
            "type": "FREEZE_SHOP"
        })
        
    def send_upgrade_tavern(self):
        """Upgrade tavern"""
        self.network.send({
            "type": "UPGRADE_TAVERN"
        })
        
    def send_end_turn(self):
        """End turn"""
        self.network.send({
            "type": "END_TURN"
        })
        
    def send_use_hero_power(self):
        """Use hero power"""
        self.network.send({
            "type": "USE_HERO_POWER"
        })
        
    # ========================================================================
    # DRAWING METHODS
    # ========================================================================
    
    def draw_background(self):
        """Draw game background"""
        self.screen.blit(game_bg, (0, 0))
        
        # Draw phase indicator
        phase_colors = {
            "LOBBY": (100, 100, 255),
            "HERO_SELECT": (150, 100, 255),
            "RECRUIT": (100, 255, 100),
            "COMBAT_CALC": (255, 100, 100),
            "LOG_REPLAY": (255, 150, 100),
            "GAME_OVER": (100, 100, 100)
        }
        
        color = phase_colors.get(self.game_state.phase, (255, 255, 255))
        pygame.draw.rect(self.screen, color, (0, 0, 800, 5))
        
        # Phase text
        font = pygame.font.Font(None, 32)
        phase_text = font.render(f"Phase: {self.game_state.phase}", True, color)
        self.screen.blit(phase_text, (300, 10))
        
    def draw_lobby(self):
        """Draw lobby screen"""
        font_large = pygame.font.Font(None, 48)
        font_medium = pygame.font.Font(None, 32)
        font_small = pygame.font.Font(None, 24)
        
        # Title
        title = font_large.render("Hearthstone Battlegrounds", True, (100, 200, 255))
        self.screen.blit(title, (150, 100))
        
        # Players list
        players_text = font_medium.render("Players:", True, (200, 200, 255))
        self.screen.blit(players_text, (100, 200))
        
        y_offset = 250
        for player in self.game_state.players:
            name = player.get("name", "Unknown")
            ready = "✅" if player.get("is_ready", False) else "❌"
            player_text = font_small.render(f"{ready} {name}", True, (255, 255, 255))
            self.screen.blit(player_text, (120, y_offset))
            y_offset += 30
            
        # Input box for name
        pygame.draw.rect(self.screen, (255, 255, 255), self.input_box, 2)
        input_font = pygame.font.Font(None, 32)
        input_surface = input_font.render(self.input_text, True, (255, 255, 255))
        self.screen.blit(input_surface, (self.input_box.x + 5, self.input_box.y + 5))
        
        # Ready button
        mouse_pos = pygame.mouse.get_pos()
        self.buttons["READY"].draw(self.screen, mouse_pos)
        
    def draw_hero_selection(self):
        """Draw hero selection screen"""
        font_large = pygame.font.Font(None, 48)
        font_medium = pygame.font.Font(None, 32)
        
        # Title
        title = font_large.render("Select Your Hero", True, (255, 215, 0))
        self.screen.blit(title, (250, 50))
        
        # Hero offers
        heroes = self.game_state.hero_offers
        hero_names = [
            "Sylvanas",
            "Lich King", 
            "Millhouse",
            "Yogg-Saron",
            "Patches",
            "Ragnaros",
            "Kel'Thuzad",
            "Mal'Ganis"
        ]
        
        for i, hero_type in enumerate(heroes):
            if 0 <= hero_type < len(hero_names):
                x = 150 + (i * 200)
                y = 200
                
                # Hero card
                hero_rect = pygame.Rect(x, y, 150, 200)
                pygame.draw.rect(self.screen, (70, 70, 120), hero_rect)
                pygame.draw.rect(self.screen, (150, 150, 200), hero_rect, 3)
                
                # Hero name
                name = hero_names[hero_type]
                name_text = font_medium.render(name, True, (255, 255, 255))
                name_rect = name_text.get_rect(center=(x + 75, y + 30))
                self.screen.blit(name_text, name_rect)
                
                # Select button
                button_rect = pygame.Rect(x + 25, y + 150, 100, 40)
                mouse_pos = pygame.mouse.get_pos()
                
                if button_rect.collidepoint(mouse_pos):
                    pygame.draw.rect(self.screen, (100, 200, 100), button_rect, border_radius=5)
                else:
                    pygame.draw.rect(self.screen, (50, 150, 50), button_rect, border_radius=5)
                    
                pygame.draw.rect(self.screen, (200, 200, 200), button_rect, 2, border_radius=5)
                
                select_text = pygame.font.Font(None, 24).render("SELECT", True, (255, 255, 255))
                select_rect = select_text.get_rect(center=button_rect.center)
                self.screen.blit(select_text, select_rect)
                
    def draw_recruit_phase(self):
        """Draw recruit phase"""
        # Draw shop
        shop_positions = [(130, 200), (230, 200), (330, 200), (430, 200), (530, 200)]
        
        for i, (x, y) in enumerate(shop_positions):
            # Slot background
            slot_rect = pygame.Rect(x, y, 70, 100)
            pygame.draw.rect(self.screen, (40, 40, 60, 150), slot_rect)
            pygame.draw.rect(self.screen, (100, 100, 150), slot_rect, 2)
            
            # Minion in slot
            if i < len(self.game_state.shop) and self.game_state.shop[i] is not None:
                minion_card = MinionCard(self.screen, x, y, self.game_state.shop[i])
                minion_card.draw()
                
                # Cost
                font = pygame.font.Font(None, 20)
                cost_text = font.render("3G", True, (255, 215, 0))
                self.screen.blit(cost_text, (x + 25, y - 20))
                
        # Draw board
        board_positions = [(105, 340), (185, 340), (265, 340), (345, 340),
                          (425, 340), (505, 340), (585, 340)]
        
        for i, (x, y) in enumerate(board_positions):
            # Slot background
            slot_rect = pygame.Rect(x, y, 70, 100)
            pygame.draw.rect(self.screen, (30, 30, 50, 150), slot_rect)
            pygame.draw.rect(self.screen, (80, 80, 120), slot_rect, 1)
            
            # Minion in slot
            if i < len(self.game_state.board) and self.game_state.board[i] is not None:
                minion_card = MinionCard(self.screen, x, y, self.game_state.board[i])
                minion_card.draw()
                
        # Draw hand
        hand_positions = [(180, 580), (270, 580), (360, 580), (450, 580), (540, 580)]
        
        for i, (x, y) in enumerate(hand_positions):
            # Slot background
            slot_rect = pygame.Rect(x, y, 70, 100)
            pygame.draw.rect(self.screen, (50, 30, 30, 150), slot_rect)
            pygame.draw.rect(self.screen, (120, 80, 80), slot_rect, 1)
            
            # Minion in slot
            if i < len(self.game_state.hand) and self.game_state.hand[i] is not None:
                minion_card = MinionCard(self.screen, x, y, self.game_state.hand[i])
                minion_card.draw()
                
        # Draw buttons
        mouse_pos = pygame.mouse.get_pos()
        
        # Update button states
        self.buttons["END_TURN"].enabled = (self.game_state.phase == "RECRUIT")
        self.buttons["UPGRADE"].enabled = self.game_state.can_upgrade_tavern()
        self.buttons["REFRESH"].enabled = self.game_state.can_refresh_shop()
        self.buttons["FREEZE"].enabled = True
        
        for button in self.buttons.values():
            if button != self.buttons["READY"]:  # Don't draw ready button in recruit
                button.draw(self.screen, mouse_pos)
                
        # Draw gold
        self.gold_display.draw(self.screen, self.game_state.gold)
        
        # Draw timer
        self.timer_display.draw(self.screen, self.game_state.phase_timer)
        
        # Draw player info
        font = pygame.font.Font(None, 24)
        health_text = font.render(f"Health: {self.game_state.health}", True, (255, 50, 50))
        self.screen.blit(health_text, (650, 50))
        
        tier_text = font.render(f"Tier: {self.game_state.tavern_tier}", True, (100, 200, 255))
        self.screen.blit(tier_text, (650, 80))
        
        # Draw hero info
        if self.game_state.hero:
            hero_name = self.game_state.hero.get("name", "No Hero")
            hero_text = font.render(f"Hero: {hero_name}", True, (255, 215, 0))
            self.screen.blit(hero_text, (650, 110))
            
        # Draw frozen indicator
        if self.game_state.shop_frozen:
            freeze_font = pygame.font.Font(None, 24)
            freeze_text = freeze_font.render("SHOP FROZEN", True, (100, 200, 255))
            self.screen.blit(freeze_text, (350, 280))
            
    def draw_combat_phase(self):
        """Draw combat phase"""
        font_large = pygame.font.Font(None, 48)
        font_medium = pygame.font.Font(None, 32)
        
        title = font_large.render("COMBAT IN PROGRESS", True, (255, 100, 100))
        self.screen.blit(title, (200, 300))
        
        if self.game_state.combat_log:
            log_text = font_medium.render("Combat log available", True, (200, 200, 255))
            self.screen.blit(log_text, (250, 380))
            
    def draw_game_over(self):
        """Draw game over screen"""
        font_large = pygame.font.Font(None, 48)
        font_medium = pygame.font.Font(None, 32)
        
        title = font_large.render("GAME OVER", True, (255, 215, 0))
        self.screen.blit(title, (300, 200))
        
        # Show winner if available
        if hasattr(self.game_state, 'winner'):
            winner_text = font_medium.render(f"Winner: {self.game_state.winner}", True, (100, 255, 100))
            self.screen.blit(winner_text, (300, 280))
            
    def draw(self):
        """Draw everything based on current phase"""
        self.draw_background()
        
        if self.game_state.phase == "LOBBY":
            self.draw_lobby()
        elif self.game_state.phase == "HERO_SELECT":
            self.draw_hero_selection()
        elif self.game_state.phase == "RECRUIT":
            self.draw_recruit_phase()
        elif self.game_state.phase in ["COMBAT_CALC", "LOG_REPLAY"]:
            self.draw_combat_phase()
        elif self.game_state.phase == "GAME_OVER":
            self.draw_game_over()
            
    # ========================================================================
    # INPUT HANDLING
    # ========================================================================
    
    def handle_input(self, event):
        """Handle user input"""
        if event.type == pygame.KEYDOWN:
            if self.input_active:
                if event.key == pygame.K_RETURN:
                    # Submit name
                    if self.input_text:
                        self.send_join(self.input_text)
                        self.input_active = False
                elif event.key == pygame.K_BACKSPACE:
                    self.input_text = self.input_text[:-1]
                else:
                    if len(self.input_text) < 20:
                        self.input_text += event.unicode
                        
            # Global shortcuts
            if event.key == pygame.K_r:
                if self.game_state.phase == "RECRUIT":
                    self.send_refresh_shop()
            elif event.key == pygame.K_f:
                if self.game_state.phase == "RECRUIT":
                    self.send_freeze_shop()
            elif event.key == pygame.K_u:
                if self.game_state.phase == "RECRUIT":
                    self.send_upgrade_tavern()
            elif event.key == pygame.K_SPACE:
                if self.game_state.phase == "RECRUIT":
                    self.send_end_turn()
                    
        elif event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = pygame.mouse.get_pos()
            
            # Handle input box click
            if self.input_box.collidepoint(mouse_pos):
                self.input_active = True
            else:
                self.input_active = False
                
            # Handle button clicks
            if self.game_state.phase == "LOBBY":
                if self.buttons["READY"].is_clicked(mouse_pos, pygame.mouse.get_pressed()):
                    self.send_ready(True)
                    
            elif self.game_state.phase == "HERO_SELECT":
                # Check hero selection
                heroes = self.game_state.hero_offers
                for i, hero_type in enumerate(heroes):
                    x = 150 + (i * 200)
                    y = 200
                    button_rect = pygame.Rect(x + 25, y + 150, 100, 40)
                    if button_rect.collidepoint(mouse_pos):
                        self.send_select_hero(hero_type)
                        break
                        
            elif self.game_state.phase == "RECRUIT":
                # Shop clicks
                for i in range(5):
                    x = 130 + (i * 100)
                    y = 200
                    shop_rect = pygame.Rect(x, y, 70, 100)
                    if shop_rect.collidepoint(mouse_pos):
                        if i < len(self.game_state.shop) and self.game_state.shop[i] is not None:
                            if self.game_state.can_buy_minion():
                                self.send_buy_minion(i)
                        break
                        
                # Board clicks (for selling)
                for i in range(7):
                    x = 105 + (i * 80)
                    y = 340
                    board_rect = pygame.Rect(x, y, 70, 100)
                    if board_rect.collidepoint(mouse_pos):
                        if i < len(self.game_state.board) and self.game_state.board[i] is not None:
                            instance_id = self.game_state.board[i].get("instance_id")
                            if instance_id:
                                self.send_sell_minion(instance_id)
                        break
                        
                # Hand clicks (for playing)
                for i in range(5):
                    x = 180 + (i * 90)
                    y = 580
                    hand_rect = pygame.Rect(x, y, 70, 100)
                    if hand_rect.collidepoint(mouse_pos):
                        if i < len(self.game_state.hand) and self.game_state.hand[i] is not None:
                            instance_id = self.game_state.hand[i].get("instance_id")
                            if instance_id:
                                # Find empty board slot
                                for board_slot in range(7):
                                    if board_slot >= len(self.game_state.board) or self.game_state.board[board_slot] is None:
                                        self.send_play_minion(instance_id, board_slot)
                                        break
                        break
                        
                # Button clicks
                if self.buttons["END_TURN"].is_clicked(mouse_pos, pygame.mouse.get_pressed()):
                    self.send_end_turn()
                elif self.buttons["UPGRADE"].is_clicked(mouse_pos, pygame.mouse.get_pressed()):
                    self.send_upgrade_tavern()
                elif self.buttons["FREEZE"].is_clicked(mouse_pos, pygame.mouse.get_pressed()):
                    self.send_freeze_shop()
                elif self.buttons["REFRESH"].is_clicked(mouse_pos, pygame.mouse.get_pressed()):
                    self.send_refresh_shop()
                elif self.buttons["HERO_POWER"].is_clicked(mouse_pos, pygame.mouse.get_pressed()):
                    self.send_use_hero_power()
                    
    def run(self):
        """Main game loop"""
        while self.running:
            # Handle network messages
            self.handle_network_messages()
            
            # Process events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    self.network.stop()
                    
                self.handle_input(event)
                
            # Update timer
            current_time = pygame.time.get_ticks()
            if hasattr(self, 'last_timer_update'):
                delta = (current_time - self.last_timer_update) / 1000.0
                if self.game_state.phase_timer > 0:
                    self.game_state.phase_timer = max(0, self.game_state.phase_timer - delta)
                if self.game_state.grace_timer > 0:
                    self.game_state.grace_timer = max(0, self.game_state.grace_timer - delta)
            self.last_timer_update = current_time
            
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
    parser.add_argument("--token", help="Authentication token for reconnection")
    parser.add_argument("--name", default="Player", help="Player name")
    
    args = parser.parse_args()
    
    # Create and run client
    client = HearthstoneBattlegroundsClient()
    client.network.server_url = args.server
    client.network.set_player_name(args.name)
    
    if args.token:
        client.network.set_token(args.token)
        client.game_state.set_token(args.token)
        
    print("🚀 Starting Hearthstone Battlegrounds Client...")
    print(f"📡 Server: {args.server}")
    print(f"👤 Name: {args.name}")
    if args.token:
        print(f"🔑 Token: {args.token}")
    
    client.run()