"""
Workflow execution logic.
"""

import json
import logging
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, Any, Iterator, List, Optional

from .core import (
    WorkflowDefinition, WorkflowDAG, WorkflowStep, WorkflowExecution,
    StepStatus, WorkflowStatus
)
from .conditions import ConditionEvaluator

logger = logging.getLogger(__name__)


class ExecutionContext:
    """Context for workflow execution."""

    def __init__(self, workflow: WorkflowDefinition, execution: WorkflowExecution):
        """Initialize execution context.

        Args:
            workflow: Workflow definition
            execution: Workflow execution tracking
        """
        self.workflow = workflow
        self.execution = execution
        self.variables = {}  # Step outputs and variables
        self.env = workflow.env.copy()
        self.artifacts = {}

        # Initialize with workflow params
        self.variables.update(workflow.params)
        self.variables.update(execution.params)

    def get_variable(self, name: str) -> Any:
        """Get variable value."""
        return self.variables.get(name)

    def set_variable(self, name: str, value: Any):
        """Set variable value."""
        self.variables[name] = value

    def add_artifact(self, name: str, value: Any):
        """Add artifact to context."""
        self.artifacts[name] = value
        self.execution.artifacts[name] = value

    def evaluate_condition(self, condition: str) -> bool:
        """Evaluate a condition expression."""
        evaluator = ConditionEvaluator(self.variables)
        return evaluator.evaluate(condition)

    def substitute_variables(self, text: str) -> str:
        """Substitute variables in text."""
        import re

        def replace_var(match):
            var_name = match.group(1) or match.group(2)
            return str(self.variables.get(var_name, match.group(0)))

        # Replace ${var} or $var patterns
        text = re.sub(r'\$\{([^}]+)\}|\$(\w+)', replace_var, text)
        return text


