"""Slide 2: service design in a complex digital public service (NHS App)."""
import sys

W, H = 1920, 1080
INK = "#1F2933"
MUTED = "#52606D"
BLUE = "#2F5BD3"
BLUE_L = "#EAF0FD"
TEAL = "#0F766E"
TEAL_L = "#E3F4F1"
CORAL = "#D9532B"
CORAL_L = "#FCEDE6"
PURPLE = "#8B6CE0"
PURPLE_L = "#F0EBFB"
F = "Inter"
FG = "#FFFFFF"
FG2 = "#D5DBE1"
PURPLE_T = "#C4B5FD"
LIGHT = {BLUE: "#9DB8FF", TEAL: "#5EEAD4", CORAL: "#FFA07F"}

out = []
add = out.append


def text(x, y, s, size=18, weight=500, fill=INK, anchor="start", extra=""):
    add(f'<text x="{x}" y="{y}" font-family="{F}" font-size="{size}" font-weight="{weight}" '
        f'fill="{fill}" text-anchor="{anchor}" {extra}>{s}</text>')


def chip(x, y, w, h, lines, stroke, fill, size=17, weight=600):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" stroke="{stroke}" stroke-width="2.5"/>')
    lh = size * 1.25
    y0 = y + h / 2 - (len(lines) - 1) * lh / 2 + size * 0.35
    for i, ln in enumerate(lines):
        text(x + w / 2, y0 + i * lh, ln, size, weight, INK, "middle")


defs = f"""
<defs>
  <marker id="ah" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
    <path d="M0,0 L10,5 L0,10 z" fill="{FG2}"/></marker>
  <marker id="ahT" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse">
    <path d="M0,0 L10,5 L0,10 z" fill="{TEAL}"/></marker>
  <marker id="ahP" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="4" markerHeight="4" orient="auto">
    <path d="M0,0 L10,5 L0,10 z" fill="{PURPLE}"/></marker>
  <linearGradient id="band" x1="0" x2="1">
    <stop offset="0" stop-color="{CORAL}" stop-opacity="0.08"/>
    <stop offset="1" stop-color="{TEAL}" stop-opacity="0.18"/></linearGradient>
</defs>"""

# ---------------- title ----------------
text(60, 82, "Service Design in digital public services: the NHS App", 50, 800, FG, extra='font-family="Inter Display, Inter"')
text(60, 124, "One app on the surface; a living system of people, organisations, technology and policy underneath, designed and redesigned as one service.", 22, 500, FG2)

LX, LW = 60, 230          # lane label column
CX0, CX1 = 310, 1660      # content columns
RX0 = 1690                # evolution column

# ---------------- value chain row ----------------
icons = {
    "res": f'''<path d="M-22,-30 L-22,0 a22,22 0 0 0 44,0 L22,-30" fill="none" stroke="{INK}" stroke-width="6" stroke-linecap="round"/>
        <path d="M0,22 L0,30 a14,14 0 0 0 28,0 L28,8" fill="none" stroke="{INK}" stroke-width="6" stroke-linecap="round"/>
        <circle cx="28" cy="0" r="10" fill="{CORAL}"/><circle cx="-22" cy="-32" r="5" fill="{INK}"/><circle cx="22" cy="-32" r="5" fill="{INK}"/>''',
    "prod": f'''<g transform="rotate(-35)"><rect x="-34" y="-14" width="68" height="28" rx="14" fill="#fff" stroke="{INK}" stroke-width="4"/>
        <path d="M0,-14 L-20,-14 a14,14 0 0 0 0,28 L0,14 z" fill="{CORAL}"/></g>
        <circle cx="22" cy="24" r="14" fill="{BLUE}"/><path d="M14,24 L30,24" stroke="#fff" stroke-width="4"/>''',
    "svc": f'''<rect x="-34" y="-22" width="68" height="56" fill="#fff" stroke="{INK}" stroke-width="4"/>
        <path d="M-42,-20 L0,-44 L42,-20" fill="none" stroke="{INK}" stroke-width="4" stroke-linejoin="round"/>
        <path d="M-6,-14 h12 v10 h10 v12 h-10 v10 h-12 v-10 h-10 v-12 h10z" fill="{BLUE}"/><rect x="-8" y="18" width="16" height="16" fill="{INK}"/>''',
    "dig": f'''<rect x="-26" y="-42" width="52" height="84" rx="9" fill="{INK}"/><rect x="-21" y="-34" width="42" height="68" rx="4" fill="#fff"/>
        <rect x="-16" y="-29" width="32" height="11" rx="3" fill="{BLUE}"/>
        <rect x="-16" y="-14" width="14" height="14" rx="3" fill="{TEAL}"/><rect x="2" y="-14" width="14" height="14" rx="3" fill="{CORAL}"/>
        <rect x="-16" y="4" width="14" height="14" rx="3" fill="{PURPLE}"/><rect x="2" y="4" width="14" height="14" rx="3" fill="{BLUE}"/>''',
    "trans": f'''<path d="M-40,-4 L0,-40 L40,-4 L40,38 L-40,38 z" fill="#fff" stroke="{INK}" stroke-width="4" stroke-linejoin="round"/>
        <path d="M0,28 C-30,8 -22,-18 0,-6 C22,-18 30,8 0,28 z" fill="{TEAL}"/>''',
}
chain = [
    ("res", "Health resources", "Clinical knowledge, workforce, data", CORAL),
    ("prod", "Health products", "Medicines, tests, vaccines", CORAL),
    ("svc", "Care services", "GP, pharmacy, hospital, 111", BLUE),
    ("dig", "Digital experience", "NHS App as a front door", BLUE),
    ("trans", "Transformation", "People manage health, anywhere", TEAL),
]
cy = 204
xs = [CX0 + 135 + i * 270 for i in range(5)]
add(f'<rect x="{CX0}" y="150" width="{CX1-CX0}" height="172" rx="40" fill="url(#band)"/>')
for i, (k, t, s, c) in enumerate(chain):
    x = xs[i]
    add(f'<circle cx="{x}" cy="{cy}" r="44" fill="#fff" stroke="{c}" stroke-width="4"/>')
    add(f'<g transform="translate({x},{cy}) scale(0.66)">{icons[k]}</g>')
    text(x, cy + 76, t, 20, 800, FG, "middle")
    text(x, cy + 100, s, 15, 500, FG2, "middle")
    if i < 4:
        add(f'<path d="M{x+56},{cy} L{xs[i+1]-60},{cy}" stroke="{FG2}" stroke-width="4" marker-end="url(#ah)" stroke-linecap="round"/>')
