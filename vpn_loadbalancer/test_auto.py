#!/usr/bin/env python3
"""
Automated test to check OpenVPN connection functionality
Run with: python test_auto.py
"""

import time
import tempfile
import os
import base64
from vpngate_api import fetch_servers
from vpn_connector import create_openvpn_config, start_openvpn, stop_openvpn

print("=" * 60)
print("AUTOMATED OPENVPN TEST")
print("=" * 60)

# Fetch servers
print("\n[1] Fetching VPN servers...")
servers = fetch_servers()
print(f"    Found {len(servers)} servers")

if not servers:
    print("ERROR: No servers found!")
    exit(1)

# Get first 3 servers with OpenVPN config
test_servers = [s for s in servers if s.get('openvpn_config', '') and len(s.get('openvpn_config', '')) > 100][:3]

if not test_servers:
    print("ERROR: No servers with OpenVPN config!")
    exit(1)

print(f"    Testing {len(test_servers)} servers with OpenVPN configs")

# Test each server
successful = 0
failed = 0

for i, server in enumerate(test_servers):
    ip = server.get('ip', 'unknown')
    config_b64 = server.get('openvpn_config', '')
    
    print(f"\n[{i+1}] Testing server: {ip}")
    print(f"    Config size: {len(config_b64)} bytes")
    
    # Create config file
    temp_dir = tempfile.gettempdir()
    config_name = f"TEST_{ip.replace('.', '_')}"
    config_path = os.path.join(temp_dir, f"{config_name}.ovpn")
    
    try:
        # Create config
        if not create_openvpn_config(config_b64, config_path):
            print(f"    ERROR: Failed to create config file")
            failed += 1
            continue
        
        print(f"    Config file created: {config_path}")
        
        # Try to connect
        print(f"    Attempting connection (30s timeout)...")
        success, interface_ip = start_openvpn(config_path, config_name)
        
        if success and interface_ip:
            print(f"    ✓ SUCCESS! Connected with IP: {interface_ip}")
            successful += 1
            
            # Give it 2 seconds then disconnect
            time.sleep(2)
            stop_openvpn(config_name)
            print(f"    Disconnected")
        else:
            print(f"    ✗ FAILED: Could not establish connection")
            failed += 1
        
    except Exception as e:
        print(f"    ERROR: {str(e)[:100]}")
        failed += 1
    
    finally:
        # Clean up
        try:
            if os.path.exists(config_path):
                os.remove(config_path)
        except:
            pass

# Summary
print("\n" + "=" * 60)
print("TEST SUMMARY")
print("=" * 60)
print(f"Successful: {successful}/{len(test_servers)}")
print(f"Failed: {failed}/{len(test_servers)}")

if successful > 0:
    print("\n✓ OpenVPN IS WORKING!")
    print("The app.py should work fine when run with admin privileges.")
else:
    print("\n✗ OpenVPN IS NOT WORKING")
    print("Check if you're running with admin privileges.")
