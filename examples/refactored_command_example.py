"""
Example showing how to refactor commands to use the standard progress pattern.
"""

import click
import time
from ghops.cli_utils import standard_command, add_common_options


# BEFORE: Old style with mixed concerns
@click.command()
@click.option('--pretty', is_flag=True, help='Pretty output')
def old_style_command(pretty):
    """Old style command with mixed output concerns."""
    if pretty:
        print("Starting process...")
    
    results = []
    for i in range(5):
        time.sleep(0.1)
        if pretty:
            print(f"Processing item {i}")
        result = {"id": i, "status": "processed"}
        results.append(result)
    
    if pretty:
        print(f"Processed {len(results)} items")
        for r in results:
            print(f"  - Item {r['id']}: {r['status']}")
    else:
        import json
        for r in results:
            print(json.dumps(r))


# AFTER: New style with clean separation
@click.command()
@standard_command(streaming=True)
def new_style_command(progress, **kwargs):
    """New style command with clean separation of concerns."""
    progress("Starting process...")
    
    with progress.task("Processing items", total=5) as update:
        for i in range(5):
            update(i + 1, f"Item {i}")
            time.sleep(0.1)
            
            # Yield result for streaming output
            yield {"id": i, "status": "processed"}
    
    progress.success("All items processed successfully")


# AFTER: Alternative using decorator for common options
@click.command()
@add_common_options('verbose', 'dry_run', 'limit')
@standard_command()
def new_style_with_options(progress, dry_run, limit, **kwargs):
    """Command with common options."""
    items = range(limit or 10)
    
    progress(f"Processing {len(list(items))} items")
    if dry_run:
        progress.warning("DRY RUN - no changes will be saved")
    
    results = []
    with progress.task("Processing", total=len(list(items))) as update:
        for i in items:
            update(i + 1, f"Item {i}")
            
            if not dry_run:
                # Actually do something
                time.sleep(0.1)
            
            results.append({
                "id": i, 
                "status": "processed" if not dry_run else "simulated"
            })
    
    progress.success(f"Completed {'(dry run)' if dry_run else ''}")
    return results


# Pattern for commands that need custom error handling
@click.command()
@standard_command()
def command_with_error_handling(progress, **kwargs):
    """Command showing error handling."""
    try:
        with progress.spinner("Connecting to service..."):
            time.sleep(1)
            # Simulate potential failure
            import random
            if random.random() < 0.3:
                raise ConnectionError("Failed to connect to service")
        
        progress.success("Connected successfully")
        
        # Return results
        return {"status": "success", "data": [1, 2, 3]}
        
    except ConnectionError as e:
        progress.error(f"Connection failed: {e}")
        # Re-raise to let standard_command handle it
        raise


if __name__ == "__main__":
    # Example usage patterns:
    
    print("=" * 60)
    print("OLD STYLE (pretty mode):")
    print("=" * 60)
    ctx = click.Context(old_style_command)
    ctx.invoke(old_style_command, pretty=True)
    
    print("\n" + "=" * 60)
    print("OLD STYLE (json mode):")
    print("=" * 60)
    ctx = click.Context(old_style_command)
    ctx.invoke(old_style_command, pretty=False)
    
    print("\n" + "=" * 60)
    print("NEW STYLE (automatic progress):")
    print("=" * 60)
    ctx = click.Context(new_style_command)
    for item in ctx.invoke(new_style_command, verbose=True):
        pass  # Items are printed as JSONL automatically