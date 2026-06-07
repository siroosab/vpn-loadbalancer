"""
Connectivity Tester Module
Tests each VPN server for OpenVPN connectivity.
"""

import time
import subprocess
import tempfile
import os
from typing import List, Dict, Callable, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from vpn_connector import (
    create_openvpn_config, start_openvpn, stop_openvpn
)


def ping_server(ip: str, timeout: int = 5) -> bool:
    """
    Test if a server is reachable via ping.
    """
    try:
        cmd = f'ping -n 1 -w {timeout*1000} {ip}'
        result = subprocess.run(cmd, shell=True, capture_output=True, timeout=timeout+2, text=True)
        return result.returncode == 0
    except:
        return False


def test_server(server: Dict, callback: Optional[Callable] = None) -> Dict:
    """
    Test a VPN server for OpenVPN connectivity.
    
    Args:
        server: Server dict from vpngate_api
        callback: Callback function for logging (receives log_message: str)
        
    Returns:
        Updated server dict with openvpn flag
    """
    def log(message: str):
        if callback:
            callback(message)
        else:
            print(message)
    
    server_ip = server.get('ip', '')
    openvpn_config = server.get('openvpn_config', '')
    
    log(f"[TEST] Testing {server_ip}")
    
    # Check if config exists
    if not openvpn_config:
        log(f"[OpenVPN] ✗ No OpenVPN config available")
        server['openvpn'] = False
        server['tested'] = True
        return server
    
    # Check if config is valid base64
    if len(openvpn_config) < 100:
        log(f"[OpenVPN] ✗ Config too short, probably invalid")
        server['openvpn'] = False
        server['tested'] = True
        return server
    
    # Quick ping test first
    log(f"[PING] Testing reachability...")
    if not ping_server(server_ip, timeout=3):
        log(f"[PING] ✗ Server not reachable")
        server['openvpn'] = False
        server['tested'] = True
        return server
    
    log(f"[PING] ✓ Server is reachable")
    
    # Test OpenVPN
    temp_dir = tempfile.gettempdir()
    config_name = f"VPNLB_{server_ip.replace('.', '_')}"
    config_path = os.path.join(temp_dir, f"{config_name}.ovpn")
    
    try:
        log(f"[OpenVPN] Creating config file...")
        
        # Decode and write config
        if not create_openvpn_config(openvpn_config, config_path):
            log(f"[OpenVPN] ✗ Failed to create config")
            server['openvpn'] = False
        elif not os.path.exists(config_path):
            log(f"[OpenVPN] ✗ Config file was not created")
            server['openvpn'] = False
        elif os.path.getsize(config_path) < 100:
            log(f"[OpenVPN] ✗ Config file is too small/invalid")
            server['openvpn'] = False
        else:
            log(f"[OpenVPN] Connecting (timeout: 30s)...")
            
            # Start OpenVPN connection - returns (success, interface_ip)
            success, interface_ip = start_openvpn(config_path, config_name)
            
            if success and interface_ip:
                log(f"[OpenVPN] ✓ Connected! Interface IP: {interface_ip}")
                server['openvpn'] = True
                server['interface_ip'] = interface_ip
                server['protocols'].append('OpenVPN')
                
                # Wait a bit then disconnect
                time.sleep(2)
            else:
                log(f"[OpenVPN] ✗ Connection failed or no IP assigned")
                server['openvpn'] = False
            
            # Always stop OpenVPN
            try:
                time.sleep(1)
                stop_openvpn(config_name)
            except:
                pass
    
    except Exception as e:
        log(f"[OpenVPN] ✗ Error: {str(e)[:40]}")
        server['openvpn'] = False
    
    finally:
        # Cleanup config file
        try:
            if os.path.exists(config_path):
                os.remove(config_path)
        except:
            pass
    
    server['tested'] = True
    
    # Summary
    if server['openvpn']:
        log(f"[✓] {server_ip}: OpenVPN working!")
    else:
        log(f"[✗] {server_ip}: OpenVPN failed")
    
    return server


def test_all_servers(
    servers: List[Dict],
    callback: Optional[Callable] = None,
    max_workers: int = 1
) -> List[Dict]:
    """
    Test all servers in parallel for OpenVPN connectivity.
    
    Args:
        servers: List of server dicts
        callback: Callback function for logging
        max_workers: Maximum number of parallel tests (1 for OpenVPN stability)
        
    Returns:
        List of servers where openvpn==True
    """
    def log(message: str):
        if callback:
            callback(message)
        else:
            print(message)
    
    if not servers:
        log("No servers to test")
        return []
    
    log(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    log(f"Starting OpenVPN tests for {len(servers)} servers")
    log(f"Max parallel workers: {max_workers}")
    log(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    tested_servers = []
    
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(test_server, server, callback): server 
                for server in servers
            }
            
            completed = 0
            for future in as_completed(futures):
                try:
                    result = future.result()
                    tested_servers.append(result)
                    completed += 1
                    log(f"[PROGRESS] {completed}/{len(servers)} servers tested")
                except Exception as e:
                    log(f"[ERROR] Exception during testing: {e}")
    except Exception as e:
        log(f"[ERROR] ThreadPoolExecutor error: {e}")
    
    # Filter healthy servers (OpenVPN working)
    healthy_servers = [s for s in tested_servers if s.get('openvpn', False)]
    
    log(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    log(f"Testing complete!")
    log(f"Tested: {len(tested_servers)}, Healthy: {len(healthy_servers)}")
    log(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    return healthy_servers
