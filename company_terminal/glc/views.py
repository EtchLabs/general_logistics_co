from __future__ import annotations

from collections import deque
from datetime import datetime, timezone

from rich import box
from rich.columns import Columns
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from glc.collector import ServiceHealth, Snapshot

SPARK_BLOCKS = "▁▂▃▄▅▆▇█"


def _status_style(status: str) -> str:
    s = (status or "").lower()
    if s in {"ok", "healthy", "running"}:
        return "bold green"
    if s in {"degraded", "partial"}:
        return "bold yellow"
    if s in {"down", "error", "unknown"}:
        return "bold red"
    return "cyan"


def _money(value: object) -> str:
    if value is None:
        return "—"
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def _ts(value: object) -> str:
    if not value:
        return "—"
    text = str(value)
    if "T" in text:
        return text.replace("T", " ")[:19]
    return text[:19]


def sparkline(values: deque[float], width: int = 40) -> str:
    if not values:
        return "▁" * min(width, 10)
    recent = list(values)[-width:]
    lo, hi = min(recent), max(recent)
    span = hi - lo or 1.0
    chars = []
    for v in recent:
        idx = int((v - lo) / span * (len(SPARK_BLOCKS) - 1))
        chars.append(SPARK_BLOCKS[idx])
    return "".join(chars).ljust(width, "▁")


def render_overview(
    snap: Snapshot,
    order_history: deque[float],
    rate_per_min: float,
) -> Panel:
    healthy = sum(1 for s in snap.services if s.status in {"ok", "running"})
    total_svc = len(snap.services)

    kpi = Table.grid(padding=(0, 2))
    kpi.add_column(justify="left")
    kpi.add_column(justify="right")
    kpi.add_row("[bold cyan]Orders (total)[/]", f"[bold white]{snap.order_count}[/]")
    kpi.add_row("[bold cyan]Order rate[/]", f"[bold white]{rate_per_min:.2f}/min[/]")
    if snap.sales:
        kpi.add_row("[bold cyan]Revenue[/]", f"[bold green]{_money(snap.sales.get('total_revenue'))}[/]")
        kpi.add_row("[bold cyan]Avg order[/]", f"[bold white]{_money(snap.sales.get('average_order_value'))}[/]")
    kpi.add_row("[bold cyan]Notifications[/]", f"[bold white]{snap.notification_total}[/]")
    kpi.add_row("[bold cyan]Services up[/]", f"[bold green]{healthy}/{total_svc}[/]")

    sim = Table.grid(padding=(0, 1))
    sim.add_column()
    if snap.customer_sim:
        stats = snap.customer_sim.get("stats", {})
        sim.add_row(f"[dim]Customer sim[/] [green]{stats.get('orders_placed', 0)}[/] orders · "
                    f"[cyan]{stats.get('registrations', 0)}[/] signups · "
                    f"[white]{stats.get('catalog_skus', 0)}[/] SKUs")
    else:
        sim.add_row("[dim]Customer simulator offline[/]")
    sim.add_row(f"[dim]Gateway[/] {'[green]online[/]' if snap.gateway_ok else '[red]offline[/]'}")

    throughput = Panel(
        Text(sparkline(order_history), style="bold bright_blue"),
        title="Order volume (sparkline)",
        border_style="blue",
    )

    recent = Table(box=box.SIMPLE, expand=True, show_header=True, header_style="bold magenta")
    recent.add_column("Time", style="dim", width=19)
    recent.add_column("Order", width=10)
    recent.add_column("Status", width=12)
    recent.add_column("Total", justify="right", width=10)
    recent.add_column("Payment", width=10)
    for order in snap.orders[:8]:
        recent.add_row(
            _ts(order.get("created_at")),
            str(order.get("id", ""))[:8],
            str(order.get("status", "")),
            _money(order.get("grand_total")),
            str(order.get("payment_status", "")),
        )

    body = Columns(
        [
            Panel(kpi, title="Live KPIs", border_style="cyan"),
            Panel(sim, title="Simulators", border_style="green"),
        ],
        equal=True,
        expand=True,
    )

    from rich.console import Group

    return Panel(
        Group(body, throughput, Panel(recent, title="Latest orders", border_style="magenta")),
        title="[bold white]GLC Operations Overview[/]",
        border_style="bright_blue",
        padding=(1, 1),
    )


def render_services(snap: Snapshot) -> Panel:
    table = Table(box=box.HEAVY_HEAD, expand=True, show_lines=False)
    table.add_column("Service", style="bold")
    table.add_column("Group", style="dim")
    table.add_column("Port", justify="right")
    table.add_column("Status")
    table.add_column("Latency", justify="right")
    table.add_column("Uptime", justify="right")
    table.add_column("Detail", overflow="fold")

    for svc in snap.services:
        table.add_row(
            svc.label,
            svc.group,
            str(svc.port) if svc.port else "—",
            Text(svc.status, style=_status_style(svc.status)),
            f"{svc.latency_ms}ms" if svc.latency_ms is not None else "—",
            f"{svc.uptime:.0f}s" if svc.uptime is not None else "—",
            svc.detail or "",
        )

    return Panel(table, title="[bold]Service Health Grid[/]", border_style="green")


