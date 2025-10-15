#!/bin/bash
# Simple CLI wrapper to interact with InfantAgent via Docker

CONTAINER_NAME="infant-agent-cli"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to check if container is running
check_container() {
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo -e "${RED}❌ Error: Container '${CONTAINER_NAME}' is not running.${NC}"
        echo -e "${YELLOW}Please start the containers with: docker compose up -d${NC}"
        exit 1
    fi
}

# Function to send prompt via stdin
send_prompt() {
    local prompt="$1"
    echo -e "${BLUE}📤 Sending prompt to agent:${NC} $prompt"
    echo -e "${YELLOW}⏳ Agent is processing...${NC}"
    echo ""

    # Send the prompt to the container's stdin
    echo "$prompt" | docker attach --no-stdin "$CONTAINER_NAME" 2>/dev/null || \
    echo "$prompt" | docker exec -i "$CONTAINER_NAME" /bin/bash -c "cat" || \
    echo -e "${RED}Failed to send prompt. Try: docker exec -it $CONTAINER_NAME python -m infant${NC}"
}

# Function to view logs
view_logs() {
    echo -e "${BLUE}📋 Viewing agent logs...${NC}"
    if [ "$1" = "-f" ]; then
        docker logs -f "$CONTAINER_NAME"
    else
        docker logs --tail 100 "$CONTAINER_NAME"
    fi
}

# Function to show status
show_status() {
    echo -e "${BLUE}📊 Container Status:${NC}"
    docker ps --filter "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}

# Function to enter interactive mode
interactive_mode() {
    echo -e "${GREEN}🤖 Entering interactive mode with agent...${NC}"
    docker exec -it "$CONTAINER_NAME" /bin/bash
}

# Function to show help
show_help() {
    cat << EOF
${GREEN}InfantAgent CLI - Docker Container Interface${NC}

Usage: $0 [COMMAND] [OPTIONS]

${YELLOW}Commands:${NC}
  send "prompt"     Send a prompt to the agent
  logs              View agent logs (last 100 lines)
  logs -f           Follow agent logs in real-time
  status            Show container status
  shell             Open interactive shell in container
  restart           Restart the agent container
  help              Show this help message

${YELLOW}Examples:${NC}
  $0 send "Create a Python script to analyze data.csv"
  $0 logs -f
  $0 status
  $0 shell

${YELLOW}Direct interaction:${NC}
  For direct interaction with the agent, use:
    docker exec -it ${CONTAINER_NAME} /bin/bash
    # Then inside container:
    # The agent is already running with input prompt

${YELLOW}View logs while agent is running:${NC}
  docker logs -f ${CONTAINER_NAME}
EOF
}

# Main script logic
case "$1" in
    send)
        check_container
        if [ -z "$2" ]; then
            echo -e "${RED}❌ Error: Please provide a prompt${NC}"
            echo "Usage: $0 send \"your prompt here\""
            exit 1
        fi
        send_prompt "$2"
        ;;
    logs)
        check_container
        view_logs "$2"
        ;;
    status)
        check_container
        show_status
        ;;
    shell)
        check_container
        interactive_mode
        ;;
    restart)
        echo -e "${YELLOW}⏳ Restarting agent container...${NC}"
        docker restart "$CONTAINER_NAME"
        echo -e "${GREEN}✅ Container restarted${NC}"
        ;;
    help|--help|-h|"")
        show_help
        ;;
    *)
        echo -e "${RED}❌ Unknown command: $1${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac
