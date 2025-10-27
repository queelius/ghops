"""
Core workflow execution engine.
"""

import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime
from collections import defaultdict
import subprocess
import os

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """DAG-based workflow execution engine for repository operations."""

    def __init__(self, workflow_def: Dict[str, Any], context: Optional[Dict[str, Any]] = None):
        """Initialize workflow engine.

        Args:
            workflow_def: Workflow definition dictionary.
            context: Initial context/variables for workflow.
        """
        self.workflow = workflow_def
        self.context = context or {}
        self.tasks = workflow_def.get('tasks', [])
        self.dependencies = self._build_dependency_graph()
        self.status = {}  # task_id -> status
        self.results = {}  # task_id -> result
        self.start_time = None
        self.end_time = None

    def _build_dependency_graph(self) -> Dict[str, Set[str]]:
        """Build dependency graph from task definitions.

        Returns:
            Dictionary mapping task IDs to their dependencies.
        """
        graph = defaultdict(set)

        for task in self.tasks:
            task_id = task['id']
            deps = task.get('depends_on', [])
            if isinstance(deps, str):
                deps = [deps]
            graph[task_id] = set(deps)

        return dict(graph)

    def validate(self) -> Tuple[bool, List[str]]:
        """Validate workflow for cycles and missing dependencies.

        Returns:
            Tuple of (is_valid, error_messages).
        """
        errors = []

        # Check for cycles
        if self._has_cycle():
            errors.append("Workflow contains circular dependencies")

        # Check for missing task definitions
        all_task_ids = {task['id'] for task in self.tasks}
        for task_id, deps in self.dependencies.items():
            for dep in deps:
                if dep not in all_task_ids:
                    errors.append(f"Task '{task_id}' depends on undefined task '{dep}'")

        # Check required fields
        for task in self.tasks:
            if 'id' not in task:
                errors.append("Task missing required field 'id'")
            if 'type' not in task:
                errors.append(f"Task '{task.get('id', 'unknown')}' missing required field 'type'")

        return len(errors) == 0, errors

    def _has_cycle(self) -> bool:
        """Check if dependency graph has cycles using DFS.

        Returns:
            True if cycle exists, False otherwise.
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        color = defaultdict(lambda: WHITE)

        def visit(node):
            if color[node] == GRAY:
                return True  # Back edge found
            if color[node] == BLACK:
                return False  # Already processed

            color[node] = GRAY
            for neighbor in self.dependencies.get(node, []):
                if visit(neighbor):
                    return True
            color[node] = BLACK
            return False

        for task_id in self.dependencies:
            if color[task_id] == WHITE:
                if visit(task_id):
                    return True
        return False

    def get_execution_order(self) -> List[List[str]]:
        """Get topological execution order with parallel groups.

        Returns:
            List of task groups that can be executed in parallel.
        """
        # Kahn's algorithm for topological sort with level detection
        in_degree = defaultdict(int)
        all_tasks = set()

        # Calculate in-degrees
        for task_id, deps in self.dependencies.items():
            all_tasks.add(task_id)
            for dep in deps:
                in_degree[dep] += 0  # Ensure dep is in dict
                all_tasks.add(dep)
            for dep in deps:
                in_degree[task_id] += 1

        # Find tasks with no dependencies
        queue = [task for task in all_tasks if in_degree[task] == 0]
        execution_order = []

        while queue:
            # All tasks in current queue can be executed in parallel
            current_level = queue.copy()
            execution_order.append(current_level)
            queue = []

            for task in current_level:
                # Reduce in-degree for dependent tasks
                for next_task, deps in self.dependencies.items():
                    if task in deps:
                        in_degree[next_task] -= 1
                        if in_degree[next_task] == 0:
                            queue.append(next_task)

        return execution_order

    async def execute(self, dry_run: bool = False) -> Dict[str, Any]:
        """Execute workflow tasks.

        Args:
            dry_run: If True, simulate execution without running tasks.

        Returns:
            Execution results dictionary.
        """
        self.start_time = datetime.now()
        execution_order = self.get_execution_order()

        for task_group in execution_order:
            # Execute tasks in parallel within each group
            if dry_run:
                for task_id in task_group:
                    self.status[task_id] = 'simulated'
                    self.results[task_id] = {'dry_run': True}
            else:
                await self._execute_task_group(task_group)

        self.end_time = datetime.now()

        return {
            'workflow': self.workflow.get('name', 'unnamed'),
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'duration': (self.end_time - self.start_time).total_seconds(),
            'tasks_executed': len(self.status),
            'tasks_succeeded': sum(1 for s in self.status.values() if s == 'success'),
            'tasks_failed': sum(1 for s in self.status.values() if s == 'failed'),
            'task_results': self.results,
        }

    async def _execute_task_group(self, task_ids: List[str]):
        """Execute a group of tasks in parallel.

        Args:
            task_ids: List of task IDs to execute.
        """
        tasks = []
        for task_id in task_ids:
            task_def = self._get_task_definition(task_id)
            if task_def:
                # Check conditions
                if self._should_execute(task_def):
                    tasks.append(self._execute_single_task(task_id, task_def))
                else:
                    self.status[task_id] = 'skipped'
                    self.results[task_id] = {'skipped': True, 'reason': 'condition_failed'}

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_single_task(self, task_id: str, task_def: Dict[str, Any]):
        """Execute a single task.

        Args:
            task_id: Task identifier.
            task_def: Task definition dictionary.
        """
        try:
            self.status[task_id] = 'running'
            task_type = task_def['type']

            if task_type == 'shell':
                result = await self._execute_shell_task(task_def)
            elif task_type == 'ghops':
                result = await self._execute_ghops_task(task_def)
            elif task_type == 'python':
                result = await self._execute_python_task(task_def)
            elif task_type == 'parallel':
                result = await self._execute_parallel_task(task_def)
            else:
                raise ValueError(f"Unknown task type: {task_type}")

            self.status[task_id] = 'success'
            self.results[task_id] = result

        except Exception as e:
            self.status[task_id] = 'failed'
            self.results[task_id] = {'error': str(e)}

            # Check if failure should stop workflow
            if task_def.get('on_failure') == 'stop':
                raise WorkflowExecutionError(f"Task {task_id} failed: {e}")

    async def _execute_shell_task(self, task_def: Dict[str, Any]) -> Dict[str, Any]:
        """Execute shell command task.

        Args:
            task_def: Task definition.

        Returns:
            Task execution result.
        """
        command = task_def['command']

        # Substitute variables
        command = self._substitute_variables(command)

        # Get working directory
        cwd = task_def.get('cwd')
        if cwd:
            cwd = self._substitute_variables(cwd)

        # Execute command
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env={**os.environ, **self.context.get('env', {})}
        )

        stdout, stderr = await process.communicate()

        result = {
            'command': command,
            'return_code': process.returncode,
            'stdout': stdout.decode('utf-8'),
            'stderr': stderr.decode('utf-8'),
        }

        # Store output in context if specified
        if 'output_var' in task_def:
            self.context[task_def['output_var']] = result['stdout'].strip()

        # Check for success
        if process.returncode != 0 and not task_def.get('ignore_errors', False):
            raise RuntimeError(f"Command failed: {command}")

        return result

    async def _execute_ghops_task(self, task_def: Dict[str, Any]) -> Dict[str, Any]:
        """Execute ghops command task.

        Args:
            task_def: Task definition.

        Returns:
            Task execution result.
        """
        command = task_def['command']
        args = task_def.get('args', [])

        # Build full command
        full_command = f"ghops {command}"
        if args:
            if isinstance(args, list):
                args_str = ' '.join(str(a) for a in args)
            else:
                args_str = str(args)
            full_command = f"{full_command} {args_str}"

        # Substitute variables
        full_command = self._substitute_variables(full_command)

        # Execute as shell command
        process = await asyncio.create_subprocess_shell(
            full_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, **self.context.get('env', {})}
        )

        stdout, stderr = await process.communicate()

        result = {
            'command': full_command,
            'return_code': process.returncode,
            'output': stdout.decode('utf-8'),
            'errors': stderr.decode('utf-8'),
        }

        # Parse JSONL output if expected
        if task_def.get('parse_output', False):
            lines = result['output'].strip().split('\n')
            parsed = []
            for line in lines:
                if line:
                    try:
                        parsed.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            result['parsed_output'] = parsed

        return result

    async def _execute_python_task(self, task_def: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Python code task.

        Args:
            task_def: Task definition.

        Returns:
            Task execution result.
        """
        code = task_def['code']

        # Substitute variables
        code = self._substitute_variables(code)

        # Create a restricted execution environment
        exec_globals = {
            '__builtins__': __builtins__,
            'context': self.context,
            'results': self.results,
        }

        # Execute code
        try:
            exec(code, exec_globals)

            # Extract any new variables added to context
            if 'context' in exec_globals:
                self.context.update(exec_globals['context'])

            return {
                'executed': True,
                'context_updated': True,
            }
        except Exception as e:
            raise RuntimeError(f"Python execution failed: {e}")

    async def _execute_parallel_task(self, task_def: Dict[str, Any]) -> Dict[str, Any]:
        """Execute parallel sub-tasks.

        Args:
            task_def: Task definition with sub-tasks.

        Returns:
            Combined results from all sub-tasks.
        """
        sub_tasks = task_def.get('tasks', [])
        if not sub_tasks:
            return {'error': 'No sub-tasks defined'}

        # Execute all sub-tasks in parallel
        results = await asyncio.gather(
            *[self._execute_single_task(f"{task_def['id']}_{i}", task)
              for i, task in enumerate(sub_tasks)],
            return_exceptions=True
        )

        # Combine results
        combined = {
            'sub_task_count': len(sub_tasks),
            'sub_task_results': results,
        }

        return combined

    def _get_task_definition(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task definition by ID.

        Args:
            task_id: Task identifier.

        Returns:
            Task definition or None if not found.
        """
        for task in self.tasks:
            if task['id'] == task_id:
                return task
        return None

    def _should_execute(self, task_def: Dict[str, Any]) -> bool:
        """Check if task should be executed based on conditions.

        Args:
            task_def: Task definition.

        Returns:
            True if task should execute, False otherwise.
        """
        condition = task_def.get('condition')
        if not condition:
            return True

        # Simple condition evaluation
        # In production, use a safe expression evaluator
        try:
            # Substitute variables in condition
            condition = self._substitute_variables(condition)

            # Very basic condition checking
            if condition.startswith('not '):
                return not self._evaluate_simple_condition(condition[4:])
            else:
                return self._evaluate_simple_condition(condition)
        except:
            # If condition evaluation fails, execute by default
            return True

    def _evaluate_simple_condition(self, condition: str) -> bool:
        """Evaluate simple condition expressions.

        Args:
            condition: Condition string.

        Returns:
            Boolean result of condition.
        """
        # Check for variable existence
        if condition in self.context:
            return bool(self.context[condition])

        # Check for simple comparisons
        if '==' in condition:
            left, right = condition.split('==', 1)
            left = left.strip()
            right = right.strip().strip('"').strip("'")
            return str(self.context.get(left, '')) == right

        if '!=' in condition:
            left, right = condition.split('!=', 1)
            left = left.strip()
            right = right.strip().strip('"').strip("'")
            return str(self.context.get(left, '')) != right

        # Default to false for unknown conditions
        return False

    def _substitute_variables(self, text: str) -> str:
        """Substitute variables in text.

        Args:
            text: Text containing variable references.

        Returns:
            Text with variables substituted.
        """
        # Simple variable substitution
        for key, value in self.context.items():
            text = text.replace(f'${{{key}}}', str(value))
            text = text.replace(f'${key}', str(value))

        # Environment variables
        for key, value in os.environ.items():
            text = text.replace(f'$ENV_{key}', value)

        return text

    def visualize(self) -> str:
        """Generate visual representation of workflow.

        Returns:
            ASCII art representation of workflow DAG.
        """
        execution_order = self.get_execution_order()
        lines = []

        lines.append(f"Workflow: {self.workflow.get('name', 'unnamed')}")
        lines.append(f"Description: {self.workflow.get('description', 'No description')}")
        lines.append("")
        lines.append("Execution Order:")
        lines.append("=" * 50)

        for i, task_group in enumerate(execution_order, 1):
            lines.append(f"Stage {i} (parallel execution):")
            for task_id in task_group:
                task_def = self._get_task_definition(task_id)
                if task_def:
                    task_type = task_def.get('type', 'unknown')
                    desc = task_def.get('name', task_id)
                    deps = self.dependencies.get(task_id, set())

                    status_icon = self._get_status_icon(task_id)
                    dep_str = f" <- {', '.join(deps)}" if deps else ""

                    lines.append(f"  {status_icon} [{task_type}] {desc}{dep_str}")

        lines.append("=" * 50)
        lines.append("")
        lines.append("Legend:")
        lines.append("  ○ Not started")
        lines.append("  ◉ Running")
        lines.append("  ✓ Success")
        lines.append("  ✗ Failed")
        lines.append("  ⊘ Skipped")

        return '\n'.join(lines)

    def _get_status_icon(self, task_id: str) -> str:
        """Get status icon for task.

        Args:
            task_id: Task identifier.

        Returns:
            Unicode icon representing task status.
        """
        status = self.status.get(task_id, 'pending')
        icons = {
            'pending': '○',
            'running': '◉',
            'success': '✓',
            'failed': '✗',
            'skipped': '⊘',
            'simulated': '◊',
        }
        return icons.get(status, '?')

    def export_mermaid(self) -> str:
        """Export workflow as Mermaid diagram.

        Returns:
            Mermaid diagram definition.
        """
        lines = ['graph TD']

        # Add nodes
        for task in self.tasks:
            task_id = task['id']
            task_name = task.get('name', task_id)
            task_type = task.get('type', 'unknown')

            # Style based on status
            status = self.status.get(task_id, 'pending')
            if status == 'success':
                style = f"{task_id}[{task_name}]:::success"
            elif status == 'failed':
                style = f"{task_id}[{task_name}]:::failed"
            elif status == 'running':
                style = f"{task_id}[{task_name}]:::running"
            elif status == 'skipped':
                style = f"{task_id}[{task_name}]:::skipped"
            else:
                style = f"{task_id}[{task_name}]"

            lines.append(f"    {style}")

        # Add edges
        for task_id, deps in self.dependencies.items():
            for dep in deps:
                lines.append(f"    {dep} --> {task_id}")

        # Add style definitions
        lines.extend([
            "",
            "    classDef success fill:#90EE90,stroke:#333,stroke-width:2px;",
            "    classDef failed fill:#FFB6C1,stroke:#333,stroke-width:2px;",
            "    classDef running fill:#87CEEB,stroke:#333,stroke-width:2px;",
            "    classDef skipped fill:#D3D3D3,stroke:#333,stroke-width:2px;",
        ])

        return '\n'.join(lines)


class WorkflowExecutionError(Exception):
    """Raised when workflow execution fails."""
    pass