text(LX, cy + 20, "VALUE CHAIN", 17, 800, FG, extra='letter-spacing="2"')
text(LX, cy + 46, "from resources", 16, 500, FG2)
text(LX, cy + 68, "to transformation", 16, 500, FG2)

# ---------------- blueprint lanes ----------------
lanes = [
    ("PEOPLE", ["Who the service", "is for and with"], 340, 76, FG, "#FFFFFF"),
    ("FRONTSTAGE", ["What users see", "and do in the app"], 440, 96, BLUE, BLUE_L),
    ("BACKSTAGE", ["Systems and teams", "that make it work"], 584, 96, TEAL, TEAL_L),
    ("ENABLERS", ["Policy, standards", "and governance"], 704, 96, CORAL, CORAL_L),
]
for name, sub, y, h, c, fl in lanes:
    add(f'<rect x="{LX-10}" y="{y-10}" width="{CX1-LX+20}" height="{h+20}" rx="18" fill="{c}" opacity="{0.0 if fl=="#FFFFFF" else 0.16}"/>')
    add(f'<rect x="{LX-10}" y="{y-10}" width="8" height="{h+20}" rx="4" fill="{c}"/>')
    text(LX + 12, y + h / 2 - 8, name, 17, 800, LIGHT.get(c, FG), extra='letter-spacing="2"')
    text(LX + 12, y + h / 2 + 14, sub[0], 15, 500, FG2)
    text(LX + 12, y + h / 2 + 32, sub[1], 15, 500, FG2)

# people
people = ["Patients", "Carers", "Practice staff", "Clinicians", "Pharmacists", "Hospital teams", "Product teams"]
pw, gap = 178, (CX1 - CX0 - 7 * 178) / 6
for i, p in enumerate(people):
    x = CX0 + i * (pw + gap)
    add(f'<rect x="{x}" y="342" width="{pw}" height="72" rx="36" fill="#fff" stroke="{INK}" stroke-width="2"/>')
    add(f'<circle cx="{x+34}" cy="368" r="9" fill="{[BLUE,BLUE,TEAL,TEAL,TEAL,TEAL,PURPLE][i]}"/>')
    add(f'<path d="M{x+18},{396} c0,-20 32,-20 32,0 z" fill="{[BLUE,BLUE,TEAL,TEAL,TEAL,TEAL,PURPLE][i]}"/>')
    text(x + 58, 384, p, 16, 600)

cols = 7
cw = 178
cg = (CX1 - CX0 - cols * cw) / (cols - 1)
front = [["Log in", "securely"], ["Book &amp; manage", "appointments"], ["Order repeat", "prescriptions"],
         ["View record &amp;", "test results"], ["Messages &amp;", "notifications"], ["Manage hospital", "referrals"],
         ["Vaccinations", "&amp; screening"]]
back = [["NHS login", "identity checks"], ["GP clinical", "system APIs"], ["Electronic", "Prescription Service"],
        ["Records &amp;", "interoperability"], ["Messaging &amp;", "notify services"], ["e-Referral", "Service"],
        ["National", "immunisation data"]]
for i in range(cols):
    x = CX0 + i * (cw + cg)
    chip(x, 444, cw, 88, front[i], BLUE, "#FFFFFF")
    chip(x, 588, cw, 88, back[i], TEAL, "#FFFFFF")
    mx = x + cw / 2
    add(f'<path d="M{mx},{536} L{mx},{582}" stroke="{TEAL}" stroke-width="3" marker-start="url(#ahT)" marker-end="url(#ahT)"/>')
