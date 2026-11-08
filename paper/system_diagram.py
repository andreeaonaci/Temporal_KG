"""System figure for the paper (IEEE figure*, 7.16 in wide, drawn at print size).

Run: python paper/system_diagram.py  ->  paper/system_diagram.{pdf,png}
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Ellipse, FancyArrowPatch, Polygon, Rectangle

plt.rcParams.update({
    "font.family": "Liberation Serif",  # metric-compatible with Times (IEEE body font)
    "mathtext.fontset": "custom",
    "mathtext.rm": "Liberation Serif",
    "mathtext.it": "Liberation Serif:italic",
    "mathtext.bf": "Liberation Serif:bold",
    "pdf.fonttype": 42,
})

W, H = 7.16, 3.16
K = "black"
G = "0.55"          # mid grey
LG = "0.88"         # light grey fill
ACC = "#1f4e8c"     # single accent: the novel module
RED, GRN = "#b42318", "#1e7b3c"
FS = 8

fig = plt.figure(figsize=(W, H))
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W)
ax.set_ylim(0, H)
ax.set_aspect("equal")
ax.axis("off")


def T(x, y, s, size=FS, ha="center", va="center", color=K, **kw):
    ax.text(x, y, s, fontsize=size, ha=ha, va=va, color=color, zorder=10, **kw)


def A(p, q, color=K, lw=0.8, ms=6, conn="arc3", ls="-", style="-|>"):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=ms, color=color, lw=lw,
                                 connectionstyle=conn, ls=ls, shrinkA=0, shrinkB=0, zorder=6))


def L(xs, ys, color=K, lw=0.8, ls="-", z=5):
    ax.plot(xs, ys, color=color, lw=lw, ls=ls, zorder=z, solid_capstyle="round")


def R(x, y, w, h, fc="white", ec=K, lw=0.8, ls="-", z=3):
    ax.add_patch(Rectangle((x, y), w, h, fc=fc, ec=ec, lw=lw, ls=ls, zorder=z))


def check(x, y, s=0.05, color=GRN):
    L([x - s, x - s * 0.3, x + s], [y, y - s * 0.7, y + s * 0.8], color=color, lw=1.4, z=9)


def cross(x, y, s=0.045, color=RED):
    L([x - s, x + s], [y - s, y + s], color=color, lw=1.4, z=9)
    L([x - s, x + s], [y + s, y - s], color=color, lw=1.4, z=9)


def doc(x, y, w=0.24, h=0.30, lines=4, fc="white"):
    R(x, y, w, h, fc=fc, z=4)
    for i in range(lines):
        L([x + 0.04, x + w - 0.04 - (0.05 if i == lines - 1 else 0)],
          [y + h - 0.07 - i * 0.06] * 2, color=G, lw=0.6, z=5)


# ───────────────────────────── top: pipeline ─────────────────────────────
YC = 2.70        # icon centre line
YL = 2.30        # label line
xs = [0.42, 1.28, 2.10, 2.98, 3.90, 4.92, 5.92, 6.72]

# 1 sources: stacked documents
for k in range(3):
    doc(xs[0] - 0.17 + k * 0.06, YC - 0.20 + k * 0.05, lines=3)
T(xs[0], YL, "GDELT, RSS")

# 2 full text + MT
doc(xs[1] - 0.20, YC - 0.17)
R(xs[1] + 0.02, YC - 0.10, 0.22, 0.17, fc=LG, z=6)
T(xs[1] + 0.13, YC - 0.015, "EN", size=7, weight="bold")
T(xs[1], YL, "scrape, MT")

# 3 relevance filter: funnel
ax.add_patch(Polygon([(xs[2] - 0.20, YC + 0.17), (xs[2] + 0.20, YC + 0.17), (xs[2] + 0.05, YC - 0.03),
                      (xs[2] + 0.05, YC - 0.18), (xs[2] - 0.05, YC - 0.13), (xs[2] - 0.05, YC - 0.03)],
                     closed=True, fc="white", ec=K, lw=0.8, zorder=4))
T(xs[2], YL, r"CN $\wedge$ RO")

# 4 extraction: sentence with typed spans
x0 = xs[3] - 0.30
for (a, b, tag) in [(0.00, 0.16, "e"), (0.22, 0.40, "v"), (0.46, 0.60, r"\tau")]:
    R(x0 + a, YC - 0.03, b - a, 0.07, fc=LG, ec="none", z=4)
    L([x0 + a, x0 + b], [YC - 0.05] * 2, lw=0.8)
    T(x0 + (a + b) / 2, YC + 0.12, f"${tag}$", size=FS)
L([x0, x0 + 0.60], [YC - 0.15] * 2, color=G, lw=0.6)
T(xs[3], YL, "IE, TIMEX3")

# 5 ontology: small tree
rx, ry = xs[4], YC + 0.13
for cx in (-0.20, 0.0, 0.20):
    L([rx, rx + cx], [ry, YC - 0.12], lw=0.7)
    ax.add_patch(Circle((rx + cx, YC - 0.12), 0.045, fc="white", ec=K, lw=0.8, zorder=6))
ax.add_patch(Circle((rx, ry), 0.05, fc=K, ec=K, zorder=6))
T(xs[4], YL, "ontology")

# 6 gated verification (novel): four gates
gx, gw, gh = xs[5] - 0.36, 0.72, 0.40
R(gx, YC - gh / 2, gw, gh, fc="#e8eef7", ec=ACC, lw=1.2, z=3)
for i in range(4):
    bx = gx + 0.12 + i * 0.16
    R(bx, YC - 0.12, 0.05, 0.24, fc=ACC, ec="none", z=5)
L([gx + 0.04, gx + gw - 0.04], [YC, YC], color=ACC, lw=0.8, z=4)
T(xs[5], YL, "gated verification", color=ACC, weight="bold")

# 7 temporal KG
pts = {"a": (-0.20, 0.08), "b": (0.0, 0.17), "c": (0.20, 0.06), "d": (-0.10, -0.14), "e": (0.14, -0.13)}
for p, q in ["ab", "bc", "ad", "de", "ce", "bd"]:
    L([xs[6] + pts[p][0], xs[6] + pts[q][0]], [YC + pts[p][1], YC + pts[q][1]], lw=0.7, z=4)
for name, (dx, dy) in pts.items():
    ax.add_patch(Circle((xs[6] + dx, YC + dy), 0.045, fc=ACC if name == "b" else "white",
                        ec=K, lw=0.8, zorder=6))
T(xs[6], YL, "temporal KG")

# 8 competency queries: magnifier
ax.add_patch(Circle((xs[7] - 0.03, YC + 0.04), 0.11, fc="white", ec=K, lw=1.0, zorder=5))
L([xs[7] + 0.05, xs[7] + 0.16], [YC - 0.04, YC - 0.15], lw=1.8)
T(xs[7], YL, "CQ1–CQ5")

# arrows between stages
edges = [(0.62, 1.04), (1.52, 1.86), (2.30, 2.62), (3.34, 3.62), (4.18, gx), (gx + gw, 5.66), (6.18, 6.52)]
for a, b in edges:
    A((a, YC), (b, YC))
# extraction also loads the graph directly (bypass over the novel module)
L([xs[3], xs[3], 5.92, 5.92], [YC + 0.22, 3.02, 3.02, YC + 0.27], color=G, lw=0.7)
A((5.92, 3.02), (5.92, YC + 0.24), color=G)
T(4.45, 3.02, " events, entities, time ", size=7, color=G, backgroundcolor="white")

# ───────────────────────────── bottom: zoom on the novel module ─────────────────────────────
PY, PH = 0.05, 1.95
PX, PW = 0.06, W - 0.12
R(PX, PY, PW, PH, fc="none", ec=ACC, lw=0.8, ls=(0, (4, 2)), z=2)
L([gx, PX], [YL - 0.12, PY + PH], color=ACC, lw=0.6, ls=(0, (4, 2)), z=1)
L([gx + gw, PX + PW], [YL - 0.12, PY + PH], color=ACC, lw=0.6, ls=(0, (4, 2)), z=1)

cap_y = PY + 0.14
pw = [1.22, 1.30, 1.45, 1.55, 1.22]
gap = (PW - 0.10 - sum(pw)) / 4
px = [PX + 0.05]
for w in pw[:-1]:
    px.append(px[-1] + w + gap)
caps = ["(a) semantic merge", "(b) NLI disagreement", "(c) Allen gate",
        "(d) lifecycle check", "(e) publisher networks"]
for x, w, c in zip(px, pw, caps):
    T(x + w / 2, cap_y, c)
for i in range(4):
    A((px[i] + pw[i] + 0.01, 1.15), (px[i + 1] - 0.01, 1.15), color=ACC, lw=1.0, ms=7)
MY = 0.45  # line for the one math condition per panel

# (a) embedding space: two clusters -> groups
cx0 = px[0] + pw[0] / 2
for (ox, oy, lab) in [(-0.27, 0.12, "$G_1$"), (0.25, -0.12, "$G_2$")]:
    ax.add_patch(Ellipse((cx0 + ox, 1.20 + oy), 0.46, 0.34, fc="none", ec=ACC, lw=0.8, ls=(0, (3, 2)), zorder=4))
    for dx, dy in [(-0.10, 0.04), (0.02, 0.08), (0.09, -0.05), (-0.03, -0.07)]:
        ax.add_patch(Circle((cx0 + ox + dx, 1.20 + oy + dy), 0.025, fc=K, ec="none", zorder=6))
    T(cx0 + ox, 1.20 + oy + (0.25 if oy > 0 else -0.25), lab)
T(cx0, MY, r"$\cos(e_a,e_b)\geq\tau_m$")

# (b) two sentences, NLI both directions
cx1 = px[1] + pw[1] / 2
for dy, lab in [(0.30, "$s_a$"), (-0.30, "$s_b$")]:
    R(cx1 - 0.50, 1.15 + dy - 0.08, 0.38, 0.16, fc=LG, ec=K, lw=0.6)
    T(cx1 - 0.31, 1.15 + dy, lab)
ax.add_patch(Polygon([(cx1 + 0.22, 1.33), (cx1 + 0.40, 1.15), (cx1 + 0.22, 0.97), (cx1 + 0.04, 1.15)],
                     closed=True, fc="white", ec=K, lw=0.8, zorder=5))
T(cx1 + 0.22, 1.15, "NLI", size=7)
A((cx1 - 0.12, 1.45), (cx1 + 0.13, 1.25), lw=0.7, ms=5)
A((cx1 - 0.12, 0.85), (cx1 + 0.13, 1.05), lw=0.7, ms=5)
T(cx1, MY, r"$P_{\mathrm{contra}}\geq\tau_n$")

# (c) Allen gate: disjoint -> evolution, overlap -> contradiction
x0c = px[2] + 0.12
for row, (ia, ib, ok) in enumerate([((0.00, 0.40), (0.55, 0.95), True), ((0.00, 0.60), (0.35, 0.95), False)]):
    yy = 1.48 - row * 0.52
    R(x0c + ia[0], yy, ia[1] - ia[0], 0.07, fc=G, ec="none", z=5)
    R(x0c + ib[0], yy - 0.13, ib[1] - ib[0], 0.07, fc=ACC, ec="none", z=5)
    (check if ok else cross)(x0c + 1.15, yy - 0.01)
    T(x0c + 1.15, yy - 0.17, "evolution" if ok else "contradiction", size=6.5)
T(x0c - 0.06, 1.515, "$I_a$", size=7, ha="right")
T(x0c - 0.06, 1.385, "$I_b$", size=7, ha="right")
A((x0c, 0.66), (x0c + 0.85, 0.66), color=G, lw=0.6, ms=5)
T(x0c + 0.90, 0.66, "$t$", size=7, color=G, ha="left")
T(px[2] + pw[2] / 2, MY, r"$R(I_a,I_b)\in\{<,>,m,mi\}$")

# (d) lifecycle FSM with an illegal observed order
x0d = px[3] + 0.20
names = ["prop.", "signed", "ratif."]
for i, n in enumerate(names):
    ax.add_patch(Circle((x0d + i * 0.55, 1.30), 0.15, fc="white", ec=K, lw=0.8, zorder=5))
    T(x0d + i * 0.55, 1.30, n, size=6.5)
    if i < 2:
        A((x0d + i * 0.55 + 0.15, 1.30), (x0d + (i + 1) * 0.55 - 0.15, 1.30), lw=0.8, ms=5)
A((x0d + 1.10, 1.15), (x0d + 0.55, 1.15), color=RED, lw=0.9, ms=6, conn="arc3,rad=-0.6", ls=(0, (3, 1.5)))
cross(x0d + 0.825, 0.86)
T(x0d + 0.825, 0.70, "observed order", size=6.5, color=RED)
T(px[3] + pw[3] / 2, MY, r"$(q_i,q_{i+1})\in E_t$")

# (e) mirror domains collapse to one publisher network -> verdict
x0e = px[4] + 0.25
for i in range(3):
    R(x0e - 0.08, 1.55 - i * 0.22, 0.16, 0.13, fc="white", ec=K, lw=0.7)
    A((x0e + 0.08, 1.615 - i * 0.22), (x0e + 0.42, 1.40), lw=0.6, ms=4)
ax.add_patch(Circle((x0e + 0.52, 1.40), 0.10, fc=ACC, ec=K, lw=0.8, zorder=6))
T(x0e + 0.52, 1.40, r"$\nu$", size=8, color="white")
vy = 0.88
for i, mark in enumerate([check, None, cross]):
    vx = x0e - 0.12 + i * 0.38
    ax.add_patch(Circle((vx, vy), 0.10, fc="white", ec=K, lw=0.7, zorder=5))
    if mark:
        mark(vx, vy)
    else:
        T(vx, vy - 0.005, "?", size=9, weight="bold", color=G)
    T(vx, vy - 0.17, ["corrob.", "unverif.", "contested"][i], size=6.5)
T(px[4] + pw[4] / 2, MY, r"$\mathrm{div}(G)=|\{\nu(d)\}|$")

out = Path(__file__).with_suffix("")
fig.savefig(f"{out}.pdf")
fig.savefig(f"{out}.png", dpi=300)
print(f"wrote {out}.pdf / .png")
