#!/usr/bin/env python3
from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import signal
import sys
import json
import subprocess
import time
from datetime import datetime

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health' or self.path == '/':
            # Check if Celery worker is running
            is_healthy, status_info = self.check_celery_health()
            
            self.send_response(200 if is_healthy else 503)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            health_data = {
                "status": "healthy" if is_healthy else "unhealthy",
                "service": "celery-worker",
                "timestamp": datetime.now().isoformat(),
                "details": status_info
            }
            
            self.wfile.write(json.dumps(health_data).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def check_celery_health(self):
        """Check if Celery worker is running and operational"""
        try:
            # Run celery inspect ping command to check worker health
            result = subprocess.run(
                ["celery", "-A", "rhesis.backend.worker.app", "inspect", "ping"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            # If ping was successful, it should contain a pong response
            if result.returncode == 0 and "pong" in result.stdout:
                return True, {"message": "Celery worker is responding"}
            else:
                return False, {
                    "message": "Celery worker is not responding properly",
                    "details": result.stdout[:200] if result.stdout else "No output",
                    "error": result.stderr[:200] if result.stderr else "No error"
                }
                
        except subprocess.TimeoutExpired:
            return False, {"message": "Celery health check timed out"}
        except Exception as e:
            return False, {"message": f"Error checking Celery health: {str(e)}"}

def run_server(port=8080):
    server_address = ('', port)
    httpd = HTTPServer(server_address, HealthHandler)
    print(f"Starting health check server on port {port}")
    httpd.serve_forever()

if __name__ == '__main__':
    # Give the Celery worker a moment to start before health checks become meaningful
    time.sleep(5)
    run_server(int(os.environ.get('HEALTH_PORT', 8080))) 