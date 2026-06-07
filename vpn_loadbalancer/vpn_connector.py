"""
VPN Connector Module
Manages OpenVPN connections using native Windows OpenVPN client.
"""

import subprocess
import re
import os
import base64
import tempfile
import time
import psutil
from dataclasses import dataclass
from typing import Optional, Dict


# Global dictionary to track OpenVPN processes by name
_openvpn_processes: Dict[str, object] = {}
_temp_files: Dict[str, str] = {}  # Track temp credential files for cleanup


# VPNGate public credentials
VPN_USERNAME = "vpn"
VPN_PASSWORD = "vpn"


@dataclass
class VpnSession:
    """Represents an active VPN connection."""
    name: str              # e.g., "VPNLB_1"
    server_ip: str         # IP of the VPN server
    protocol: str          # "L2TP" or "SSTP"
    interface_ip: str      # Local IP after connection (10.x.x.x or 192.168.x.x)
    connected: bool        # Connection status
    requests_routed: int = 0  # Number of requests routed through this session


def run_command(cmd: str, timeout: int = 20, log_errors: bool = True) -> tuple[bool, str]:
    """
    Run a shell command and return success status and output.
    
    Args:
        cmd: Command to run
        timeout: Command timeout in seconds
        log_errors: Whether to print errors
        
    Returns:
        (success: bool, output: str)
    """
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            timeout=timeout,
            text=True
        )
        output = result.stdout + result.stderr
        
        if not result.returncode == 0 and log_errors:
            if output:
                print(f"Command failed: {output[:100]}")
        
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        if log_errors:
            print(f"Command timeout after {timeout}s")
        return False, f"Command timeout after {timeout}s"
    except Exception as e:
        if log_errors:
            print(f"Command error: {str(e)[:100]}")
        return False, str(e)


