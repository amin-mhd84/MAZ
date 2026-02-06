#!/bin/bash

echo "🎮 MAW Game - Fixed Launcher"
echo "============================"

# Configuration
SERVER_CPP="server.cpp"
SERVER_BINARY="maw_server_fixed"
CLIENT_PY="client.py"
PORT=8888

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_msg() {
    echo -e "${2}${1}${NC}"
}

# Function to create a robust client
create_robust_client() {
    print_msg "📝 Creating robust client.py..." "$BLUE"
    
    cat > "$CLIENT_PY" << 'EOF'
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
EOF
    
    chmod +x "$CLIENT_PY"
    print_msg "✅ Created robust client.py" "$GREEN"
}

# Function to compile server with debug info
compile_server_debug() {
    print_msg "🔨 Compiling server with debug info..." "$BLUE"
    
    if [[ ! -f "$SERVER_CPP" ]]; then
        print_msg "❌ server.cpp not found!" "$RED"
        exit 1
    fi
    
    # Clean previous
    rm -f "$SERVER_BINARY"
    
    # Compile with debug symbols and all warnings
    g++ -std=c++17 -pthread -g -Wall -Wextra -Werror "$SERVER_CPP" \
        -o "$SERVER_BINARY" -lboost_system 2>/tmp/compile_errors.log
    
    if [[ $? -eq 0 ]]; then
        print_msg "✅ Server compiled with debug symbols" "$GREEN"
        return 0
    else
        print_msg "❌ Compilation failed:" "$RED"
        cat /tmp/compile_errors.log
        return 1
    fi
}

# Function to start server in background
start_server_background() {
    print_msg "🚀 Starting server in background..." "$BLUE"
    
    # Kill existing
    pkill -f "./$SERVER_BINARY" 2>/dev/null
    sleep 1
    
    if [[ ! -f "./$SERVER_BINARY" ]]; then
        print_msg "❌ Server binary not found!" "$RED"
        return 1
    fi
    
    # Start server with GDB to catch crashes
    echo "Starting server at $(date)" > /tmp/maw_server_debug.log
    gdb -ex "set pagination off" \
        -ex "run" \
        -ex "bt" \
        -ex "quit" \
        ./"$SERVER_BINARY" >> /tmp/maw_server_debug.log 2>&1 &
    SERVER_PID=$!
    
    # Wait for server to start
    print_msg "⏳ Waiting for server..." "$YELLOW"
    
    for i in {1..30}; do
        if ps -p $SERVER_PID > /dev/null 2>&1; then
            if netstat -tln 2>/dev/null | grep -q ":$PORT"; then
                print_msg "✅ Server running (PID: $SERVER_PID)" "$GREEN"
                echo "Server PID: $SERVER_PID" > /tmp/maw_server.pid
                return 0
            fi
        fi
        echo -n "."
        sleep 1
    done
    
    print_msg "\n❌ Server failed to start properly" "$RED"
    print_msg "Check /tmp/maw_server_debug.log for details" "$YELLOW"
    return 1
}

# Function to start clients in separate terminals
start_clients_separate() {
    print_msg "🎮 Starting 4 game clients..." "$BLUE"
    
    PLAYER_NAMES=("Sylvanas" "Lich_King" "Millhouse" "Yogg_Saron")
    
    # Check for terminal
    if ! command -v gnome-terminal > /dev/null 2>&1; then
        print_msg "⚠️ gnome-terminal not found, installing..." "$YELLOW"
        sudo apt-get install -y gnome-terminal 2>/dev/null || true
    fi
    
    # Start each client in separate terminal
    for player in "${PLAYER_NAMES[@]}"; do
        print_msg "Opening client for $player..." "$PURPLE"
        
        # Create a script for this client
        CLIENT_SCRIPT="/tmp/maw_client_${player}.sh"
        cat > "$CLIENT_SCRIPT" << SCRIPT
#!/bin/bash
echo "Starting MAW Client: $player"
cd "$PWD"
python3 "$CLIENT_PY" "$player"
echo "Press Enter to close this window..."
read
SCRIPT
        chmod +x "$CLIENT_SCRIPT"
        
        # Open new terminal
        gnome-terminal --title="MAW Game - $player" \
                      -- bash -c "$CLIENT_SCRIPT; exec bash" &
        
        sleep 2  # Wait between opening terminals
    done
    
    print_msg "✅ All clients should open in separate windows" "$GREEN"
    print_msg "⚠️ If windows don't open, run clients manually:" "$YELLOW"
    for player in "${PLAYER_NAMES[@]}"; do
        echo "  Terminal 1: python3 client.py $player"
    done
}

# Function to check server status
check_server() {
    if [[ -f /tmp/maw_server.pid ]]; then
        SERVER_PID=$(cat /tmp/maw_server.pid)
        if ps -p $SERVER_PID > /dev/null 2>&1; then
            if netstat -tln 2>/dev/null | grep -q ":$PORT"; then
                return 0
            fi
        fi
    fi
    return 1
}

# Main
main() {
    echo ""
    print_msg "🎮 MAW Game Debug Launcher" "$BLUE"
    echo ""
    
    # Create client
    create_robust_client
    
    # Compile server
    if ! compile_server_debug; then
        exit 1
    fi
    
    # Start server
    if ! start_server_background; then
        # Show debug log
        echo ""
        print_msg "📋 Server Debug Log:" "$YELLOW"
        tail -n 20 /tmp/maw_server_debug.log
        exit 1
    fi
    
    # Wait a bit
    sleep 3
    
    # Check server
    if ! check_server; then
        print_msg "❌ Server crashed after start" "$RED"
        echo ""
        print_msg "📋 Crash Log:" "$YELLOW"
        tail -n 50 /tmp/maw_server_debug.log
        exit 1
    fi
    
    # Start clients
    start_clients_separate
    
    # Show status
    echo ""
    print_msg "==========================================" "$GREEN"
    print_msg "        🎮 MAW GAME STATUS               " "$GREEN"
    print_msg "==========================================" "$GREEN"
    print_msg "Server:   PID: $SERVER_PID, Port: $PORT" "$BLUE"
    print_msg "Status:   $(check_server && echo 'RUNNING ✅' || echo 'STOPPED ❌')" "$BLUE"
    print_msg "Players:  4 clients starting..." "$BLUE"
    print_msg "Logs:     /tmp/maw_server_debug.log" "$YELLOW"
    print_msg "          /tmp/maw_server_debug.log" "$YELLOW"
    print_msg "==========================================" "$GREEN"
    print_msg "Manual start if clients didn't open:" "$YELLOW"
    print_msg "  1. Open 4 terminal windows" "$YELLOW"
    print_msg "  2. In each, run: python3 client.py <name>" "$YELLOW"
    print_msg "     Names: Sylvanas Lich_King Millhouse Yogg_Saron" "$YELLOW"
    print_msg "==========================================" "$GREEN"
    
    # Monitor
    print_msg "🔄 Monitoring server (Ctrl+C to stop)..." "$BLUE"
    while check_server; do
        sleep 5
    done
    
    print_msg "❌ Server stopped" "$RED"
}

# Cleanup
cleanup() {
    echo ""
    print_msg "🛑 Cleaning up..." "$YELLOW"
    pkill -f "./$SERVER_BINARY" 2>/dev/null
    pkill -f "python3 $CLIENT_PY" 2>/dev/null
    print_msg "✅ Cleanup complete" "$GREEN"
    exit 0
}

trap cleanup SIGINT SIGTERM

main