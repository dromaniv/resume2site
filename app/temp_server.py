"""
Temporary file server for serving generated HTML files locally
"""
import threading
import socket
import tempfile
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import time


class TempHTMLServer:
    def __init__(self):
        self.server = None
        self.server_thread = None
        self.temp_dir = None
        self.port = None
        self.is_running = False

    def start_server(self, html_content: str, filename: str = "website.html") -> str:
        """
        Start a temporary HTTP server and serve the HTML content.
        Returns the URL where the content can be accessed.
        Automatically stops any existing server before starting a new one.
        """
        # Always stop existing server first to ensure only one instance
        if self.is_running:
            self.stop_server()

        # Create temporary directory
        self.temp_dir = tempfile.mkdtemp()
        
        # Write HTML content to file
        html_path = Path(self.temp_dir) / filename
        html_path.write_text(html_content, encoding='utf-8')
        
        # Find available port
        self.port = self._find_free_port()
        
        # Create custom handler that serves from temp directory
        class CustomHandler(SimpleHTTPRequestHandler):
            def __init__(self, *args, directory=None, **kwargs):
                super().__init__(*args, directory=directory or self.temp_dir, **kwargs)
        
        # Create server without changing working directory
        self.server = HTTPServer(('0.0.0.0', self.port),
                                lambda *args: CustomHandler(*args, directory=self.temp_dir))
        
        # Start server in background thread
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        self.is_running = True
        local_ip = self._get_local_ip()
        return f"Local URL: http://localhost:{self.port}/{filename}\nNetwork URL: http://{local_ip}:{self.port}/{filename}"

    def stop_server(self):
        """Stop the temporary server and clean up resources"""
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception:
                pass  # Ignore shutdown errors
            self.server = None
        
        if self.server_thread:
            self.server_thread.join(timeout=2)  # Wait up to 2 seconds
            self.server_thread = None
        
        if self.temp_dir and os.path.exists(self.temp_dir):
            # Clean up temp directory
            import shutil
            try:
                shutil.rmtree(self.temp_dir)
            except Exception:
                pass  # Ignore cleanup errors
            self.temp_dir = None
        
        self.is_running = False

    def update_content(self, html_content: str, filename: str = "website.html") -> str:
        """
        Update the content of the currently running server without changing port.
        If no server is running, starts a new one.
        Returns the URL where the content can be accessed.
        """
        if not self.is_running or not self.temp_dir:
            # No server running, start a new one
            return self.start_server(html_content, filename)
        
        # Update the HTML file in the existing temp directory
        html_path = Path(self.temp_dir) / filename
        html_path.write_text(html_content, encoding='utf-8')
        
        return f"http://localhost:{self.port}/{filename}"

    def is_server_running(self) -> bool:
        """Check if the server is currently running"""
        return self.is_running and self.server is not None

    def get_current_url(self) -> str:
        """Get the current server URL if running, None otherwise"""
        if self.is_server_running():
            return f"http://localhost:{self.port}/website.html"
        return None

    def _is_port_available(self, port: int) -> bool:
        """Check if a port is available for use"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(('localhost', port))
                return result != 0  # Port is available if connection fails
        except Exception:
            return False

    def _find_free_port(self) -> int:
        """Find a free port to use for the server"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port

    def _get_local_ip(self):
        """Get the local network IP address of the machine."""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Doesn't have to be reachable
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        except Exception:
            ip = "127.0.0.1"
        finally:
            s.close()
        return ip

    def __del__(self):
        """Cleanup when object is destroyed"""
        self.stop_server()


# Global instance for the streamlit app
_temp_server = TempHTMLServer()


def serve_html_temporarily(html_content: str, filename: str = "website.html") -> str:
    """
    Convenience function to serve HTML content temporarily.
    Updates existing server content if running, otherwise starts a new server.
    Returns URL where the content can be accessed.
    """
    return _temp_server.update_content(html_content, filename)


def cleanup_temp_server():
    """Stop and cleanup the temporary server"""
    _temp_server.stop_server()


def get_server_status() -> dict:
    """Get current server status information"""
    return {
        "is_running": _temp_server.is_server_running(),
        "url": _temp_server.get_current_url(),
        "port": _temp_server.port if _temp_server.is_running else None
    }
