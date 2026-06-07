#!/usr/bin/env python3
"""Test script to check VPNGate API"""

from vpngate_api import fetch_servers

servers = fetch_servers()
print(f"Total servers: {len(servers)}")

# Check first 5 servers
for i, s in enumerate(servers[:5]):
    ip = s.get('ip', 'N/A')
    config = s.get('openvpn_config', '')
    has_config = len(config) > 100
    
    print(f"\nServer {i+1}: {ip}")
    print(f"  OpenVPN config: {has_config}")
    print(f"  Config size: {len(config)} bytes")
    
    if has_config:
        # Try to decode first 100 chars
        import base64
        try:
            decoded = base64.b64decode(config[:100])
            print(f"  Config valid base64: True")
        except:
            print(f"  Config valid base64: False")

print(f"\n\nServers with OpenVPN configs: {sum(1 for s in servers if len(s.get('openvpn_config', '')) > 100)}")
