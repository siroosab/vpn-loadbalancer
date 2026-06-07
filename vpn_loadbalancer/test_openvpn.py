#!/usr/bin/env python3
import base64
import tempfile
import os
import subprocess
import time
from vpngate_api import fetch_servers

servers = fetch_servers()
if not servers:
    print("No servers found")
    exit(1)

server = servers[0]
config_b64 = server.get("openvpn_config", "")
server_ip = server.get("ip", "?")

print("Testing OpenVPN: " + server_ip)

config_data = base64.b64decode(config_b64).decode("utf-8", errors="ignore")
temp_dir = tempfile.gettempdir()
config_path = os.path.join(temp_dir, "test.ovpn")

with open(config_path, "w") as f:
    f.write(config_data)

creds_path = os.path.join(temp_dir, "test_creds.txt")
with open(creds_path, "w") as f:
    f.write("vpn\nvpn\n")

openvpn_exe = r"C:\Program Files\OpenVPN\bin\openvpn.exe"
cmd = openvpn_exe + ' --config "' + config_path + '" --auth-user-pass "' + creds_path + '"'

print("Starting OpenVPN...")
process = subprocess.Popen(cmd, shell=False)

for i in range(5):
    time.sleep(1)
    rc = process.poll()
    if rc is not None:
        print("EXITED: " + str(rc))
        break
    print("Running..." + str(i))

process.terminate()
