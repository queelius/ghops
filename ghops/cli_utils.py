"""
Common CLI utilities and decorators for consistent command behavior.
"""

import json
import sys
import click
from functools import wraps
from typing import Any, Dict, Generator
from .progress import get_progress
from .exit_codes import (
    SUCCESS, GENERAL_ERROR, USAGE_ERROR, INTERRUPTED,
    get_exit_code_for_exception, CommandError
)


def standard_command(streaming: bool = False):
    """
    Decorator that provides standard CLI behavior:
    - Progress reporting on stderr
    - Clean JSON output on stdout
    - Automatic --verbose/-v flag
    - Automatic --quiet/-q flag to suppress data output
    - Consistent error handling
    
    Args:
        streaming: If True, output JSONL as items are processed.
                  If False, collect results and output at end.
    """
    def decorator(func):
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract flags
            verbose = kwargs.get('verbose', False)
            quiet = kwargs.get('quiet', False)
            
            # Initialize progress reporter
            progress = get_progress(enabled=verbose or None)
            
            # Inject progress into kwargs
            kwargs['progress'] = progress
            
            try:
                # Call the actual command
                result = func(*args, **kwargs)
                
                # Handle output based on result type (unless quiet mode)
                if quiet:
                    # In quiet mode, consume the generator but don't output
                    if isinstance(result, Generator):
                        for _ in result:
                            pass
                elif result is None:
                    # Command handles its own output
                    pass
                elif isinstance(result, Generator):
                    # Stream results as JSONL
                    for item in result:
                        print(json.dumps(item, ensure_ascii=False), flush=True)
                elif isinstance(result, (list, tuple)):
                    # Output each item as JSONL
                    for item in result:
                        print(json.dumps(item, ensure_ascii=False), flush=True)
                elif isinstance(result, dict):
                    # Single JSON object
                    print(json.dumps(result, ensure_ascii=False), flush=True)
                else:
                    # Raw output (for backwards compatibility)
                    print(result, flush=True)
                
                # Successful completion
                sys.exit(SUCCESS)
                    
            except KeyboardInterrupt:
                progress.error("Interrupted by user")
                sys.exit(INTERRUPTED)
            except click.ClickException:
                # Click exceptions already have their exit code
                raise
            except CommandError as e:
                # Our custom command errors with specific exit codes
                progress.error(str(e))
                if not quiet:
                    error_obj = {
                        "error": str(e),
                        "type": type(e).__name__,
                        "exit_code": e.exit_code
                    }
                    # Add extra fields for PartialSuccessError
                    if hasattr(e, 'succeeded'):
                        error_obj['succeeded'] = e.succeeded
                        error_obj['failed'] = e.failed
                    print(json.dumps(error_obj, ensure_ascii=False), flush=True)
                sys.exit(e.exit_code)
            except Exception as e:
                progress.error(f"Command failed: {e}")
                # Output error as JSON for consistency (unless quiet)
                if not quiet:
                    error_obj = {
                        "error": str(e),
                        "type": type(e).__name__
                    }
                    print(json.dumps(error_obj, ensure_ascii=False), flush=True)
                # Exit with appropriate code
                sys.exit(get_exit_code_for_exception(e))
        
        return wrapper
    return decorator


def output_result(result: Any, progress: Any = None):
    """
    Standard output handler for results.
    
    Args:
        result: The result to output (dict, list, or generator)
        progress: Optional progress reporter for status messages
    """
    if isinstance(result, Generator):
        for item in result:
            print(json.dumps(item, ensure_ascii=False), flush=True)
    elif isinstance(result, (list, tuple)):
        for item in result:
            print(json.dumps(item, ensure_ascii=False), flush=True)
    elif isinstance(result, dict):
        print(json.dumps(result, ensure_ascii=False), flush=True)


def with_progress(func):
    """
    Simple decorator that just adds progress to a function.
    Less opinionated than standard_command.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Check if verbose flag exists
        verbose = kwargs.get('verbose', False)
        progress = get_progress(enabled=verbose or None)
        kwargs['progress'] = progress
        return func(*args, **kwargs)
    return wrapper


# Standard options that many commands share
common_options = {
    'verbose': click.option('-v', '--verbose', is_flag=True, 
                           help='Force progress output even when piped'),
    'quiet': click.option('-q', '--quiet', is_flag=True,
                         help='Suppress data output, show only progress'),
    'no_progress': click.option('--no-progress', is_flag=True,
                               help='Suppress progress output'),
    'dry_run': click.option('--dry-run', is_flag=True, 
                           help='Preview changes without saving'),
    'limit': click.option('--limit', type=int, 
                         help='Limit number of items to process'),
    'output_format': click.option('--format', type=click.Choice(['json', 'jsonl', 'csv']),
                                 default='jsonl', help='Output format'),
}


def add_common_options(*option_names):
    """
    Decorator to add common options to a command.
    
    Example:
        @add_common_options('verbose', 'dry_run')
        def my_command(verbose, dry_run):
            ...
    """
    def decorator(func):
        for name in reversed(option_names):
            if name in common_options:
                func = common_options[name](func)
        return func
    return decorator