def render_orders(snap: Snapshot) -> Panel:
    table = Table(box=box.MINIMAL_DOUBLE_HEAD, expand=True)
    table.add_column("Created", style="dim", width=19)
    table.add_column("ID", width=36)
    table.add_column("Customer", width=10)
    table.add_column("Status", width=14)
    table.add_column("Pay", width=12)
    table.add_column("Subtotal", justify="right")
    table.add_column("Tax", justify="right")
    table.add_column("Total", justify="right", style="bold green")
    table.add_column("Items", justify="right")

    for order in snap.orders:
        items = sum(li.get("quantity", 0) for li in order.get("line_items", []))
        table.add_row(
            _ts(order.get("created_at")),
            str(order.get("id", "")),
            str(order.get("customer_id", ""))[:8],
            str(order.get("status", "")),
            str(order.get("payment_status", "")),
            _money(order.get("subtotal")),
            _money(order.get("tax_total")),
            _money(order.get("grand_total")),
            str(items),
        )

    return Panel(table, title=f"[bold]Orders[/] ({snap.order_count} total)", border_style="yellow")


def render_notifications(snap: Snapshot) -> Panel:
    table = Table(box=box.SIMPLE, expand=True)
    table.add_column("Time", style="dim", width=19)
    table.add_column("Channel", width=10)
    table.add_column("Event", width=22)
    table.add_column("Status", width=10)
    table.add_column("Payload", overflow="fold")

    for note in snap.notifications:
        payload = note.get("payload", {})
        summary = payload.get("order_id") or payload.get("message") or str(payload)[:80]
        table.add_row(
            _ts(note.get("created_at")),
            str(note.get("channel", "")),
            str(note.get("event_type", "")),
            str(note.get("status", "")),
            str(summary)[:80],
        )

    return Panel(
        table,
        title=f"[bold]Notification Feed[/] ({snap.notification_total} total)",
        border_style="bright_magenta",
    )


def render_inventory(snap: Snapshot) -> Panel:
    fc_table = Table(box=box.SIMPLE, title="Fulfillment Centers", expand=True)
    fc_table.add_column("Code", style="bold cyan")
    fc_table.add_column("Name")
    fc_table.add_column("City")
    fc_table.add_column("State")
    fc_table.add_column("Active")
    for fc in snap.fulfillment_centers:
        fc_table.add_row(
            str(fc.get("code", "")),
            str(fc.get("name", "")),
            str(fc.get("city", "")),
            str(fc.get("state", "")),
            "yes" if fc.get("is_active", True) else "no",
        )

    stock_table = Table(box=box.SIMPLE, title="Stock by SKU", expand=True)
    stock_table.add_column("SKU", style="bold")
    stock_table.add_column("Available", justify="right", style="green")
    stock_table.add_column("Reserved", justify="right", style="yellow")
    stock_table.add_column("On Hand", justify="right")
    stock_table.add_column("FC", style="dim")

    for row in snap.stock_levels:
        for fc_row in row.get("locations", []):
            stock_table.add_row(
                str(row.get("sku", "")),
                str(fc_row.get("available", 0)),
                str(fc_row.get("reserved", 0)),
                str(fc_row.get("on_hand", 0)),
                str(fc_row.get("fulfillment_center_code", ""))[:12],
            )

    summary = snap.inventory_summary or {}
    header = Text.assemble(
        ("Products: ", "dim"),
        (str(summary.get("product_count", "—")), "bold white"),
        ("  Active: ", "dim"),
        (str(summary.get("active_products", "—")), "bold green"),
    )

    from rich.console import Group

    return Panel(
        Group(header, fc_table, stock_table),
        title="[bold]Inventory & Warehousing[/]",
        border_style="blue",
    )


