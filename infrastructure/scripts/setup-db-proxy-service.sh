#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SERVICE_NAME="db-proxy"
SERVICE_FILE="$(dirname "$0")/db-proxy.service"
SYSTEMD_PATH="/etc/systemd/system/${SERVICE_NAME}.service"

# Functions
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Get absolute script path
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    ACTUAL_SCRIPT_PATH="$SCRIPT_DIR/db-proxy.sh"
    
    # Check if script exists
    if [ ! -f "$ACTUAL_SCRIPT_PATH" ]; then
        print_error "Script not found at $ACTUAL_SCRIPT_PATH"
        print_warning "Please ensure db-proxy.sh is in the same directory as this setup script"
        exit 1
    fi
    
    # Check if script is executable
    if [ ! -x "$ACTUAL_SCRIPT_PATH" ]; then
        print_warning "Making script executable..."
        chmod +x "$ACTUAL_SCRIPT_PATH"
    fi
    
    # Check if running as root/sudo
    if [ "$EUID" -ne 0 ]; then
        print_error "This script must be run with sudo privileges"
        print_status "Usage: sudo ./setup-db-proxy-service.sh [install|start|stop|restart|status|logs|uninstall]"
        exit 1
    fi
}

install_service() {
    print_status "Installing db-proxy service..."
    
    # Get absolute paths and current user info
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    SCRIPT_ABSOLUTE_PATH="$SCRIPT_DIR/db-proxy.sh"
    CURRENT_USER="$(logname 2>/dev/null || echo $SUDO_USER || whoami)"
    CURRENT_GROUP="$(id -gn "$CURRENT_USER" 2>/dev/null || groups "$CURRENT_USER" | cut -d' ' -f1)"
    
    # Create service file with dynamic paths
    sed -e "s|__WORKING_DIRECTORY__|$SCRIPT_DIR|g" \
        -e "s|__SCRIPT_PATH__|$SCRIPT_ABSOLUTE_PATH|g" \
        -e "s|__USER__|$CURRENT_USER|g" \
        -e "s|__GROUP__|$CURRENT_GROUP|g" \
        "$SERVICE_FILE" > "$SYSTEMD_PATH"
    
    # Reload systemd daemon
    systemctl daemon-reload
    
    # Enable service to start on boot
    systemctl enable "$SERVICE_NAME"
    
    print_status "Service installed successfully!"
    print_status "Working Directory: $SCRIPT_DIR"
    print_status "Script Path: $SCRIPT_ABSOLUTE_PATH"
    print_status "Running as User: $CURRENT_USER"
    print_status "Running as Group: $CURRENT_GROUP"
    print_status "Use 'sudo systemctl start $SERVICE_NAME' to start the service"
}

start_service() {
    print_status "Starting db-proxy service..."
    systemctl start "$SERVICE_NAME"
    print_status "Service started!"
}

stop_service() {
    print_status "Stopping db-proxy service..."
    systemctl stop "$SERVICE_NAME"
    print_status "Service stopped!"
}

restart_service() {
    print_status "Restarting db-proxy service..."
    systemctl restart "$SERVICE_NAME"
    print_status "Service restarted!"
}

service_status() {
    print_status "Service status:"
    systemctl status "$SERVICE_NAME" --no-pager
}

show_logs() {
    print_status "Service logs (last 50 lines):"
    journalctl -u "$SERVICE_NAME" -n 50 --no-pager
}

follow_logs() {
    print_status "Following service logs (Ctrl+C to exit):"
    journalctl -u "$SERVICE_NAME" -f
}

uninstall_service() {
    print_status "Uninstalling db-proxy service..."
    
    # Stop service if running
    systemctl stop "$SERVICE_NAME" 2>/dev/null || true
    
    # Disable service
    systemctl disable "$SERVICE_NAME" 2>/dev/null || true
    
    # Remove service file
    rm -f "$SYSTEMD_PATH"
    
    # Reload systemd daemon
    systemctl daemon-reload
    
    print_status "Service uninstalled successfully!"
}

# Main script
case "${1:-install}" in
    install)
        check_prerequisites
        install_service
        ;;
    start)
        check_prerequisites
        start_service
        ;;
    stop)
        check_prerequisites
        stop_service
        ;;
    restart)
        check_prerequisites
        restart_service
        ;;
    status)
        service_status
        ;;
    logs)
        show_logs
        ;;
    follow-logs)
        follow_logs
        ;;
    uninstall)
        uninstall_service
        ;;
    *)
        echo "Usage: sudo $0 {install|start|stop|restart|status|logs|follow-logs|uninstall}"
        echo ""
        echo "Commands:"
        echo "  install      - Install the service and enable it to start on boot"
        echo "  start        - Start the service"
        echo "  stop         - Stop the service"
        echo "  restart      - Restart the service"
        echo "  status       - Show service status"
        echo "  logs         - Show recent service logs"
        echo "  follow-logs  - Follow service logs in real-time"
        echo "  uninstall    - Remove the service completely"
        exit 1
        ;;
esac 