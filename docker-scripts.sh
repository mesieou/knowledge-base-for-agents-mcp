#!/bin/bash

# Docker management scripts for MCP server

case "$1" in
    "build")
        echo "Building MCP server Docker image..."
        docker build -t knowledge-base-mcp .
        ;;
    "run")
        echo "Running MCP server container..."
        docker run -d -p 8080:8080 --name mcp-server knowledge-base-mcp
        ;;
    "stop")
        echo "Stopping MCP server container..."
        docker stop mcp-server
        ;;
    "start")
        echo "Starting MCP server container..."
        docker start mcp-server
        ;;
    "restart")
        echo "Restarting MCP server container..."
        docker restart mcp-server
        ;;
    "logs")
        echo "Showing MCP server logs..."
        docker logs -f mcp-server
        ;;
    "remove")
        echo "Removing MCP server container..."
        docker stop mcp-server
        docker rm mcp-server
        ;;
    "compose-up")
        echo "Starting with docker-compose..."
        docker-compose up -d
        ;;
    "compose-down")
        echo "Stopping with docker-compose..."
        docker-compose down
        ;;
    "compose-logs")
        echo "Showing docker-compose logs..."
        docker-compose logs -f
        ;;
    "status")
        echo "Docker container status:"
        docker ps -a | grep mcp-server
        ;;
    *)
        echo "Usage: $0 {build|run|stop|start|restart|logs|remove|compose-up|compose-down|compose-logs|status}"
        echo ""
        echo "Commands:"
        echo "  build         - Build the Docker image"
        echo "  run           - Run the container"
        echo "  stop          - Stop the container"
        echo "  start         - Start the container"
        echo "  restart       - Restart the container"
        echo "  logs          - Show container logs"
        echo "  remove        - Remove the container"
        echo "  compose-up    - Start with docker-compose"
        echo "  compose-down  - Stop with docker-compose"
        echo "  compose-logs  - Show docker-compose logs"
        echo "  status        - Show container status"
        ;;
esac
