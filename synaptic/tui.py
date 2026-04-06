"""
tui.py — Interactive TUI for synaptic using Textual.

Design: ego-graph explorer
  ┌─────────────────────────────────────────────────────────────────┐
  │  ⬡ synaptic  project · 237 nodes · 643 edges                   │
  ├─────────────┬───────────────────────────────────────────────────┤
  │             │  ← imported by          imports →                 │
  │  All nodes  │                                                   │
  │  (sidebar)  │   predecessor1 ──╮                               │
  │             │   predecessor2 ──┤──▶ [ SELECTED NODE ] ──┬──▶  s1│
  │  ● internal │   predecessor3 ──╯                        ├──▶  s2│
  │  ◈ AWS                                                  ╰──▶  s3│
  │  ◈ HTTP     │                                                   │
  ├─────────────┴───────────────────────────────────────────────────┤
  │  kind · in: N · out: N · ⚠ circular                             │
  └─────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import networkx as nx
from rich.align import Align
from rich.box import ROUNDED, SIMPLE, MINIMAL
from rich.columns import Columns
from rich.console import Group
from rich.padding import Padding
from rich.panel import Panel
from rich.rule import Rule
from rich.style import Style
from rich.table import Table
from rich.text import Text
from textual import events, on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Footer, Input, Label, Static

# ─── Palette ─────────────────────────────────────────────────────────────────

KIND_COLOR: dict[str, str] = {
    "internal": "#4F8EF7",
    "external": "#888899",
    "stdlib":   "#444466",
    "AWS":      "#FF9900",
    "GCP":      "#4285F4",
    "Azure":    "#0089D6",
    "http":     "#E84393",
}

KIND_ICON: dict[str, str] = {
    "internal": "◉",
    "external": "○",
    "stdlib":   "·",
    "AWS":      "◈",
    "GCP":      "◈",
    "Azure":    "◈",
    "http":     "◈",
}

KIND_LABEL: dict[str, str] = {
    "internal": "Internal",
    "AWS":      "AWS SDK",
    "GCP":      "GCP SDK",
    "Azure":    "Azure SDK",
    "http":     "HTTP client",
    "external": "External pkg",
    "stdlib":   "Stdlib",
}


# ─── Messages ────────────────────────────────────────────────────────────────

class NodeSelected(Message):
    def __init__(self, node: str) -> None:
        super().__init__()
        self.node = node


# ─── Sidebar ─────────────────────────────────────────────────────────────────

class NodeSidebar(Widget, can_focus=False):
    DEFAULT_CSS = """
    NodeSidebar {
        width: 28;
        background: #08081a;
        border-right: solid #1e1e3a;
        overflow-y: scroll;
    }
    NodeSidebar Input {
        background: #111128;
        border: solid #2a2a4a;
        color: #a0a0cc;
        margin: 0 1;
        height: 3;
    }
    NodeSidebar Input:focus {
        border: solid #4F8EF7;
    }
    NodeSidebar .node-row {
        padding: 0 2;
        height: 1;
        color: #888899;
    }
    NodeSidebar .node-row:hover {
        background: #14143a;
        color: white;
    }
    NodeSidebar .node-row.--selected {
        background: #0d2060;
        color: white;
    }
    NodeSidebar .section-header {
        padding: 0 1;
        height: 1;
        color: #444466;
        background: #0a0a1e;
    }
    """

    filter_text: reactive[str] = reactive("")
    selected_node: reactive[str | None] = reactive(None)

    def __init__(self, graph: nx.DiGraph, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.graph = graph
        self._all_nodes: list[tuple[str, dict[str, Any]]] = sorted(
            graph.nodes(data=True), key=lambda x: (x[1].get("kind", "z"), x[0])
        )

    def compose(self) -> ComposeResult:
        yield Input(placeholder="🔍 filter nodes…", id="search-input")
        yield Label(
            f" {self.graph.number_of_nodes()} nodes · {self.graph.number_of_edges()} edges",
            classes="section-header",
        )
        self._render_list()

    def _render_list(self) -> None:
        """Mount node rows, grouped by kind."""
        # Remove existing rows
        for w in self.query(".node-row,.section-header.kind-header"):
            w.remove()

        q = self.filter_text.lower()
        current_kind: str | None = None

        for node, data in self._all_nodes:
            label = data.get("label", node.split(".")[-1])
            if q and q not in node.lower() and q not in label.lower():
                continue

            kind = data.get("kind", "internal")
            if kind != current_kind:
                current_kind = kind
                color = KIND_COLOR.get(kind, "#888")
                icon = KIND_ICON.get(kind, "·")
                kind_lbl = KIND_LABEL.get(kind, kind)
                self.mount(
                    Label(
                        Text.assemble((f" {icon} {kind_lbl}", f"bold {color}")),
                        classes="section-header kind-header",
                    )
                )

            color = KIND_COLOR.get(kind, "#888")
            icon = KIND_ICON.get(kind, "·")
            is_sel = node == self.selected_node

            row = Static(
                Text.assemble(
                    (f"  {icon} ", f"{'bold ' if is_sel else ''}{color}"),
                    (label[:20], f"{'bold white' if is_sel else color}"),
                ),
                classes=f"node-row{'  --selected' if is_sel else ''}",
            )
            row._node_id = node  # type: ignore[attr-defined]
            self.mount(row)

    def watch_filter_text(self, _: str) -> None:
        self._render_list()

    def watch_selected_node(self, _: str | None) -> None:
        self._render_list()

    @on(Input.Changed, "#search-input")
    def on_search(self, event: Input.Changed) -> None:
        self.filter_text = event.value

    def on_click(self, event: events.Click) -> None:
        for child in self.query(".node-row"):
            node_id = getattr(child, "_node_id", None)
            if node_id and child.region.contains(event.screen_x, event.screen_y):
                self.post_message(NodeSelected(node_id))
                break


# ─── Ego graph canvas ─────────────────────────────────────────────────────────

class EgoCanvas(Widget, can_focus=True):
    """
    3-column ego graph view:

      predecessors  │  center node  │  successors
      (imported by) │               │  (imports)
    """

    DEFAULT_CSS = """
    EgoCanvas {
        background: #09091a;
        height: 1fr;
        padding: 1 2;
    }
    EgoCanvas:focus {
        border: solid #4F8EF7 25%;
    }
    """

    selected_node: reactive[str | None] = reactive(None, layout=True)

    _MAX_NEIGHBORS = 18   # max per side before truncating

    def __init__(self, graph: nx.DiGraph, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.graph = graph
        self._node_order: list[str] = list(graph.nodes())

    def render(self) -> Any:
        if self.selected_node is None:
            return self._render_welcome()
        return self._render_ego(self.selected_node)

    def _render_welcome(self) -> Panel:
        t = Text(justify="center")
        t.append("\n\n\n")
        t.append("⬡ synaptic\n\n", style="bold #4F8EF7")
        t.append("Press ", style="dim")
        t.append("Tab", style="bold cyan")
        t.append(" or ", style="dim")
        t.append("click a node", style="bold cyan")
        t.append(" in the sidebar\n", style="dim")
        t.append("to explore its dependency graph", style="dim")
        return Panel(Align.center(t, vertical="middle"), border_style="#1e1e3a", box=ROUNDED)

    def _render_ego(self, node: str) -> Any:
        data = self.graph.nodes.get(node, {})
        kind = data.get("kind", "internal")
        color = KIND_COLOR.get(kind, "#cccccc")
        icon = KIND_ICON.get(kind, "◉")

        predecessors = list(self.graph.predecessors(node))
        successors   = list(self.graph.successors(node))

        # Detect circular edges involving this node
        circular_partners: set[str] = set()
        for u, v, d in self.graph.edges(data=True):
            if d.get("circular") and (u == node or v == node):
                circular_partners.add(v if u == node else u)

        # ── Center node panel ─────────────────────────────────────────
        center_text = Text(justify="center")
        center_text.append(f"\n{icon}\n", style=f"bold {color}")
        center_text.append(f"{node}\n", style=f"bold {color}")
        center_text.append(f"\n{KIND_LABEL.get(kind, kind)}", style="dim #666688")
        center_text.append(f"\n\n← {len(predecessors)}   {len(successors)} →", style="#444466")
        if circular_partners:
            center_text.append(f"\n⚠ {len(circular_partners)} circular", style="bold red")

        center_panel = Panel(
            Align.center(center_text, vertical="middle"),
            border_style=color,
            box=ROUNDED,
            expand=True,
        )

        # ── Predecessors column ───────────────────────────────────────
        pred_rows = self._build_neighbor_column(
            predecessors, circular_partners, arrow="→", title="imported by"
        )

        # ── Successors column ─────────────────────────────────────────
        succ_rows = self._build_neighbor_column(
            successors, circular_partners, arrow="←", title="imports"
        )

        # ── 3-column table ────────────────────────────────────────────
        table = Table.grid(expand=True, padding=(0, 1))
        table.add_column(ratio=3, no_wrap=False)   # predecessors
        table.add_column(ratio=2, no_wrap=False)   # center
        table.add_column(ratio=3, no_wrap=False)   # successors
        table.add_row(pred_rows, center_panel, succ_rows)

        return table

    def _build_neighbor_column(
        self,
        neighbors: list[str],
        circular_partners: set[str],
        arrow: str,
        title: str,
    ) -> Panel:
        content = Text()
        total = len(neighbors)
        shown = neighbors[: self._MAX_NEIGHBORS]

        if not shown:
            content.append(f"\n  (none)", style="dim #444466")
        else:
            for i, nb in enumerate(shown):
                nb_data = self.graph.nodes.get(nb, {})
                nb_kind  = nb_data.get("kind", "internal")
                nb_color = KIND_COLOR.get(nb_kind, "#888")
                nb_icon  = KIND_ICON.get(nb_kind, "·")
                nb_label = nb_data.get("label", nb.split(".")[-1])

                is_circ = nb in circular_partners
                connector = "⚠ " if is_circ else "  "
                circ_style = "bold red" if is_circ else ""

                content.append(f"\n")
                if arrow == "→":
                    content.append(f"  {connector}", circ_style)
                    content.append(f"{nb_icon} ", f"{nb_color}")
                    content.append(f"{nb_label[:22]}", f"{'bold ' if is_circ else ''}{nb_color}")
                    content.append(f"  {arrow}", "#2a3a6a")
                else:
                    content.append(f"  {arrow}  ", "#2a3a6a")
                    content.append(f"{nb_icon} ", f"{nb_color}")
                    content.append(f"{nb_label[:22]}", f"{'bold ' if is_circ else ''}{nb_color}")
                    content.append(f"  {connector}", circ_style)

            if total > self._MAX_NEIGHBORS:
                content.append(f"\n  … +{total - self._MAX_NEIGHBORS} more", style="dim #444466")

        border_title = (
            f"[dim]← [bold]{title}[/bold]  {total}[/dim]" if arrow == "→"
            else f"[dim]{title}  [bold]{total}[/bold] →[/dim]"
        )
        return Panel(
            content,
            title=border_title,
            border_style="#1e1e3a",
            box=ROUNDED,
            expand=True,
        )

    # ── Keyboard navigation ───────────────────────────────────────────

    def on_key(self, event: events.Key) -> None:
        nodes = self._node_order
        if not nodes:
            return
        if self.selected_node is None:
            self.selected_node = nodes[0]
            self.post_message(NodeSelected(nodes[0]))
            return

        try:
            idx = nodes.index(self.selected_node)
        except ValueError:
            idx = 0

        if event.key in ("tab", "down", "j", "n"):
            new = nodes[(idx + 1) % len(nodes)]
        elif event.key in ("shift+tab", "up", "k", "p"):
            new = nodes[(idx - 1) % len(nodes)]
        else:
            return

        event.stop()
        self.selected_node = new
        self.post_message(NodeSelected(new))

    def select(self, node: str) -> None:
        self.selected_node = node
        self.refresh()


# ─── Bottom detail bar ────────────────────────────────────────────────────────

class DetailBar(Widget):
    DEFAULT_CSS = """
    DetailBar {
        height: 3;
        background: #0a0a1e;
        border-top: solid #1e1e3a;
        padding: 0 2;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("", id="detail-text")

    def update(self, node: str, graph: nx.DiGraph) -> None:
        data = graph.nodes.get(node, {})
        kind  = data.get("kind", "internal")
        color = KIND_COLOR.get(kind, "#888")
        icon  = KIND_ICON.get(kind, "·")

        preds = list(graph.predecessors(node))
        succs = list(graph.successors(node))
        circs = [
            (u, v) for u, v, d in graph.edges(data=True)
            if d.get("circular") and (u == node or v == node)
        ]

        t = Text()
        t.append(f" {icon} ", f"bold {color}")
        t.append(node, f"bold {color}")
        t.append("  ·  ", "dim #333355")
        t.append(KIND_LABEL.get(kind, kind), f"dim {color}")
        t.append("  ·  ", "dim #333355")
        t.append("imported by ", "dim")
        t.append(str(len(preds)), "bold #a0a0ff")
        t.append("  imports ", "dim")
        t.append(str(len(succs)), "bold #4F8EF7")
        if circs:
            t.append("  ·  ", "dim #333355")
            t.append(f"⚠ {len(circs)} circular dep{'s' if len(circs)>1 else ''}", "bold red")

        self.query_one("#detail-text", Static).update(t)


# ─── Mini stats bar (top) ─────────────────────────────────────────────────────

class StatsBar(Widget):
    DEFAULT_CSS = """
    StatsBar {
        height: 1;
        background: #111122;
        padding: 0 2;
        dock: top;
    }
    """

    def __init__(self, graph: nx.DiGraph, project: Path, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.graph = graph
        self.project = project

    def render(self) -> Text:
        from synaptic import __version__
        G = self.graph

        internals = sum(1 for _, d in G.nodes(data=True) if d.get("kind") == "internal")
        clouds    = sum(1 for _, d in G.nodes(data=True) if d.get("kind") in ("AWS","GCP","Azure"))
        http_     = sum(1 for _, d in G.nodes(data=True) if d.get("kind") == "http")
        circs     = sum(1 for *_, d in G.edges(data=True) if d.get("circular"))

        t = Text(no_wrap=True, overflow="crop")
        t.append("⬡ ", "bold #4F8EF7")
        t.append("synaptic", "bold #4F8EF7")
        t.append(f"  {self.project.name}", "#666688")
        t.append("  ·  ", "dim #333355")
        t.append(str(G.number_of_nodes()), "bold #4F8EF7")
        t.append(" nodes  ", "dim #444466")
        t.append(str(G.number_of_edges()), "bold #4F8EF7")
        t.append(" edges  ", "dim #444466")
        if clouds:
            t.append(f"  ◈ {clouds} cloud", "#FF9900")
        if http_:
            t.append(f"  ◈ {http_} http", "#E84393")
        if circs:
            t.append(f"  ⚠ {circs} circular", "bold red")
        t.append(f"  ·  v{__version__}", "dim #333355")
        return t


# ─── Main App ─────────────────────────────────────────────────────────────────

class SynapticApp(App[None]):
    CSS = """
    Screen {
        layout: vertical;
        background: #0d0d1a;
    }
    #body {
        layout: horizontal;
        height: 1fr;
    }
    #main {
        layout: vertical;
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("q",         "quit",           "Quit"),
        Binding("tab",       "next_node",       "Next",    show=False),
        Binding("shift+tab", "prev_node",       "Prev",    show=False),
        Binding("r",         "reset",           "Reset"),
        Binding("g",         "focus_canvas",    "Graph"),
        Binding("s",         "focus_search",    "Search"),
    ]

    def __init__(self, graph: nx.DiGraph, project: Path, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.graph = graph
        self.project = project

    def compose(self) -> ComposeResult:
        from textual.containers import Horizontal, Vertical

        canvas  = EgoCanvas(self.graph, id="canvas")
        sidebar = NodeSidebar(self.graph, id="sidebar")
        detail  = DetailBar(id="detail")

        yield StatsBar(self.graph, self.project)

        with Horizontal(id="body"):
            yield sidebar
            with Vertical(id="main"):
                yield canvas
                yield detail

        yield Footer()

    # ── Event handlers ───────────────────────────────────────────────

    def on_node_selected(self, message: NodeSelected) -> None:
        canvas  = self.query_one("#canvas",  EgoCanvas)
        sidebar = self.query_one("#sidebar", NodeSidebar)
        detail  = self.query_one("#detail",  DetailBar)

        canvas.selected_node     = message.node
        sidebar.selected_node    = message.node
        detail.update(message.node, self.graph)

    # ── Actions ──────────────────────────────────────────────────────

    def action_next_node(self) -> None:
        self.query_one("#canvas", EgoCanvas).on_key(
            events.Key(self, "tab", character=None)
        )

    def action_prev_node(self) -> None:
        self.query_one("#canvas", EgoCanvas).on_key(
            events.Key(self, "shift+tab", character=None)
        )

    def action_reset(self) -> None:
        canvas  = self.query_one("#canvas",  EgoCanvas)
        sidebar = self.query_one("#sidebar", NodeSidebar)
        canvas.selected_node  = None
        sidebar.selected_node = None

    def action_focus_canvas(self) -> None:
        self.query_one("#canvas", EgoCanvas).focus()

    def action_focus_search(self) -> None:
        self.query_one("#search-input", Input).focus()


# ─── Entry point ──────────────────────────────────────────────────────────────

def launch(graph: nx.DiGraph, project: Path) -> None:
    SynapticApp(graph=graph, project=project).run()
