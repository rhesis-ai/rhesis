#!/usr/bin/env python3
import os
import signal
import sys
import json
import subprocess
import time
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress default HTTP server logging to reduce noise
        pass
    
    def do_GET(self):
        if self.path == '/health' or self.path == '/':
            # Check if Celery worker is running
            is_healthy, status_info = self.check_celery_health()
            
            self.send_response(200 if is_healthy else 503)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            
            health_data = {
                "status": "healthy" if is_healthy else "unhealthy",
                "service": "celery-worker",
                "timestamp": datetime.now().isoformat(),
                "details": status_info
            }
            
            self.wfile.write(json.dumps(health_data, indent=2).encode())
        else:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not found"}).encode())
    
    def check_celery_health(self):
        """Check if Celery worker is running and operational"""
        try:
            # Run celery inspect ping command to check worker health
            result = subprocess.run(
                ["celery", "-A", "rhesis.backend.worker.app", "inspect", "ping"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # If ping was successful, it should contain a pong response
            if result.returncode == 0 and "pong" in result.stdout:
                return True, {
                    "message": "Celery worker is responding",
                    "last_check": datetime.now().isoformat()
                }
            else:
                return False, {
                    "message": "Celery worker is not responding properly",
                    "return_code": result.returncode,
                    "stdout": result.stdout[:500] if result.stdout else "No output",
                    "stderr": result.stderr[:500] if result.stderr else "No error"
                }
                
        except subprocess.TimeoutExpired:
            return False, {"message": "Celery health check timed out after 10 seconds"}
        except FileNotFoundError:
            return False, {"message": "Celery command not found"}
        except Exception as e:
            return False, {"message": f"Error checking Celery health: {str(e)}"}

class HealthServer:
    def __init__(self, port=8080):
        self.port = port
        self.httpd = None
        self.server_thread = None
        
    def start(self):
        """Start the health server in a separate thread"""
        try:
            server_address = ('', self.port)
            self.httpd = HTTPServer(server_address, HealthHandler)
            self.server_thread = threading.Thread(target=self.httpd.serve_forever)
            self.server_thread.daemon = True
            self.server_thread.start()
            print(f"Health check server started on port {self.port}")
            return True
        except Exception as e:
            print(f"Failed to start health server: {e}")
            return False
    
    def stop(self):
        """Stop the health server"""
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=5)

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print(f"Received signal {signum}, shutting down health server...")
    sys.exit(0)

def run_server(port=8080):
    """Run the health server"""
    # Set up signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Give the Celery worker a moment to start before health checks become meaningful
    print("Waiting 10 seconds for Celery worker to initialize...")
    time.sleep(10)
    
    server = HealthServer(port)
    if server.start():
        try:
            # Keep the main thread alive
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Keyboard interrupt received")
        finally:
            server.stop()
    else:
        sys.exit(1)

if __name__ == '__main__':
    run_server(int(os.environ.get('HEALTH_PORT', 8080))) 