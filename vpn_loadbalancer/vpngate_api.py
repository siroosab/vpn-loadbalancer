"""
VPNGate API Module
Fetches and parses the public VPN server list from VPNGate.
"""

import requests
import csv
import io
import time
import base64
from typing import List, Dict, Optional


# Cache for API results
_server_cache: Optional[List[Dict]] = None
_cache_timestamp: float = 0


def fix_openvpn_config(config_b64: str) -> str:
    """
    Fix OpenVPN config for compatibility with OpenVPN 2.5+
    Removes deprecated cipher lines.
    Cipher directives will be set via command-line flags instead.
    
    Args:
        config_b64: Base64 encoded config from VPNGate
        
    Returns:
        Fixed base64 encoded config
    """
    try:
        # Decode
        config_text = base64.b64decode(config_b64).decode('utf-8', errors='ignore')
        
        # Fix issues line by line
        lines = config_text.split('\n')
        fixed_lines = []
        
        for line in lines:
            # Skip/comment deprecated options
            if line.strip().startswith('persist-key'):
                fixed_lines.append('# ' + line + ' # DEPRECATED')
                continue
            
            # Remove all cipher-related lines, they will be set via CLI flags
            if 'data-ciphers' in line or 'cipher' in line:
                continue
            
            # Remove tun-ipv6 (causes issues)
            if line.strip() == 'tun-ipv6':
                fixed_lines.append('# ' + line)
                continue
            
            fixed_lines.append(line)
        
        # Re-encode
        fixed_text = '\n'.join(fixed_lines)
        fixed_b64 = base64.b64encode(fixed_text.encode('utf-8')).decode('utf-8')
        
        return fixed_b64
    except Exception as e:
        print(f"Warning: Could not fix config: {e}")
        return config_b64  # Return original if fix fails


def fetch_servers(force_refresh: bool = False) -> List[Dict]:
    """
    Fetch the VPNGate public VPN server list.
    
    Args:
        force_refresh: If True, ignore cache and fetch fresh data
        
    Returns:
        List of server dicts with keys:
        - hostname, ip, score, ping, speed, country, sessions, protocols
        
    Returns empty list on network errors.
    """
    global _server_cache, _cache_timestamp
    
    # Return cache if available and not forced refresh
    if not force_refresh and _server_cache is not None:
        return _server_cache
    
    api_url = "http://www.vpngate.net/api/iphone/"
    max_retries = 3
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            
            # Parse CSV response
            lines = response.text.strip().split('\n')
            servers = []
            
            for line in lines:
                # Skip comment/header lines and empty lines
                if not line or line.startswith('*') or line.startswith('#'):
                    continue
                
                # Parse CSV
                reader = csv.reader(io.StringIO(line))
                try:
                    row = next(reader)
                    if len(row) < 14:
                        continue
                    
                    server = {
                        'hostname': row[0],
                        'ip': row[1],
                        'score': int(row[2]) if row[2].isdigit() else 0,
                        'ping': int(row[3]) if row[3].isdigit() else 0,
                        'speed': int(row[4]) if row[4].isdigit() else 0,
                        'country': row[5],
                        'country_short': row[6],
                        'sessions': int(row[7]) if row[7].isdigit() else 0,
                        'uptime': int(row[8]) if row[8].isdigit() else 0,
                        'users': int(row[9]) if row[9].isdigit() else 0,
                        'traffic': int(row[10]) if row[10].isdigit() else 0,
                        'log_type': row[11] if len(row) > 11 else "",
                        'operator': row[12] if len(row) > 12 else "",
                        'openvpn_config': fix_openvpn_config(row[14]) if len(row) > 14 and row[14] else "",  # Fixed config
                        'protocols': [],  # Will be filled by tester
                        'openvpn': False,
                        'interface_ip': None,  # Will be filled during connection
                        'tested': False
                    }
                    servers.append(server)
                except (IndexError, ValueError):
                    continue
            
            # Cache the result
            _server_cache = servers
            _cache_timestamp = time.time()
            return servers
            
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            else:
                print(f"Failed to fetch servers after {max_retries} attempts: {e}")
                return []
    
    return []


def clear_cache():
    """Clear the server cache (for manual refresh)."""
    global _server_cache, _cache_timestamp
    _server_cache = None
    _cache_timestamp = 0
