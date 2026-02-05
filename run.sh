#!/bin/bash

echo "🎮 MAW Game Launcher"
echo "==================="

# Configuration
SERVER_BINARY="server"
CLIENT_SCRIPT="client.py"
PORT=8888
MAX_PLAYERS=4

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Function to check and install minimal Python dependencies
check_python_deps() {
    echo -e "${BLUE}🔍 Checking Python...${NC}"
    
    if ! command -v python3 > /dev/null 2>&1; then
        echo -e "${RED}❌ Python3 not found${NC}"
        echo "Installing Python3..."
        sudo apt-get install -y python3
    fi
    
    # Check basic modules
    if ! python3 -c "import json" 2>/dev/null; then
        echo -e "${RED}❌ json module missing${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Python3 ready${NC}"
}

# Function to compile server
compile_server() {
    echo -e "${BLUE}🔨 Compiling server...${NC}"
    
    # Try to compile with basic flags
    if g++ -std=c++17 -pthread server.cpp -o $SERVER_BINARY -lboost_system -lboost_thread 2>/dev/null; then
        echo -e "${GREEN}✅ Server compiled${NC}"
        return 0
    fi
    
    # Try alternative
    echo -e "${YELLOW}Trying alternative compilation...${NC}"
    
    # Create minimal test
    echo "#include <iostream>" > /tmp/test_server.cpp
    echo "int main() { std::cout << \"Test OK\\n\"; return 0; }" >> /tmp/test_server.cpp
    
    if g++ -std=c++17 /tmp/test_server.cpp -o /tmp/test_server 2>/dev/null; then
        echo -e "${GREEN}✅ Basic C++ compilation works${NC}"
    else
        echo -e "${RED}❌ C++ compiler issue${NC}"
        return 1
    fi
    
    # Final try with all warnings
    echo -e "${YELLOW}Final compilation attempt...${NC}"
    g++ -std=c++17 -pthread server.cpp -o $SERVER_BINARY -lboost_system -lboost_thread 2>&1 | head -20
    
    if [ -f "$SERVER_BINARY" ]; then
        echo -e "${GREEN}✅ Server compiled (with warnings)${NC}"
        return 0
    else
        echo -e "${RED}❌ Compilation failed${NC}"
        return 1
    fi
}

# Function to create a SUPER SIMPLE client that doesn't need websocket
create_simple_client() {
    echo -e "${BLUE}📝 Creating simple test client...${NC}"
    
    cat > $CLIENT_SCRIPT << 'EOF'
#!/usr/bin/env python3
"""
Super Simple MAW Game Test Client
Does NOT require websocket library
"""
import socket
import json
import sys
import time

class TCPGameClient:
    def __init__(self, player_id):
        self.player_id = player_id
        self.name = f"Player{player_id}"
        self.token = f"player{player_id}"
        
    def run_test(self):
        print(f"🎮 {self.name} starting test...")
        
        try:
            # Create TCP socket (NOT WebSocket)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            
            # Connect to server
            print(f"  Connecting to localhost:8888...")
            sock.connect(('localhost', 8888))
            print(f"  ✅ Connected!")
            
            # Simple test message
            test_msg = json.dumps({
                "type": "JOIN",
                "token": self.token,
                "name": self.name
            }) + "\n"
            
            # Send message
            sock.sendall(test_msg.encode('utf-8'))
            print(f"  📤 Sent JOIN message")
            
            # Try to receive response
            try:
                response = sock.recv(4096)
                if response:
                    print(f"  📨 Received {len(response)} bytes")
                    # Try to parse as JSON
                    try:
                        data = json.loads(response.decode('utf-8').strip())
                        print(f"  📊 Message type: {data.get('type', 'UNKNOWN')}")
                    except:
                        print(f"  📊 Raw response: {response[:50]}...")
            except socket.timeout:
                print(f"  ⏰ Timeout waiting for response")
                
            # Close connection
            sock.close()
            print(f"  👋 Disconnected")
            
        except ConnectionRefusedError:
            print(f"  ❌ Connection refused - Is server running?")
        except Exception as e:
            print(f"  ❌ Error: {e}")
            
        print(f"🎮 {self.name} test complete")

def main():
    if len(sys.argv) > 1:
        player_id = sys.argv[1]
    else:
        player_id = "1"
    
    client = TCPGameClient(player_id)
    client.run_test()
    
    # Keep client alive for a bit
    time.sleep(2)

if __name__ == "__main__":
    main()
EOF
    
    chmod +x $CLIENT_SCRIPT
    echo -e "${GREEN}✅ Created $CLIENT_SCRIPT${NC}"
}

# Main function
main() {
    # Check Python
    check_python_deps
    
    # Compile server
    if ! compile_server; then
        echo -e "${RED}Cannot continue without server${NC}"
        exit 1
    fi
    
    # Create client
    create_simple_client
    
    # Kill existing server
    echo -e "${YELLOW}🛑 Stopping existing server...${NC}"
    pkill -f "./$SERVER_BINARY" 2>/dev/null || true
    sleep 1
    
    # Start server
    echo -e "${BLUE}🚀 Starting server...${NC}"
    ./$SERVER_BINARY &
    SERVER_PID=$!
    sleep 3
    
    if ! ps -p $SERVER_PID > /dev/null; then
        echo -e "${RED}❌ Server failed to start${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Server started (PID: $SERVER_PID)${NC}"
    
    # Start simple test clients
    echo -e "${BLUE}🎮 Starting simple tests...${NC}"
    for i in $(seq 1 $MAX_PLAYERS); do
        echo "  Testing Player $i..."
        python3 $CLIENT_SCRIPT $i &
        sleep 1
    done
    
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}   🎮 MAW Server is running!           ${NC}"
    echo -e "${GREEN}   PID: $SERVER_PID                   ${NC}"
    echo -e "${GREEN}   Port: 8888                         ${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "${YELLOW}To test manually:${NC}"
    echo "  Open browser to: http://localhost:8888"
    echo "  Or use: telnet localhost 8888"
    echo ""
    echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
    
    # Wait
    wait $SERVER_PID
}

# Cleanup
cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 Stopping server...${NC}"
    kill $SERVER_PID 2>/dev/null || true
    echo -e "${GREEN}✅ Done${NC}"
    exit 0
}

trap cleanup SIGINT
main