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
        """
        if self.is_running:
            self.stop_server()

        # Create temporary directory
        self.temp_dir = tempfile.mkdtemp()
        
        # Write HTML content to file
        html_path = Path(self.temp_dir) / filename
        html_path.write_text(html_content, encoding='utf-8')
        
        # Find available port
        self.port = self._find_free_port()
        
        # Store current directory and change to temp dir
        self.original_dir = os.getcwd()
        
        # Create custom handler that serves from temp directory
        class CustomHandler(SimpleHTTPRequestHandler):
            def __init__(self, *args, directory=None, **kwargs):
                super().__init__(*args, directory=directory or self.temp_dir, **kwargs)
        
        # Create server without changing working directory
        self.server = HTTPServer(('localhost', self.port), 
                                lambda *args: CustomHandler(*args, directory=self.temp_dir))
        
        # Start server in background thread
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        self.is_running = True
        
        return f"http://localhost:{self.port}/{filename}"

    def stop_server(self):
        """Stop the temporary server and clean up"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        
        if self.server_thread:
            self.server_thread.join(timeout=1)
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

    def _find_free_port(self) -> int:
        """Find a free port to use for the server"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port

    def __del__(self):
        """Cleanup when object is destroyed"""
        self.stop_server()


# Global instance for the streamlit app
_temp_server = TempHTMLServer()


def serve_html_temporarily(html_content: str, filename: str = "website.html") -> str:
    """
    Convenience function to serve HTML content temporarily.
    Returns URL where the content can be accessed.
    """
    return _temp_server.start_server(html_content, filename)


def cleanup_temp_server():
    """Stop and cleanup the temporary server"""
    _temp_server.stop_server()
