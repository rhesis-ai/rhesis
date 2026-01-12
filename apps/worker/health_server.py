#!/usr/bin/env python3
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress default HTTP server logging to reduce noise
        pass
    
    def do_GET(self):
        if self.path == '/health':
            self._handle_health_check()
        elif self.path == '/health/basic' or self.path == '/':
            self._handle_basic_health_check()
        elif self.path == '/ping':
            self._handle_ping()
        elif self.path == '/debug':
            self._handle_debug()
        elif self.path == '/debug/env':
            self._handle_debug_env()
        elif self.path == '/debug/redis':
            self._handle_debug_redis()
        elif self.path == '/debug/detailed':
            self._handle_debug_detailed()
        else:
            self._handle_not_found()
    
    def _handle_health_check(self):
        """Handle health check request with error handling for broken pipes"""
        try:
            # Check if Celery worker is running
            is_healthy, status_info = self.check_celery_health()
            
            response_code = 200 if is_healthy else 503
            self.send_response(response_code)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'close')  # Ensure connection closes after response
            self.end_headers()
            
            health_data = {
                "status": "healthy" if is_healthy else "unhealthy",
                "service": "celery-worker",
                "timestamp": datetime.now().isoformat(),
                "details": status_info
            }
            
            response_body = json.dumps(health_data).encode()
            self._safe_write(response_body)
            
        except Exception as e:
            logger.error(f"Error in health check handler: {e}")
            try:
                self.send_error(500, "Internal server error")
            except:
                pass  # Connection might already be broken
    
    def _handle_basic_health_check(self):
        """Handle basic health check that only verifies the server is running"""
        try:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'close')
            self.end_headers()
            
            health_data = {
                "status": "healthy",
                "service": "celery-worker-server",
                "timestamp": datetime.now().isoformat(),
                "details": {"message": "Health server is running"}
            }
            
            response_body = json.dumps(health_data).encode()
            self._safe_write(response_body)
            
        except Exception as e:
            logger.error(f"Error in basic health check handler: {e}")
            try:
                self.send_error(500, "Internal server error")
            except:
                pass
    
    def _handle_ping(self):
        """Simplest possible health check"""
        try:
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.send_header('Connection', 'close')
            self.end_headers()
            self._safe_write(b'pong')
        except Exception as e:
            logger.error(f"Error in ping handler: {e}")
    
    def _handle_debug(self):
        """Handle comprehensive debug information"""
        try:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'close')
            self.end_headers()
            
            debug_data = {
                "timestamp": datetime.now().isoformat(),
                "service": "celery-worker-debug",
                "environment": {
                    "tls_detected": self._is_tls_connection(),
                    "broker_url_type": "rediss://" if self._is_tls_connection() else "redis://",
                    "has_broker_url": bool(os.getenv("BROKER_URL")),
                    "has_result_backend": bool(os.getenv("CELERY_RESULT_BACKEND")),
                    "python_path": sys.path[:3],  # First 3 entries
                    "working_directory": os.getcwd(),
                },
                "redis_connectivity": self._test_redis_connection(),
                "celery_status": self._get_celery_debug_info(),
                "system_info": {
                    "pid": os.getpid(),
                    "platform": sys.platform,
                    "python_version": sys.version.split()[0],
                }
            }
            
            response_body = json.dumps(debug_data, indent=2).encode()
            self._safe_write(response_body)
            
        except Exception as e:
            logger.error(f"Error in debug handler: {e}")
            self._send_error_response(500, f"Debug error: {str(e)}")
    
    def _handle_debug_env(self):
        """Handle environment variables debug (sanitized)"""
        try:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'close')
            self.end_headers()
            
            # Sanitize environment variables (don't expose sensitive values)
            env_debug = {}
            sensitive_keys = ['PASSWORD', 'SECRET', 'KEY', 'TOKEN', 'AUTH']
            
            for key, value in os.environ.items():
                if any(sensitive in key.upper() for sensitive in sensitive_keys):
                    env_debug[key] = f"***REDACTED*** (length: {len(value)})"
                elif key.startswith(('BROKER_URL', 'CELERY_RESULT_BACKEND')):
                    # Show connection type but redact credentials
                    if value.startswith('rediss://'):
                        env_debug[key] = "rediss://***REDACTED***/X (TLS)"
                    elif value.startswith('redis://'):
                        env_debug[key] = "redis://***REDACTED***/X (Standard)"
                    else:
                        env_debug[key] = f"***REDACTED*** (type: {value.split('://')[0] if '://' in value else 'unknown'})"
                else:
                    env_debug[key] = value
            
            debug_data = {
                "timestamp": datetime.now().isoformat(),
                "environment_variables": env_debug,
                "total_env_vars": len(os.environ)
            }
            
            response_body = json.dumps(debug_data, indent=2).encode()
            self._safe_write(response_body)
            
        except Exception as e:
            logger.error(f"Error in env debug handler: {e}")
            self._send_error_response(500, f"Env debug error: {str(e)}")
    
    def _handle_debug_redis(self):
        """Handle Redis-specific debug information"""
        try:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'close')
            self.end_headers()
            
            debug_data = {
                "timestamp": datetime.now().isoformat(),
                "redis_debug": self._get_redis_debug_info(),
                "celery_redis_config": self._get_celery_redis_config()
            }
            
            response_body = json.dumps(debug_data, indent=2).encode()
            self._safe_write(response_body)
            
        except Exception as e:
            logger.error(f"Error in Redis debug handler: {e}")
            self._send_error_response(500, f"Redis debug error: {str(e)}")
    
    def _handle_debug_detailed(self):
        """Handle detailed health check including worker ping"""
        try:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'close')
            self.end_headers()
            
            # Run the detailed health check with celery inspect ping
            celery_detailed = self.check_celery_health_detailed()
            redis_debug = self._get_redis_debug_info()
            celery_debug = self._get_celery_debug_info()
            
            response_data = {
                "detailed_health_check": celery_detailed,
                "redis_debug": redis_debug,
                "celery_debug": celery_debug,
                "timestamp": datetime.now().isoformat(),
                "warning": "This endpoint uses 'celery inspect ping' which may be slow during startup"
            }
            
            response_body = json.dumps(response_data, indent=2).encode()
            self._safe_write(response_body)
            
        except Exception as e:
            logger.error(f"Error in detailed debug handler: {e}")
            self._send_error_response(500, f"Detailed debug error: {str(e)}")
    
    def _handle_not_found(self):
        """Handle 404 requests with error handling"""
        try:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.send_header('Connection', 'close')
            self.end_headers()
            
            error_response = json.dumps({"error": "Not found"}).encode()
            self._safe_write(error_response)
        except Exception as e:
            logger.error(f"Error in 404 handler: {e}")
    
    def _safe_write(self, data):
        """Safely write data to response, handling broken pipe errors"""
        try:
            self.wfile.write(data)
            self.wfile.flush()
        except BrokenPipeError:
            logger.debug("Client disconnected before response was fully sent (broken pipe)")
        except ConnectionResetError:
            logger.debug("Client reset connection before response was fully sent")
        except Exception as e:
            logger.warning(f"Unexpected error writing response: {e}")
    
    def check_celery_health(self):
        """Check if Celery worker is running and operational - lightweight version"""
        try:
            # Import check
            import rhesis.backend.worker
            
            # Test broker connectivity (this is the main requirement)
            broker_test = self._test_redis_connection()
            if broker_test != "connected":
                return False, {
                    "message": "Broker connection failed",
                    "broker_status": broker_test,
                    "last_check": datetime.now().isoformat()
                }
            
            # Test if we can create app and access its configuration
            app = rhesis.backend.worker.app
            
            # Basic app validation - fast checks only
            if not app.conf.broker_url:
                return False, {"message": "Celery app has no broker URL configured"}
            
            # Fast health check: broker connectivity + app importability
            # The slow `celery inspect ping` is moved to /debug endpoint for detailed debugging
            
            return True, {
                "message": "Celery app is healthy and broker is connected",
                "broker_connectivity": broker_test,
                "app_name": app.main,
                "broker_configured": bool(app.conf.broker_url),
                "task_count": len(app.tasks),
                "last_check": datetime.now().isoformat(),
                "health_check_type": "lightweight"
            }
                
        except ImportError as e:
            logger.error(f"Failed to import Celery app: {e}")
            return False, {"message": f"Failed to import Celery app: {str(e)}"}
        except Exception as e:
            logger.error(f"Error checking Celery health: {e}")
            return False, {"message": f"Error checking Celery health: {str(e)}"}
    
    def check_celery_health_detailed(self):
        """Detailed Celery health check with worker ping - used for debugging only"""
        try:
            import rhesis.backend.worker
            
            # For TLS connections, we need to be more patient and robust
            is_tls = self._is_tls_connection()
            timeout = 10 if is_tls else 3  # Longer timeout for TLS handshake
            
            # Test Redis connectivity first
            redis_healthy = self._test_redis_connection()
            
            # Test broker connectivity first before running celery inspect
            if redis_healthy != "connected":
                return False, {
                    "message": "Broker connection failed before Celery test",
                    "connection_type": "TLS" if is_tls else "standard",
                    "broker_status": redis_healthy,
                    "last_check": datetime.now().isoformat()
                }
            
            # Heavy operation: ping actual workers (only used for detailed debugging)
            result = subprocess.run(
                ["celery", "-A", "rhesis.backend.worker.app", "inspect", "ping"],
                capture_output=True,
                text=True,
                timeout=timeout,
                env=os.environ.copy()
            )
            
            # If ping was successful, it should contain a pong response
            if result.returncode == 0 and "pong" in result.stdout:
                return True, {
                    "message": "Celery worker is responding to ping",
                    "connection_type": "TLS" if is_tls else "standard",
                    "redis_connectivity": redis_healthy,
                    "worker_ping_successful": True,
                    "last_check": datetime.now().isoformat(),
                    "response_time": f"< {timeout}s",
                    "health_check_type": "detailed_with_ping"
                }
            else:
                return False, {
                    "message": "Celery worker is not responding to ping",
                    "connection_type": "TLS" if is_tls else "standard",
                    "redis_connectivity": redis_healthy,
                    "worker_ping_successful": False,
                    "return_code": result.returncode,
                    "stdout": result.stdout[:200] if result.stdout else "No output",
                    "stderr": result.stderr[:200] if result.stderr else "No error"
                }
                
        except subprocess.TimeoutExpired:
            logger.warning(f"Detailed Celery health check timed out after {timeout}s")
            return False, {
                "message": f"Detailed Celery health check timed out after {timeout} seconds",
                "connection_type": "TLS" if self._is_tls_connection() else "standard",
                "timeout_on": "celery_inspect_ping"
            }
        except FileNotFoundError:
            logger.error("Celery command not found")
            return False, {"message": "Celery command not found"}
        except ImportError as e:
            logger.error(f"Failed to import Celery app: {e}")
            return False, {"message": f"Failed to import Celery app: {str(e)}"}
        except Exception as e:
            logger.error(f"Error checking detailed Celery health: {e}")
            return False, {"message": f"Error checking detailed Celery health: {str(e)}"}
    
    def _is_tls_connection(self):
        """Check if we're using TLS connections (rediss://)"""
        broker_url = os.getenv("BROKER_URL", "")
        result_backend = os.getenv("CELERY_RESULT_BACKEND", "")
        return broker_url.startswith("rediss://") or result_backend.startswith("rediss://")
    
    def _test_redis_connection(self):
        """Quick Redis connection test using Celery's connection method"""
        try:
            # Use Celery's connection method instead of direct Redis
            # This ensures we use the same SSL handling as Celery
            import rhesis.backend.worker
            app = rhesis.backend.worker.app
            
            # Test broker connection using Celery's method
            with app.connection() as conn:
                conn.connect()
            return "connected"
            
        except ImportError:
            return "celery_not_available"
        except Exception as e:
            # Fallback to direct Redis test if Celery method fails
            try:
                from urllib.parse import urlparse

                import redis
                
                broker_url = os.getenv("BROKER_URL", "")
                if not broker_url:
                    return "no_broker_url"
                
                # Parse Redis URL
                parsed = urlparse(broker_url)
                if not parsed.hostname:
                    return "invalid_url"
                
                # Quick connection test with short timeout
                # Don't modify SSL parameters - let Redis library handle URL parsing
                r = redis.Redis.from_url(broker_url, socket_connect_timeout=1, socket_timeout=1)
                
                # Simple ping
                r.ping()
                return "connected"
                
            except ImportError:
                return "redis_not_available"
            except redis.ConnectionError:
                return "connection_failed"
            except redis.TimeoutError:
                return "timeout"
            except Exception as redis_e:
                return f"celery_error: {str(e)[:25]}, redis_error: {str(redis_e)[:25]}"

    def _get_celery_debug_info(self):
        """Get detailed Celery debug information"""
        try:
            import rhesis.backend.worker
            app = rhesis.backend.worker.app
            
            return {
                "app_name": app.main,
                "broker_configured": bool(app.conf.broker_url),
                "result_backend_configured": bool(app.conf.result_backend),
                "task_count": len(app.tasks),
                "worker_state": "importable",
                "configuration": {
                    "task_serializer": app.conf.task_serializer,
                    "result_serializer": app.conf.result_serializer,
                    "timezone": str(app.conf.timezone),
                    "broker_connection_retry": app.conf.broker_connection_retry,
                    "broker_connection_retry_on_startup": app.conf.broker_connection_retry_on_startup,
                }
            }
        except ImportError as e:
            return {"error": f"Cannot import Celery app: {str(e)}", "worker_state": "not_importable"}
        except Exception as e:
            return {"error": f"Celery debug error: {str(e)}", "worker_state": "error"}

    def _get_redis_debug_info(self):
        """Get detailed Redis debug information"""
        try:
            import redis
            
            broker_url = os.getenv("BROKER_URL", "")
            result_backend = os.getenv("CELERY_RESULT_BACKEND", "")
            
            debug_info = {
                "broker_url_present": bool(broker_url),
                "result_backend_present": bool(result_backend),
                "tls_detected": self._is_tls_connection(),
                "redis_module_available": True,
            }
            
            # Test connections using Celery's method
            if broker_url:
                try:
                    parsed = urlparse(broker_url)
                    debug_info["broker_host"] = parsed.hostname
                    debug_info["broker_port"] = parsed.port
                    debug_info["broker_db"] = parsed.path.lstrip('/')
                    
                    # Use Celery's connection method for accurate testing
                    import rhesis.backend.worker
                    app = rhesis.backend.worker.app
                    with app.connection() as conn:
                        conn.connect()
                    debug_info["broker_connectivity"] = "success"
                except ImportError:
                    debug_info["broker_connectivity"] = "celery_not_available"
                except Exception as e:
                    debug_info["broker_connectivity"] = f"error: {str(e)[:50]}"
            
            if result_backend and result_backend != broker_url:
                try:
                    parsed = urlparse(result_backend)
                    debug_info["result_backend_host"] = parsed.hostname
                    debug_info["result_backend_port"] = parsed.port
                    debug_info["result_backend_db"] = parsed.path.lstrip('/')
                    
                    r = redis.Redis.from_url(result_backend, socket_connect_timeout=1, socket_timeout=1)
                    r.ping()
                    debug_info["result_backend_connectivity"] = "success"
                except Exception as e:
                    debug_info["result_backend_connectivity"] = f"error: {str(e)[:50]}"
            
            return debug_info
            
        except ImportError:
            return {"error": "Redis module not available", "redis_module_available": False}
        except Exception as e:
            return {"error": f"Redis debug error: {str(e)}"}

    def _get_celery_redis_config(self):
        """Get Celery Redis configuration details"""
        try:
            import rhesis.backend.worker
            app = rhesis.backend.worker.app
            
            return {
                "broker_url_configured": bool(app.conf.broker_url),
                "result_backend_configured": bool(app.conf.result_backend),
                "broker_transport_options": dict(app.conf.broker_transport_options) if app.conf.broker_transport_options else {},
                "result_backend_transport_options": dict(app.conf.result_backend_transport_options) if app.conf.result_backend_transport_options else {},
                "result_expires": app.conf.result_expires,
                "result_compression": app.conf.result_compression,
                "broker_connection_retry": app.conf.broker_connection_retry,
                "broker_connection_retry_on_startup": app.conf.broker_connection_retry_on_startup,
                "broker_connection_max_retries": app.conf.broker_connection_max_retries,
            }
        except Exception as e:
            return {"error": f"Cannot get Celery Redis config: {str(e)}"}

    def _send_error_response(self, status_code, message):
        """Send error response safely"""
        try:
            self.send_response(status_code)
            self.send_header('Content-type', 'application/json')
            self.send_header('Connection', 'close')
            self.end_headers()
            error_data = {"error": message, "timestamp": datetime.now().isoformat()}
            self._safe_write(json.dumps(error_data).encode())
        except:
            pass

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
            # Configure server to handle connections more gracefully
            self.httpd.allow_reuse_address = True
            self.httpd.timeout = 10  # Set socket timeout
            
            self.server_thread = threading.Thread(target=self.httpd.serve_forever)
            self.server_thread.daemon = True
            self.server_thread.start()
            logger.info(f"Health check server started on port {self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to start health server: {e}")
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
    logger.info(f"Received signal {signum}, shutting down health server...")
    sys.exit(0)

def run_server(port=8080):
    """Run the health server"""
    # Set up signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Give the Celery worker a moment to start before health checks become meaningful
    # But start the health server immediately for basic checks
    logger.info("Starting health server immediately for basic checks...")
    
    server = HealthServer(port)
    if server.start():
        try:
            # Keep the main thread alive
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            server.stop()
    else:
        sys.exit(1)

if __name__ == '__main__':
    run_server(int(os.environ.get('HEALTH_PORT', 8080))) 