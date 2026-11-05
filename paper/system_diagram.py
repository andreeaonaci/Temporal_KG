"""System diagram for the paper (IEEE two-column figure*, 7.16 in wide).

Run: python paper/system_diagram.py  ->  paper/system_diagram.{pdf,png}
Drawn at final print size, so every font size below is the size in the paper.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

plt.rcParams.update({
    "font.family": "Liberation Sans",  # metric-compatible with Arial/Helvetica
    "pdf.fonttype": 42,                # embed TrueType: IEEE PDF eXpress-friendly
    "mathtext.fontset": "custom",
    "mathtext.rm": "Liberation Sans",
    "mathtext.it": "Liberation Sans:italic",
})

W, H = 7.16, 4.60
INK = "#1b2430"
GREY_FILL, GREY_EDGE = "#f3f4f6", "#6b7280"
NOV_FILL, NOV_EDGE = "#e8f0fb", "#1f4e8c"
STAGE_FILL = "#ffffff"
RED, GREEN = "#b42318", "#1e7b3c"
BODY, SMALL, HEAD = 8, 7.5, 9

fig = plt.figure(figsize=(W, H))
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W)
ax.set_ylim(0, H)
ax.axis("off")


def box(x, y, w, h, fill=STAGE_FILL, edge=GREY_EDGE, lw=0.8, r=0.05, ls="-", z=1):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                fc=fill, ec=edge, lw=lw, ls=ls, zorder=z))


def text(x, y, s, size=BODY, ha="center", va="center", color=INK, weight="normal", z=5, **kw):
    ax.text(x, y, s, fontsize=size, ha=ha, va=va, color=color, weight=weight, zorder=z, **kw)


def arrow(p, q, color=INK, lw=1.0, style="-|>", ms=8, conn="arc3", z=4, ls="-"):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=ms, color=color,
                                 lw=lw, connectionstyle=conn, zorder=z, ls=ls,
                                 shrinkA=0, shrinkB=0))


def badge(x, y, n, fill=INK):
    ax.add_patch(plt.Circle((x, y), 0.095, fc=fill, ec="none", zorder=6))
    text(x, y - 0.005, n, size=BODY, color="white", weight="bold", z=7)


def module(x, y, w, h, n, title, fill=GREY_FILL, edge=GREY_EDGE, lw=0.9, dx=0.0):
    box(x, y, w, h, fill=fill, edge=edge, lw=lw, r=0.07)
    badge(x + 0.15 + dx, y + h - 0.15, n, fill=edge if edge != GREY_EDGE else INK)
    text(x + 0.30 + dx, y + h - 0.15, title, size=HEAD, ha="left", weight="bold")


# ───────────────────────── top row: ① ingestion, ② extraction, ③ ontology ─────────
TY, TH = 3.02, 1.52
# ① Ingestion
x1, w1 = 0.06, 2.92
module(x1, TY, w1, TH, "1", "Multilingual ingestion")
chips = [  # (x, y, w, title, detail)
    (x1 + 0.10, TY + 0.70, 1.30, "News sources", "GDELT 2.0 (DOC API,\nBigQuery GKG) · RSS"),
    (x1 + 1.52, TY + 0.70, 1.30, "Full-text scraping", "trafilatura; Google\nNews URL resolution"),
    (x1 + 1.52, TY + 0.08, 1.30, "Language ID + MT", "NLLB-200 / Google → EN;\nerror-page guard"),
    (x1 + 0.10, TY + 0.08, 1.30, "Relevance filter", "China $\\wedge$ Romania;\nsports excluded; dedup"),
]
for cx, cy, cw, t, d in chips:
    box(cx, cy, cw, 0.54)
    text(cx + cw / 2, cy + 0.40, t, weight="bold")
    text(cx + cw / 2, cy + 0.17, d, size=SMALL, linespacing=1.05)
arrow((x1 + 1.40, TY + 0.97), (x1 + 1.52, TY + 0.97))
arrow((x1 + 2.17, TY + 0.70), (x1 + 2.17, TY + 0.62))
arrow((x1 + 1.52, TY + 0.35), (x1 + 1.40, TY + 0.35))

# ② Extraction
x2, w2 = 3.10, 2.02
module(x2, TY, w2, TH, "2", "Temporal IE")
rows2 = [
    ("Entities", "spaCy NER + normalisation"),
    ("Events, relations", "dependency rules (opt. DeepKE)"),
    ("Time", "HeidelTime TIMEX3 → interval $I$"),
]
for i, (t, d) in enumerate(rows2):
    cy = TY + 0.86 - i * 0.39
    box(x2 + 0.10, cy, w2 - 0.20, 0.34)
    text(x2 + 0.17, cy + 0.235, t, ha="left", weight="bold", size=SMALL)
    text(x2 + 0.17, cy + 0.09, d, ha="left", size=SMALL)

# ③ Ontology
x3, w3 = 5.24, 1.86
module(x3, TY, w3, TH, "3", "Ontology alignment")
rows3 = [
    ("CAMEO / GDELT", "11 bilateral event types"),
    ("IPTC Media Topics", "topic per event"),
    ("W3C OWL-Time", "[start, end], granularity"),
]
for i, (t, d) in enumerate(rows3):
    cy = TY + 0.86 - i * 0.39
    box(x3 + 0.10, cy, w3 - 0.20, 0.34)
    text(x3 + 0.17, cy + 0.235, t, ha="left", weight="bold", size=SMALL)
    text(x3 + 0.17, cy + 0.09, d, ha="left", size=SMALL)

arrow((x1 + w1, TY + 0.65), (x2, TY + 0.65), lw=1.2)
arrow((x2 + w2, TY + 0.65), (x3, TY + 0.65), lw=1.2)

# ───────────────────────── bottom: ④ novel gated verification ─────────────────────
BY, BH = 0.06, 2.56
x4, w4 = 0.06, 5.20
module(x4, BY, w4, BH, "4", "Gated claim verification", fill=NOV_FILL, edge=NOV_EDGE, lw=1.4, dx=0.42)
text(x4 + 2.40, BY + BH - 0.15, "novel: a gate only demotes, with a named reason",
     size=BODY, ha="left", color=NOV_EDGE, style="italic")

# claim bus from ③ into ④
SY, SH, SW, GAP = BY + 0.93, 1.25, 1.15, 0.13
bus_y = 2.82
ax.plot([x3 + 0.55, x3 + 0.55], [TY, bus_y], color=INK, lw=1.2, zorder=3)
ax.plot([x3 + 0.55, 0.40], [bus_y, bus_y], color=INK, lw=1.2, zorder=3)
arrow((0.40, bus_y), (0.40, SY + SH), lw=1.2)
text(2.90, bus_y - 0.04, r"claims  $c=(s,\ t,\ I,\ \mathrm{source})$:  sentence, event type, interval",
     size=BODY, va="top")

sx = [x4 + 0.12 + i * (SW + GAP) for i in range(4)]
stages = [
    ("Semantic merge", ["MiniLM embeddings", r"cos $\geq$ 0.75, same type", "union-find → group $G$"]),
    ("NLI disagreement", ["DeBERTa-v3 NLI", r"relevance cos $\geq$ 0.15", r"$\max(P_{ab},P_{ba})\geq 0.5$", "both directions"]),
    ("Allen gate", ["13 relations $R(I_a,I_b)$"]),
    ("Lifecycle FSM", ["zero-shot NLI state $\\hat q$"]),
]
for i, (t, lines) in enumerate(stages):
    box(sx[i], SY, SW, SH, edge=NOV_EDGE, lw=0.9)
    box(sx[i] + 0.06, SY + SH - 0.08, 0.26, 0.16, fill=NOV_EDGE, edge=NOV_EDGE, r=0.04, z=6)
    text(sx[i] + 0.19, SY + SH, f"S{i + 1}", size=SMALL, weight="bold", color="white", z=7)
    text(sx[i] + SW / 2, SY + SH - 0.20, t, weight="bold")
    for j, ln in enumerate(lines):
        text(sx[i] + SW / 2, SY + SH - 0.44 - j * 0.22, ln, size=SMALL)
    if i < 3:
        arrow((sx[i] + SW, SY + SH / 2), (sx[i + 1], SY + SH / 2), color=NOV_EDGE, lw=1.2)

# S3 icon: two timelines (disjoint = evolution, overlap = contradiction)
ix = sx[2] + 0.20
for k, (a, b, lab, col) in enumerate([((0.00, 0.30), (0.42, 0.72), "<,>,m,mi → EVOLUTION", GREEN),
                                      ((0.00, 0.42), (0.22, 0.72), "overlap → CONTRA", RED)]):
    yy = SY + 0.62 - k * 0.34
    ax.add_patch(Rectangle((ix + a[0], yy), a[1] - a[0], 0.06, fc="#9aa5b1", ec="none", zorder=5))
    ax.add_patch(Rectangle((ix + b[0], yy - 0.08), b[1] - b[0], 0.06, fc=NOV_EDGE, ec="none", zorder=5))
    text(sx[2] + SW / 2, yy - 0.17, lab, size=6.5, color=col, weight="bold")

# S4 icon: TradeAgreement FSM
fx, fy = sx[3] + 0.06, SY + 0.58
states = ["prop.", "sign.", "ratif."]
for k, s in enumerate(states):
    cx = fx + 0.17 + k * 0.36
    box(cx - 0.15, fy - 0.08, 0.30, 0.17, edge=INK, lw=0.6, r=0.08)
    text(cx, fy, s, size=6.5)
    if k < 2:
        arrow((cx + 0.15, fy), (cx + 0.21, fy), lw=0.8, ms=5)
text(sx[3] + SW / 2, fy - 0.25, "ratified before signed", size=6.5)
text(sx[3] + SW / 2, fy - 0.42, "LIFECYCLE VIOLATION", size=6.5, color=RED, weight="bold")

# bottom row of ④: diversity, TCVS, labels
RY, RH = BY + 0.08, 0.64
bx = [x4 + 0.12, x4 + 1.79, x4 + 3.76]
bw = [1.55, 1.85, 1.40]
rows = [
    ("Publisher-network diversity", [(r"div$(G)=|\{\nu(\mathrm{domain})\}|$", INK), ("wire mirrors count once", INK)]),
    ("Veracity score (TCVS)", [("0.3 cred. + 0.4 corr. + 0.3 temp.", INK), ("contradiction: hard override", RED)]),
    ("Claim verdict", [("corroborated", GREEN), ("unverified  ·  contested", RED)]),
]
for i, (t, lines) in enumerate(rows):
    box(bx[i], RY, bw[i], RH, edge=NOV_EDGE, lw=0.9)
    text(bx[i] + bw[i] / 2, RY + RH - 0.15, t, weight="bold")
    for j, (ln, col) in enumerate(lines):
        text(bx[i] + bw[i] / 2, RY + RH - 0.35 - j * 0.18, ln, size=SMALL, color=col,
             weight="bold" if i == 2 else "normal")
    if i < 2:
        arrow((bx[i] + bw[i], RY + RH / 2), (bx[i + 1], RY + RH / 2), color=NOV_EDGE, lw=1.0)

arrow((sx[0] + 0.40, SY), (sx[0] + 0.40, RY + RH), color=NOV_EDGE, lw=1.0)
text(sx[0] + 0.47, (SY + RY + RH) / 2, "groups", size=6.5, ha="left", color=NOV_EDGE)
# final pair verdicts (after S4) feed the score
mid = (SY + RY + RH) / 2
ax.plot([sx[3] + SW / 2, sx[3] + SW / 2, bx[1] + 1.30], [SY, mid, mid], color=NOV_EDGE, lw=1.0, zorder=3)
arrow((bx[1] + 1.30, mid), (bx[1] + 1.30, RY + RH), color=NOV_EDGE, lw=1.0)
text(sx[2] + 0.10, mid + 0.01, "pair verdicts", size=6.5, color=NOV_EDGE, ha="left", va="bottom")

# ───────────────────────── bottom right: ⑤ temporal KG ───────────────────────────
x5, w5 = 5.38, 1.72
module(x5, BY, w5, BH, "5", "Temporal KG")
box(x5 + 0.10, BY + 1.07, w5 - 0.20, 1.07)
text(x5 + w5 / 2, BY + 1.97, "Neo4j, event-centric", weight="bold", size=SMALL)
# mini graph schema
cx, cy = x5 + w5 / 2, BY + 1.50
nodes = {"Event": (cx, cy), "Entity": (cx - 0.45, cy + 0.20), "Article": (cx + 0.45, cy + 0.20),
         "Time": (cx - 0.45, cy - 0.30), "Claim": (cx + 0.45, cy - 0.30)}
for (a, b) in [("Event", "Entity"), ("Event", "Article"), ("Event", "Time"), ("Claim", "Event")]:
    ax.plot(*zip(nodes[a], nodes[b]), color=GREY_EDGE, lw=0.7, zorder=4)
for n, (nx, ny) in nodes.items():
    hl = n in ("Event", "Claim")
    box(nx - 0.22, ny - 0.085, 0.44, 0.17, fill=NOV_FILL if hl else "white",
        edge=NOV_EDGE if hl else GREY_EDGE, lw=0.6, r=0.08, z=5)
    text(nx, ny, n, size=6.5, weight="bold" if hl else "normal")

box(x5 + 0.10, BY + 0.57, w5 - 0.20, 0.42)
text(x5 + w5 / 2, BY + 0.85, "Competency queries", weight="bold", size=SMALL)
text(x5 + w5 / 2, BY + 0.67, "CQ1–CQ5 (Cypher)", size=SMALL)
box(x5 + 0.10, BY + 0.08, w5 - 0.20, 0.42)
text(x5 + w5 / 2, BY + 0.36, "Evaluation", weight="bold", size=SMALL)
text(x5 + w5 / 2, BY + 0.18, "P/R/F1 ablations · κ", size=SMALL)

# ③ → ⑤ (events, entities, intervals) and ④ → ⑤ (verdicts)
arrow((x3 + 1.40, TY), (x3 + 1.40, BY + BH), lw=1.2)
text(x3 + 1.34, (TY + BY + BH) / 2 + 0.06, "graph load", size=SMALL, ha="right")
ax.plot([bx[2] + bw[2], 5.31, 5.31], [RY + RH / 2, RY + RH / 2, BY + 1.20], color=INK, lw=1.2, zorder=3)
arrow((5.31, BY + 1.20), (x5 + 0.10, BY + 1.20), lw=1.2)

out = Path(__file__).with_suffix("")
fig.savefig(f"{out}.pdf")
fig.savefig(f"{out}.png", dpi=300)
print(f"wrote {out}.pdf / .png")
