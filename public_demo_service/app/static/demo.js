(() => {
  const boards = {};
  let ws = null;

  function connectWs() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws/events`);
    const status = document.getElementById("ws-status");

    ws.onopen = () => {
      status.textContent = "Connected";
      status.style.cssText = "font-size:0.75rem; color:#4a4a4a;";
    };
    ws.onclose = () => {
      status.textContent = "Reconnecting…";
      status.style.cssText = "font-size:0.75rem; color:#767676;";
      setTimeout(connectWs, 2000);
    };
    ws.onmessage = (ev) => {
      try {
        handleMessage(JSON.parse(ev.data));
      } catch (e) {
        console.warn(e);
      }
    };
  }

  function handleMessage(msg) {
    if (msg.type === "history") {
      msg.items.slice().reverse().forEach((item) => addActivity(item, false));
      return;
    }
    if (msg.type === "stats") {
      updateStats(msg);
      return;
    }
    if (msg.type === "activity") {
      addActivity(msg, true);
      return;
    }
    if (msg.type === "flow") {
      showToast(msg.label);
      animateFlow(msg.view, msg.steps || [], msg.pulse_node, msg.node_blurbs || {});
    }
  }

  function updateStats(msg) {
    document.getElementById("stats-bar").classList.add("visible");
    document.getElementById("stat-orders").textContent = msg.order_count ?? "—";
    document.getElementById("stat-revenue").textContent = msg.total_revenue
      ? `$${Number(msg.total_revenue).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
      : "—";
    document.getElementById("stat-aov").textContent = msg.avg_order_value
      ? `$${Number(msg.avg_order_value).toFixed(2)}`
      : "—";
  }

  function addActivity(item, prepend) {
    const feed = document.getElementById("activity-feed");
    const li = document.createElement("li");
    const cat = item.category || "order";
    li.className = `activity-item ${cat}`;
    const time = item.time ? new Date(item.time).toLocaleTimeString() : "—";
    const icon = cat === "storefront" ? "🛍️" : cat === "supply" ? "📦" : "📋";
    li.innerHTML = `
      <p style="font-size:0.65rem;text-transform:uppercase;letter-spacing:0.07em;color:#9a9a9a;font-family:Inter,sans-serif;">${time}</p>
      <p style="margin-top:0.2rem;font-size:0.8rem;font-weight:600;color:#080808;font-family:Inter,sans-serif;">${icon} ${escapeHtml(item.title || "Event")}</p>
      <p style="margin-top:0.2rem;font-size:0.72rem;line-height:1.5;color:#767676;font-family:Inter,sans-serif;">${escapeHtml(item.detail || "")}</p>`;
    if (prepend) feed.prepend(li);
    else feed.appendChild(li);
    while (feed.children.length > 80) feed.removeChild(feed.lastChild);
  }

  function showToast(text) {
    const el = document.getElementById("flow-toast");
    el.textContent = text;
    el.classList.remove("hidden");
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => el.classList.add("hidden"), 3200);
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function edgePath(fromNode, toNode) {
    const fc = { x: fromNode.x + fromNode.w / 2, y: fromNode.y + fromNode.h / 2 };
    const tc = { x: toNode.x + toNode.w / 2, y: toNode.y + toNode.h / 2 };
    const dx = tc.x - fc.x;
    const dy = tc.y - fc.y;
    let a;
    let b;

    if (Math.abs(dx) >= Math.abs(dy)) {
      if (dx >= 0) {
        a = { x: fromNode.x + fromNode.w, y: fc.y };
        b = { x: toNode.x, y: tc.y };
      } else {
        a = { x: fromNode.x, y: fc.y };
        b = { x: toNode.x + toNode.w, y: tc.y };
      }
    } else if (dy >= 0) {
      a = { x: fc.x, y: fromNode.y + fromNode.h };
      b = { x: tc.x, y: toNode.y };
    } else {
      a = { x: fc.x, y: fromNode.y };
      b = { x: tc.x, y: toNode.y + toNode.h };
    }

    const c1 = { x: a.x + dx * 0.42, y: a.y + dy * 0.08 };
    const c2 = { x: b.x - dx * 0.42, y: b.y - dy * 0.08 };
    return `M ${a.x} ${a.y} C ${c1.x} ${c1.y}, ${c2.x} ${c2.y}, ${b.x} ${b.y}`;
  }

  function buildBoard(view, containerId) {
    fetch(`/api/topology/${view}`)
      .then((r) => r.json())
      .then((data) => {
        const el = document.getElementById(containerId);
        el.innerHTML = "";
        const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        svg.setAttribute("viewBox", "0 0 1100 620");
        svg.setAttribute("class", "board-svg");
        svg.setAttribute("preserveAspectRatio", "xMidYMid meet");

        const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
        defs.innerHTML = `
          <pattern id="dot-grid-${view}" width="24" height="24" patternUnits="userSpaceOnUse">
            <circle cx="1" cy="1" r="1" fill="#dceef7"/>
          </pattern>
          <marker id="arrow-${view}" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
            <path d="M0,0 L6,3 L0,6 Z" fill="rgba(155,204,231,0.8)"/>
          </marker>`;
        svg.appendChild(defs);

        const bg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        bg.setAttribute("width", "1100");
        bg.setAttribute("height", "620");
        bg.setAttribute("fill", "#ffffff");
        svg.appendChild(bg);

        const grid = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        grid.setAttribute("width", "1100");
        grid.setAttribute("height", "620");
        grid.setAttribute("fill", `url(#dot-grid-${view})`);
        grid.setAttribute("class", "board-grid");
        svg.appendChild(grid);

        const gEdges = document.createElementNS("http://www.w3.org/2000/svg", "g");
        const gNodes = document.createElementNS("http://www.w3.org/2000/svg", "g");
        const pathMap = {};

        data.edges.forEach(({ from, to }) => {
          const f = data.nodes[from];
          const t = data.nodes[to];
          if (!f || !t) return;
          const d = edgePath(f, t);
          const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
          path.setAttribute("d", d);
          path.setAttribute("class", "edge-path");
          path.setAttribute("marker-end", `url(#arrow-${view})`);
          gEdges.appendChild(path);
          pathMap[`${from}->${to}`] = path;
        });

        Object.entries(data.nodes).forEach(([id, n]) => {
          const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
          g.setAttribute("id", `node-${view}-${id}`);

          const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
          rect.setAttribute("x", n.x);
          rect.setAttribute("y", n.y);
          rect.setAttribute("width", n.w);
          rect.setAttribute("height", n.h);
          rect.setAttribute("rx", "12");
          rect.setAttribute("fill", n.color || "#0f172a");
          rect.setAttribute("stroke", "rgba(155,204,231,0.55)");
          rect.setAttribute("stroke-width", "1.5");
          rect.setAttribute("class", "node-box");

          const t1 = document.createElementNS("http://www.w3.org/2000/svg", "text");
          t1.setAttribute("x", n.x + 14);
          t1.setAttribute("y", n.y + 28);
          t1.setAttribute("fill", "#080808");
          t1.setAttribute("font-size", "13");
          t1.setAttribute("font-weight", "600");
          t1.setAttribute("font-family", "Inter, system-ui, sans-serif");
          t1.textContent = n.label;

          g.appendChild(rect);
          g.appendChild(t1);

          const sub = n.subtitle || "";
          if (sub) {
            const t2 = document.createElementNS("http://www.w3.org/2000/svg", "text");
            t2.setAttribute("x", n.x + 14);
            t2.setAttribute("y", n.y + 48);
            t2.setAttribute("fill", "#767676");
            t2.setAttribute("font-size", "9.5");
            t2.setAttribute("font-family", "Inter, system-ui, sans-serif");
            t2.setAttribute("opacity", "1");
            t2.textContent = sub.length > 32 ? `${sub.slice(0, 30)}…` : sub;
            g.appendChild(t2);
          }

          gNodes.appendChild(g);
        });

        svg.appendChild(gEdges);
        svg.appendChild(gNodes);
        el.appendChild(svg);

        boards[view] = { svg, pathMap, nodes: data.nodes, view };
      });
  }

  function pulseNode(view, nodeId, blurbText) {
    const g = document.getElementById(`node-${view}-${nodeId}`);
    if (!g) return;
    const rect = g.querySelector("rect");
    if (!rect) return;
    rect.classList.add("pulse");
    setTimeout(() => rect.classList.remove("pulse"), 1400);
    if (blurbText) showNodeBlurb(view, nodeId, blurbText);
  }

  function showNodeBlurb(view, nodeId, text) {
    const board = boards[view];
    if (!board || !text) return;
    const node = board.nodes[nodeId];
    if (!node) return;

    const blurbId = `blurb-${view}-${nodeId}`;
    const existing = document.getElementById(blurbId);
    if (existing) {
      clearTimeout(existing._hideTimer);
      clearTimeout(existing._removeTimer);
      existing.remove();
    }

    const paddingX = 10;
    const paddingY = 6;
    const fontSize = 11;
    const charW = 6.2;
    const textW = Math.min(text.length * charW + paddingX * 2, 240);
    const boxW = Math.max(textW, 100);
    const boxH = fontSize + paddingY * 2;
    const cx = node.x + node.w / 2;
    const bx = Math.max(8, Math.min(cx - boxW / 2, 1100 - boxW - 8));
    const by = Math.max(8, node.y - boxH - 10);

    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    g.setAttribute("id", blurbId);
    g.setAttribute("class", "node-blurb");

    const bg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    bg.setAttribute("x", bx);
    bg.setAttribute("y", by);
    bg.setAttribute("width", boxW);
    bg.setAttribute("height", boxH);
    bg.setAttribute("rx", "8");
    bg.setAttribute("class", "node-blurb-bg");

    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("x", bx + boxW / 2);
    label.setAttribute("y", by + boxH / 2 + 4);
    label.setAttribute("text-anchor", "middle");
    label.setAttribute("class", "node-blurb-text");
    label.textContent = text.length > 38 ? `${text.slice(0, 36)}…` : text;

    const tail = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
    const tailCx = Math.max(bx + 12, Math.min(cx, bx + boxW - 12));
    tail.setAttribute(
      "points",
      `${tailCx - 6},${by + boxH} ${tailCx + 6},${by + boxH} ${tailCx},${by + boxH + 7}`
    );
    tail.setAttribute("class", "node-blurb-tail");

    g.appendChild(bg);
    g.appendChild(tail);
    g.appendChild(label);
    board.svg.appendChild(g);

    g._hideTimer = setTimeout(() => g.classList.add("fade-out"), 3200);
    g._removeTimer = setTimeout(() => g.remove(), 3600);
  }

  function animateFlow(view, steps, pulseNodeId, nodeBlurbs) {
    const board = boards[view];
    if (!board || !steps.length) return;
    if (pulseNodeId) pulseNode(view, pulseNodeId, nodeBlurbs[pulseNodeId]);

    let delay = 0;
    steps.forEach((step) => {
      const key = `${step.from}->${step.to}`;
      const pathEl = board.pathMap[key];
      if (!pathEl) return;

      setTimeout(() => {
        const len = pathEl.getTotalLength();
        const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        dot.setAttribute("r", "6");
        dot.setAttribute("class", "flow-dot");
        board.svg.appendChild(dot);

        const start = performance.now();
        const duration = 850;

        function tick(now) {
          const t = Math.min(1, (now - start) / duration);
          const pt = pathEl.getPointAtLength(t * len);
          dot.setAttribute("cx", pt.x);
          dot.setAttribute("cy", pt.y);
          if (t < 1) {
            requestAnimationFrame(tick);
          } else {
            dot.remove();
            pulseNode(view, step.to, nodeBlurbs[step.to]);
            pathEl.classList.add("lit");
            setTimeout(() => pathEl.classList.remove("lit"), 700);
          }
        }
        requestAnimationFrame(tick);
      }, delay);
      delay += 280;
    });
  }

  buildBoard("business", "board-business");
  connectWs();

  setInterval(() => {
    if (ws && ws.readyState === 1) ws.send("ping");
  }, 25000);
})();
