"""
Test to replicate start_openvpn behaviour.
"""
import base64
import tempfile
import os
import subprocess
import time
from vpngate_api import fetch_servers
from vpn_connector import create_openvpn_config, start_openvpn

servers = fetch_servers()
if not servers:
    print("No servers found")
    exit(1)

server = servers[0]
config_b64 = server.get("openvpn_config", "")
server_ip = server.get("ip", "?")

print("Testing start_openvpn with: " + server_ip)

# Same as app.py does:
temp_dir = tempfile.gettempdir()
config_name = f"VPNLB_TEST_{server_ip.replace('.', '_')}"
config_path = os.path.join(temp_dir, f"{config_name}.ovpn")

if not create_openvpn_config(config_b64, config_path):
    print("Failed to create config")
    exit(1)

print(f"Config file: {config_path}")
print("Config content preview:")
with open(config_path, 'r') as f:
    content = f.read()
    # Print only cipher-related lines
    for line in content.split('\n'):
        if 'cipher' in line.lower() or 'data' in line.lower():
            print(f"  {line}")

success, ip = start_openvpn(config_path, config_name)
if success:
    print(f"SUCCESS! Interface IP: {ip}")
else:
    print("FAILED")