class WorkflowExecutor:
    """Executes workflow steps."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize executor.

        Args:
            config: Executor configuration
        """
        self.config = config or {}
        self.max_parallel = self.config.get('max_parallel', 4)

    def execute(self, workflow: WorkflowDefinition, dag: WorkflowDAG,
                execution: WorkflowExecution, dry_run: bool = False) -> Iterator[Dict]:
        """Execute workflow.

        Args:
            workflow: Workflow definition
            dag: Workflow DAG
            execution: Execution tracking
            dry_run: Simulate execution

        Yields:
            Execution progress updates
        """
        context = ExecutionContext(workflow, execution)
        execution.status = WorkflowStatus.RUNNING

        # Get execution plan
        groups = dag.get_parallel_groups()

        yield {
            "action": "execution_plan",
            "groups": [[step.name for step in group] for group in groups],
            "total_steps": len(workflow.steps)
        }

        # Execute groups in order
        for group_idx, group in enumerate(groups):
            yield {
                "action": "group_started",
                "group": group_idx + 1,
                "steps": [step.name for step in group]
            }

            if len(group) > 1 and any(step.parallel for step in group):
                # Execute parallel steps
                for update in self._execute_parallel_steps(group, context, dry_run):
                    yield update
            else:
                # Execute sequential steps
                for step in group:
                    for update in self._execute_step(step, context, dry_run):
                        yield update

                    # Check if we should stop
                    if step.status == StepStatus.FAILED:
                        if step.on_failure == "stop":
                            execution.status = WorkflowStatus.FAILED
                            yield {
                                "action": "workflow_stopped",
                                "reason": f"Step '{step.name}' failed",
                                "step": step.name
                            }
                            return

            yield {
                "action": "group_completed",
                "group": group_idx + 1
            }

    def _execute_step(self, step: WorkflowStep, context: ExecutionContext,
                     dry_run: bool) -> Iterator[Dict]:
        """Execute a single step.

        Args:
            step: Step to execute
            context: Execution context
            dry_run: Simulate execution

        Yields:
            Step execution updates
        """
        # Check condition
        if step.condition:
            if not context.evaluate_condition(step.condition):
                step.status = StepStatus.SKIPPED
                yield {
                    "action": "step_skipped",
                    "step": step.name,
                    "condition": step.condition
                }
                return

        step.status = StepStatus.RUNNING
        step.start_time = datetime.now()
        context.execution.current_step = step.name

        yield {
            "action": "step_started",
            "step": step.name,
            "action_type": step.action,
            "params": step.params
        }

        if dry_run:
            # Simulate execution
            step.status = StepStatus.SUCCESS
            step.output = f"[DRY RUN] Would execute: {step.action}"
            yield {
                "action": "step_completed",
                "step": step.name,
                "status": "success",
                "dry_run": True
            }
        else:
            # Execute action
            for attempt in range(step.retry + 1):
                try:
                    output = self._execute_action(step, context)
                    step.output = output
                    step.status = StepStatus.SUCCESS

                    # Store output as variable
                    context.set_variable(f"{step.id}_output", output)

                    yield {
                        "action": "step_completed",
                        "step": step.name,
                        "status": "success",
                        "output": output
                    }
                    break

                except Exception as e:
                    if attempt < step.retry:
                        yield {
                            "action": "step_retry",
                            "step": step.name,
                            "attempt": attempt + 1,
                            "max_attempts": step.retry + 1,
                            "error": str(e)
                        }
                        time.sleep(2 ** attempt)  # Exponential backoff
                    else:
                        step.status = StepStatus.FAILED
                        step.error = str(e)
                        yield {
                            "action": "step_failed",
                            "step": step.name,
                            "error": str(e)
                        }

        step.end_time = datetime.now()
        context.execution.steps_completed += 1

    def _execute_parallel_steps(self, steps: List[WorkflowStep], context: ExecutionContext,
                               dry_run: bool) -> Iterator[Dict]:
        """Execute steps in parallel.

        Args:
            steps: Steps to execute
            context: Execution context
            dry_run: Simulate execution

        Yields:
            Parallel execution updates
        """
        with ThreadPoolExecutor(max_workers=min(self.max_parallel, len(steps))) as executor:
            futures = {}

            for step in steps:
                future = executor.submit(self._execute_step_sync, step, context, dry_run)
                futures[future] = step

            for future in as_completed(futures):
                step = futures[future]
                try:
                    updates = future.result()
                    for update in updates:
                        yield update
                except Exception as e:
                    yield {
                        "action": "step_failed",
                        "step": step.name,
                        "error": str(e)
                    }

    def _execute_step_sync(self, step: WorkflowStep, context: ExecutionContext,
                          dry_run: bool) -> List[Dict]:
        """Execute step synchronously (for parallel execution).

        Args:
            step: Step to execute
            context: Execution context
            dry_run: Simulate execution

        Returns:
            List of updates
        """
        updates = []
        for update in self._execute_step(step, context, dry_run):
            updates.append(update)
        return updates

    def _execute_action(self, step: WorkflowStep, context: ExecutionContext) -> Any:
        """Execute the actual action for a step.

        Args:
            step: Step containing action
            context: Execution context

        Returns:
            Action output
        """
        action = step.action
        params = step.params.copy()

        # Substitute variables in params
        for key, value in params.items():
            if isinstance(value, str):
                params[key] = context.substitute_variables(value)

        # Built-in actions
        if action == "shell":
            return self._execute_shell(params, context)
        elif action == "ghops":
            return self._execute_ghops(params, context)
        elif action == "python":
            return self._execute_python(params, context)
        elif action == "http":
            return self._execute_http(params, context)
        elif action == "git":
            return self._execute_git(params, context)
        elif action == "set_variable":
            return self._execute_set_variable(params, context)
        elif action == "condition":
            return self._execute_condition(params, context)
        elif action == "loop":
            return self._execute_loop(params, context)
        else:
            # Custom action - try to find handler
            return self._execute_custom(action, params, context)

    def _execute_shell(self, params: Dict, context: ExecutionContext) -> str:
        """Execute shell command."""
        command = params.get('command', '')
        cwd = params.get('cwd', None)
        timeout = params.get('timeout', 300)

        # Set environment
        env = context.env.copy()
        env.update(params.get('env', {}))

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            env=env,
            timeout=timeout
        )

        if result.returncode != 0:
            raise RuntimeError(f"Command failed: {result.stderr}")

        return result.stdout

    def _execute_ghops(self, params: Dict, context: ExecutionContext) -> str:
        """Execute ghops command."""
        command = params.get('command', '')
        args = params.get('args', [])

        # Build full command
        full_command = f"ghops {command} {' '.join(args)}"

        return self._execute_shell({'command': full_command}, context)

    def _execute_python(self, params: Dict, context: ExecutionContext) -> Any:
        """Execute Python code."""
        code = params.get('code', '')

        # Create execution environment
        exec_globals = {
            'context': context,
            'params': params,
            'variables': context.variables
        }

        # Execute code
        exec(code, exec_globals)

        # Return result if set
        return exec_globals.get('result', None)

    def _execute_http(self, params: Dict, context: ExecutionContext) -> Dict:
        """Execute HTTP request."""
        import requests

        method = params.get('method', 'GET')
        url = params.get('url', '')
        headers = params.get('headers', {})
        body = params.get('body', None)
        timeout = params.get('timeout', 30)

        response = requests.request(
            method,
            url,
            headers=headers,
            json=body,
            timeout=timeout
        )

        response.raise_for_status()

        return {
            'status_code': response.status_code,
            'headers': dict(response.headers),
            'body': response.json() if response.content else None
        }

    def _execute_git(self, params: Dict, context: ExecutionContext) -> str:
        """Execute git command."""
        operation = params.get('operation', '')
        repo_path = params.get('repo', '.')

        git_commands = {
            'pull': 'git pull',
            'push': 'git push',
            'commit': f"git commit -m '{params.get('message', 'Auto commit')}'",
            'tag': f"git tag {params.get('tag_name', '')}",
            'status': 'git status --porcelain'
        }

        command = git_commands.get(operation, operation)

        return self._execute_shell({
            'command': command,
            'cwd': repo_path
        }, context)

    def _execute_set_variable(self, params: Dict, context: ExecutionContext) -> Any:
        """Set variable in context."""
        name = params.get('name', '')
        value = params.get('value', '')

        context.set_variable(name, value)
        return value

    def _execute_condition(self, params: Dict, context: ExecutionContext) -> bool:
        """Evaluate condition."""
        expression = params.get('expression', '')
        return context.evaluate_condition(expression)

    def _execute_loop(self, params: Dict, context: ExecutionContext) -> List[Any]:
        """Execute loop."""
        items = params.get('items', [])
        action = params.get('action', '')
        action_params = params.get('params', {})

        results = []
        for item in items:
            # Set loop variable
            context.set_variable('item', item)

            # Execute action for each item
            step = WorkflowStep(
                id=f"loop_{item}",
                name=f"Loop: {item}",
                action=action,
                params=action_params
            )

            output = self._execute_action(step, context)
            results.append(output)

        return results

    def _execute_custom(self, action: str, params: Dict, context: ExecutionContext) -> Any:
        """Execute custom action."""
        # Look for custom action handler
        # This could be extended to load plugins
        raise NotImplementedError(f"Unknown action: {action}")