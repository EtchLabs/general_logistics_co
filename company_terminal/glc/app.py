from __future__ import annotations

from collections import deque
from datetime import datetime, timezone

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Footer, Header, RichLog, Select, Static, TabbedContent, TabPane

from glc.collector import DataCollector, Snapshot
from glc.config import get_settings
from glc.logs import DockerLogTailer
from glc.registry import LOG_SERVICES
from glc.views import (
    render_finance,
    render_inventory,
    render_logistics,
    render_notifications,
    render_orders,
    render_overview,
    render_services,
    render_status_bar,
    render_supply_chain,
)


class GLCTerminalApp(App):
    """Fullscreen Rich-based operations terminal for General Logistics Co."""

    CSS = """
    Screen {
        background: #0a0e14;
    }

    TabbedContent {
        height: 1fr;
        padding: 0 1;
    }

    TabPane {
        height: 1fr;
    }

    VerticalScroll {
        height: 1fr;
        scrollbar-gutter: stable;
    }

    #status-bar {
        dock: bottom;
        height: 1;
        background: #101820;
        color: #8aa0b3;
        padding: 0 1;
    }

    RichLog {
        height: 1fr;
        border: solid #2a3f5f;
        background: #06080c;
        padding: 0 1;
    }

    Select {
        width: 1fr;
        max-width: 40;
        margin: 0 0 1 0;
    }

    Static.view-pane {
        width: 1fr;
        height: auto;
        min-height: 100%;
    }

    Header {
        background: #0d47a1;
    }

    Footer {
        background: #101820;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh_data", "Refresh", show=True),
        Binding("1", "show_tab('overview')", "Overview", show=False),
        Binding("2", "show_tab('services')", "Services", show=False),
        Binding("3", "show_tab('orders')", "Orders", show=False),
        Binding("4", "show_tab('inventory')", "Inventory", show=False),
        Binding("5", "show_tab('finance')", "Finance", show=False),
        Binding("6", "show_tab('supply')", "Supply", show=False),
        Binding("7", "show_tab('logistics')", "Logistics", show=False),
        Binding("l", "show_tab('logs')", "Logs", show=True),
        Binding("left", "prev_log_service", "Prev log", show=False),
        Binding("right", "next_log_service", "Next log", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(initial="overview"):
            with TabPane("Overview", id="overview"):
                with VerticalScroll():
                    yield Static(id="view-overview", classes="view-pane")
            with TabPane("Services", id="services"):
                with VerticalScroll():
                    yield Static(id="view-services", classes="view-pane")
            with TabPane("Orders & Events", id="orders"):
                with VerticalScroll():
                    yield Static(id="view-orders", classes="view-pane")
                    yield Static(id="view-notifications", classes="view-pane")
            with TabPane("Inventory", id="inventory"):
                with VerticalScroll():
                    yield Static(id="view-inventory", classes="view-pane")
            with TabPane("Finance", id="finance"):
                with VerticalScroll():
                    yield Static(id="view-finance", classes="view-pane")
            with TabPane("Supply Chain", id="supply"):
                with VerticalScroll():
                    yield Static(id="view-supply", classes="view-pane")
            with TabPane("Logistics", id="logistics"):
                with VerticalScroll():
                    yield Static(id="view-logistics", classes="view-pane")
            with TabPane("Live Logs", id="logs"):
                with Vertical():
                    yield Select(
                        [(name, name) for name in LOG_SERVICES],
                        value="order_service",
                        id="log-select",
                        prompt="Service logs",
                    )
                    yield RichLog(id="log-view", highlight=True, markup=True, wrap=True)
        yield Static(id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        settings = get_settings()
        self.collector = DataCollector(settings)
        self.log_tailer = DockerLogTailer(settings.compose_file, settings.compose_project)
        self.snapshot = Snapshot()
        self.order_history: deque[float] = deque(maxlen=120)
        self._last_order_count = 0
        self._last_rate_ts = datetime.now(timezone.utc)
        self._order_rate_per_min = 0.0
        self._log_service = "order_service"
        self._log_index = LOG_SERVICES.index("order_service")

        self.title = "General Logistics Co"
        self.sub_title = "Operations Terminal"
        self.set_interval(settings.refresh_seconds, self.refresh_data)
        self.run_worker(self._fetch_snapshot, thread=True, group="refresh", exclusive=True)
        self._start_log_tail(self._log_service)

    def on_unmount(self) -> None:
        self.log_tailer.stop()

    @on(Select.Changed, "#log-select")
    def on_log_select(self, event: Select.Changed) -> None:
        if event.value and event.value is not Select.BLANK:
            self._log_service = str(event.value)
            self._log_index = LOG_SERVICES.index(self._log_service)
            self._start_log_tail(self._log_service)

    def _start_log_tail(self, service: str) -> None:
        log_view = self.query_one("#log-view", RichLog)
        log_view.clear()
        log_view.write(f"[bold cyan]Tailing docker compose logs: {service}[/]")
        self.log_tailer.start(service, lambda line: self.call_from_thread(self._append_log, line))

    def _append_log(self, line: str) -> None:
        log_view = self.query_one("#log-view", RichLog)
        style = "white"
        lower = line.lower()
        if "error" in lower or "failed" in lower:
            style = "bold red"
        elif "warning" in lower or "warn" in lower:
            style = "yellow"
        elif "info" in lower:
            style = "cyan"
        log_view.write(line, shrink=False)

    def _update_rate(self, count: int) -> None:
        now = datetime.now(timezone.utc)
        elapsed = (now - self._last_rate_ts).total_seconds()
        if elapsed >= 1.0:
            delta = max(count - self._last_order_count, 0)
            self._order_rate_per_min = round(delta / elapsed * 60, 2)
            self._last_order_count = count
            self._last_rate_ts = now
        self.order_history.append(float(count))

    def _render_all(self, snap: Snapshot) -> None:
        self.query_one("#view-overview", Static).update(
            render_overview(snap, self.order_history, self._order_rate_per_min)
        )
        self.query_one("#view-services", Static).update(render_services(snap))
        self.query_one("#view-orders", Static).update(render_orders(snap))
        self.query_one("#view-notifications", Static).update(render_notifications(snap))
        self.query_one("#view-inventory", Static).update(render_inventory(snap))
        self.query_one("#view-finance", Static).update(render_finance(snap))
        self.query_one("#view-supply", Static).update(render_supply_chain(snap))
        self.query_one("#view-logistics", Static).update(render_logistics(snap))
        self.query_one("#status-bar", Static).update(
            render_status_bar(snap, self._order_rate_per_min, self._log_service)
        )

    def refresh_data(self) -> None:
        self.run_worker(self._fetch_snapshot, thread=True, group="refresh", exclusive=True)

    def _fetch_snapshot(self) -> None:
        snap = self.collector.collect()
        self.call_from_thread(self._after_refresh, snap)

    def _after_refresh(self, snap: Snapshot) -> None:
        self.snapshot = snap
        self._update_rate(snap.order_count)
        self._render_all(snap)

    def action_refresh_data(self) -> None:
        self.refresh_data()

    def action_show_tab(self, tab_id: str) -> None:
        tabs = self.query_one(TabbedContent)
        tabs.active = tab_id

    def action_prev_log_service(self) -> None:
        self._log_index = (self._log_index - 1) % len(LOG_SERVICES)
        self._log_service = LOG_SERVICES[self._log_index]
        select = self.query_one("#log-select", Select)
        select.value = self._log_service
        self._start_log_tail(self._log_service)

    def action_next_log_service(self) -> None:
        self._log_index = (self._log_index + 1) % len(LOG_SERVICES)
        self._log_service = LOG_SERVICES[self._log_index]
        select = self.query_one("#log-select", Select)
        select.value = self._log_service
        self._start_log_tail(self._log_service)


def run() -> None:
    GLCTerminalApp().run()
