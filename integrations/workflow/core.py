"""
Core workflow engine implementation.
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Iterator, Set, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)


class StepStatus(Enum):
    """Status of a workflow step."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class WorkflowStatus(Enum):
    """Status of entire workflow."""
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


@dataclass
class WorkflowStep:
    """Represents a single workflow step."""
    id: str
    name: str
    action: str
    params: Dict[str, Any] = field(default_factory=dict)
    condition: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)
    parallel: bool = False
    retry: int = 0
    timeout: Optional[int] = None  # seconds
    on_failure: Optional[str] = None  # 'continue', 'stop', 'rollback'
    artifacts: Dict[str, Any] = field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    output: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class WorkflowDAG:
    """Directed Acyclic Graph of workflow steps."""
    steps: Dict[str, WorkflowStep] = field(default_factory=dict)
    edges: Dict[str, Set[str]] = field(default_factory=dict)  # step_id -> dependent_ids
    reverse_edges: Dict[str, Set[str]] = field(default_factory=dict)  # step_id -> dependency_ids

    def add_step(self, step: WorkflowStep):
        """Add a step to the DAG."""
        self.steps[step.id] = step

        # Initialize edge sets
        if step.id not in self.edges:
            self.edges[step.id] = set()
        if step.id not in self.reverse_edges:
            self.reverse_edges[step.id] = set()

        # Add dependencies
        for dep_id in step.depends_on:
            if dep_id not in self.edges:
                self.edges[dep_id] = set()
            self.edges[dep_id].add(step.id)
            self.reverse_edges[step.id].add(dep_id)

    def get_ready_steps(self) -> List[WorkflowStep]:
        """Get steps that are ready to run (all dependencies completed)."""
        ready = []

        for step_id, step in self.steps.items():
            if step.status != StepStatus.PENDING:
                continue

            # Check if all dependencies are completed
            deps_completed = all(
                self.steps[dep_id].status == StepStatus.SUCCESS
                for dep_id in self.reverse_edges.get(step_id, [])
            )

            if deps_completed:
                ready.append(step)

        return ready

    def get_parallel_groups(self) -> List[List[WorkflowStep]]:
        """Get groups of steps that can run in parallel."""
        groups = []
        visited = set()

        while len(visited) < len(self.steps):
            # Get all ready steps not yet visited
            ready = []
            for step in self.get_ready_steps():
                if step.id not in visited:
                    ready.append(step)
                    visited.add(step.id)

            if ready:
                # Group parallel steps
                parallel_group = []
                sequential_group = []

                for step in ready:
                    if step.parallel:
                        parallel_group.append(step)
                    else:
                        sequential_group.append(step)

                if parallel_group:
                    groups.append(parallel_group)
                for step in sequential_group:
                    groups.append([step])

            # Mark ready steps as completed for next iteration
            for step in ready:
                step.status = StepStatus.SUCCESS

        # Reset statuses
        for step in self.steps.values():
            step.status = StepStatus.PENDING

        return groups

    def validate(self) -> Tuple[bool, Optional[str]]:
        """Validate the DAG for cycles and missing dependencies."""
        # Check for cycles using DFS
        visited = set()
        rec_stack = set()

        def has_cycle(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for neighbor in self.edges.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        for node in self.steps:
            if node not in visited:
                if has_cycle(node):
                    return False, f"Cycle detected involving step: {node}"

        # Check for missing dependencies
        for step_id, step in self.steps.items():
            for dep_id in step.depends_on:
                if dep_id not in self.steps:
                    return False, f"Step '{step_id}' depends on non-existent step '{dep_id}'"

        return True, None


@dataclass
class WorkflowDefinition:
    """Complete workflow definition."""
    name: str
    version: str = "1.0"
    description: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    env: Dict[str, str] = field(default_factory=dict)
    triggers: List[str] = field(default_factory=list)
    steps: List[WorkflowStep] = field(default_factory=list)
    on_success: Optional[str] = None
    on_failure: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowExecution:
    """Tracks a workflow execution."""
    id: str
    workflow_name: str
    status: WorkflowStatus = WorkflowStatus.CREATED
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    params: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    steps_completed: int = 0
    steps_total: int = 0
    current_step: Optional[str] = None
    logs: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: Dict[str, Any] = field(default_factory=dict)


class WorkflowEngine:
    """Main workflow orchestration engine."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize workflow engine.

        Args:
            config: Engine configuration
        """
        self.config = config or {}
        self.workflows = {}  # name -> WorkflowDefinition
        self.executions = {}  # execution_id -> WorkflowExecution
        self.dag_cache = {}  # workflow_name -> WorkflowDAG

    def load_workflow(self, workflow_path: str) -> WorkflowDefinition:
        """Load workflow from YAML file.

        Args:
            workflow_path: Path to workflow YAML file

        Returns:
            Loaded workflow definition
        """
        from .parser import WorkflowParser

        parser = WorkflowParser()
        workflow = parser.parse_file(workflow_path)

        self.workflows[workflow.name] = workflow

        # Build and cache DAG
        dag = self._build_dag(workflow)
        self.dag_cache[workflow.name] = dag

        return workflow

    def _build_dag(self, workflow: WorkflowDefinition) -> WorkflowDAG:
        """Build DAG from workflow definition."""
        dag = WorkflowDAG()

        for step in workflow.steps:
            dag.add_step(step)

        return dag

    def execute(self, workflow_name: str, params: Optional[Dict[str, Any]] = None,
                dry_run: bool = False) -> Iterator[Dict]:
        """Execute a workflow.

        Args:
            workflow_name: Name of workflow to execute
            params: Parameters for workflow
            dry_run: If True, simulate execution without running actions

        Yields:
            Execution progress updates
        """
        if workflow_name not in self.workflows:
            yield {
                "action": "error",
                "error": f"Workflow '{workflow_name}' not found"
            }
            return

        workflow = self.workflows[workflow_name]
        dag = self.dag_cache[workflow_name]

        # Validate DAG
        valid, error = dag.validate()
        if not valid:
            yield {
                "action": "error",
                "error": f"Invalid workflow: {error}"
            }
            return

        # Create execution
        execution = WorkflowExecution(
            id=self._generate_execution_id(),
            workflow_name=workflow_name,
            params=params or {},
            start_time=datetime.now(),
            steps_total=len(workflow.steps)
        )

        self.executions[execution.id] = execution

        yield {
            "action": "workflow_started",
            "execution_id": execution.id,
            "workflow": workflow_name,
            "params": params,
            "dry_run": dry_run
        }

        # Execute workflow
        from .executor import WorkflowExecutor

        executor = WorkflowExecutor(self.config)

        for update in executor.execute(workflow, dag, execution, dry_run):
            yield update

        # Finalize execution
        execution.end_time = datetime.now()
        execution.status = WorkflowStatus.COMPLETED

        yield {
            "action": "workflow_completed",
            "execution_id": execution.id,
            "duration": (execution.end_time - execution.start_time).total_seconds(),
            "steps_completed": execution.steps_completed,
            "artifacts": execution.artifacts
        }

    def _generate_execution_id(self) -> str:
        """Generate unique execution ID."""
        timestamp = datetime.now().isoformat()
        hash_input = f"{timestamp}-{len(self.executions)}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:12]

    def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Get execution details."""
        return self.executions.get(execution_id)

    def list_workflows(self) -> List[Dict]:
        """List available workflows."""
        return [
            {
                "name": workflow.name,
                "version": workflow.version,
                "description": workflow.description,
                "steps": len(workflow.steps),
                "params": list(workflow.params.keys())
            }
            for workflow in self.workflows.values()
        ]

    def visualize_workflow(self, workflow_name: str) -> str:
        """Generate workflow visualization."""
        if workflow_name not in self.workflows:
            raise ValueError(f"Workflow '{workflow_name}' not found")

        dag = self.dag_cache[workflow_name]

        # Generate DOT format for Graphviz
        dot = ["digraph Workflow {"]
        dot.append('  rankdir="TB";')
        dot.append('  node [shape=box, style=rounded];')

        # Add nodes
        for step_id, step in dag.steps.items():
            label = f"{step.name}\\n({step.action})"
            color = "lightblue" if step.parallel else "lightgray"
            dot.append(f'  "{step_id}" [label="{label}", fillcolor={color}, style=filled];')

        # Add edges
        for from_id, to_ids in dag.edges.items():
            for to_id in to_ids:
                dot.append(f'  "{from_id}" -> "{to_id}";')

        dot.append("}")

        return "\n".join(dot)

    def export_workflow(self, workflow_name: str, format: str = "yaml") -> str:
        """Export workflow in specified format.

        Args:
            workflow_name: Workflow to export
            format: Export format ('yaml', 'json', 'dot')

        Returns:
            Exported workflow string
        """
        if workflow_name not in self.workflows:
            raise ValueError(f"Workflow '{workflow_name}' not found")

        workflow = self.workflows[workflow_name]

        if format == "yaml":
            import yaml
            return yaml.dump(asdict(workflow), default_flow_style=False)
        elif format == "json":
            return json.dumps(asdict(workflow), indent=2)
        elif format == "dot":
            return self.visualize_workflow(workflow_name)
        else:
            raise ValueError(f"Unsupported format: {format}")