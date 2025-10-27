"""
Tests for events.py module.

Tests the event system including:
- Event creation and serialization
- EventHandler base class behavior
- EventDispatcher routing and execution
- Configuration loading
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
from ghops.events import (
    Event,
    EventHandler,
    EventDispatcher,
    load_handlers_from_config,
    create_dispatcher_from_config
)


class TestEvent:
    """Test Event dataclass functionality."""

    def test_event_creation(self):
        """Test creating an event with all fields."""
        event = Event(
            id='test_event_123',
            type='git_tag',
            repo_path='/test/repo',
            timestamp=datetime.now(),
            context={'tag': 'v1.0.0', 'branch': 'main'}
        )

        assert event.id == 'test_event_123'
        assert event.type == 'git_tag'
        assert event.repo_path == '/test/repo'
        assert isinstance(event.timestamp, datetime)
        assert event.context['tag'] == 'v1.0.0'

    def test_event_create_factory(self):
        """Test Event.create factory method."""
        event = Event.create(
            event_type='git_tag',
            repo_path='/test/repo',
            tag='v1.0.0',
            branch='main'
        )

        assert event.type == 'git_tag'
        assert event.repo_path == '/test/repo'
        assert event.id.startswith('git_tag_')
        assert isinstance(event.timestamp, datetime)
        assert event.context['tag'] == 'v1.0.0'
        assert event.context['branch'] == 'main'

    def test_event_to_dict(self):
        """Test converting event to dictionary."""
        timestamp = datetime.now()
        event = Event(
            id='test_123',
            type='git_tag',
            repo_path='/test/repo',
            timestamp=timestamp,
            context={'tag': 'v1.0.0'}
        )

        event_dict = event.to_dict()

        assert event_dict['id'] == 'test_123'
        assert event_dict['type'] == 'git_tag'
        assert event_dict['repo_path'] == '/test/repo'
        assert event_dict['timestamp'] == timestamp.isoformat()
        assert event_dict['context']['tag'] == 'v1.0.0'

    def test_event_timestamp_string_conversion(self):
        """Test that string timestamps are converted to datetime."""
        timestamp_str = '2024-01-15T10:30:00'
        event = Event(
            id='test_123',
            type='git_tag',
            repo_path='/test/repo',
            timestamp=timestamp_str,
            context={}
        )

        assert isinstance(event.timestamp, datetime)
        assert event.timestamp.isoformat().startswith('2024-01-15T10:30:00')

    def test_event_empty_context(self):
        """Test event with empty context."""
        event = Event.create(
            event_type='git_tag',
            repo_path='/test/repo'
        )

        assert event.context == {}


class MockHandler(EventHandler):
    """Mock handler for testing."""

    def __init__(self, config):
        super().__init__(config)
        self.handled_events = []

    def should_handle(self, event: Event) -> bool:
        """Check if should handle based on event type."""
        trigger = self.config.get('trigger', 'git_tag')
        return event.type == trigger

    def handle(self, event: Event) -> list:
        """Handle event and record it."""
        self.handled_events.append(event)
        return [{
            'action': 'mock_action',
            'status': 'success',
            'event_id': event.id
        }]


class TestEventHandler:
    """Test EventHandler base class."""

    def test_handler_initialization(self):
        """Test handler initialization with config."""
        config = {'enabled': True, 'trigger': 'git_tag'}
        handler = MockHandler(config)

        assert handler.config == config
        assert handler.enabled is True

    def test_handler_default_enabled(self):
        """Test handler is enabled by default."""
        handler = MockHandler({})
        assert handler.enabled is True

    def test_handler_disabled(self):
        """Test handler can be disabled."""
        handler = MockHandler({'enabled': False})
        assert handler.enabled is False

    def test_handler_should_handle(self):
        """Test should_handle logic."""
        handler = MockHandler({'trigger': 'git_tag'})

        event1 = Event.create('git_tag', '/repo')
        event2 = Event.create('release', '/repo')

        assert handler.should_handle(event1) is True
        assert handler.should_handle(event2) is False

    def test_handler_handle(self):
        """Test handler processing an event."""
        handler = MockHandler({})
        event = Event.create('git_tag', '/repo', tag='v1.0.0')

        results = handler.handle(event)

        assert len(handler.handled_events) == 1
        assert handler.handled_events[0] == event
        assert results[0]['status'] == 'success'

    def test_check_conditions_tag_pattern(self):
        """Test _check_conditions with tag_pattern."""
        handler = MockHandler({})

        event = Event.create('git_tag', '/repo', tag='v1.0.0')
        conditions = {'tag_pattern': 'v*'}

        assert handler._check_conditions(event, conditions) is True

        # Non-matching pattern
        conditions = {'tag_pattern': 'release-*'}
        assert handler._check_conditions(event, conditions) is False

    def test_check_conditions_branches(self):
        """Test _check_conditions with branch filtering."""
        handler = MockHandler({})

        event = Event.create('git_tag', '/repo', branch='main')
        conditions = {'branches': ['main', 'master']}

        assert handler._check_conditions(event, conditions) is True

        # Non-matching branch
        conditions = {'branches': ['develop']}
        assert handler._check_conditions(event, conditions) is False

    def test_check_conditions_project_types(self):
        """Test _check_conditions with project_type filtering."""
        handler = MockHandler({})

        event = Event.create('git_tag', '/repo', project_type='python')
        conditions = {'project_types': ['python', 'javascript']}

        assert handler._check_conditions(event, conditions) is True

        # Non-matching type
        conditions = {'project_types': ['rust']}
        assert handler._check_conditions(event, conditions) is False

    def test_check_conditions_multiple(self):
        """Test _check_conditions with multiple conditions."""
        handler = MockHandler({})

        event = Event.create('git_tag', '/repo', tag='v1.0.0', branch='main')
        conditions = {
            'tag_pattern': 'v*',
            'branches': ['main']
        }

        assert handler._check_conditions(event, conditions) is True

        # One condition fails
        conditions['branches'] = ['develop']
        assert handler._check_conditions(event, conditions) is False

    def test_check_conditions_empty(self):
        """Test _check_conditions with no conditions."""
        handler = MockHandler({})
        event = Event.create('git_tag', '/repo')

        assert handler._check_conditions(event, {}) is True


class TestEventDispatcher:
    """Test EventDispatcher functionality."""

    def test_dispatcher_initialization(self):
        """Test dispatcher starts with no handlers."""
        dispatcher = EventDispatcher()
        assert dispatcher.handlers == []

    def test_register_handler(self):
        """Test registering a handler."""
        dispatcher = EventDispatcher()
        handler = MockHandler({})

        dispatcher.register(handler)

        assert len(dispatcher.handlers) == 1
        assert dispatcher.handlers[0] == handler

    def test_register_multiple_handlers(self):
        """Test registering multiple handlers."""
        dispatcher = EventDispatcher()
        handler1 = MockHandler({'trigger': 'git_tag'})
        handler2 = MockHandler({'trigger': 'release'})

        dispatcher.register(handler1)
        dispatcher.register(handler2)

        assert len(dispatcher.handlers) == 2

    def test_dispatch_to_matching_handler(self):
        """Test dispatching event to matching handler."""
        dispatcher = EventDispatcher()
        handler = MockHandler({'trigger': 'git_tag'})
        dispatcher.register(handler)

        event = Event.create('git_tag', '/repo', tag='v1.0.0')
        results = dispatcher.dispatch(event)

        assert len(results) == 1
        assert results[0]['status'] == 'success'
        assert len(handler.handled_events) == 1

    def test_dispatch_skips_non_matching_handler(self):
        """Test that non-matching handlers are skipped."""
        dispatcher = EventDispatcher()
        handler = MockHandler({'trigger': 'release'})
        dispatcher.register(handler)

        event = Event.create('git_tag', '/repo')
        results = dispatcher.dispatch(event)

        assert len(results) == 0
        assert len(handler.handled_events) == 0

    def test_dispatch_to_multiple_handlers(self):
        """Test dispatching to multiple matching handlers."""
        dispatcher = EventDispatcher()
        handler1 = MockHandler({'trigger': 'git_tag'})
        handler2 = MockHandler({'trigger': 'git_tag'})
        dispatcher.register(handler1)
        dispatcher.register(handler2)

        event = Event.create('git_tag', '/repo')
        results = dispatcher.dispatch(event)

        assert len(results) == 2
        assert len(handler1.handled_events) == 1
        assert len(handler2.handled_events) == 1

    def test_dispatch_skips_disabled_handler(self):
        """Test that disabled handlers are skipped."""
        dispatcher = EventDispatcher()
        handler = MockHandler({'enabled': False, 'trigger': 'git_tag'})
        dispatcher.register(handler)

        event = Event.create('git_tag', '/repo')
        results = dispatcher.dispatch(event)

        assert len(results) == 0
        assert len(handler.handled_events) == 0

    def test_dispatch_handles_handler_errors(self):
        """Test that handler errors are caught and returned as failed results."""
        class FailingHandler(EventHandler):
            def should_handle(self, event):
                return True

            def handle(self, event):
                raise ValueError("Handler failed!")

        dispatcher = EventDispatcher()
        handler = FailingHandler({})
        dispatcher.register(handler)

        event = Event.create('git_tag', '/repo')
        results = dispatcher.dispatch(event)

        assert len(results) == 1
        assert results[0]['status'] == 'failed'
        assert 'Handler failed!' in results[0]['error']

    @patch('ghops.analytics_store.get_analytics_store')
    def test_dispatch_and_record(self, mock_get_store):
        """Test dispatching and recording to analytics."""
        # Mock analytics store
        mock_store = MagicMock()
        mock_get_store.return_value = mock_store

        dispatcher = EventDispatcher()
        handler = MockHandler({'trigger': 'git_tag'})
        dispatcher.register(handler)

        event = Event.create('git_tag', '/repo', tag='v1.0.0')
        results = dispatcher.dispatch_and_record(event)

        # Should record event
        mock_store.record_event.assert_called_once_with(
            event_id=event.id,
            event_type='git_tag',
            repo_path='/repo',
            context=event.context,
            status='processing'
        )

        # Should record action
        mock_store.record_event_action.assert_called_once()
        action_call = mock_store.record_event_action.call_args
        assert action_call[1]['event_id'] == event.id
        assert action_call[1]['action_type'] == 'mock_action'
        assert action_call[1]['status'] == 'success'

        # Should update event status
        mock_store.update_event_status.assert_called_once_with(event.id, 'completed')

    @patch('ghops.analytics_store.get_analytics_store')
    def test_dispatch_and_record_failed_action(self, mock_get_store):
        """Test that failed actions update event status to failed."""
        mock_store = MagicMock()
        mock_get_store.return_value = mock_store

        class FailingHandler(EventHandler):
            def should_handle(self, event):
                return True

            def handle(self, event):
                raise ValueError("Action failed")

        dispatcher = EventDispatcher()
        dispatcher.register(FailingHandler({}))

        event = Event.create('git_tag', '/repo')
        dispatcher.dispatch_and_record(event)

        # Should update event status to failed
        mock_store.update_event_status.assert_called_once_with(event.id, 'failed')


class TestConfigLoading:
    """Test configuration loading for handlers."""

    def test_load_handlers_empty_config(self):
        """Test loading handlers with empty config."""
        handlers = load_handlers_from_config({})
        assert handlers == []

    def test_load_handlers_disabled(self):
        """Test that disabled event system returns no handlers."""
        config = {
            'events': {
                'enabled': False,
                'handlers': [{'type': 'social_media_post'}]
            }
        }

        handlers = load_handlers_from_config(config)
        assert handlers == []

    @patch('ghops.event_handlers.SocialMediaPostHandler')
    def test_load_social_media_handler(self, mock_handler_class):
        """Test loading social media post handler."""
        config = {
            'events': {
                'enabled': True,
                'handlers': [
                    {
                        'type': 'social_media_post',
                        'trigger': 'git_tag',
                        'enabled': True
                    }
                ]
            }
        }

        handlers = load_handlers_from_config(config)

        mock_handler_class.assert_called_once()
        assert len(handlers) == 1

    @patch('ghops.event_handlers.PublishPackageHandler')
    def test_load_publish_handler(self, mock_handler_class):
        """Test loading publish package handler."""
        config = {
            'events': {
                'enabled': True,
                'handlers': [
                    {
                        'type': 'publish_package',
                        'trigger': 'git_tag'
                    }
                ]
            }
        }

        handlers = load_handlers_from_config(config)

        mock_handler_class.assert_called_once()
        assert len(handlers) == 1

    @patch('ghops.event_handlers.SocialMediaPostHandler')
    @patch('ghops.event_handlers.PublishPackageHandler')
    def test_load_multiple_handlers(self, mock_publish, mock_social):
        """Test loading multiple handlers."""
        config = {
            'events': {
                'enabled': True,
                'handlers': [
                    {'type': 'social_media_post'},
                    {'type': 'publish_package'}
                ]
            }
        }

        handlers = load_handlers_from_config(config)

        assert len(handlers) == 2
        mock_social.assert_called_once()
        mock_publish.assert_called_once()

    def test_load_unknown_handler_type(self):
        """Test that unknown handler types are logged and skipped."""
        config = {
            'events': {
                'enabled': True,
                'handlers': [
                    {'type': 'unknown_handler_type'}
                ]
            }
        }

        handlers = load_handlers_from_config(config)

        # Unknown handlers should be skipped
        assert handlers == []

    @patch('ghops.events.load_handlers_from_config')
    def test_create_dispatcher_from_config(self, mock_load_handlers):
        """Test creating dispatcher from config."""
        mock_handler = MockHandler({})
        mock_load_handlers.return_value = [mock_handler]

        config = {'events': {'enabled': True}}
        dispatcher = create_dispatcher_from_config(config)

        assert isinstance(dispatcher, EventDispatcher)
        assert len(dispatcher.handlers) == 1
        assert dispatcher.handlers[0] == mock_handler


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