# line of visibility
add(f'<path d="M{LX+230},{558} L{CX1},{558}" stroke="{FG}" stroke-width="2" stroke-dasharray="10 8" opacity="0.55"/>')

text(LX + 12, 564, "LINE OF VISIBILITY", 14, 800, FG2, "start", 'letter-spacing="2"')

enablers = ["NHS &amp; GDS service standards", "Clinical safety (DCB0129 / 0160)", "Accessibility (WCAG 2.2 AA)",
            "Data protection &amp; consent", "Interoperability (FHIR APIs)", "Digital inclusion",
            "Commissioning &amp; funding", "Cyber security"]
ex, ey = CX0, 710
for e in enablers:
    w = len(e.replace("&amp;", "&")) * 9.2 + 36
    if ex + w > CX1:
        ex, ey = CX0, ey + 44
    add(f'<rect x="{ex}" y="{ey}" width="{w}" height="36" rx="18" fill="#fff" stroke="{CORAL}" stroke-width="2"/>')
    text(ex + w / 2, ey + 24, e, 16, 600, INK, "middle")
    ex += w + 12

# ---------------- outcomes ----------------
oy = 836
add(f'<rect x="{LX-10}" y="{oy}" width="{CX1-LX+20}" height="96" rx="18" fill="#FFFFFF" fill-opacity="0.08" stroke="#FFFFFF" stroke-opacity="0.35" stroke-width="2"/>')
text(LX + 12, oy + 42, "OUTCOMES", 17, 800, "#FFFFFF", extra='letter-spacing="2"')
text(LX + 12, oy + 66, "what changes", 15, 500, "#CBD2D9")
outs = [("Easier, fairer access", "for patients and carers"), ("Less admin", "for practices and pharmacies"),
        ("Safer, joined-up care", "through shared records"), ("Three shifts", "analogue → digital, hospital →"),
        ]
outs[-1] = ("Three shifts", "analogue → digital · hospital → community · sickness → prevention")
ox = CX0
for i, (a, b) in enumerate(outs):
    text(ox, oy + 42, a, 19, 800, "#FFFFFF")
    text(ox, oy + 68, b, 15, 500, "#CBD2D9")
    ox += 280 if i < 2 else 300
    if i < 3:
        add(f'<rect x="{ox-24}" y="{oy+22}" width="2" height="54" fill="#52606D"/>')

# ---------------- continuous evolution column ----------------
RW = W - 40 - RX0
add(f'<rect x="{RX0}" y="156" width="{RW}" height="776" rx="24" fill="{PURPLE}" fill-opacity="0.18" stroke="{PURPLE}" stroke-width="2.5"/>')
text(RX0 + RW / 2, 196, "CONTINUOUS", 17, 800, PURPLE_T, "middle", 'letter-spacing="2"')
text(RX0 + RW / 2, 218, "EVOLUTION", 17, 800, PURPLE_T, "middle", 'letter-spacing="2"')
phases = ["Discover", "Alpha", "Beta", "Live", "Iterate"]
cx_r = RX0 + RW / 2
py0, pstep = 262, 74
for i, ph in enumerate(phases):
    y = py0 + i * pstep
    add(f'<rect x="{RX0+22}" y="{y}" width="{RW-44}" height="46" rx="23" fill="#fff" stroke="{PURPLE}" stroke-width="2"/>')
    text(cx_r, y + 30, ph, 18, 700, INK, "middle")
    if i < 4:
        add(f'<path d="M{cx_r},{y+48} L{cx_r},{y+pstep-4}" stroke="{PURPLE}" stroke-width="3" marker-end="url(#ahP)"/>')
# loop back from Iterate to Discover
ly1, ly2 = py0 + 4 * pstep + 23, py0 + 23
add(f'<path d="M{RX0+22},{ly1} C{RX0-6},{ly1} {RX0-6},{ly2} {RX0+18},{ly2}" stroke="{PURPLE}" stroke-width="3" fill="none" marker-end="url(#ahP)"/>')
text(cx_r, 664, "Signals that", 15, 700, PURPLE_T, "middle")
text(cx_r, 684, "feed the loop", 15, 700, PURPLE_T, "middle")
signals = ["User research", "App analytics", "Ratings &amp; reviews", "Clinical incidents", "Staff feedback", "Policy change"]
for i, s in enumerate(signals):
    y = 702 + i * 36
    add(f'<rect x="{RX0+18}" y="{y}" width="{RW-36}" height="28" rx="14" fill="#fff"/>')
    text(cx_r, y + 19, s, 14, 600, INK, "middle")
# arrows from evolution column into blueprint
for y in (378, 488, 632, 752, 884):
    add(f'<path d="M{RX0-4},{y} L{CX1+16},{y}" stroke="{PURPLE}" stroke-width="3" marker-end="url(#ahP)" opacity="0.8"/>')

# footer
text(60, 1000, "Service design shapes the whole system, not only the screens, and keeps it evolving as needs, technology and policy change.", 22, 700, FG)
text(60, 1034, "Illustrative map. System names are examples of the kinds of national services an app like this depends on.", 16, 500, FG2)

svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">{defs}{"".join(out)}</svg>'
open(sys.argv[1], "w").write(svg)
