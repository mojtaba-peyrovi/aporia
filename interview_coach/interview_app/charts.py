from __future__ import annotations

import json
import uuid
from typing import Any

import streamlit.components.v1 as components


def render_correctness_over_time(*, timeline: list[dict[str, Any]]) -> None:
    chart_id = f"chart-{uuid.uuid4().hex}"
    payload = json.dumps(
        [
            {
                "x": int(item["question_order"]),
                "y": item.get("correctness"),
            }
            for item in timeline
        ]
    )
    html = f"""
    <div id="{chart_id}"></div>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <script>
      const data = {payload}.filter(d => d.y !== null && d.y !== undefined);
      const container = document.getElementById("{chart_id}");
      const width = Math.min(760, container.clientWidth || 760);
      const height = 220;
      const margin = {{top: 20, right: 18, bottom: 28, left: 44}};

      const svg = d3.select(container).append("svg")
        .attr("width", width)
        .attr("height", height);

      svg.append("text")
        .attr("x", margin.left)
        .attr("y", 14)
        .attr("font-size", "12px")
        .attr("font-weight", 700)
        .text("Correctness over time");

      if (data.length === 0) {{
        svg.append("text")
          .attr("x", margin.left)
          .attr("y", 60)
          .attr("font-size", "12px")
          .text("No scored answers yet.");
      }} else {{
        const x = d3.scaleLinear()
          .domain(d3.extent(data, d => d.x))
          .range([margin.left, width - margin.right]);

        const y = d3.scaleLinear()
          .domain([0, 100])
          .range([height - margin.bottom, margin.top + 10]);

        const xAxis = d3.axisBottom(x).ticks(Math.min(10, data.length)).tickFormat(d3.format("d"));
        const yAxis = d3.axisLeft(y).ticks(5);

        svg.append("g")
          .attr("transform", `translate(0,${{height - margin.bottom}})`)
          .call(xAxis);

        svg.append("g")
          .attr("transform", `translate(${{margin.left}},0)`)
          .call(yAxis);

        const line = d3.line()
          .x(d => x(d.x))
          .y(d => y(d.y));

        svg.append("path")
          .datum(data)
          .attr("fill", "none")
          .attr("stroke", "#2563eb")
          .attr("stroke-width", 2)
          .attr("d", line);

        svg.selectAll("circle")
          .data(data)
          .enter()
          .append("circle")
          .attr("cx", d => x(d.x))
          .attr("cy", d => y(d.y))
          .attr("r", 3)
          .attr("fill", "#2563eb");
      }}
    </script>
    """
    components.html(html, height=250)


def render_avg_bars(*, avg_correctness: float | None, avg_role_relevance: float | None) -> None:
    chart_id = f"chart-{uuid.uuid4().hex}"
    payload = json.dumps(
        [
            {"label": "Correctness", "value": float(avg_correctness) if avg_correctness is not None else None},
            {"label": "Role relevance", "value": float(avg_role_relevance) if avg_role_relevance is not None else None},
        ]
    )
    html = f"""
    <div id="{chart_id}"></div>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <script>
      const raw = {payload};
      const data = raw.filter(d => d.value !== null && d.value !== undefined);
      const container = document.getElementById("{chart_id}");
      const width = Math.min(760, container.clientWidth || 760);
      const height = 200;
      const margin = {{top: 20, right: 18, bottom: 30, left: 120}};

      const svg = d3.select(container).append("svg")
        .attr("width", width)
        .attr("height", height);

      svg.append("text")
        .attr("x", margin.left)
        .attr("y", 14)
        .attr("font-size", "12px")
        .attr("font-weight", 700)
        .text("Average scores");

      if (data.length === 0) {{
        svg.append("text")
          .attr("x", margin.left)
          .attr("y", 60)
          .attr("font-size", "12px")
          .text("No scored answers yet.");
      }} else {{
        const x = d3.scaleLinear().domain([0, 100]).range([margin.left, width - margin.right]);
        const y = d3.scaleBand().domain(data.map(d => d.label)).range([margin.top + 10, height - margin.bottom]).padding(0.25);

        svg.append("g")
          .attr("transform", `translate(0,${{height - margin.bottom}})`)
          .call(d3.axisBottom(x).ticks(5));

        svg.append("g")
          .attr("transform", `translate(${{margin.left}},0)`)
          .call(d3.axisLeft(y));

        svg.selectAll("rect")
          .data(data)
          .enter()
          .append("rect")
          .attr("x", x(0))
          .attr("y", d => y(d.label))
          .attr("height", y.bandwidth())
          .attr("width", d => x(d.value) - x(0))
          .attr("fill", "#10b981");

        svg.selectAll("text.value")
          .data(data)
          .enter()
          .append("text")
          .attr("class", "value")
          .attr("x", d => x(d.value) + 6)
          .attr("y", d => y(d.label) + y.bandwidth() / 2 + 4)
          .attr("font-size", "12px")
          .text(d => `${{Math.round(d.value)}}%`);
      }}
    </script>
    """
    components.html(html, height=230)


