import pytest
import asyncio
import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))

from jarvis.tools import ToolRegistry
from jarvis.email_service import EmailService

def test_email_tools_registered():
    registry = ToolRegistry()
    assert 'check_email' in registry.tools
    assert 'read_email' in registry.tools
    assert 'email_summary' in registry.tools
    assert 'send_email' in registry.tools
    assert 'list_sent_emails' in registry.tools
    assert 'delete_sent_email' in registry.tools

def test_send_email_confirmation_gate():
    mock_email_service = MagicMock(spec=EmailService)
    mock_email_service.send_email.return_value = "Email sent successfully."
    
    registry = ToolRegistry(email_service=mock_email_service)
    
    loop = asyncio.new_event_loop()
    
    # 1. Unconfirmed call must return CONFIRMATION REQUIRED and NOT call send_email
    res_unconfirmed = loop.run_until_complete(
        registry.execute('send_email', {
            'to': 'user@example.com',
            'subject': 'Test Subject',
            'body': 'Test Body',
            'confirmed': False
        })
    )
    
    # 1. Unconfirmed call must return PENDING_CONFIRMATION and NOT call send_email
    res_unconfirmed = loop.run_until_complete(
        registry.execute('send_email', {
            'to': 'user@example.com',
            'subject': 'Test Subject',
            'body': 'Test Body'
        })
    )

    assert "PENDING_CONFIRMATION" in res_unconfirmed
    assert "user@example.com" in res_unconfirmed
    mock_email_service.send_email.assert_not_called()
    
    # Extract action ID and confirm
    import re
    act_id = re.search(r'Action ID:\s*(act_[a-f0-9]+)', res_unconfirmed).group(1)
    res_confirmed = registry.confirm_action(act_id)
    
    assert res_confirmed == "Email sent successfully."
    mock_email_service.send_email.assert_called_once_with(
        to='user@example.com',
        subject='Test Subject',
        body='Test Body'
    )
    
    loop.close()

def test_delete_sent_email_confirmation_gate():
    mock_email_service = MagicMock(spec=EmailService)
    mock_email_service.delete_sent_email_by_index.return_value = "Successfully deleted sent email #1."
    
    registry = ToolRegistry(email_service=mock_email_service)
    loop = asyncio.new_event_loop()
    
    # 1. Unconfirmed delete must require confirmation
    res_unconfirmed = loop.run_until_complete(
        registry.execute('delete_sent_email', {
            'index': 1
        })
    )
    assert "PENDING_CONFIRMATION" in res_unconfirmed
    mock_email_service.delete_sent_email_by_index.assert_not_called()
    
    # 2. Confirmed delete executes
    import re
    act_id = re.search(r'Action ID:\s*(act_[a-f0-9]+)', res_unconfirmed).group(1)
    res_confirmed = registry.confirm_action(act_id)

    assert res_confirmed == "Successfully deleted sent email #1."
    mock_email_service.delete_sent_email_by_index.assert_called_once_with(index_1_based=1)
    
    loop.close()

def test_read_and_sent_email_tools():
    mock_email_service = MagicMock(spec=EmailService)
    mock_email_service.format_unread_list.return_value = "=== Recent Unread Emails ==="
    mock_email_service.format_sent_list.return_value = "=== Recent Sent Emails ==="
    mock_email_service.read_email_body_by_index.return_value = "=== Reading Email #1 ==="
    mock_email_service.generate_email_summary_briefing.return_value = "Found 1 unread email"
    
    registry = ToolRegistry(email_service=mock_email_service)
    loop = asyncio.new_event_loop()
    
    res_check = loop.run_until_complete(registry.execute('check_email', {'limit': 5}))
    assert "=== Recent Unread Emails ===" in res_check
    mock_email_service.format_unread_list.assert_called_once_with(limit=5)
    
    res_sent = loop.run_until_complete(registry.execute('list_sent_emails', {'limit': 5}))
    assert "=== Recent Sent Emails ===" in res_sent
    mock_email_service.format_sent_list.assert_called_once_with(limit=5)
    
    res_read = loop.run_until_complete(registry.execute('read_email', {'index': 1}))
    assert "=== Reading Email #1 ===" in res_read
    mock_email_service.read_email_body_by_index.assert_called_once_with(index_1_based=1)
    
    res_summary = loop.run_until_complete(registry.execute('email_summary', {}))
    assert "Found 1 unread email" in res_summary
    mock_email_service.generate_email_summary_briefing.assert_called_once()
    
    loop.close()
