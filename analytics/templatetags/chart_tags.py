"""
Dependency-free SVG charts. Geometry is computed here; markup lives in templates,
so every label goes through Django's auto-escaping.
"""

from django import template

register = template.Library()

WIDTH = 640
HEIGHT = 240
PAD_X = 12
PAD_TOP = 16
PAD_BOTTOM = 28


def _values(data):
    return [float(item.get("value") or 0) for item in data]


@register.inclusion_tag("includes/chart_line.html")
def line_chart(data, title="Trend"):
    values = _values(data)
    has_data = any(values)
    max_value = max(values) if has_data else 1
    plot_w = WIDTH - 2 * PAD_X
    plot_h = HEIGHT - PAD_TOP - PAD_BOTTOM
    step = plot_w / (len(values) - 1) if len(values) > 1 else 0

    points = []
    for index, (item, value) in enumerate(zip(data, values)):
        x = PAD_X + index * step
        y = PAD_TOP + plot_h - (value / max_value) * plot_h
        points.append({"x": round(x, 1), "y": round(y, 1), "label": item["label"], "value": item.get("value") or 0})

    polyline = " ".join(f"{p['x']},{p['y']}" for p in points)
    area = f"{PAD_X},{PAD_TOP + plot_h} {polyline} {PAD_X + plot_w},{PAD_TOP + plot_h}" if points else ""
    label_every = max(1, len(points) // 6)
    return {
        "title": title,
        "points": points,
        "polyline": polyline,
        "area": area,
        "axis_labels": [p for i, p in enumerate(points) if i % label_every == 0],
        "has_data": has_data,
        "width": WIDTH,
        "height": HEIGHT,
        "baseline": PAD_TOP + plot_h,
        "label_y": HEIGHT - 8,
        "max_value": max_value if has_data else 0,
        "total": sum(values),
    }


@register.inclusion_tag("includes/chart_bars.html")
def bar_chart(data, title="Breakdown"):
    """Horizontal bars; ``data`` items need ``label`` and ``value`` (and optional ``units``)."""
    values = _values(data)
    max_value = max(values) if values and max(values) > 0 else 1
    rows = [
        {
            "label": item.get("label") or "Uncategorised",
            "value": item.get("value") or 0,
            "units": item.get("units"),
            "percent": round(value / max_value * 100, 1),
        }
        for item, value in zip(data, values)
    ]
    return {"title": title, "rows": rows, "has_data": bool(rows)}
