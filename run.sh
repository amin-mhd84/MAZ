#!/bin/bash

echo "🎮 MAW Game - Auto Launcher"
echo "============================"

# Configuration
SERVER_CPP="server.cpp"
SERVER_BINARY="maw_server"
CLIENT_PY="client.py"
PORT=8888
MAX_PLAYERS=4

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# Function to print with color
print_msg() {
    echo -e "${2}${1}${NC}"
}

# Function to check and install dependencies
install_deps() {
    print_msg "📦 Checking and installing dependencies..." "$BLUE"
    
    # Check for C++ compiler
    if ! command -v g++ > /dev/null 2>&1; then
        print_msg "Installing g++..." "$YELLOW"
        sudo apt-get update
        sudo apt-get install -y g++ 2>/dev/null
    fi
    
    # Check for Boost
    if [[ ! -f "/usr/include/boost/asio.hpp" ]] && [[ ! -f "/usr/local/include/boost/asio.hpp" ]]; then
        print_msg "Installing Boost library..." "$YELLOW"
        sudo apt-get install -y libboost-system-dev 2>/dev/null || true
    fi
    
    # Check for Python3
    if ! command -v python3 > /dev/null 2>&1; then
        print_msg "Installing python3..." "$YELLOW"
        sudo apt-get install -y python3 python3-pip 2>/dev/null
    fi
    
    # Install Python websockets if needed
    if ! python3 -c "import websockets" 2>/dev/null; then
        print_msg "Installing websockets for Python..." "$YELLOW"
        pip3 install websockets --user 2>/dev/null || true
    fi
    
    print_msg "✅ Dependencies checked" "$GREEN"
}

# Function to compile the C++ server
compile_server() {
    print_msg "🔨 Compiling C++ server..." "$BLUE"
    
    # Check if server.cpp exists
    if [[ ! -f "$SERVER_CPP" ]]; then
        print_msg "❌ ERROR: $SERVER_CPP not found!" "$RED"
        exit 1
    fi
    
    # Try different compilation methods
    if g++ -std=c++17 -pthread "$SERVER_CPP" -o "$SERVER_BINARY" -lboost_system 2>/dev/null; then
        print_msg "✅ Server compiled successfully" "$GREEN"
        return 0
    fi
    
    # Try with different include paths
    print_msg "Trying alternative compilation method..." "$YELLOW"
    
    # Create a simple test to check Boost
    cat > /tmp/test_boost.cpp << 'EOF'
#include <iostream>
#include <boost/version.hpp>
int main() {
    std::cout << "Boost version: " << BOOST_VERSION << std::endl;
    return 0;
}
EOF
    
    if g++ -std=c++17 /tmp/test_boost.cpp -o /tmp/test_boost -lboost_system 2>/dev/null; then
        print_msg "Boost is working, trying server again..." "$GREEN"
        
        # Final attempt with all possible flags
        g++ -std=c++17 -pthread "$SERVER_CPP" -o "$SERVER_BINARY" -lboost_system -I/usr/include -I/usr/local/include 2>/tmp/compile.log
        
        if [[ -f "$SERVER_BINARY" ]]; then
            print_msg "✅ Server compiled (with possible warnings)" "$GREEN"
            return 0
        else
            print_msg "❌ Compilation failed. Check /tmp/compile.log" "$RED"
            return 1
        fi
    else
        print_msg "❌ Boost library not found or not working" "$RED"
        return 1
    fi
}

