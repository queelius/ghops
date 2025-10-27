"""
Analysis command group for ghops.

Provides various analysis operations including:
- audit: Repository health checks and auto-fix capabilities
- network: Network analysis of repository relationships
- ai: AI conversation import and analysis
"""

import click

from .audit import audit_cmd
from .network import network_cmd
from .ai import ai_cmd


@click.group(name='analysis')
def analysis_cmd():
    """Analyze repositories and their relationships.

    This group provides various analysis operations:

    \b
    - audit: Check repository health and compliance
    - network: Analyze repository relationship networks
    - ai: Import and analyze AI conversation data

    Examples:

    \b
        ghops analysis audit --auto-fix
        ghops analysis network analyze --output network.html
        ghops analysis ai import conversations.json
    """
    pass


# Add subcommands from existing implementations
# Note: These are already full commands/groups, so we add them directly
analysis_cmd.add_command(audit_cmd, name='audit')
analysis_cmd.add_command(network_cmd, name='network')
analysis_cmd.add_command(ai_cmd, name='ai')
