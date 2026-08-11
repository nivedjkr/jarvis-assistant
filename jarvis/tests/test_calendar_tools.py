import pytest
import asyncio
import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))

from jarvis.tools import ToolRegistry
from jarvis.calendar_service import CalendarService


def test_calendar_tools_registered():
    registry = ToolRegistry()
    assert 'list_calendar_events' in registry.tools
    assert 'create_calendar_event' in registry.tools
    assert 'search_calendar_events' in registry.tools
    assert 'update_calendar_event' in registry.tools
    assert 'delete_calendar_event' in registry.tools


def test_delete_calendar_event_confirmation_gate():
    mock_cal_service = MagicMock(spec=CalendarService)
    mock_cal_service.delete_event.return_value = True

    registry = ToolRegistry(calendar_service=mock_cal_service)
    loop = asyncio.new_event_loop()

    # 1. Unconfirmed call must return PENDING_CONFIRMATION and NOT delete event
    res_unconfirmed = loop.run_until_complete(
        registry.execute('delete_calendar_event', {
            'event_id': 'evt12345'
        })
    )

    assert "PENDING_CONFIRMATION" in res_unconfirmed
    assert "evt12345" in res_unconfirmed
    mock_cal_service.delete_event.assert_not_called()

    # 2. Confirmed call passes through to delete_event via confirm_action
    import re
    act_id = re.search(r'Action ID:\s*(act_[a-f0-9]+)', res_unconfirmed).group(1)
    res_confirmed = registry.confirm_action(act_id)

    assert "deleted successfully" in res_confirmed
    mock_cal_service.delete_event.assert_called_once_with(event_id='evt12345')

    loop.close()


def test_calendar_list_and_create_tools():
    mock_cal_service = MagicMock(spec=CalendarService)
    mock_cal_service.format_calendar_command.return_value = "=== Google Calendar (Today: 2026-08-09) ==="
    mock_cal_service.create_event.return_value = {
        "id": "evt999",
        "summary": "Team Sync",
        "start": "2026-08-09T18:00:00Z"
    }

    registry = ToolRegistry(calendar_service=mock_cal_service)
    loop = asyncio.new_event_loop()

    # List events tool call
    res_list = loop.run_until_complete(registry.execute('list_calendar_events', {'mode': 'today'}))
    assert "=== Google Calendar" in res_list
    mock_cal_service.format_calendar_command.assert_called_once_with(mode='today')

    # Create event tool call
    res_create = loop.run_until_complete(registry.execute('create_calendar_event', {
        'summary': 'Team Sync',
        'start_time': '2026-08-09T18:00:00'
    }))
    assert "Event created successfully" in res_create
    assert "Team Sync" in res_create
    mock_cal_service.create_event.assert_called_once_with(
        summary='Team Sync',
        start_time='2026-08-09T18:00:00',
        end_time=None,
        location=None,
        description=None
    )

    loop.close()


def test_calendar_search_and_update_tools():
    mock_cal_service = MagicMock(spec=CalendarService)
    mock_cal_service.format_calendar_command.return_value = "=== Search Results for 'Doctor' ==="
    mock_cal_service.update_event.return_value = {
        "id": "evt101",
        "summary": "Updated Doctor Appointment"
    }

    registry = ToolRegistry(calendar_service=mock_cal_service)
    loop = asyncio.new_event_loop()

    # Search event tool call
    res_search = loop.run_until_complete(registry.execute('search_calendar_events', {'query': 'Doctor'}))
    assert "Search Results for 'Doctor'" in res_search
    mock_cal_service.format_calendar_command.assert_called_once_with(mode='search', query='Doctor')

    # Update event tool call
    res_update = loop.run_until_complete(registry.execute('update_calendar_event', {
        'event_id': 'evt101',
        'summary': 'Updated Doctor Appointment'
    }))
    assert "Event updated successfully" in res_update
    assert "Updated Doctor Appointment" in res_update

    loop.close()


def test_check_calendar_alias_and_parameter_normalization():
    mock_cal_service = MagicMock(spec=CalendarService)
    mock_cal_service.format_calendar_command.return_value = "=== Google Calendar (Today) ==="
    mock_cal_service.create_event.return_value = {
        "id": "evt202",
        "summary": "Meeting",
        "start": "2026-08-09T14:00:00Z"
    }

    registry = ToolRegistry(calendar_service=mock_cal_service)
    loop = asyncio.new_event_loop()

    # 1. Test check_calendar tool alias
    res_alias = loop.run_until_complete(registry.execute('check_calendar', {'mode': 'today'}))
    assert "=== Google Calendar" in res_alias

    # 2. Test create_event tool name alias & parameter normalization ('title' -> 'summary', 'time' -> 'start_time')
    res_create_alias = loop.run_until_complete(registry.execute('create_event', {
        'title': 'Meeting',
        'time': '2026-08-09T14:00:00'
    }))
    assert "Event created successfully" in res_create_alias
    mock_cal_service.create_event.assert_called_with(
        summary='Meeting',
        start_time='2026-08-09T14:00:00',
        end_time=None,
        location=None,
        description=None
    )

    loop.close()
