"""
Event system for ghops automation.

Provides event-driven automation for repositories:
- Detect events (git tags, releases, milestones)
- Dispatch to handlers
- Execute actions (post to social media, publish packages)

Events are recorded in the analytics database for tracking.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import uuid

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """
    Represents an event that occurred in a repository.

    Events can be:
    - git_tag: New git tag created
    - release_published: GitHub release published
    - milestone_stars: Repository reached star milestone
    """

    id: str
    type: str  # Event type (git_tag, release_published, etc.)
    repo_path: str  # Absolute path to repository
    timestamp: datetime
    context: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Ensure timestamp is datetime."""
        if isinstance(self.timestamp, str):
            self.timestamp = datetime.fromisoformat(self.timestamp)

    @classmethod
    def create(cls, event_type: str, repo_path: str, **context) -> 'Event':
        """
        Create a new event with auto-generated ID.

        Args:
            event_type: Type of event
            repo_path: Repository path
            **context: Event context data

        Returns:
            Event instance
        """
        return cls(
            id=f"{event_type}_{uuid.uuid4().hex[:8]}",
            type=event_type,
            repo_path=repo_path,
            timestamp=datetime.now(),
            context=context
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'id': self.id,
            'type': self.type,
            'repo_path': self.repo_path,
            'timestamp': self.timestamp.isoformat(),
            'context': self.context
        }


class EventHandler(ABC):
    """
    Abstract base class for event handlers.

    Event handlers process events and perform actions.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize handler with configuration.

        Args:
            config: Handler configuration from config file
        """
        self.config = config
        self.enabled = config.get('enabled', True)

    @abstractmethod
    def should_handle(self, event: Event) -> bool:
        """
        Determine if this handler should process the event.

        Args:
            event: Event to check

        Returns:
            True if handler should process this event
        """
        pass

    @abstractmethod
    def handle(self, event: Event) -> List[Dict[str, Any]]:
        """
        Process the event and perform actions.

        Args:
            event: Event to process

        Returns:
            List of action results
        """
        pass

    def _check_conditions(self, event: Event, conditions: Dict[str, Any]) -> bool:
        """
        Check if event matches configured conditions.

        Args:
            event: Event to check
            conditions: Conditions from config

        Returns:
            True if all conditions match
        """
        # Check tag pattern for git_tag events
        if 'tag_pattern' in conditions and event.type == 'git_tag':
            import fnmatch
            tag = event.context.get('tag', '')
            pattern = conditions['tag_pattern']
            if not fnmatch.fnmatch(tag, pattern):
                return False

        # Check branches
        if 'branches' in conditions:
            branch = event.context.get('branch', '')
            if branch not in conditions['branches']:
                return False

        # Check project types
        if 'project_types' in conditions:
            project_type = event.context.get('project_type', '')
            if project_type not in conditions['project_types']:
                return False

        return True


class EventDispatcher:
    """
    Dispatches events to registered handlers.

    The dispatcher maintains a list of event handlers and routes
    events to appropriate handlers based on their should_handle() method.
    """

    def __init__(self):
        """Initialize event dispatcher."""
        self.handlers: List[EventHandler] = []

    def register(self, handler: EventHandler):
        """
        Register an event handler.

        Args:
            handler: EventHandler instance to register
        """
        self.handlers.append(handler)
        logger.info(f"Registered event handler: {handler.__class__.__name__}")

    def dispatch(self, event: Event) -> List[Dict[str, Any]]:
        """
        Dispatch an event to all matching handlers.

        Args:
            event: Event to dispatch

        Returns:
            List of all action results from handlers
        """
        logger.info(f"Dispatching event: {event.type} for {event.repo_path}")

        all_results = []

        for handler in self.handlers:
            if not handler.enabled:
                logger.debug(f"Handler {handler.__class__.__name__} is disabled, skipping")
                continue

            try:
                if handler.should_handle(event):
                    logger.info(f"Handler {handler.__class__.__name__} processing event {event.id}")
                    results = handler.handle(event)
                    all_results.extend(results)
                else:
                    logger.debug(f"Handler {handler.__class__.__name__} skipped event {event.id}")
            except Exception as e:
                logger.error(f"Handler {handler.__class__.__name__} failed: {e}", exc_info=True)
                all_results.append({
                    'action': handler.__class__.__name__,
                    'status': 'failed',
                    'error': str(e)
                })

        logger.info(f"Event {event.id} dispatched to {len(all_results)} actions")
        return all_results

    def dispatch_and_record(self, event: Event) -> List[Dict[str, Any]]:
        """
        Dispatch event and record it in analytics database.

        Args:
            event: Event to dispatch

        Returns:
            List of action results
        """
        from .analytics_store import get_analytics_store

        store = get_analytics_store()

        # Record event
        store.record_event(
            event_id=event.id,
            event_type=event.type,
            repo_path=event.repo_path,
            context=event.context,
            status='processing'
        )

        # Dispatch to handlers
        results = self.dispatch(event)

        # Record actions
        for result in results:
            store.record_event_action(
                event_id=event.id,
                action_type=result.get('action', 'unknown'),
                platform=result.get('platform'),
                status=result.get('status', 'unknown'),
                result=result
            )

        # Update event status
        if all(r.get('status') == 'success' for r in results):
            status = 'completed'
        elif any(r.get('status') == 'failed' for r in results):
            status = 'failed'
        else:
            status = 'completed'

        store.update_event_status(event.id, status)

        return results


def load_handlers_from_config(config: Dict[str, Any]) -> List[EventHandler]:
    """
    Load event handlers from configuration.

    Args:
        config: Full configuration dict

    Returns:
        List of configured EventHandler instances
    """
    from .event_handlers import (
        SocialMediaPostHandler,
        PublishPackageHandler
    )

    handlers = []
    events_config = config.get('events', {})

    if not events_config.get('enabled', True):
        logger.info("Event system is disabled in config")
        return handlers

    handler_configs = events_config.get('handlers', [])

    for handler_config in handler_configs:
        handler_type = handler_config.get('type')

        if handler_type == 'social_media_post':
            handlers.append(SocialMediaPostHandler(handler_config))
        elif handler_type == 'publish_package':
            handlers.append(PublishPackageHandler(handler_config))
        else:
            logger.warning(f"Unknown handler type: {handler_type}")

    logger.info(f"Loaded {len(handlers)} event handlers from config")
    return handlers


def create_dispatcher_from_config(config: Dict[str, Any]) -> EventDispatcher:
    """
    Create and configure an event dispatcher from config.

    Args:
        config: Full configuration dict

    Returns:
        Configured EventDispatcher instance
    """
    dispatcher = EventDispatcher()
    handlers = load_handlers_from_config(config)

    for handler in handlers:
        dispatcher.register(handler)

    return dispatcher
