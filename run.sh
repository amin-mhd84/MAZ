#!/bin/bash

# Terminal 1: Server
gnome-terminal -- bash -c './maw_server; exec bash' &

# Wait a bit for server to start
sleep 2

# Terminal 2: Client P1
gnome-terminal -- bash -c 'python3 client.py --name "P1"; exec bash' &

# Terminal 3: Client P2
gnome-terminal -- bash -c 'python3 client.py --name "P2"; exec bash' &

# Terminal 4: Client P3
gnome-terminal -- bash -c 'python3 client.py --name "P3"; exec bash' &

# Terminal 5: Client P4
gnome-terminal -- bash -c 'python3 client.py --name "P4"; exec bash' &