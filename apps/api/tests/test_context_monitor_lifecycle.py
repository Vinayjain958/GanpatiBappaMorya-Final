from __future__ import annotations

import asyncio

import pytest

from src.adapters.events import SeedEventAdapter
from src.adapters.weather import MockWeatherAdapter
from src.core.config import get_settings
from src.services.context_monitor import ContextMonitor


@pytest.mark.parametrize("start_twice", [False, True])
def test_monitor_starts_once_and_stops_cleanly(session_factory, monkeypatch, start_twice: bool) -> None:
    async def run() -> None:
        monitor = ContextMonitor(
            settings=get_settings(),
            session_factory=session_factory,
            weather_adapter=MockWeatherAdapter(),
            event_adapter=SeedEventAdapter(),
        )
        started = asyncio.Event()
        cancelled = asyncio.Event()

        async def wait_for_stop() -> None:
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        monkeypatch.setattr(monitor, "_run_loop", wait_for_stop)
        monitor.start()
        first_task = monitor._task
        if start_twice:
            monitor.start()
            assert monitor._task is first_task
        await asyncio.wait_for(started.wait(), timeout=1)
        await monitor.stop()

        assert cancelled.is_set()
        assert monitor._task is None
        assert monitor._started is False

    asyncio.run(run())


def test_app_lifespan_starts_live_monitor_once_and_stops_it(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    import src.core.app as app_module
    import src.services.context_monitor as monitor_module

    settings = get_settings().model_copy(update={"openweather_api_key": "test-key"})

    class FakeMonitor:
        started = 0
        stopped = 0

        def start(self) -> None:
            self.started += 1

        async def stop(self) -> None:
            self.stopped += 1

    fake_monitor = FakeMonitor()
    monkeypatch.setattr(app_module, "get_settings", lambda: settings)
    monkeypatch.setattr(app_module, "validate_startup", lambda _settings: None)
    monkeypatch.setattr(monitor_module, "get_context_monitor", lambda **_kwargs: fake_monitor)

    with TestClient(app_module.create_app()) as client:
        assert client.app.state.context_monitor is fake_monitor
        assert fake_monitor.started == 1
        assert fake_monitor.stopped == 0

    assert fake_monitor.started == 1
    assert fake_monitor.stopped == 1
