#!/usr/bin/env python3
"""Series Dashboard TUI — visualize patch series tracking data."""

import sys
from pathlib import Path

# Make lib/ importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import project as _proj
from lib import state as _state

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static

STATE_FILE = _proj.series_state_path()

# Lifecycle phases in order
LIFECYCLE = ["翻译", "检查", "补丁", "自审", "内审", "上游", "合并"]

# Map phase field values to lifecycle index
PHASE_INDEX = {
    "internal_review": 4,
    "upstream": 5,
    "merged": 6,
}

# Patch status icons
STATUS_ICON = {
    "approved": "✓",
    "changes_requested": "✗",
    "no_feedback": "…",
}


def load_state() -> dict:
    """Load series-state.json, return empty structure on failure."""
    return _state.load_series_state(STATE_FILE)


def build_lifecycle_bar(phase: str) -> str:
    """Build a lifecycle progress string with the current phase highlighted."""
    idx = PHASE_INDEX.get(phase, 0)
    parts = []
    for i, name in enumerate(LIFECYCLE):
        if i == idx:
            parts.append(f"[bold reverse] {name} [/]")
        elif i < idx:
            parts.append(f"[dim]{name}[/]")
        else:
            parts.append(name)
    return " → ".join(parts)


class SeriesListView(ListView):
    """Left panel: list of series."""

    DEFAULT_CSS = """
    SeriesListView {
        width: 30;
        min-width: 24;
        border: solid $accent;
    }
    """


class DetailPanel(Static):
    """Right panel: series detail view."""

    DEFAULT_CSS = """
    DetailPanel {
        border: solid $accent;
    }
    """


class LifecycleBar(Static):
    """Bottom bar: lifecycle progress."""

    DEFAULT_CSS = """
    LifecycleBar {
        height: 3;
        border: solid $accent;
        content-align: center middle;
    }
    """


