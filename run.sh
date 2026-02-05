#!/bin/bash
# =========================================
# MAW Battlegrounds Launcher - 4 Players
# =========================================

echo "🎮 MAW Battlegrounds Launcher (4 Players)"
echo "========================================"

# نصب dependencies پایتون
echo "📦 Installing Python dependencies..."
pip3 install -r requirements.txt

# کامپایل سرور C++
echo "🔨 Compiling server..."
g++ -std=c++17 -o server server.cpp -lboost_system -lboost_thread -lpthread -lboost_json

if [ $? -ne 0 ]; then
    echo "❌ Server compilation failed!"
    echo "⚠️ Make sure Boost libraries are installed:"
    echo "   Ubuntu/Debian: sudo apt-get install libboost-all-dev"
    echo "   Fedora: sudo dnf install boost-devel"
    echo "   Arch: sudo pacman -S boost"
    exit 1
fi

echo "✅ Server compiled successfully!"

# اجرای سرور در پس‌زمینه
echo "🌐 Starting server on port 8888..."
./server > server.log 2>&1 &
SERVER_PID=$!
sleep 3

# بررسی وضعیت سرور
if ! kill -0 $SERVER_PID 2>/dev/null; then
    echo "❌ Server failed to start!"
    exit 1
fi

echo "✅ Server is running (PID: $SERVER_PID)"
echo "========================================"

# باز کردن ۴ کلاینت در ترمینال جدا
for i in 1 2 3 4; do
    gnome-terminal -- bash -c "python3 client.py --player $i; echo 'Player $i exited'; exec bash"
done

echo "🎮 4 Clients launched. Press Ctrl+C to stop the server."

# وقتی Ctrl+C زدی، سرور بسته شود
trap "echo '🛑 Stopping server...'; kill $SERVER_PID 2>/dev/null; wait $SERVER_PID 2>/dev/null; echo '✅ Server stopped.'; exit" SIGINT SIGTERM

# صبر تا سرور بسته شود
wait $SERVER_PID
