"""
Setup script for PostgreSQL and Redis.
This script helps users set up the required infrastructure.
"""

import os
import sys
import subprocess


def check_docker():
    """Check if Docker is installed."""
    try:
        subprocess.run(["docker", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def check_docker_compose():
    """Check if Docker Compose is installed."""
    try:
        subprocess.run(["docker-compose", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Try docker compose (v2)
        try:
            subprocess.run(["docker", "compose", "version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False


def start_services():
    """Start PostgreSQL and Redis using Docker Compose."""
    print("Starting PostgreSQL and Redis...")
    try:
        # Try docker-compose first
        result = subprocess.run(
            ["docker-compose", "up", "-d"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("✓ Services started successfully")
            return True
        
        # Try docker compose v2
        result = subprocess.run(
            ["docker", "compose", "up", "-d"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("✓ Services started successfully")
            return True
        
        print(f"✗ Failed to start services: {result.stderr}")
        return False
    except Exception as e:
        print(f"✗ Error starting services: {e}")
        return False


def stop_services():
    """Stop PostgreSQL and Redis using Docker Compose."""
    print("Stopping PostgreSQL and Redis...")
    try:
        # Try docker-compose first
        result = subprocess.run(
            ["docker-compose", "down"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("✓ Services stopped successfully")
            return True
        
        # Try docker compose v2
        result = subprocess.run(
            ["docker", "compose", "down"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("✓ Services stopped successfully")
            return True
        
        print(f"✗ Failed to stop services: {result.stderr}")
        return False
    except Exception as e:
        print(f"✗ Error stopping services: {e}")
        return False


def show_status():
    """Show the status of services."""
    print("Checking service status...")
    try:
        # Check PostgreSQL
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=patient-agent-postgres", "--format", "{{.Status}}"],
            capture_output=True,
            text=True
        )
        postgres_status = result.stdout.strip() or "Not running"
        print(f"PostgreSQL: {postgres_status}")
        
        # Check Redis
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=patient-agent-redis", "--format", "{{.Status}}"],
            capture_output=True,
            text=True
        )
        redis_status = result.stdout.strip() or "Not running"
        print(f"Redis: {redis_status}")
        
        return True
    except Exception as e:
        print(f"✗ Error checking status: {e}")
        return False


def main():
    """Main setup function."""
    if len(sys.argv) < 2:
        print("Usage: python setup_services.py <command>")
        print("Commands:")
        print("  start    - Start PostgreSQL and Redis")
        print("  stop     - Stop PostgreSQL and Redis")
        print("  status   - Show service status")
        return
    
    command = sys.argv[1].lower()
    
    if command == "start":
        if not check_docker():
            print("✗ Docker is not installed. Please install Docker first.")
            print("  Visit: https://docs.docker.com/get-docker/")
            return
        
        if not check_docker_compose():
            print("✗ Docker Compose is not installed.")
            print("  Visit: https://docs.docker.com/compose/install/")
            return
        
        start_services()
    elif command == "stop":
        stop_services()
    elif command == "status":
        show_status()
    else:
        print(f"Unknown command: {command}")
        print("Available commands: start, stop, status")


if __name__ == "__main__":
    main()