class SeriesDashboard(App):
    """Textual TUI for patch series tracking."""

    TITLE = "Series Dashboard"

    CSS = """
    Screen {
        layout: vertical;
    }
    #main {
        height: 1fr;
    }
    #detail-scroll {
        width: 1fr;
    }
    #footer-hint {
        height: 1;
        dock: bottom;
        text-align: center;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
    ]

    selected_id: reactive[str] = reactive("")

    def __init__(self) -> None:
        super().__init__()
        self.state: dict = {}
        self.series_ids: list[str] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            yield SeriesListView(id="series-list")
            with Vertical(id="detail-scroll"):
                yield DetailPanel(id="detail", expand=True)
        yield LifecycleBar(id="lifecycle")
        yield Label("[r] Refresh  [q] Quit", id="footer-hint")

    def on_mount(self) -> None:
        self._load_data()

    def _load_data(self) -> None:
        """Load state and populate the series list."""
        self.state = load_state()
        series = self.state.get("series", {})
        self.series_ids = list(series.keys())

        lv = self.query_one("#series-list", SeriesListView)
        lv.clear()
        for sid in self.series_ids:
            s = series[sid]
            phase = s.get("phase", "?")
            # Truncate for display
            display = f"{sid[:16]:<16s} {phase[:8]}"
            lv.append(ListItem(Label(display), name=sid))

        # Auto-select first
        if self.series_ids:
            lv.index = 0
            self.selected_id = self.series_ids[0]
        else:
            self.selected_id = ""
            self._show_empty()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        if idx is not None and 0 <= idx < len(self.series_ids):
            self.selected_id = self.series_ids[idx]

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        idx = event.list_view.index
        if idx is not None and 0 <= idx < len(self.series_ids):
            self.selected_id = self.series_ids[idx]

    def watch_selected_id(self, value: str) -> None:
        if value:
            self._update_detail(value)
            self._update_lifecycle(value)

    def _show_empty(self) -> None:
        detail = self.query_one("#detail", DetailPanel)
        detail.update("No series found.\nCheck data/series-state.json")
        lc = self.query_one("#lifecycle", LifecycleBar)
        lc.update("")

    def _update_detail(self, sid: str) -> None:
        """Render detail panel for the given series."""
        series = self.state.get("series", {}).get(sid)
        if not series:
            self.query_one("#detail", DetailPanel).update("Series not found.")
            return

        lines: list[str] = []

        # --- Basic info ---
        lines.append(f"[bold]Subject:[/] {series.get('subject', '?')}")
        lines.append(f"[bold]Phase:[/]   {series.get('phase', '?')}")

        phase_key = series.get("phase", "")
        phases = series.get("phases", {})
        phase_data = phases.get(phase_key, {})
        lines.append(f"[bold]Status:[/]  {phase_data.get('status', '?')}")
        lines.append(f"[bold]Files:[/]   {len(series.get('files', []))}")

        commits = series.get("commits", [])
        if commits:
            lines.append(
                f"[bold]Commits:[/] {commits[0][:11]}"
                + (f" … +{len(commits)-1}" if len(commits) > 1 else "")
            )
        lines.append("")

        # --- Patches table ---
        rounds = phase_data.get("rounds", [])
        if rounds:
            latest = rounds[-1]
            version = latest.get("version", "?")
            sent_at = latest.get("sent_at", "?")
            lines.append(
                f"[bold underline]Patches (v{version}, {sent_at})[/]"
            )

            per_patch = latest.get("per_patch", {})
            for num in sorted(per_patch.keys(), key=lambda x: int(x)):
                p = per_patch[num]
                icon = STATUS_ICON.get(p.get("status", ""), "?")
                fname = p.get("file", "?")
                # Truncate long filenames
                if len(fname) > 30:
                    fname = "…" + fname[-29:]
                rb = p.get("reviewed_by", [])
                rb_str = f"  [dim]Rb: {', '.join(rb)}[/]" if rb else ""
                lines.append(f"  {icon} {num}: {fname}{rb_str}")

            lines.append("")

        # --- Action items ---
        action_items: list[str] = []
        if rounds:
            latest = rounds[-1]
            for num in sorted(
                latest.get("per_patch", {}).keys(), key=lambda x: int(x)
            ):
                p = latest["per_patch"][num]
                for item in p.get("action_items", []):
                    action_items.append(item)

        if action_items:
            lines.append("[bold underline]Action Items[/]")
            for item in action_items:
                lines.append(f"  • {item}")
            lines.append("")

        # --- Round history ---
        all_rounds = []
        for pk in ("internal_review", "upstream"):
            pd = phases.get(pk, {})
            for rd in pd.get("rounds", []):
                all_rounds.append((pk, rd))

        if len(all_rounds) > 1:
            lines.append("[bold underline]History[/]")
            for pk, rd in all_rounds:
                v = rd.get("version", "?")
                d = rd.get("sent_at", "?")
                lines.append(f"  {pk} v{v} — {d}")

        detail = self.query_one("#detail", DetailPanel)
        detail.update("\n".join(lines))

    def _update_lifecycle(self, sid: str) -> None:
        """Update the lifecycle bar for the given series."""
        series = self.state.get("series", {}).get(sid)
        if not series:
            return
        phase = series.get("phase", "")
        lc = self.query_one("#lifecycle", LifecycleBar)
        lc.update(build_lifecycle_bar(phase))

    def action_refresh(self) -> None:
        """Reload data from disk."""
        old_id = self.selected_id
        self._load_data()
        # Restore selection if still present
        if old_id in self.series_ids:
            idx = self.series_ids.index(old_id)
            lv = self.query_one("#series-list", SeriesListView)
            lv.index = idx
            self.selected_id = old_id
        self.notify("Refreshed")


def main() -> None:
    if not STATE_FILE.exists():
        print(f"Error: {STATE_FILE} not found.", file=sys.stderr)
        print("Run /setup first to initialize the environment.", file=sys.stderr)
        sys.exit(1)

    app = SeriesDashboard()
    app.run()


if __name__ == "__main__":
    main()
