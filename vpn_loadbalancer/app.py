"""
VPNGate Multi-Server Load Balancer
Main tkinter UI application
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue
import os
import sys
import time
from datetime import datetime
from typing import List, Dict, Optional
import ctypes
import random
from vpngate_api import fetch_servers, clear_cache
from vpn_connector import (
    VpnSession, cleanup_vpn_entries, disconnect_vpn, delete_vpn_entry,
    create_openvpn_config, start_openvpn, stop_openvpn, check_openvpn_installed
)
from tester import test_all_servers
import tempfile


class VPNLoadBalancerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🛡 VPNGate Load Balancer")
        self.root.geometry("950x600")
        self.root.resizable(True, True)
        
        # Check admin rights
        self.check_admin_rights()
        
        # Check if OpenVPN is installed
        self.check_openvpn_installed()
        
        # State variables
        self.all_servers: List[Dict] = []
        self.healthy_servers: List[Dict] = []
        self.active_sessions: List[VpnSession] = []
        self.is_testing = False
        self.is_connecting = False
        self.log_queue: queue.Queue = queue.Queue()
        
        # Setup UI
        self.setup_styles()
        self.create_ui()
        self.cleanup_vpn_entries()
        
        # Process queue for thread-safe logging
        self.process_log_queue()
        
        # Hook window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def check_admin_rights(self):
        """Check if running with administrator privileges."""
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        except:
            is_admin = False
        
        if not is_admin:
            messagebox.showerror(
                "Admin Required",
                "This application requires administrator privileges.\n\n"
                "Please run as Administrator."
            )
            sys.exit(1)
    
    def check_openvpn_installed(self):
        """Check if OpenVPN is installed on the system."""
        if not check_openvpn_installed():
            messagebox.showerror(
                "OpenVPN Not Found",
                "OpenVPN client is not installed on this system.\n\n"
                "Please download and install OpenVPN from:\n"
                "https://openvpn.net/community-downloads/\n\n"
                "Standard installation path should be:\n"
                "C:\\Program Files\\OpenVPN\\bin\\openvpn.exe"
            )
            sys.exit(1)
    
    def setup_styles(self):
        """Configure tkinter styles."""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure colors for light theme
        bg_color = "#f0f0f0"
        fg_color = "#000000"
        
        style.configure("TButton", font=("Arial", 9))
        style.configure("TLabel", font=("Arial", 9), background=bg_color)
        style.configure("TLabelframe", font=("Arial", 9, "bold"), background=bg_color)
        style.configure("Treeview", font=("Courier", 8), rowheight=20)
        style.configure("Treeview.Heading", font=("Arial", 8, "bold"))
    
    def create_ui(self):
        """Create the main UI layout."""
        # Header
        header_frame = ttk.Frame(self.root)
        header_frame.pack(fill=tk.X, padx=5, pady=5)
        
        title_label = ttk.Label(header_frame, text="🛡 VPNGate Load Balancer", 
                               font=("Arial", 14, "bold"))
        title_label.pack(side=tk.LEFT)
        
        self.status_label = ttk.Label(header_frame, text="Status: Idle", 
                                     font=("Arial", 9, "bold"), foreground="green")
        self.status_label.pack(side=tk.RIGHT)
        
        # Main content frame with two panels
        content_frame = ttk.Frame(self.root)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # LEFT PANEL
        left_frame = ttk.LabelFrame(content_frame, text="Controls & Servers", padding=5)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 3))
        left_frame.configure(width=280)
        
        # Buttons
        button_frame = ttk.Frame(left_frame)
        button_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.fetch_btn = ttk.Button(button_frame, text="🔄 Fetch Servers", 
                                    command=self.on_fetch_servers)
        self.fetch_btn.pack(fill=tk.X, pady=2)
        
        self.test_btn = ttk.Button(button_frame, text="🧪 Test Servers", 
                                   command=self.on_test_servers, state=tk.DISABLED)
        self.test_btn.pack(fill=tk.X, pady=2)
        
        # Max connections spinbox
        spinbox_frame = ttk.Frame(left_frame)
        spinbox_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(spinbox_frame, text="Max servers:").pack(side=tk.LEFT)
        self.max_connections_var = tk.IntVar(value=3)
        self.max_spinbox = ttk.Spinbox(spinbox_frame, from_=1, to=10, 
                                       textvariable=self.max_connections_var,
                                       width=5, state="readonly")
        self.max_spinbox.pack(side=tk.LEFT, padx=5)
        
        # Server list treeview
        ttk.Label(left_frame, text="Healthy Servers:", 
                 font=("Arial", 8, "bold")).pack(pady=(5, 2))
        
        tree_frame = ttk.Frame(left_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.server_tree = ttk.Treeview(
            tree_frame,
            columns=("Country", "IP", "Ping", "Speed", "OpenVPN"),
            show="tree headings",
            height=8,
            yscrollcommand=scrollbar.set
        )
        scrollbar.config(command=self.server_tree.yview)
        
        # Configure columns
        self.server_tree.column("#0", width=30, anchor="center")  # # column
        self.server_tree.column("Country", width=60, anchor="center")
        self.server_tree.column("IP", width=100, anchor="center")
        self.server_tree.column("Ping", width=50, anchor="center")
        self.server_tree.column("Speed", width=50, anchor="center")
        self.server_tree.column("OpenVPN", width=60, anchor="center")
        
        # Configure headings
        self.server_tree.heading("#0", text="#", anchor="center")
        self.server_tree.heading("Country", text="Country")
        self.server_tree.heading("IP", text="IP")
        self.server_tree.heading("Ping", text="Ping")
        self.server_tree.heading("Speed", text="Speed")
        self.server_tree.heading("OpenVPN", text="OpenVPN")
        
        self.server_tree.pack(fill=tk.BOTH, expand=True)
        
        # Active sessions treeview
        ttk.Label(left_frame, text="Active Sessions:", 
                 font=("Arial", 8, "bold")).pack(pady=(5, 2))
        
        sessions_frame = ttk.Frame(left_frame)
        sessions_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        scrollbar_sessions = ttk.Scrollbar(sessions_frame)
        scrollbar_sessions.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.sessions_tree = ttk.Treeview(
            sessions_frame,
            columns=("ServerIP", "LocalIP", "Requests"),
            show="tree headings",
            height=3,
            yscrollcommand=scrollbar_sessions.set
        )
        scrollbar_sessions.config(command=self.sessions_tree.yview)
        
        # Configure columns
        self.sessions_tree.column("#0", width=30, anchor="center")  # # column
        self.sessions_tree.column("ServerIP", width=100, anchor="center")
        self.sessions_tree.column("LocalIP", width=100, anchor="center")
        self.sessions_tree.column("Requests", width=60, anchor="center")
        
        # Configure headings
        self.sessions_tree.heading("#0", text="#", anchor="center")
        self.sessions_tree.heading("ServerIP", text="Server IP")
        self.sessions_tree.heading("LocalIP", text="Local IP")
        self.sessions_tree.heading("Requests", text="Requests")
        
        self.sessions_tree.pack(fill=tk.BOTH, expand=True)
        
        # Connect/Disconnect buttons
        conn_frame = ttk.Frame(left_frame)
        conn_frame.pack(fill=tk.X, pady=(0, 3))
        
        self.connect_btn = ttk.Button(conn_frame, text="▶ Connect", 
                                      command=self.on_connect, state=tk.DISABLED)
        self.connect_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        
        self.disconnect_btn = ttk.Button(conn_frame, text="■ Disconnect All", 
                                         command=self.on_disconnect, state=tk.DISABLED)
        self.disconnect_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # RIGHT PANEL
        right_frame = ttk.LabelFrame(content_frame, text="Live Log Dashboard", padding=5)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(3, 0))
        
        # Log textbox
        log_frame = ttk.Frame(right_frame)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        scrollbar_y = ttk.Scrollbar(log_frame)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.log_text = tk.Text(log_frame, height=16, wrap=tk.WORD, 
                               font=("Courier New", 8),
                               bg="#1e1e1e", fg="#d4d4d4",
                               yscrollcommand=scrollbar_y.set,
                               state=tk.DISABLED)
        scrollbar_y.config(command=self.log_text.yview)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Configure log text tags for colors
        self.log_text.tag_config("info", foreground="#d4d4d4")
        self.log_text.tag_config("success", foreground="#4ec994")
        self.log_text.tag_config("error", foreground="#f48771")
        self.log_text.tag_config("warning", foreground="#dcdcaa")
        self.log_text.tag_config("section", foreground="#569cd6")
        
        # Stats row
        stats_frame = ttk.Frame(right_frame)
        stats_frame.pack(fill=tk.X)
        
        # Tested count
        tested_card = ttk.LabelFrame(stats_frame, text="Tested", padding=3)
        tested_card.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))
        self.tested_label = ttk.Label(tested_card, text="0", 
                                     font=("Arial", 11, "bold"), foreground="blue")
        self.tested_label.pack()
        
        # Healthy count
        healthy_card = ttk.LabelFrame(stats_frame, text="Healthy", padding=3)
        healthy_card.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)
        self.healthy_label = ttk.Label(healthy_card, text="0", 
                                      font=("Arial", 11, "bold"), foreground="green")
        self.healthy_label.pack()
        
        # Active count
        active_card = ttk.LabelFrame(stats_frame, text="Active", padding=3)
        active_card.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(3, 0))
        self.active_label = ttk.Label(active_card, text="0", 
                                     font=("Arial", 11, "bold"), foreground="orange")
        self.active_label.pack()
    
    def log(self, message: str, level: str = "info"):
        """Add a log message to the queue (thread-safe)."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}"
        self.log_queue.put((formatted, level))
    
    def process_log_queue(self):
        """Process log queue and update UI (main thread only)."""
        try:
            while True:
                message, level = self.log_queue.get_nowait()
                self.log_text.config(state=tk.NORMAL)
                
                # Determine tag based on message content
                if "✓" in message:
                    tag = "success"
                elif "✗" in message or "ERROR" in message:
                    tag = "error"
                elif "⚠" in message or "WARNING" in message:
                    tag = "warning"
                elif "━" in message:
                    tag = "section"
                else:
                    tag = level
                
                self.log_text.insert(tk.END, message + "\n", tag)
                
                # Trim to 500 lines
                line_count = int(self.log_text.index('end-1c').split('.')[0])
                if line_count > 500:
                    self.log_text.delete('1.0', '2.0')
                
                self.log_text.see(tk.END)
                self.log_text.config(state=tk.DISABLED)
        except queue.Empty:
            pass
        
        # Schedule next check
        self.root.after(100, self.process_log_queue)
    
    def update_stats(self):
        """Update statistics display."""
        tested_count = len([s for s in self.all_servers if s.get('tested', False)])
        healthy_count = len(self.healthy_servers)
        active_count = len([s for s in self.active_sessions if s.connected])
        
        self.tested_label.config(text=str(tested_count))
        self.healthy_label.config(text=str(healthy_count))
        self.active_label.config(text=str(active_count))
    
    def update_server_tree(self):
        """Update the server treeview with healthy servers."""
        for item in self.server_tree.get_children():
            self.server_tree.delete(item)
        
        for idx, server in enumerate(self.healthy_servers, 1):
            openvpn_status = "✓" if server.get('openvpn', False) else "✗"
            
            values = (
                server.get('country', '')[:15],
                server.get('ip', ''),
                server.get('ping', 0),
                server.get('speed', 0),
                openvpn_status
            )
            
            # Color code row
            if server.get('openvpn'):
                tags = ("green",)
            else:
                tags = ("yellow",)
            
            self.server_tree.insert('', 'end', text=str(idx), values=values, tags=tags)
        
        # Define tag colors
        self.server_tree.tag_configure("green", foreground="darkgreen", background="#e8f5e9")
        self.server_tree.tag_configure("yellow", foreground="goldenrod", background="#fff9e6")
    
    def update_sessions_tree(self):
        """Update the active sessions treeview."""
        for item in self.sessions_tree.get_children():
            self.sessions_tree.delete(item)
        
        for idx, session in enumerate(self.active_sessions, 1):
            if session.connected:
                values = (
                    session.server_ip,
                    session.interface_ip,
                    session.requests_routed
                )
                self.sessions_tree.insert('', 'end', text=str(idx), values=values, tags=("active",))
        
        # Define tag colors
        self.sessions_tree.tag_configure("active", foreground="darkblue", background="#e3f2fd")
    
    def on_fetch_servers(self):
        """Fetch servers from VPNGate API."""
        if self.is_testing or self.is_connecting:
            messagebox.showwarning("Busy", "Please wait for current operation to complete.")
            return
        
        def fetch_thread():
            self.log("Starting server fetch from VPNGate API...", "info")
            self.set_status("Fetching", "orange")
            self.fetch_btn.config(state=tk.DISABLED)
            
            try:
                clear_cache()
                servers = fetch_servers(force_refresh=True)
                self.all_servers = servers
                
                if servers:
                    self.log(f"✓ Fetched {len(servers)} servers from VPNGate", "success")
                    self.test_btn.config(state=tk.NORMAL)
                    self.set_status("Idle", "green")
                else:
                    self.log("✗ Failed to fetch servers", "error")
                    self.set_status("Error", "red")
                
                self.update_stats()
            except Exception as e:
                self.log(f"✗ Error during fetch: {e}", "error")
                self.set_status("Error", "red")
            finally:
                self.fetch_btn.config(state=tk.NORMAL)
        
        thread = threading.Thread(target=fetch_thread, daemon=True)
        thread.start()
    
    def on_test_servers(self):
        """Test all servers for connectivity."""
        if not self.all_servers:
            messagebox.showwarning("No Servers", "Please fetch servers first.")
            return
        
        if self.is_testing or self.is_connecting:
            messagebox.showwarning("Busy", "Testing or connecting already in progress.")
            return
        
        def test_thread():
            self.is_testing = True
            self.set_status("Testing", "orange")
            self.test_btn.config(state=tk.DISABLED)
            self.fetch_btn.config(state=tk.DISABLED)
            
            try:
                def test_callback(msg: str):
                    self.log(msg, "info")
                
                self.healthy_servers = test_all_servers(
                    self.all_servers,
                    callback=test_callback,
                    max_workers=5
                )
                
                self.update_server_tree()
                self.update_stats()
                self.connect_btn.config(state=tk.NORMAL if self.healthy_servers else tk.DISABLED)
                self.set_status("Idle", "green")
            except Exception as e:
                self.log(f"✗ Error during testing: {e}", "error")
                self.set_status("Error", "red")
            finally:
                self.is_testing = False
                self.test_btn.config(state=tk.NORMAL)
                self.fetch_btn.config(state=tk.NORMAL)
        
        thread = threading.Thread(target=test_thread, daemon=True)
        thread.start()
    
    def on_connect(self):
        """Connect to multiple VPN servers."""
        if not self.healthy_servers:
            messagebox.showwarning("No Servers", "No healthy servers available.")
            return
        
        max_servers = self.max_connections_var.get()
        selected_servers = random.sample(
            self.healthy_servers,
            min(max_servers, len(self.healthy_servers))
        )
        
        if self.is_connecting:
            messagebox.showwarning("Busy", "Connection already in progress.")
            return
        
        def connect_thread():
            self.is_connecting = True
            self.set_status("Connecting", "orange")
            self.connect_btn.config(state=tk.DISABLED)
            
            for idx, server in enumerate(selected_servers, 1):
                try:
                    server_ip = server['ip']
                    openvpn_config = server.get('openvpn_config', '')
                    
                    self.log(f"[CONNECT] Connecting to {server_ip}...", "info")
                    
                    if not openvpn_config:
                        self.log(f"✗ No OpenVPN config for {server_ip}", "error")
                        continue
                    
                    # Create OpenVPN config file
                    temp_dir = tempfile.gettempdir()
                    config_name = f"VPNLB_{idx}_{server_ip.replace('.', '_')}"
                    config_path = os.path.join(temp_dir, f"{config_name}.ovpn")
                    
                    if not create_openvpn_config(openvpn_config, config_path):
                        self.log(f"✗ Failed to create config for {server_ip}", "error")
                        continue
                    
                    # Start OpenVPN connection
                    success, interface_ip = start_openvpn(config_path, config_name)
                    
                    if success and interface_ip:
                        self.log(f"✓ Connected to {server_ip}, Interface IP: {interface_ip}", "success")
                        
                        # Create session
                        session = VpnSession(
                            name=config_name,
                            server_ip=server_ip,
                            protocol="OpenVPN",
                            interface_ip=interface_ip,
                            connected=True
                        )
                        self.active_sessions.append(session)
                    else:
                        self.log(f"✗ Failed to connect to {server_ip}", "error")
                
                except Exception as e:
                    self.log(f"✗ Exception connecting: {str(e)[:50]}", "error")
            
            self.update_stats()
            self.update_sessions_tree()
            self.disconnect_btn.config(state=tk.NORMAL if self.active_sessions else tk.DISABLED)
            self.set_status("Running", "green")
            self.is_connecting = False
        
        thread = threading.Thread(target=connect_thread, daemon=True)
        thread.start()
    
    def on_disconnect(self):
        """Disconnect all active VPN sessions."""
        if not self.active_sessions:
            messagebox.showinfo("No Sessions", "No active VPN sessions.")
            return
        
        def disconnect_thread():
            self.log("Disconnecting all VPN sessions...", "info")
            
            for session in self.active_sessions:
                try:
                    self.log(f"[DISCONNECT] Disconnecting {session.server_ip}...", "info")
                    stop_openvpn(session.name)
                    session.connected = False
                    self.log(f"✓ Disconnected from {session.server_ip}", "success")
                except Exception as e:
                    self.log(f"✗ Error disconnecting: {e}", "error")
            
            self.active_sessions = []
            self.update_stats()
            self.update_sessions_tree()
            self.disconnect_btn.config(state=tk.DISABLED)
            self.set_status("Idle", "green")
        
        thread = threading.Thread(target=disconnect_thread, daemon=True)
        thread.start()
    
    def route_request(self) -> Optional[VpnSession]:
        """
        Random load balancing: pick a random active session.
        
        Returns:
            VpnSession or None if no active sessions
        """
        if not self.active_sessions:
            return None
        
        session = random.choice([s for s in self.active_sessions if s.connected])
        session.requests_routed += 1
        self.log(f"[ROUTE] Request routed to {session.server_ip} (total: {session.requests_routed})")
        return session
    
    def set_status(self, status: str, color: str):
        """Update status label."""
        self.status_label.config(text=f"Status: {status}", foreground=color)
    
    def cleanup_vpn_entries(self):
        """Clean up leftover VPN entries from previous runs."""
        self.log("Cleaning up leftover VPN entries...", "info")
        cleanup_vpn_entries()
        self.log("✓ Cleanup complete", "success")
    
    def on_close(self):
        """Handle window close event."""
        # Disconnect all VPN sessions
        if self.active_sessions:
            self.log("Closing app, disconnecting all sessions...", "info")
            for session in self.active_sessions:
                try:
                    disconnect_vpn(session.name)
                    delete_vpn_entry(session.name)
                except:
                    pass
        
        cleanup_vpn_entries()
        self.root.destroy()


def main():
    """Main entry point."""
    root = tk.Tk()
    app = VPNLoadBalancerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
