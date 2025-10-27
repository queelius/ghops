#!/usr/bin/env python3
"""
Demo script showing TUI capabilities.

This script demonstrates how to launch and interact with the ghops TUI.
"""

import subprocess
import sys
from pathlib import Path


def check_dependencies():
    """Check if TUI dependencies are installed."""
    try:
        import textual
        print("✓ Textual is installed")
        return True
    except ImportError:
        print("✗ Textual is not installed")
        print("\nInstall with: pip install ghops[tui]")
        return False


def show_demo_info():
    """Display demo information."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║              ghops TUI - Interactive Demo                    ║
╚══════════════════════════════════════════════════════════════╝

This demo will launch the ghops TUI with the following features:

📁 Repository Navigation
   - Tree view of all repositories
   - Visual status indicators
   - Quick statistics

🔍 Clustering Analysis
   - Interactive clustering (press 'c')
   - Duplication detection
   - Consolidation suggestions

⚙️ Workflow Orchestration
   - Workflow editor (press 'w')
   - Real-time execution
   - YAML syntax highlighting

🎯 Command Palette
   - Quick command access (Ctrl+p)
   - Fuzzy search
   - Command history

Keyboard Shortcuts:
   Tab/Shift+Tab  - Cycle focus
   c              - Clustering analysis
   w              - Workflows
   p              - Command palette
   /              - Search
   h              - Help
   q              - Quit

Press Enter to launch TUI...
""")
    input()


def launch_tui(config_path=None):
    """Launch the TUI."""
    cmd = ["ghops", "tui"]

    if config_path:
        cmd.extend(["--config", config_path])

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\nTUI closed.")
    except Exception as e:
        print(f"Error launching TUI: {e}")
        sys.exit(1)


def main():
    """Main demo function."""
    print("ghops TUI Demo")
    print("=" * 60)

    # Check dependencies
    if not check_dependencies():
        sys.exit(1)

    # Show demo info
    show_demo_info()

    # Launch TUI
    print("\nLaunching ghops TUI...\n")
    launch_tui()

    print("\n" + "=" * 60)
    print("Demo complete!")
    print("\nNext steps:")
    print("1. Run 'ghops tui' to launch the TUI")
    print("2. Press 'h' for help and keyboard shortcuts")
    print("3. Explore the clustering analysis (press 'c')")
    print("4. Try the workflow orchestration (press 'w')")
    print("5. Use the command palette (Ctrl+p) for quick actions")


if __name__ == "__main__":
    main()