def create_vpn_entry(name: str, server_ip: str, protocol: str) -> bool:
    """
    Create a VPN connection entry in Windows.
    
    Args:
        name: Connection name (e.g., "VPNLB_TEST_1_2_3_4_L2TP")
        server_ip: IP address of the VPN server
        protocol: "L2TP" or "SSTP"
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if protocol.upper() == "L2TP":
            cmd = f'''powershell -Command "Add-VpnConnection -Name '{name}' -ServerAddress '{server_ip}' -TunnelType L2tp -L2tpPsk 'vpn' -AuthenticationMethod MSChapv2 -Force -RememberCredential"'''
        elif protocol.upper() == "SSTP":
            cmd = f'''powershell -Command "Add-VpnConnection -Name '{name}' -ServerAddress '{server_ip}' -TunnelType Sstp -AuthenticationMethod MSChapv2 -Force -RememberCredential"'''
        else:
            return False
        
        success, output = run_command(cmd, timeout=15)
        return success
    except Exception as e:
        print(f"Error creating VPN entry: {e}")
        return False


def connect_vpn(name: str) -> bool:
    """
    Connect to a VPN by name using rasdial.
    
    Args:
        name: Connection name
        
    Returns:
        True if successful, False otherwise
    """
    try:
        cmd = f'rasdial "{name}" {VPN_USERNAME} {VPN_PASSWORD}'
        success, output = run_command(cmd, timeout=20)
        return success
    except Exception as e:
        print(f"Error connecting VPN: {e}")
        return False


def disconnect_vpn(name: str) -> bool:
    """
    Disconnect from a VPN by name.
    
    Args:
        name: Connection name
        
    Returns:
        True if successful, False otherwise
    """
    try:
        cmd = f'rasdial "{name}" /disconnect'
        success, output = run_command(cmd, timeout=10)
        return success
    except Exception as e:
        print(f"Error disconnecting VPN: {e}")
        return False


def delete_vpn_entry(name: str) -> bool:
    """
    Delete a VPN connection entry.
    
    Args:
        name: Connection name
        
    Returns:
        True if successful, False otherwise
    """
    try:
        cmd = f'powershell -Command "Remove-VpnConnection -Name \'{name}\' -Force -ErrorAction SilentlyContinue"'
        success, output = run_command(cmd, timeout=10)
        return True  # Don't fail if connection doesn't exist
    except Exception as e:
        print(f"Error deleting VPN entry: {e}")
        return False


def get_interface_ip(name: str) -> Optional[str]:
    """
    Get the local IP assigned to the VPN interface.
    
    Args:
        name: Connection name
        
    Returns:
        IP address (10.x.x.x or 192.168.x.x) or None if not found
    """
    try:
        # Use ipconfig to get VPN adapter IP
        success, output = run_command("ipconfig", timeout=10)
        if not success:
            return None
        
        # Parse ipconfig output for the VPN adapter
        lines = output.split('\n')
        in_vpn_adapter = False
        
        for line in lines:
            # Look for the VPN adapter section (usually RAS adapter or similar)
            if name.lower() in line.lower() or "ppp adapter" in line.lower():
                in_vpn_adapter = True
            
            if in_vpn_adapter and "IPv4 Address" in line:
                # Extract IP address
                match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                if match:
                    ip = match.group(1)
                    # Return if it's a private IP
                    if ip.startswith('10.') or ip.startswith('192.168.'):
                        return ip
        
        # Alternative: use netstat to find the VPN connection
        success, output = run_command("netstat -an", timeout=10)
        if success:
            # Look for established connections from VPN IP range
            import psutil
            for conn in psutil.net_if_addrs().values():
                for addr in conn:
                    if addr.family == 2:  # IPv4
                        if addr.address.startswith('10.') or addr.address.startswith('192.168.'):
                            return addr.address
        
        return None
    except Exception as e:
        print(f"Error getting interface IP: {e}")
        return None


def cleanup_vpn_entries():
    """
    Clean up any leftover VPN entries from previous runs (VPNLB_* entries).
    Called at startup to avoid orphaned connections.
    """
    try:
        cmd = '''powershell -Command "Get-VpnConnection | Where-Object {$_.Name -like 'VPNLB_*'} | Remove-VpnConnection -Force -ErrorAction SilentlyContinue"'''
        run_command(cmd, timeout=15)
    except Exception as e:
        print(f"Error cleaning up VPN entries: {e}")


# ============================================================================
# OpenVPN Management Functions
# ============================================================================

def create_openvpn_config(config_base64: str, config_path: str) -> bool:
    """
    Decode and write OpenVPN config from base64.
    Config is already fixed at API fetch time.
    
    Args:
        config_base64: Base64 encoded OpenVPN config (already fixed)
        config_path: Path to write .ovpn file
        
    Returns:
        True if successful
    """
    try:
        # Decode base64 (already fixed at API fetch)
        config_data = base64.b64decode(config_base64).decode('utf-8', errors='ignore')
        
        # Write to file
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, 'w') as f:
            f.write(config_data)
        
        return True
    except Exception as e:
        print(f"Error creating OpenVPN config: {e}")
        return False


def start_openvpn(config_path: str, name: str) -> tuple[bool, Optional[str]]:
    """
    Start OpenVPN connection and wait for it to establish.
    
    Args:
        config_path: Path to .ovpn config file
        name: Connection name for identification
        
    Returns:
        (success: bool, interface_ip: str or None)
    """
    try:
        # Find OpenVPN executable
        openvpn_paths = [
            r"C:\Program Files\OpenVPN\bin\openvpn.exe",
            r"C:\Program Files (x86)\OpenVPN\bin\openvpn.exe",
        ]
        
        openvpn_exe = None
        for path in openvpn_paths:
            if os.path.exists(path):
                openvpn_exe = path
                break
        
        if not openvpn_exe:
            print("[ERROR] OpenVPN executable not found in standard paths")
            print("[ERROR] Please install OpenVPN from: https://openvpn.net/community-downloads/")
            return False, None
        
        # Verify config file exists
        if not os.path.exists(config_path):
            print(f"[ERROR] Config file not found: {config_path}")
            return False, None
        
                # Create credentials file (more reliable than stdin piping)
        creds_dir = tempfile.gettempdir()
        creds_path = os.path.join(creds_dir, f"{name}_creds.txt")
        with open(creds_path, 'w') as f:
            f.write(f"{VPN_USERNAME}\n{VPN_PASSWORD}\n")
        _temp_files[name] = creds_path
        
        # Start OpenVPN with credential file
        cmd = f'"{openvpn_exe}" --config "{config_path}" --auth-user-pass "{creds_path}" --cipher AES-256-CBC --data-ciphers AES-256-CBC:AES-128-CBC:CHACHA20-POLY1305'
        
        # Create process
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        
        try:
            process = subprocess.Popen(
                cmd,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=startupinfo,
                text=True
            )
        except Exception as e:
            print(f"[ERROR] Failed to start OpenVPN process: {e}")
            if creds_path in _temp_files:
                try:
                    os.remove(creds_path)
                except:
                    pass
                del _temp_files[name]
            return False, None
        
        # Store process reference
        _openvpn_processes[name] = process
        
        # Wait for connection to establish (up to 30 seconds)
        for attempt in range(30):
            time.sleep(1)
            
            # Check if process is still running
            if process.poll() is not None:
                # Process exited unexpectedly
                try:
                    stdout_out = process.stdout.read() if process.stdout else ""
                    stderr_out = process.stderr.read() if process.stderr else ""
                    error_output = (stdout_out + stderr_out)[:300]
                except:
                    error_output = "Unknown error"
                
                print(f"[ERROR] OpenVPN process died after {attempt}s")
                print(f"[ERROR] Output: {error_output}")
                return False, None
            
            # Try to get interface IP
            interface_ip = _get_openvpn_interface_ip()
            if interface_ip:
                print(f"[SUCCESS] OpenVPN connected! Interface IP: {interface_ip}")
                return True, interface_ip
        
        # Timeout - process is running but no IP yet
        print(f"[ERROR] OpenVPN timeout - no IP assigned after 30 seconds")
        try:
            process.terminate()
            process.wait(timeout=5)
        except:
            try:
                process.kill()
            except:
                pass
        return False, None
        
    except Exception as e:
        print(f"[ERROR] Error starting OpenVPN: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def _get_openvpn_interface_ip() -> Optional[str]:
    """
    Find the IP address assigned to OpenVPN interface.
    Looks for TAP or TUN adapters.
    """
    try:
        import psutil
        import socket
        
        # Get all network interfaces
        addrs = psutil.net_if_addrs()
        
        for iface_name, iface_addrs in addrs.items():
            # Look for OpenVPN adapters (TAP, TUN)
            if 'tap' in iface_name.lower() or 'tun' in iface_name.lower() or 'openvpn' in iface_name.lower():
                for addr in iface_addrs:
                    # IPv4 address (family=2 for IPv4)
                    if addr.family == socket.AF_INET:
                        ip = addr.address
                        # Return if it's a private IP (VPN IP range)
                        if ip.startswith('10.') or ip.startswith('172.') or ip.startswith('192.'):
                            return ip
        
        # Alternative: check ipconfig output for TAP/TUN
        import subprocess
        result = subprocess.run('ipconfig', shell=True, capture_output=True, text=True, timeout=5)
        lines = result.stdout.split('\n')
        
        in_tap = False
        for line in lines:
            if 'tap' in line.lower() or 'tun' in line.lower() or 'openvpn' in line.lower():
                in_tap = True
            elif in_tap and 'IPv4 Address' in line:
                match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                if match:
                    return match.group(1)
            elif in_tap and 'Adapter' in line:
                in_tap = False
        
        return None
    except Exception as e:
        print(f"Error getting OpenVPN interface IP: {e}")
        return None


def stop_openvpn(name: str) -> bool:
    """
    Stop OpenVPN connection by process reference.
    
    Args:
        name: Connection name
        
    Returns:
        True if successful
    """
    try:
        # Kill by stored process reference first
        if name in _openvpn_processes:
            process = _openvpn_processes[name]
            if process.poll() is None:  # Process still running
                process.terminate()
                time.sleep(1)
                if process.poll() is None:  # Still running, force kill
                    process.kill()
            del _openvpn_processes[name]
        
        # Clean up temp credential file
        if name in _temp_files:
            try:
                os.remove(_temp_files[name])
            except:
                pass
            del _temp_files[name]
        
        # Also kill any remaining openvpn.exe processes
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                if 'openvpn' in proc.info['name'].lower():
                    proc.kill()
        except:
            pass
        
        return True
    except Exception as e:
        print(f"Error stopping OpenVPN: {e}")
        return False


def check_openvpn_installed() -> bool:
    """
    Check if OpenVPN is installed on the system.
    
    Returns:
        True if OpenVPN executable found, False otherwise
    """
    openvpn_paths = [
        r"C:\Program Files\OpenVPN\bin\openvpn.exe",
        r"C:\Program Files (x86)\OpenVPN\bin\openvpn.exe",
    ]
    
    for path in openvpn_paths:
        if os.path.exists(path):
            return True
    
    return False
