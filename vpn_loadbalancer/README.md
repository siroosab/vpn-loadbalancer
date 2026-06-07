# 🛡 VPNGate Multi-Server Load Balancer

A Windows desktop application built with Python that fetches VPN servers from VPNGate, tests their connectivity via **OpenVPN**, and enables simultaneous connections with random load balancing.

## Features

- **🔄 Server Fetching**: Automatically fetches the latest VPN server list from VPNGate public API
- **🧪 OpenVPN Testing**: Tests each server for OpenVPN connectivity
- **📊 Live Dashboard**: Real-time log display with color-coded messages and statistics
- **⚡ Multi-Server Connection**: Connect to multiple VPN servers simultaneously
- **🎲 Random Load Balancing**: Distributes requests randomly across active connections
- **🛠️ Windows Integration**: Uses native OpenVPN client for connections
- **🔒 Admin Security**: Enforces administrator privileges for safe VPN operations

## Requirements

- **Windows 10/11** with administrator privileges
- **Python 3.10+**
- **OpenVPN Client** - Download from https://openvpn.net/community-downloads/
- **Dependencies**: `requests`, `psutil` (see requirements.txt)

## Installation

### 1. Install OpenVPN Client

1. Download OpenVPN from: https://openvpn.net/community-downloads/
2. Run the Windows installer (e.g., `OpenVPN-2.6.x-I601-amd64.msi`)
3. Choose typical installation
4. Restart your computer

### 2. Clone or download the project

```bash
cd vpn_loadbalancer
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

## Usage

### Important: Run as Administrator

Open PowerShell as Administrator:
1. Right-click on PowerShell
2. Select "Run as administrator"
3. Navigate to the project directory
4. Run:

```bash
python app.py
```

### Application Workflow

1. **Fetch Servers**
   - Click `🔄 Fetch Servers` button
   - App downloads latest VPN server list from VPNGate
   - Shows total number of available servers

2. **Test Servers**
   - Click `🧪 Test Servers` button
   - App tests each server for OpenVPN connectivity
   - Live log shows progress for each server
   - Results displayed in "Healthy Servers" list
   - Green row = OpenVPN working

3. **Configure**
   - Set "Max servers" spinbox (1-10, default 3)
   - This controls how many servers to connect to simultaneously

4. **Connect**
   - Click `▶ Connect` button
   - App connects to N random healthy servers
   - Live dashboard shows connection status

5. **Disconnect**
   - Click `■ Disconnect All` button
   - All active OpenVPN sessions are disconnected

## File Structure

```
vpn_loadbalancer/
├── app.py              # Main tkinter UI application
├── vpngate_api.py      # VPNGate API client
├── vpn_connector.py    # Windows VPN management (rasdial/PowerShell)
├── tester.py           # Connectivity testing (L2TP, SSTP)
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

## Module Details

### app.py
Main tkinter application with GUI components:
- Server fetching and testing controls
- Live log dashboard with color-coded messages
- Real-time statistics (Tested, Healthy, Active servers)
- Connection management

### vpngate_api.py
Fetches VPN server list from VPNGate:
- HTTP request to VPNGate API
- CSV parsing
- Result caching
- Retry logic (3 attempts, 2s delay)

### vpn_connector.py
Windows VPN connection management:
- Decode OpenVPN config from base64
- Write .ovpn configuration files
- Start OpenVPN client process
- Verify connection status
- Stop OpenVPN gracefully

### tester.py
Tests VPN server connectivity:
- Tests OpenVPN protocol
- Ping-based server reachability check
- Parallel testing (sequential for OpenVPN stability)
- Live progress callback logging
- Automatic cleanup of temp files

## VPNGate Credentials

This application uses the official public VPNGate credentials:
- Username: `vpn`
- Password: `vpn`

These are standard credentials used by all VPNGate users.

## OpenVPN Integration

The app uses OpenVPN configuration files embedded in VPNGate's API:
- Each server provides a base64-encoded `.ovpn` config file
- The app automatically decodes and writes these configs
- Connections use standard OpenVPN client (must be installed)
- Supports all OpenVPN authentication methods

## Important Notes

### Admin Rights
This application requires administrator privileges because it needs to:
- Start OpenVPN process
- Manage network interfaces

The app will automatically check and exit if not running as admin.

### OpenVPN Installation
If OpenVPN is not installed, the app will show a friendly error message.
Download and install from: https://openvpn.net/community-downloads/

### Cleanup
- All temporary config files are stored in Windows temp directory
- Temp files are automatically cleaned up after each test
- On exit, all OpenVPN processes are terminated gracefully

### Performance
- Server testing uses sequential processing for OpenVPN stability
- Each server test takes ~20-30 seconds
- Testing 100 servers takes ~30-50 minutes
- Results are more reliable than parallel testing

### Logging
- Live dashboard shows color-coded messages:
  - **Green (✓)**: Successful operations
  - **Red (✗)**: Failures and errors
  - **Yellow (⚠)**: Warnings
  - **Blue (━)**: Section headers

## Troubleshooting

### "Admin Required" error
- Run PowerShell/CMD as Administrator first
- Then run: `python app.py`

### "Failed to fetch servers"
- Check internet connection
- VPNGate server might be temporarily unavailable
- Try clicking "Fetch Servers" again

### "OpenVPN not found" error
- Install OpenVPN client from: https://openvpn.net/community-downloads/
- Make sure installation path is standard (C:\Program Files\OpenVPN)
- Restart the application after installation

### VPN connection fails during test
- Some servers might be offline or overloaded
- OpenVPN process might be hanging (check Task Manager)
- Restart application to kill any stuck OpenVPN processes

### No healthy servers found
- Check that OpenVPN is properly installed
- Some servers might be temporarily down
- Try testing again later
- Check Windows Firewall allows OpenVPN

## Development

### Code Structure
- Modular design with separate concerns (API, connector, tester, UI)
- Thread-safe logging with `queue.Queue`
- Comprehensive error handling throughout
- Type hints for better code clarity

### Future Enhancements
- Support for WireGuard protocol
- Connection speed monitoring
- Statistics export (CSV, JSON)
- Server sorting by ping/speed
- Auto-reconnect on disconnect
- Connection time limits
- Bandwidth throttling
- Custom authentication
- Configuration profiles

## License

This project is provided as-is for educational and personal use.

## Support

For issues or questions:
1. Check the log dashboard for detailed error messages
2. Ensure you're running as Administrator
3. Verify internet connection and VPNGate API availability
4. Check requirements are installed: `pip install -r requirements.txt`

---

**Made with 🛡️ for secure, balanced VPN connectivity**