# Function to create a simple client if needed
create_client_if_missing() {
    if [[ ! -f "$CLIENT_PY" ]]; then
        print_msg "📝 Creating client.py (websocket version)..." "$BLUE"
        
        cat > "$CLIENT_PY" << 'EOF'
#!/usr/bin/env python3
"""
MAW Game Client - Auto Connect Version
"""
import asyncio
import websockets
import json
import sys
import time

class GameClient:
    def __init__(self, player_name):
        self.name = player_name
        self.token = None
        self.connected = False
        
    async def connect_and_play(self):
        print(f"\n{'='*50}")
        print(f"🎮 Player: {self.name}")
        print(f"{'='*50}")
        
        server_url = "ws://localhost:8888"
        
        try:
            # Connect to server
            print(f"🔌 Connecting to {server_url}...")
            async with websockets.connect(server_url, ping_interval=None) as websocket:
                self.connected = True
                print("✅ Connected to server!")
                
                # Receive welcome message
                welcome = await websocket.recv()
                welcome_data = json.loads(welcome)
                print(f"📨 Server: {welcome_data.get('message', 'Welcome')}")
                
                # Send join request
                join_msg = {
                    "type": "JOIN",
                    "name": self.name
                }
                await websocket.send(json.dumps(join_msg))
                print(f"📤 Joining as {self.name}...")
                
                # Get response
                response = await websocket.recv()
                resp_data = json.loads(response)
                
                if resp_data.get("type") == "JOIN_SUCCESS":
                    self.token = resp_data.get("token")
                    print(f"🎉 Successfully joined!")
                    print(f"   Token: {self.token}")
                    print(f"   Players: {resp_data.get('player_count', 0)}/4")
                    
                    # Mark ready
                    ready_msg = {
                        "type": "READY",
                        "token": self.token,
                        "ready": True
                    }
                    await websocket.send(json.dumps(ready_msg))
                    print("✅ Marked as READY")
                    
                # Listen for game events
                print("\n⏳ Waiting for game to start...")
                print("Press Ctrl+C to exit")
                
                while True:
                    try:
                        # Receive game messages
                        message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        data = json.loads(message)
                        msg_type = data.get("type", "UNKNOWN")
                        
                        if msg_type == "PHASE_CHANGE":
                            print(f"\n🔄 Phase changed to: {data.get('phase')}")
                        elif msg_type == "FULL_STATE":
                            print(f"\n📊 Game state received")
                        elif msg_type == "COMBAT_RESULT":
                            print(f"\n⚔️ Combat result: {data.get('result')}")
                        elif msg_type == "ERROR":
                            print(f"\n❌ Error: {data.get('message')}")
                        elif msg_type == "GAME_OVER":
                            print(f"\n🏆 Game Over! Winner: {data.get('winner')}")
                            break
                        else:
                            print(f"📨 [{msg_type}]")
                            
                    except asyncio.TimeoutError:
                        # No message, continue listening
                        continue
                    except KeyboardInterrupt:
                        print("\n👋 Exiting...")
                        break
                        
        except ConnectionRefusedError:
            print("❌ Could not connect to server. Is it running?")
        except Exception as e:
            print(f"❌ Error: {e}")
            
        print(f"\n🎮 {self.name} disconnected")

async def main():
    # Get player name from command line or use default
    if len(sys.argv) > 1:
        player_name = sys.argv[1]
    else:
        player_name = "Player_" + str(int(time.time()))[-4:]
    
    client = GameClient(player_name)
    await client.connect_and_play()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Game client closed")
EOF
        
        chmod +x "$CLIENT_PY"
        print_msg "✅ Created $CLIENT_PY" "$GREEN"
    else
        print_msg "✅ Client.py already exists" "$GREEN"
    fi
}

# Function to start the server
start_server() {
    print_msg "🚀 Starting server..." "$BLUE"
    
    # Kill any existing server
    pkill -f "./$SERVER_BINARY" 2>/dev/null && print_msg "Stopped previous server" "$YELLOW"
    sleep 1
    
    # Check if server binary exists
    if [[ ! -f "./$SERVER_BINARY" ]]; then
        print_msg "❌ Server binary not found! Compile first." "$RED"
        exit 1
    fi
    
    # Start server in background
    ./$SERVER_BINARY &
    SERVER_PID=$!
    
    # Wait for server to start
    print_msg "⏳ Waiting for server to initialize..." "$YELLOW"
    
    for i in {1..15}; do
        if ps -p $SERVER_PID > /dev/null 2>&1; then
            # Check if port is listening
            if netstat -tln 2>/dev/null | grep -q ":$PORT"; then
                print_msg "✅ Server is running (PID: $SERVER_PID, Port: $PORT)" "$GREEN"
                return $SERVER_PID
            fi
        fi
        echo -n "."
        sleep 1
    done
    
    print_msg "\n❌ Server failed to start properly" "$RED"
    exit 1
}