def render_population_distribution(*, population_values: list[float], user_value: float | None) -> None:
    chart_id = f"chart-{uuid.uuid4().hex}"
    payload = json.dumps({"population": [float(v) for v in population_values], "user": float(user_value) if user_value is not None else None})
    html = f"""
    <div id="{chart_id}"></div>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <script>
      const payload = {payload};
      const values = payload.population || [];
      const user = payload.user;

      const container = document.getElementById("{chart_id}");
      const width = Math.min(760, container.clientWidth || 760);
      const height = 240;
      const margin = {{top: 20, right: 18, bottom: 30, left: 44}};

      const svg = d3.select(container).append("svg")
        .attr("width", width)
        .attr("height", height);

      svg.append("text")
        .attr("x", margin.left)
        .attr("y", 14)
        .attr("font-size", "12px")
        .attr("font-weight", 700)
        .text("Your average correctness vs other users");

      if (values.length === 0) {{
        svg.append("text")
          .attr("x", margin.left)
          .attr("y", 60)
          .attr("font-size", "12px")
          .text("Not enough data yet.");
      }} else {{
        const x = d3.scaleLinear().domain([0, 100]).range([margin.left, width - margin.right]);
        const bins = d3.bin().domain(x.domain()).thresholds(10)(values);
        const y = d3.scaleLinear()
          .domain([0, d3.max(bins, d => d.length)])
          .nice()
          .range([height - margin.bottom, margin.top + 10]);

        svg.append("g")
          .attr("transform", `translate(0,${{height - margin.bottom}})`)
          .call(d3.axisBottom(x).ticks(5));

        svg.append("g")
          .attr("transform", `translate(${{margin.left}},0)`)
          .call(d3.axisLeft(y).ticks(4));

        svg.selectAll("rect")
          .data(bins)
          .enter()
          .append("rect")
          .attr("x", d => x(d.x0) + 1)
          .attr("y", d => y(d.length))
          .attr("width", d => Math.max(0, x(d.x1) - x(d.x0) - 2))
          .attr("height", d => y(0) - y(d.length))
          .attr("fill", "#6b7280");

        if (user !== null && user !== undefined) {{
          svg.append("line")
            .attr("x1", x(user))
            .attr("x2", x(user))
            .attr("y1", margin.top + 10)
            .attr("y2", height - margin.bottom)
            .attr("stroke", "#ef4444")
            .attr("stroke-width", 2);

          svg.append("text")
            .attr("x", x(user) + 6)
            .attr("y", margin.top + 22)
            .attr("font-size", "12px")
            .attr("fill", "#ef4444")
            .text(`You: ${{Math.round(user)}}%`);
        }}
      }}
    </script>
    """
    components.html(html, height=270)

