import queue
import time
from unittest import mock
from background_job_tracker.sender import BackgroundSender
from background_job_tracker.client import Tracker


def test_sender_batching():
    event_queue = queue.Queue()
    sender = BackgroundSender("key", "http://test", event_queue, batch_size=2, flush_interval=10.0)

    with mock.patch.object(sender.session, "post") as mock_post:
        mock_post.return_value.status_code = 202

        sender.start()

        # Add 3 events
        event_queue.put({"id": 1})
        event_queue.put({"id": 2})
        event_queue.put({"id": 3})

        # Wait a bit
        time.sleep(0.1)

        # Since batch_size=2, the first two should have triggered a flush
        assert mock_post.call_count == 1

        # Stop will flush remaining
        sender.stop(timeout=1.0)
        assert mock_post.call_count == 2

        # Check payloads
        calls = mock_post.call_args_list
        assert len(calls[0].kwargs["json"]["executions"]) == 2
        assert len(calls[1].kwargs["json"]["executions"]) == 1


def test_client_overflow():
    Tracker._instance = None
    client = Tracker(api_key="key", base_url="http://test", max_queue_size=2)
    # Patch sender so it doesn't drain
    client.sender.stop()

    # Fill queue
    client.enqueue_event({"id": 1})
    client.enqueue_event({"id": 2})

    # Overflow
    client.enqueue_event({"id": 3})  # Should not block or raise error

    assert client.event_queue.qsize() == 2


def test_sender_sync_tasks():
    event_queue = queue.Queue()
    sender = BackgroundSender("key", "http://test", event_queue, batch_size=10, flush_interval=10.0)

    with mock.patch.object(sender.session, "post") as mock_post:
        mock_post.return_value.status_code = 200
        sender.start()

        event_queue.put({"_type": "sync_tasks", "tasks": ["task1"]})
        time.sleep(0.1)
        sender.stop()

        mock_post.assert_called_once()
        assert mock_post.call_args.kwargs["json"]["tasks"] == ["task1"]
        assert "/api/jobs/sync/" in mock_post.call_args.args[0]


def test_periodic_discovery():
    event_queue = queue.Queue()
    provider_mock = mock.Mock(return_value=["periodic_task"])

    sender = BackgroundSender(
        "key",
        "http://test",
        event_queue,
        flush_interval=0.1,
        task_discovery_interval=0.1,
        task_provider=provider_mock,
    )

    with mock.patch.object(sender.session, "post") as mock_post:
        mock_post.return_value.status_code = 200
        sender.start()

        # Wait for periodic discovery to trigger
        time.sleep(0.3)
        sender.stop()

        assert provider_mock.called
        assert mock_post.call_count >= 1
        assert mock_post.call_args.kwargs["json"]["tasks"] == ["periodic_task"]


def test_transient_batch_recovery():
    event_queue = queue.Queue()
    sender = BackgroundSender("key", "http://test", event_queue, batch_size=1)

    # Mock time.sleep to bypass exponential backoff delay in test
    with (
        mock.patch.object(sender.session, "post") as mock_post,
        mock.patch("background_job_tracker.sender.time.sleep"),
    ):
        # 1st call: 500 (transient failure), 2nd call: 200 (success)
        mock_resp_500 = mock.Mock()
        mock_resp_500.status_code = 500
        mock_resp_200 = mock.Mock()
        mock_resp_200.status_code = 200

        mock_post.side_effect = [mock_resp_500, mock_resp_200]

        sender.start()
        event_queue.put({"id": 1, "_type": "event"})

        time.sleep(0.1)
        sender.stop()

        assert mock_post.call_count == 2
