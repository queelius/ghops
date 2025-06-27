import logging

from rich.console import Console
from rich.logging import RichHandler

# Initialize Rich Console
console = Console()

# Configure logging to use RichHandler
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True)]
)

logger = logging.getLogger("rich")
