"""Debug test for OpenVPN cipher issue."""
import base64
import tempfile
import os
import subprocess
import time
from vpngate_api import fetch_servers

# Get server config (already fixed by vpngate_api)
server = fetch_servers()[0]
config_b64 = server['openvpn_config']

# Decode and write config
config_data = base64.b64decode(config_b64).decode('utf-8', errors='ignore')
temp_dir = tempfile.gettempdir()
config_path = os.path.join(temp_dir, 'debug_test.ovpn')

with open(config_path, 'w') as f:
    f.write(config_data)

# Print config cipher-related lines
print("=== Config cipher lines ===")
for line in config_data.split('\n'):
    if 'cipher' in line.lower() or 'data' in line.lower():
        print(f"  {line}")

# Run OpenVPN with same flags as start_openvpn
openvpn_exe = r'C:\\Program Files\\OpenVPN\\bin\\openvpn.exe'
cmd = f'"{openvpn_exe}" --config "{config_path}" --auth-user-pass --cipher AES-256-CBC --data-ciphers AES-256-CBC:AES-128-CBC:CHACHA20-POLY1305'

print(f"\\nCommand: {cmd}")
print("Starting OpenVPN...")

process = subprocess.Popen(
    cmd,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

# Send credentials
process.stdin.write('vpn\\nvpn\\n')
process.stdin.flush()
process.stdin.close()

# Wait a moment
time.sleep(3)

# Check if process died
rc = process.poll()
if rc is not None:
    out, err = process.communicate()
    print(f"EXIT CODE: {rc}")
    print("=== STDOUT ===")
    print(out[:500])
    print("=== STDERR ===")
    print(err[:500])
else:
    print("Process still running!")
    out, err = process.communicate(timeout=5)
    print("=== STDOUT ===")
    print(out[:500])
    print("=== STDERR ===")
    print(err[:500])
    process.terminate()