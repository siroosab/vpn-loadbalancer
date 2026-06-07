# 🧠 Prompt: VPNGate Multi-Server Load Balancer — Python Windows App

## Project Overview

Build a **Windows desktop application** in Python that:
1. Fetches VPN server list from the **VPNGate public API**
2. Tests each server for connectivity using **L2TP/IPsec** and **MS-SSTP** protocols
3. Displays healthy servers and lets the user pick a **max connection count**
4. Connects to multiple servers simultaneously using **random load balancing**
5. Shows a **live dashboard with logs** during testing and operation

---

## Prompt (paste into VS Code AI / Copilot Chat)

```
You are an expert Python developer building a Windows desktop VPN load balancer app.
Use Python 3.10+, tkinter for UI, and follow the full spec below.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROJECT: VPNGate Multi-Server Load Balancer
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## ARCHITECTURE

The app has 4 modules:

1. vpngate_api.py      — Fetch & parse server list from VPNGate
2. vpn_connector.py    — Connect/disconnect VPN via Windows rasdial
3. tester.py           — Test each server for L2TP/IPsec & MS-SSTP
4. app.py              — Main tkinter UI dashboard (entry point)

---

## MODULE 1: vpngate_api.py

### Goal
Fetch the public VPN server list from VPNGate and return parsed server objects.

### API
- URL: http://www.vpngate.net/api/iphone/
- Response: CSV with a header comment line starting with `*`
- Fields (in order): HostName, IP, Score, Ping, Speed, CountryLong,
  CountryShort, NumVpnSessions, Uptime, TotalUsers, TotalTraffic,
  LogType, Operator, Message, OpenVPN_ConfigData_Base64
- The last line is `*` and should be skipped

### Requirements
- Function: `fetch_servers() -> list[dict]`
- Parse CSV, skip lines starting with `*` and `#`
- Each dict must include: hostname, ip, score, ping, speed, country, sessions
- Add field `protocols: []` (filled later by tester)
- Handle network errors gracefully, return empty list on failure
- Add retry logic: 3 attempts with 2s delay
- Cache result in memory for the session (don't re-fetch unless user clicks Refresh)

---

## MODULE 2: vpn_connector.py

### Goal
Create, connect, and remove Windows VPN connections using rasdial and PowerShell.

### VPNGate credentials (hardcoded constants)
```python
VPN_USERNAME = "vpn"
VPN_PASSWORD = "vpn"
```
These are the official public VPNGate credentials, same for all servers.

### Requirements

#### Function: `create_vpn_entry(name: str, server_ip: str, protocol: str) -> bool`
- Use PowerShell `Add-VpnConnection` cmdlet
- protocol is either `"L2TP"` or `"SSTP"`
- For L2TP: set `-TunnelType L2tp -L2tpPsk "vpn" -AuthenticationMethod MSChapv2`
- For SSTP: set `-TunnelType Sstp -AuthenticationMethod MSChapv2`
- Set `-Force` and `-RememberCredential` flags
- Run as subprocess, capture stdout/stderr
- Return True on success

#### Function: `connect_vpn(name: str) -> bool`
- Run: `rasdial "<name>" vpn vpn`
- Timeout: 20 seconds
- Return True if exit code == 0

#### Function: `disconnect_vpn(name: str) -> bool`
- Run: `rasdial "<name>" /disconnect`
- Return True on success

#### Function: `delete_vpn_entry(name: str)`
- Run PowerShell: `Remove-VpnConnection -Name "<name>" -Force`

#### Function: `get_interface_ip(name: str) -> str | None`
- After connecting, get the local IP of the VPN adapter
- Use `ipconfig` output or `psutil.net_if_addrs()`
- Return the 10.x.x.x or 192.168.x.x IP assigned to the VPN interface
- Return None if not found

#### Class: `VpnSession`
```python
@dataclass
class VpnSession:
    name: str          # e.g. "VPNLB_1"
    server_ip: str
    protocol: str      # "L2TP" or "SSTP"
    interface_ip: str  # local IP after connection
    connected: bool
    requests_routed: int = 0
```

---

## MODULE 3: tester.py

### Goal
Test each server for L2TP/IPsec and MS-SSTP connectivity and return results.

### Function: `test_server(server: dict, callback: callable) -> dict`

Steps:
1. Try L2TP/IPsec first:
   - Call `create_vpn_entry(name, ip, "L2TP")`
   - Call `connect_vpn(name)` with 20s timeout
   - If success: set `server["l2tp"] = True`, get interface IP, disconnect
   - If fail: set `server["l2tp"] = False`
   - Always delete the VPN entry after test
2. Try MS-SSTP second (same steps with protocol="SSTP")
3. Call `callback(log_message: str)` after each step so UI can update live
4. Return updated server dict with `l2tp: bool`, `sstp: bool`, `tested: True`

### Function: `test_all_servers(servers: list, callback: callable, max_workers: int = 5) -> list`
- Use `concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)`
- Test all servers in parallel
- Call callback with progress messages
- Return list of servers where `l2tp == True OR sstp == True`

### Naming convention for temp VPN entries
- Use unique names like `VPNLB_TEST_{ip.replace('.','_')}_{protocol}`
- Always clean up (delete) test entries even on failure (use try/finally)

---

## MODULE 4: app.py (Main UI)

### Stack
- tkinter + ttk
- threading for non-blocking operations
- queue.Queue for thread-safe UI updates

### Layout (3 panels)

```
┌─────────────────────────────────────────────────────┐
│  🛡 VPNGate Load Balancer          [status badge]   │
├──────────────────┬──────────────────────────────────┤
│  LEFT PANEL      │  RIGHT PANEL                     │
│                  │                                  │
│  [Fetch Servers] │  Live Log Dashboard              │
│  [Test Servers]  │  ┌──────────────────────────┐    │
│  ─────────────   │  │ [10:22:01] Fetching...   │    │
│  Max Connections │  │ [10:22:02] 312 servers   │    │
│  [Spinbox 1-10]  │  │ [10:22:05] Testing 1.2.. │    │
│                  │  │ [10:22:06] ✓ L2TP OK     │    │
│  Healthy Servers │  │ [10:22:07] ✗ SSTP fail   │    │
│  ┌────────────┐  │  └──────────────────────────┘    │
│  │ Server list│  │                                  │
│  │ with proto │  │  Stats row:                      │
│  │ checkboxes │  │  Tested: 0  Healthy: 0  Active:0 │
│  └────────────┘  │                                  │
│  [Connect All]   │                                  │
│  [Disconnect All]│                                  │
└──────────────────┴──────────────────────────────────┘
```

### UI Components

#### Header
- App title with shield icon (unicode: 🛡)
- Status badge: "Idle" / "Fetching" / "Testing" / "Running" — color coded

#### Left Panel: Control + Server List

**Buttons (top):**
- `[🔄 Fetch Servers]` — calls vpngate_api.fetch_servers() in thread, updates list
- `[🧪 Test Servers]` — runs tester.test_all_servers() in thread, shows progress in log

**Max Connections spinbox:**
- Label: "Max active servers:"
- ttk.Spinbox, range 1–10, default 3
- Tooltip: "Number of VPN servers to connect simultaneously"

**Server Treeview (healthy servers only):**
- Columns: #, Country, IP, Ping, Speed, L2TP, SSTP
- L2TP and SSTP columns show ✓ or ✗
- Row color: green if both protocols work, yellow if one works
- Clicking a row selects it (for future manual control)
- Shows only tested + healthy servers

**Buttons (bottom):**
- `[▶ Connect (N)]` — connects to N servers (from spinbox) randomly selected from healthy list
- `[■ Disconnect All]` — disconnects all active sessions

#### Right Panel: Live Log Dashboard

**Log textbox:**
- `tk.Text` widget, monospace font, read-only
- Dark background: `#1e1e1e`, text: `#d4d4d4`
- Color-coded lines:
  - INFO: white `#d4d4d4`
  - SUCCESS `✓`: green `#4ec994`
  - FAILURE `✗`: red `#f48771`
  - WARNING `⚠`: yellow `#dcdcaa`
  - SECTION `━`: blue `#569cd6`
- Auto-scroll to bottom
- Max 500 lines (trim old lines)

**Stats row (below log):**
- 3 metric cards side by side
- "Tested" count, "Healthy" count, "Active connections" count
- Update in real time

### Threading model
- All network operations run in `threading.Thread(daemon=True)`
- UI updates happen via `root.after(0, callback)` or `queue.Queue`
- Never call tkinter from a non-main thread directly
- Show a `ttk.Progressbar` (indeterminate) during fetch/test operations

### Load Balancing (Random)
- Maintain a list of active `VpnSession` objects
- Function `route_request(sessions: list) -> VpnSession`:
  - Pick a random session from connected ones
  - Increment `session.requests_routed`
  - Return the session (caller uses `session.interface_ip` to bind socket)
- Log each routing decision in the dashboard

### Error Handling
- All subprocess calls wrapped in try/except
- Log errors to dashboard with ✗ prefix
- If a VPN session drops unexpectedly, mark it disconnected and log ⚠ warning
- Never crash the UI on errors

---

## REQUIREMENTS FILE (requirements.txt)

```
requests>=2.31.0
psutil>=5.9.0
```
(tkinter and subprocess are stdlib)

---

## FILE STRUCTURE

```
vpn_loadbalancer/
├── app.py                 # Entry point, main UI
├── vpngate_api.py         # API fetcher
├── vpn_connector.py       # rasdial/PowerShell wrapper
├── tester.py              # Connectivity tester
├── requirements.txt
└── README.md
```

---

## IMPORTANT NOTES FOR CODE GENERATION

1. **Windows only** — use `subprocess` with `shell=True` for PowerShell/rasdial
2. **Admin rights** — Add a check at startup: if not running as admin, show a messagebox and exit
3. **VPNGate credentials** — Always use username=`vpn` password=`vpn` (public VPNGate standard)
4. **Cleanup on exit** — Hook `root.protocol("WM_DELETE_WINDOW", on_close)` to disconnect all VPNs before closing
5. **Thread safety** — Use `queue.Queue` for log messages from threads to UI
6. **No asyncio** — Use threading only (simpler, works better with tkinter)
7. **Naming** — All temp VPN connection names must start with `VPNLB_` for easy cleanup
8. **Startup check** — On launch, call PowerShell `Get-VpnConnection | Where Name -like 'VPNLB_*'` and clean up any leftover entries from previous runs

Generate all 4 files completely. Start with app.py, then the modules.
```

---

## نحوه استفاده در VS Code

1. **Ctrl+Shift+P** → `GitHub Copilot: Open Chat` یا `Cursor: New Chat`
2. پرامپت بالا را **کامل** paste کنید
3. اگر کد طولانی شد و قطع شد، بگویید: `continue from where you left off`
4. هر فایل را جداگانه در مسیر `vpn_loadbalancer/` ذخیره کنید

## نصب و اجرا

```bash
# نصب وابستگی‌ها
pip install requests psutil

# اجرا با دسترسی ادمین (ضروری)
# راست‌کلیک روی PowerShell → Run as Administrator
python app.py
```

## نکته مهم
برای اتصال L2TP/IPsec در ویندوز، اجرا با دسترسی **Administrator** الزامی است.