def render_finance(snap: Snapshot) -> Panel:
    sales = snap.sales or {}
    income = snap.income_statement or {}

    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold cyan")
    summary.add_column(justify="right")
    summary.add_row("Orders", str(sales.get("order_count", "—")))
    summary.add_row("Revenue", _money(sales.get("total_revenue")))
    summary.add_row("AOV", _money(sales.get("average_order_value")))
    summary.add_row("Generated", _ts(sales.get("generated_at")))

    income_table = Table(box=box.SIMPLE, title="Income Statement", expand=True)
    income_table.add_column("Line")
    income_table.add_column("Amount", justify="right")
    for key, label in (
        ("revenue_total", "Revenue"),
        ("expense_total", "Expenses"),
        ("net_income", "Net Income"),
    ):
        if key in income:
            income_table.add_row(label, _money(income.get(key)))

    tax_table = Table(box=box.SIMPLE, title="Tax Rates", expand=True)
    tax_table.add_column("Jurisdiction", style="cyan")
    tax_table.add_column("State")
    tax_table.add_column("Category")
    tax_table.add_column("Rate %", justify="right")
    for rate in snap.tax_rates[:10]:
        tax_table.add_row(
            str(rate.get("jurisdiction", "")),
            str(rate.get("state", "")),
            str(rate.get("product_category", "")),
            str(rate.get("rate_percent", "")),
        )

    acct_table = Table(box=box.SIMPLE, title="Chart of Accounts", expand=True)
    acct_table.add_column("Code", style="bold")
    acct_table.add_column("Name")
    acct_table.add_column("Type")
    acct_table.add_column("Balance", justify="right", style="green")
    for acct in snap.accounts[:12]:
        acct_table.add_row(
            str(acct.get("code", "")),
            str(acct.get("name", "")),
            str(acct.get("account_type", "")),
            _money(acct.get("balance")),
        )

    from rich.console import Group

    return Panel(
        Group(
            Panel(summary, title="Sales Summary", border_style="green"),
            income_table,
            Columns([tax_table, acct_table], equal=True, expand=True),
        ),
        title="[bold]Finance & Tax[/]",
        border_style="green",
    )


def render_supply_chain(snap: Snapshot) -> Panel:
    sup_table = Table(box=box.SIMPLE, title="Suppliers", expand=True)
    sup_table.add_column("Name", style="bold")
    sup_table.add_column("Email")
    sup_table.add_column("Lead days", justify="right")
    sup_table.add_column("Reliability", justify="right")
    for sup in snap.suppliers:
        sup_table.add_row(
            str(sup.get("name", "")),
            str(sup.get("contact_email", "")),
            str(sup.get("lead_time_days", "")),
            str(sup.get("reliability_score", "")),
        )

    po_table = Table(box=box.SIMPLE, title="Purchase Orders", expand=True)
    po_table.add_column("PO #", style="bold")
    po_table.add_column("Status")
    po_table.add_column("Total", justify="right")
    po_table.add_column("Supplier", width=10)
    po_table.add_column("Expected")
    for po in snap.purchase_orders[:15]:
        po_table.add_row(
            str(po.get("po_number", "")),
            str(po.get("status", "")),
            _money(po.get("total_amount")),
            str(po.get("supplier_id", ""))[:8],
            str(po.get("expected_delivery_date", "—")),
        )

    from rich.console import Group

    return Panel(
        Group(sup_table, po_table),
        title="[bold]Supply Chain[/]",
        border_style="yellow",
    )


def render_logistics(snap: Snapshot) -> Panel:
    ship_table = Table(box=box.SIMPLE, title="Sample Rate Quotes (KC → Oakland, 32oz)", expand=True)
    ship_table.add_column("Carrier", style="bold")
    ship_table.add_column("Service")
    ship_table.add_column("Cost", justify="right", style="green")
    ship_table.add_column("ETA days", justify="right")
    for quote in snap.shipping_quotes:
        ship_table.add_row(
            str(quote.get("carrier", "")),
            str(quote.get("service_level", "")),
            _money(quote.get("cost")),
            str(quote.get("estimated_days", "")),
        )

    people = Table(box=box.SIMPLE, title="Workforce", expand=True)
    people.add_column("Department", style="cyan")
    people.add_column("Employees", justify="right")
    dept_counts: dict[str, int] = {}
    dept_names = {d["id"]: d.get("code", "?") for d in snap.departments}
    for emp in snap.employees:
        code = dept_names.get(emp.get("department_id"), "—")
        dept_counts[code] = dept_counts.get(code, 0) + 1
    for code, count in sorted(dept_counts.items()):
        people.add_row(code, str(count))

    from rich.console import Group

    return Panel(
        Group(ship_table, people),
        title="[bold]Logistics & People[/]",
        border_style="bright_cyan",
    )


def render_status_bar(snap: Snapshot, rate: float, log_service: str) -> Text:
    ts = snap.fetched_at.astimezone().strftime("%H:%M:%S")
    healthy = sum(1 for s in snap.services if s.status in {"ok", "running"})
    return Text.assemble(
        (" GLC ", "bold white on blue"),
        (f"  {ts}  ", "dim"),
        (f"gateway:{'OK' if snap.gateway_ok else 'DOWN'}  ", "green" if snap.gateway_ok else "red"),
        (f"svc:{healthy}/{len(snap.services)}  ", "cyan"),
        (f"orders:{snap.order_count}  ", "yellow"),
        (f"rate:{rate:.1f}/m  ", "bright_blue"),
        (f"logs:{log_service}  ", "magenta"),
        ("[1-7] views  [l] logs  [r] refresh  [q] quit", "dim"),
    )