# Function to open 4 terminals with clients
open_client_terminals() {
    print_msg "🎮 Opening 4 game clients..." "$BLUE"
    
    # List of player names (using Hearthstone heroes)
    PLAYER_NAMES=("Sylvanas" "Lich_King" "Millhouse" "Yogg_Saron")
    
    # Check which terminal emulator is available
    TERMINAL_CMD=""
    
    if command -v gnome-terminal > /dev/null 2>&1; then
        TERMINAL_CMD="gnome-terminal --"
    elif command -v konsole > /dev/null 2>&1; then
        TERMINAL_CMD="konsole -e"
    elif command -v xterm > /dev/null 2>&1; then
        TERMINAL_CMD="xterm -e"
    elif command -v terminator > /dev/null 2>&1; then
        TERMINAL_CMD="terminator -e"
    else
        print_msg "❌ No terminal emulator found! Please install one." "$RED"
        print_msg "Try: sudo apt-get install gnome-terminal or xterm" "$YELLOW"
        exit 1
    fi
    
    print_msg "Using terminal: $TERMINAL_CMD" "$YELLOW"
    
    # Open 4 terminals
    for i in {0..3}; do
        PLAYER_NAME="${PLAYER_NAMES[$i]}"
        print_msg "Opening client for $PLAYER_NAME..." "$PURPLE"
        
        # Create command for this client
        CLIENT_CMD="python3 $CLIENT_PY '$PLAYER_NAME'"
        
        # Open terminal with client
        if [[ "$TERMINAL_CMD" == "gnome-terminal --" ]]; then
            gnome-terminal --title="MAW Game - $PLAYER_NAME" -- bash -c "$CLIENT_CMD; exec bash" &
        elif [[ "$TERMINAL_CMD" == "konsole -e" ]]; then
            konsole -e "bash -c '$CLIENT_CMD; exec bash'" &
        elif [[ "$TERMINAL_CMD" == "xterm -e" ]]; then
            xterm -title "MAW Game - $PLAYER_NAME" -e "bash -c '$CLIENT_CMD; exec bash'" &
        elif [[ "$TERMINAL_CMD" == "terminator -e" ]]; then
            terminator -e "bash -c '$CLIENT_CMD; exec bash'" &
        fi
        
        # Wait a bit between opening terminals
        sleep 2
    done
    
    print_msg "✅ All 4 clients opened in separate terminals" "$GREEN"
}

# Function to show game status
show_status() {
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}           🎮 GAME STATUS             ${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo -e "${BLUE}Server:${NC}   PID: $SERVER_PID, Port: $PORT"
    echo -e "${BLUE}Clients:${NC}  4 terminals opened"
    echo -e "${BLUE}Players:${NC}  Sylvanas, Lich_King, Millhouse, Yogg_Saron"
    echo -e "${GREEN}========================================${NC}"
    echo -e "${YELLOW}Instructions for players:${NC}"
    echo "1. In each terminal window, wait for connection"
    echo "2. Each player will automatically join the game"
    echo "3. All players will be marked as READY"
    echo "4. Game will start automatically when all are ready"
    echo -e "${GREEN}========================================${NC}"
    echo -e "${YELLOW}To stop everything:${NC}"
    echo "   Run: pkill -f './$SERVER_BINARY'"
    echo "   Or: kill $SERVER_PID"
    echo -e "${GREEN}========================================${NC}"
}

# Main execution
main() {
    echo ""
    print_msg "🎮 Starting MAW Game Auto-Launcher..." "$BLUE"
    echo ""
    
    # Step 1: Install dependencies
    install_deps
    
    # Step 2: Compile server
    compile_server
    if [[ $? -ne 0 ]]; then
        print_msg "❌ Cannot continue without server" "$RED"
        exit 1
    fi
    
    # Step 3: Create client if needed
    create_client_if_missing
    
    # Step 4: Start server
    start_server
    SERVER_PID=$?
    
    # Give server a moment to fully initialize
    sleep 3
    
    # Step 5: Open 4 client terminals
    open_client_terminals
    
    # Step 6: Show status
    show_status
    
    # Keep script running to show status
    print_msg "\n🎯 Game is running! All 4 clients should connect automatically." "$GREEN"
    print_msg "🔄 Server is running in the background." "$YELLOW"
    print_msg "❌ Press Ctrl+C in THIS window to stop everything" "$RED"
    
    # Wait for Ctrl+C
    while true; do
        sleep 1
    done
}

# Cleanup function
cleanup() {
    echo ""
    print_msg "🛑 Cleaning up..." "$YELLOW"
    
    # Kill server
    if kill $SERVER_PID 2>/dev/null; then
        print_msg "✅ Stopped server" "$GREEN"
    fi
    
    # Kill any remaining client processes
    pkill -f "python3 $CLIENT_PY" 2>/dev/null && print_msg "✅ Stopped clients" "$GREEN"
    
    print_msg "👋 Done!" "$GREEN"
    exit 0
}

# Trap Ctrl+C for cleanup
trap cleanup SIGINT

# Run main function
main