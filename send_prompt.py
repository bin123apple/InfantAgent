#!/usr/bin/env python3
"""
Simple CLI tool to send prompts to the InfantAgent running in a Docker container.

Usage:
    python send_prompt.py "Your task here"
    python send_prompt.py --interactive  # For interactive mode
"""

import sys
import subprocess
import argparse


def send_prompt_to_agent(prompt: str, container_name: str = "infant-agent-cli"):
    """
    Send a prompt to the running agent container via docker exec.

    Args:
        prompt: The user request/task to send to the agent
        container_name: Name of the agent container (default: infant-agent-cli)
    """
    try:
        # Check if container is running
        check_cmd = ["docker", "ps", "--filter", f"name={container_name}", "--format", "{{.Names}}"]
        result = subprocess.run(check_cmd, capture_output=True, text=True, check=True)

        if container_name not in result.stdout:
            print(f"❌ Error: Container '{container_name}' is not running.")
            print("Please start the containers with: docker compose up -d")
            return False

        # Escape single quotes in the prompt for bash
        escaped_prompt = prompt.replace("'", "'\\''")

        # Send the prompt to the container's stdin (PID 1)
        # We need to write to /proc/1/fd/0 which is the stdin of the main process
        exec_cmd = ["docker", "exec", "-i", container_name, "bash", "-c",
                   f"printf '%s\\n' '{escaped_prompt}' > /proc/1/fd/0"]

        print(f"📤 Sending prompt to agent: {prompt}")
        print(f"⏳ Agent is processing your request...")
        print("-" * 60)

        result = subprocess.run(exec_cmd, capture_output=True, text=True, check=True)

        if result.returncode == 0:
            print("✅ Prompt sent successfully!")
            print("\n📋 To view agent logs in real-time, run:")
            print(f"   docker logs -f {container_name}")
            print("\n💡 Or use: python send_prompt.py --logs --follow")
            return True
        else:
            print(f"❌ Error sending prompt: {result.stderr}")
            return False

    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        if e.stderr:
            print(f"stderr: {e.stderr}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def interactive_mode(container_name: str = "infant-agent-cli"):
    """Run in interactive mode, allowing multiple prompts."""
    print("🤖 InfantAgent Interactive Mode")
    print("=" * 60)
    print(f"Connected to container: {container_name}")
    print("Type 'exit' or 'quit' to stop, 'logs' to view agent logs")
    print("=" * 60)
    print()

    while True:
        try:
            prompt = input("💬 Enter your request: ").strip()

            if not prompt:
                continue

            if prompt.lower() in ['exit', 'quit', 'q']:
                print("👋 Goodbye!")
                break

            if prompt.lower() == 'logs':
                print("\n📋 Fetching agent logs...")
                try:
                    subprocess.run(["docker", "logs", "--tail", "50", container_name])
                except Exception as e:
                    print(f"❌ Error fetching logs: {e}")
                print()
                continue

            if prompt.lower() == 'status':
                print("\n📊 Container Status:")
                try:
                    subprocess.run(["docker", "ps", "--filter", f"name={container_name}",
                                  "--format", "table {{.Names}}\\t{{.Status}}\\t{{.Ports}}"])
                except Exception as e:
                    print(f"❌ Error fetching status: {e}")
                print()
                continue

            send_prompt_to_agent(prompt, container_name)
            print()

        except KeyboardInterrupt:
            print("\n👋 Interrupted. Goodbye!")
            break
        except EOFError:
            print("\n👋 EOF received. Goodbye!")
            break


def view_logs(container_name: str = "infant-agent-cli", follow: bool = False):
    """View agent logs."""
    try:
        cmd = ["docker", "logs"]
        if follow:
            cmd.append("-f")
        else:
            cmd.extend(["--tail", "100"])
        cmd.append(container_name)

        print(f"📋 Viewing logs from {container_name}...")
        print("-" * 60)
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n👋 Stopped viewing logs")
    except Exception as e:
        print(f"❌ Error viewing logs: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Send prompts to InfantAgent running in Docker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Send a single prompt
  python send_prompt.py "Create a Python script to analyze data"

  # Interactive mode
  python send_prompt.py --interactive
  python send_prompt.py -i

  # View logs
  python send_prompt.py --logs
  python send_prompt.py --logs --follow

  # Specify custom container name
  python send_prompt.py "Your task" --container my-agent-container
        """
    )

    parser.add_argument(
        "prompt",
        nargs="?",
        help="The prompt/task to send to the agent"
    )

    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Run in interactive mode"
    )

    parser.add_argument(
        "-l", "--logs",
        action="store_true",
        help="View agent logs"
    )

    parser.add_argument(
        "-f", "--follow",
        action="store_true",
        help="Follow logs (use with --logs)"
    )

    parser.add_argument(
        "-c", "--container",
        default="infant-agent-cli",
        help="Container name (default: infant-agent-cli)"
    )

    args = parser.parse_args()

    # Handle different modes
    if args.logs:
        view_logs(args.container, args.follow)
    elif args.interactive:
        interactive_mode(args.container)
    elif args.prompt:
        success = send_prompt_to_agent(args.prompt, args.container)
        sys.exit(0 if success else 1)
    else:
        parser.print_help()
        print("\n❌ Error: Please provide a prompt or use --interactive mode")
        sys.exit(1)


if __name__ == "__main__":
    main()
