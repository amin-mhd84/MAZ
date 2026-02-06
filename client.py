#!/usr/bin/env python3
"""
MAW Game Client - Robust Version
"""
import asyncio
import websockets
import json
import sys
import time
import signal

class RobustClient:
    def __init__(self, player_name):
        self.name = player_name
        self.token = None
        self.ws = None
        
    def signal_handler(self, sig, frame):
        print(f"\n⚠️ Signal received, disconnecting {self.name}...")
        if self.ws:
            asyncio.create_task(self.ws.close())
        sys.exit(0)
        
    async def connect(self):
        signal.signal(signal.SIGINT, self.signal_handler)
        
        print(f"\n{'='*60}")
        print(f"🎮 MAW Game Client - {self.name}")
        print(f"{'='*60}")
        
        max_retries = 5
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                print(f"🔌 Attempt {attempt + 1}/{max_retries} to connect...")
                
                # Connect with timeout
                async with websockets.connect(
                    'ws://localhost:8888',
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=1
                ) as websocket:
                    self.ws = websocket
                    
                    # Receive welcome
                    try:
                        welcome = await asyncio.wait_for(websocket.recv(), timeout=5)
                        welcome_data = json.loads(welcome)
                        print(f"📨 Server: {welcome_data.get('message', 'Welcome')}")
                        
                        # Join game
                        join_msg = {
                            "type": "JOIN",
                            "name": self.name
                        }
                        await websocket.send(json.dumps(join_msg))
                        print(f"📤 Joining as {self.name}...")
                        
                        # Get response
                        response = await asyncio.wait_for(websocket.recv(), timeout=5)
                        resp_data = json.loads(response)
                        
                        if resp_data.get("type") == "JOIN_SUCCESS":
                            self.token = resp_data.get("token")
                            print(f"✅ Joined successfully!")
                            print(f"   Token: {self.token[:8]}...")
                            print(f"   Players: {resp_data.get('player_count', 0)}/4")
                            
                            # Mark ready
                            ready_msg = {
                                "type": "READY",
                                "token": self.token,
                                "ready": True
                            }
                            await websocket.send(json.dumps(ready_msg))
                            print(f"✅ Marked as READY")
                        else:
                            print(f"❌ Join failed: {resp_data.get('message', 'Unknown error')}")
                            return
                            
                    except asyncio.TimeoutError:
                        print("⏰ Timeout receiving from server")
                        continue
                        
                    # Game loop
                    print(f"\n🎲 Waiting for game to start...")
                    print(f"   (Press Ctrl+C in this window to exit)")
                    
                    try:
                        while True:
                            try:
                                # Receive with timeout
                                message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                                data = json.loads(message)
                                msg_type = data.get("type")
                                
                                if msg_type == "PHASE_CHANGE":
                                    phase = data.get("phase")
                                    print(f"\n{'='*40}")
                                    print(f"🔄 PHASE: {phase}")
                                    print(f"{'='*40}")
                                    if phase == "HERO_SELECT":
                                        print("   Choose your hero from the list!")
                                    elif phase == "RECRUIT":
                                        print(f"   Turn: {data.get('turn', 1)}")
                                        print(f"   Time: {data.get('time', 30)}s")
                                    elif phase == "COMBAT":
                                        print("   ⚔️ Combat in progress...")
                                    elif phase == "GAME_OVER":
                                        winner = data.get("winner", "Unknown")
                                        print(f"   🏆 Winner: {winner}")
                                        break
                                        
                                elif msg_type == "HERO_OFFER":
                                    print(f"\n🎭 HERO SELECTION")
                                    print(f"   Choose one:")
                                    for i, hero in enumerate(data.get("heroes", [])):
                                        print(f"   {i+1}. Hero Type {hero}")
                                    print(f"   Time: {data.get('time', 15)}s")
                                    
                                elif msg_type == "FULL_STATE":
                                    print(f"\n📊 Game state updated")
                                    phase = data.get("data", {}).get("phase", "UNKNOWN")
                                    print(f"   Current phase: {phase}")
                                    
                                elif msg_type == "COMBAT_RESULT":
                                    result = data.get("result", "UNKNOWN")
                                    print(f"\n⚔️ COMBAT RESULT: {result}")
                                    if result == "WIN":
                                        print(f"   ✅ You won!")
                                        print(f"   💥 Damage dealt: {data.get('damage_dealt', 0)}")
                                    elif result == "LOSE":
                                        print(f"   ❌ You lost")
                                        print(f"   💔 Damage taken: {data.get('damage_taken', 0)}")
                                        
                                elif msg_type == "GAME_OVER":
                                    print(f"\n{'='*60}")
                                    print(f"🏆 GAME OVER!")
                                    print(f"   Winner: {data.get('winner', 'Unknown')}")
                                    print(f"{'='*60}")
                                    return
                                    
                                elif msg_type == "ERROR":
                                    print(f"\n❌ ERROR: {data.get('message', 'Unknown error')}")
                                    
                                else:
                                    # Silent handling of other messages
                                    pass
                                    
                            except asyncio.TimeoutError:
                                # No message, continue
                                continue
                                
                    except websockets.exceptions.ConnectionClosed:
                        print("\n📡 Connection closed by server")
                        break
                    except KeyboardInterrupt:
                        print(f"\n👋 {self.name} disconnecting...")
                        break
                        
            except ConnectionRefusedError:
                print(f"❌ Cannot connect to server (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    print(f"   Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 1.5  # Exponential backoff
            except Exception as e:
                print(f"❌ Error: {type(e).__name__}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    
        print(f"\n🎮 {self.name} disconnected")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 client.py <player_name>")
        print("Example: python3 client.py Sylvanas")
        sys.exit(1)
        
    player_name = sys.argv[1]
    client = RobustClient(player_name)
    
    try:
        asyncio.run(client.connect())
    except KeyboardInterrupt:
        print(f"\n👋 Client {player_name} closed")
    except Exception as e:
        print(f"💥 Fatal error: {e}")

if __name__ == "__main__":
    main()
