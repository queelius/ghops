"""
Workflow executor with scheduling and monitoring capabilities.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import threading
import schedule
import time

from .engine import WorkflowEngine
from .parser import WorkflowParser

logger = logging.getLogger(__name__)


class WorkflowExecutor:
    """Execute and manage workflow instances."""

    def __init__(self, workflows_dir: Optional[str] = None):
        """Initialize workflow executor.

        Args:
            workflows_dir: Directory containing workflow definitions.
        """
        self.workflows_dir = Path(workflows_dir) if workflows_dir else Path.cwd() / 'workflows'
        self.running_workflows = {}
        self.workflow_history = []
        self.scheduled_workflows = {}
        self.scheduler_thread = None
        self.stop_scheduler = threading.Event()

    def load_workflow(self, workflow_path: str) -> Dict[str, Any]:
        """Load a workflow definition.

        Args:
            workflow_path: Path to workflow file.

        Returns:
            Parsed workflow definition.
        """
        return WorkflowParser.load_workflow(workflow_path)

    async def execute_workflow(self,
                              workflow_path: str,
                              context: Optional[Dict[str, Any]] = None,
                              dry_run: bool = False) -> Dict[str, Any]:
        """Execute a workflow.

        Args:
            workflow_path: Path to workflow file.
            context: Initial context variables.
            dry_run: If True, simulate execution.

        Returns:
            Execution results.
        """
        # Load workflow
        workflow_def = self.load_workflow(workflow_path)

        # Create engine
        engine = WorkflowEngine(workflow_def, context)

        # Validate
        is_valid, errors = engine.validate()
        if not is_valid:
            return {
                'success': False,
                'errors': errors,
            }

        # Store in running workflows
        workflow_id = f"{workflow_def.get('name', 'unknown')}_{datetime.now().isoformat()}"
        self.running_workflows[workflow_id] = engine

        try:
            # Execute
            result = await engine.execute(dry_run)

            # Store in history
            self.workflow_history.append({
                'id': workflow_id,
                'workflow': workflow_def.get('name'),
                'start_time': result['start_time'],
                'end_time': result['end_time'],
                'duration': result['duration'],
                'success': result['tasks_failed'] == 0,
                'dry_run': dry_run,
            })

            return result

        finally:
            # Remove from running
            del self.running_workflows[workflow_id]

    def schedule_workflow(self,
                         workflow_path: str,
                         schedule_str: str,
                         context: Optional[Dict[str, Any]] = None):
        """Schedule a workflow to run periodically.

        Args:
            workflow_path: Path to workflow file.
            schedule_str: Cron-like schedule string or interval.
            context: Context variables for workflow.
        """
        workflow_def = self.load_workflow(workflow_path)
        workflow_name = workflow_def.get('name', 'unknown')

        # Parse schedule
        if schedule_str.startswith('every '):
            # Simple interval scheduling
            parts = schedule_str.split()
            if len(parts) >= 2:
                interval = int(parts[1])
                unit = parts[2] if len(parts) > 2 else 'minutes'

                if unit == 'minutes':
                    schedule.every(interval).minutes.do(
                        self._run_scheduled_workflow,
                        workflow_path,
                        context
                    )
                elif unit == 'hours':
                    schedule.every(interval).hours.do(
                        self._run_scheduled_workflow,
                        workflow_path,
                        context
                    )
                elif unit == 'days':
                    schedule.every(interval).days.do(
                        self._run_scheduled_workflow,
                        workflow_path,
                        context
                    )
        else:
            # Cron-style scheduling
            # For simplicity, using schedule library's time-based scheduling
            schedule.every().day.at(schedule_str).do(
                self._run_scheduled_workflow,
                workflow_path,
                context
            )

        self.scheduled_workflows[workflow_name] = {
            'path': workflow_path,
            'schedule': schedule_str,
            'context': context,
        }

    def _run_scheduled_workflow(self, workflow_path: str, context: Optional[Dict[str, Any]]):
        """Run a scheduled workflow (called by scheduler).

        Args:
            workflow_path: Path to workflow file.
            context: Context variables.
        """
        # Run in async context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                self.execute_workflow(workflow_path, context)
            )
            logger.info(f"Scheduled workflow completed: {result}")
        except Exception as e:
            logger.error(f"Scheduled workflow failed: {e}")
        finally:
            loop.close()

    def start_scheduler(self):
        """Start the workflow scheduler in background thread."""
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            logger.warning("Scheduler already running")
            return

        self.stop_scheduler.clear()
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop)
        self.scheduler_thread.daemon = True
        self.scheduler_thread.start()
        logger.info("Workflow scheduler started")

    def stop_scheduler(self):
        """Stop the workflow scheduler."""
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.stop_scheduler.set()
            self.scheduler_thread.join(timeout=5)
            logger.info("Workflow scheduler stopped")

    def _scheduler_loop(self):
        """Main scheduler loop (runs in separate thread)."""
        while not self.stop_scheduler.is_set():
            schedule.run_pending()
            time.sleep(1)

    def get_running_workflows(self) -> List[Dict[str, Any]]:
        """Get list of currently running workflows.

        Returns:
            List of running workflow information.
        """
        running = []
        for workflow_id, engine in self.running_workflows.items():
            running.append({
                'id': workflow_id,
                'name': engine.workflow.get('name'),
                'start_time': engine.start_time.isoformat() if engine.start_time else None,
                'tasks_total': len(engine.tasks),
                'tasks_completed': len(engine.status),
                'status': self._get_workflow_status(engine),
            })
        return running

    def _get_workflow_status(self, engine: WorkflowEngine) -> str:
        """Get overall workflow status.

        Args:
            engine: Workflow engine instance.

        Returns:
            Status string.
        """
        if not engine.status:
            return 'pending'

        if any(s == 'running' for s in engine.status.values()):
            return 'running'

        if any(s == 'failed' for s in engine.status.values()):
            return 'failed'

        if all(s in ['success', 'skipped'] for s in engine.status.values()):
            return 'success'

        return 'in_progress'

    def get_workflow_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get workflow execution history.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of historical workflow executions.
        """
        return self.workflow_history[-limit:]

    def export_workflow_report(self, workflow_id: str) -> Dict[str, Any]:
        """Export detailed report for a workflow execution.

        Args:
            workflow_id: Workflow execution ID.

        Returns:
            Detailed workflow report.
        """
        # Find in running or history
        if workflow_id in self.running_workflows:
            engine = self.running_workflows[workflow_id]
            return {
                'id': workflow_id,
                'status': 'running',
                'workflow': engine.workflow,
                'context': engine.context,
                'task_status': engine.status,
                'task_results': engine.results,
                'visualization': engine.visualize(),
            }

        # Check history
        for entry in self.workflow_history:
            if entry['id'] == workflow_id:
                return entry

        return {'error': f'Workflow {workflow_id} not found'}

    def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel a running workflow.

        Args:
            workflow_id: Workflow execution ID.

        Returns:
            True if cancelled, False if not found.
        """
        if workflow_id in self.running_workflows:
            # Simple cancellation - could be enhanced with proper async cancellation
            del self.running_workflows[workflow_id]
            logger.info(f"Workflow {workflow_id} cancelled")
            return True
        return False

    def list_available_workflows(self) -> List[Dict[str, Any]]:
        """List all available workflow definitions.

        Returns:
            List of workflow information.
        """
        workflows = []

        if self.workflows_dir.exists():
            for workflow_file in self.workflows_dir.glob('*.yaml'):
                try:
                    workflow_def = self.load_workflow(str(workflow_file))
                    workflows.append({
                        'file': workflow_file.name,
                        'path': str(workflow_file),
                        'name': workflow_def.get('name'),
                        'description': workflow_def.get('description'),
                        'task_count': len(workflow_def.get('tasks', [])),
                        'has_schedule': 'schedule' in workflow_def,
                    })
                except Exception as e:
                    logger.error(f"Failed to load {workflow_file}: {e}")

        return workflows

    def export_jsonl(self):
        """Export executor state as JSONL.

        Yields:
            JSON strings, one per line.
        """
        # Export running workflows
        for workflow in self.get_running_workflows():
            yield json.dumps({
                'type': 'running_workflow',
                **workflow
            })

        # Export scheduled workflows
        for name, info in self.scheduled_workflows.items():
            yield json.dumps({
                'type': 'scheduled_workflow',
                'name': name,
                **info
            })

        # Export recent history
        for entry in self.get_workflow_history(20):
            yield json.dumps({
                'type': 'workflow_history',
                **entry
            })