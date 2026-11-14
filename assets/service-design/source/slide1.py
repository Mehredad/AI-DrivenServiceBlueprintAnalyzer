"""Slide 1: service design explained through coffee (commodity -> transformation)."""
import sys

W, H = 1920, 1080
INK = "#1F2933"
MUTED = "#52606D"
BROWN = "#6B3E26"
BROWN_D = "#3E2316"
CARAMEL = "#C69C6D"
CREAM = "#F6EBDD"
TEAL = "#0F766E"
BLUE = "#3354C4"
CORAL = "#E4572E"

defs = f"""
<defs>
  <linearGradient id="rise" x1="0" y1="1" x2="1" y2="0">
    <stop offset="0" stop-color="{CARAMEL}" stop-opacity="0.10"/>
    <stop offset="1" stop-color="{TEAL}" stop-opacity="0.22"/>
  </linearGradient>
  <linearGradient id="loop" x1="1" y1="0" x2="0" y2="0">
    <stop offset="0" stop-color="{TEAL}"/>
    <stop offset="0.5" stop-color="{BLUE}"/>
    <stop offset="1" stop-color="{CORAL}"/>
  </linearGradient>
  <marker id="ah" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
    <path d="M0,0 L10,5 L0,10 z" fill="{MUTED}"/>
  </marker>
  <marker id="ahLoop" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="4" markerHeight="4" orient="auto">
    <path d="M0,0 L10,5 L0,10 z" fill="{CORAL}"/>
  </marker>
  <g id="bean">
    <ellipse rx="30" ry="42" fill="{BROWN}"/>
    <ellipse rx="22" ry="34" cx="-6" cy="-4" fill="#8A5636" opacity="0.6"/>
    <path d="M2,-38 C-14,-14 16,12 0,38" stroke="{BROWN_D}" stroke-width="6" fill="none" stroke-linecap="round"/>
  </g>
  <g id="cycle">
    <circle r="22" fill="#fff" stroke="{TEAL}" stroke-width="3"/>
    <path d="M-10,-4 A11,11 0 1 1 -4,9" fill="none" stroke="{TEAL}" stroke-width="3.5" stroke-linecap="round"/>
    <path d="M-15,-9 L-9,0 L-3,-8 z" fill="{TEAL}"/>
  </g>
</defs>
"""

# ---------- icons (each drawn around 0,0, ~230px box) ----------
beans = f"""
<g>
  <ellipse cx="0" cy="92" rx="120" ry="14" fill="{INK}" opacity="0.08"/>
  <use href="#bean" transform="translate(-62,52) rotate(-35)"/>
  <use href="#bean" transform="translate(4,58) rotate(15)"/>
  <use href="#bean" transform="translate(68,48) rotate(60)"/>
  <use href="#bean" transform="translate(-28,-12) rotate(-70)"/>
  <use href="#bean" transform="translate(38,-16) rotate(25)"/>
  <use href="#bean" transform="translate(4,-74) rotate(-10)"/>
</g>"""

goods = f"""
<g>
  <ellipse cx="0" cy="96" rx="125" ry="14" fill="{INK}" opacity="0.08"/>
  <!-- bag -->
  <path d="M-118,-62 L-18,-62 L-10,90 L-126,90 z" fill="{CARAMEL}"/>
  <path d="M-118,-62 L-108,-86 L-96,-70 L-84,-86 L-72,-70 L-60,-86 L-48,-70 L-36,-86 L-24,-70 L-18,-62 z" fill="#B0845A"/>
  <rect x="-108" y="-10" width="84" height="70" rx="10" fill="{CREAM}"/>
  <use href="#bean" transform="translate(-66,25) rotate(20) scale(0.55)"/>
  <!-- cup -->
  <path d="M12,-40 L112,-40 L98,92 L26,92 z" fill="#FFFFFF" stroke="{INK}" stroke-width="4" stroke-linejoin="round"/>
  <rect x="4" y="-60" width="116" height="22" rx="8" fill="{BROWN}"/>
  <rect x="20" y="-72" width="84" height="14" rx="6" fill="{BROWN_D}"/>
  <path d="M20,10 L104,10 L99,54 L25,54 z" fill="{BROWN}"/>
  <circle cx="62" cy="32" r="10" fill="{CREAM}"/>
  <!-- steam -->
  <path d="M44,-84 C34,-100 56,-108 44,-126" stroke="{MUTED}" stroke-width="4" fill="none" stroke-linecap="round" opacity="0.6"/>
  <path d="M74,-84 C64,-100 86,-108 74,-126" stroke="{MUTED}" stroke-width="4" fill="none" stroke-linecap="round" opacity="0.6"/>
</g>"""

awning = "".join(
    f'<path d="M{-120+i*30},-58 L{-90+i*30},-58 L{-90+i*30},-34 A15,15 0 0 1 {-120+i*30},-34 z" '
    f'fill="{CORAL if i % 2 == 0 else "#FFFFFF"}" stroke="{INK}" stroke-width="3"/>'
    for i in range(8)
)
shop = f"""
<g>
  <ellipse cx="0" cy="104" rx="140" ry="14" fill="{INK}" opacity="0.08"/>
  <rect x="-112" y="-40" width="224" height="140" fill="{CREAM}" stroke="{INK}" stroke-width="4"/>
  <rect x="-100" y="-110" width="200" height="50" rx="8" fill="{BROWN}"/>
  <text x="0" y="-76" text-anchor="middle" font-family="Inter" font-weight="800" font-size="28" fill="{CREAM}" letter-spacing="4">CAFÉ</text>
  {awning}
  <rect x="-92" y="-4" width="104" height="70" rx="4" fill="#DDEBF2" stroke="{INK}" stroke-width="3"/>
  <path d="M-58,24 L-24,24 L-28,52 L-54,52 z" fill="#fff" stroke="{INK}" stroke-width="3"/>
  <path d="M-24,30 a8,8 0 0 1 0,14" stroke="{INK}" stroke-width="3" fill="none"/>
  <rect x="32" y="0" width="58" height="100" rx="4" fill="{BROWN}" stroke="{INK}" stroke-width="3"/>
  <circle cx="44" cy="54" r="4" fill="{CREAM}"/>
  <rect x="-92" y="72" width="104" height="10" rx="3" fill="{CARAMEL}"/>
</g>"""

digital = f"""
<g>
  <ellipse cx="0" cy="112" rx="110" ry="12" fill="{INK}" opacity="0.08"/>
  <rect x="-60" y="-104" width="120" height="212" rx="20" fill="{INK}"/>
  <rect x="-50" y="-86" width="100" height="176" rx="10" fill="#EEF2FF"/>
  <rect x="-18" y="-98" width="36" height="6" rx="3" fill="#4B5563"/>
  <rect x="-40" y="-74" width="80" height="58" rx="8" fill="#fff"/>
  <path d="M-14,-62 L14,-62 L11,-30 L-11,-30 z" fill="{BROWN}"/>
  <rect x="-17" y="-68" width="34" height="8" rx="3" fill="{BROWN_D}"/>
  <rect x="-40" y="-6" width="80" height="22" rx="11" fill="{TEAL}"/>
  <text x="0" y="10" text-anchor="middle" font-family="Inter" font-weight="700" font-size="13" fill="#fff">Order ready</text>
  <g fill="#F2B705">
    <path d="M-30,32 l4,8 9,1 -7,6 2,9 -8,-5 -8,5 2,-9 -7,-6 9,-1z"/>
    <path d="M0,32 l4,8 9,1 -7,6 2,9 -8,-5 -8,5 2,-9 -7,-6 9,-1z"/>
    <path d="M30,32 l4,8 9,1 -7,6 2,9 -8,-5 -8,5 2,-9 -7,-6 9,-1z" opacity="0.35"/>
  </g>
  <rect x="-40" y="64" width="80" height="12" rx="6" fill="{BLUE}" opacity="0.25"/>
  <!-- floating touchpoints -->
  <g transform="translate(-102,-50)">
    <circle r="28" fill="#fff" stroke="{BLUE}" stroke-width="3"/>
    <path d="M0,-14 a10,10 0 0 1 10,10 c0,9 -10,20 -10,20 s-10,-11 -10,-20 a10,10 0 0 1 10,-10z" fill="{CORAL}"/>
    <circle cy="-4" r="4" fill="#fff"/>
  </g>
  <g transform="translate(104,-20)">
    <circle r="28" fill="#fff" stroke="{BLUE}" stroke-width="3"/>
    <path d="M-14,-2 a20,20 0 0 1 28,0 M-8,5 a11,11 0 0 1 16,0" stroke="{BLUE}" stroke-width="4" fill="none" stroke-linecap="round"/>
    <circle cy="12" r="3.5" fill="{BLUE}"/>
  </g>
  <g transform="translate(96,64)">
    <circle r="28" fill="#fff" stroke="{BLUE}" stroke-width="3"/>
    <rect x="-15" y="-10" width="30" height="20" rx="4" fill="none" stroke="{TEAL}" stroke-width="3.5"/>
    <rect x="-15" y="-4" width="30" height="5" fill="{TEAL}"/>
  </g>
</g>"""

person = lambda x, c: (f'<g transform="translate({x},0)"><circle cx="0" cy="-44" r="18" fill="{c}"/>'
                       f'<path d="M-30,20 C-30,-14 30,-14 30,20 z" fill="{c}"/></g>')
workplace = f"""
<g>
  <ellipse cx="0" cy="104" rx="150" ry="14" fill="{INK}" opacity="0.08"/>
  {person(-92, TEAL)}
  {person(96, BLUE)}
  <!-- table -->
  <rect x="-140" y="20" width="280" height="14" rx="5" fill="{BROWN}"/>
  <rect x="-110" y="34" width="10" height="66" fill="{BROWN_D}"/>
  <rect x="100" y="34" width="10" height="66" fill="{BROWN_D}"/>
  <!-- laptops -->
  <path d="M-66,18 L-60,-46 L6,-46 L0,18 z" fill="{INK}"/>
  <path d="M-56,-38 L-1,-38 L-6,10 L-61,10 z" fill="#C7D2FE"/>
  <rect x="-74" y="14" width="86" height="8" rx="3" fill="#4B5563"/>
  <rect x="-48" y="-28" width="30" height="5" rx="2" fill="{BLUE}"/>
  <rect x="-48" y="-18" width="40" height="5" rx="2" fill="#fff"/>
  <rect x="-48" y="-8" width="22" height="5" rx="2" fill="#fff"/>
  <!-- cup -->
  <path d="M28,-14 L56,-14 L52,18 L32,18 z" fill="#fff" stroke="{INK}" stroke-width="3"/>
  <rect x="25" y="-20" width="34" height="8" rx="3" fill="{BROWN}"/>
  <!-- notebook / chat -->
  <g transform="translate(0,-96)">
    <rect x="-48" y="-24" width="96" height="44" rx="14" fill="#fff" stroke="{TEAL}" stroke-width="3"/>
    <path d="M-10,20 L0,34 L8,20 z" fill="#fff" stroke="{TEAL}" stroke-width="3" stroke-linejoin="round"/>
    <rect x="-12" y="18" width="22" height="5" fill="#fff"/>
    <circle cx="-20" cy="-2" r="5" fill="{TEAL}"/><circle cx="0" cy="-2" r="5" fill="{TEAL}"/><circle cx="20" cy="-2" r="5" fill="{TEAL}"/>
  </g>
</g>"""

stages = [
    ("Commodity", "Coffee beans", beans),
    ("Goods", "Coffee products", goods),
    ("Services", "Coffee shops", shop),
    ("Experiences", "Digital touchpoints", digital),
    ("Transformation", "Cafés become workplaces", workplace),
]
xs = [215, 590, 960, 1330, 1705]
ys = [650, 590, 530, 470, 410]  # icon centre: ascending = more value

body = []
ys = [540] * 5
for i, (t, sub, icon) in enumerate(stages):
    x, y = xs[i], ys[i]
    body.append(f'<circle cx="{x}" cy="{y}" r="138" fill="#FFFFFF"/>')
    body.append(f'<circle cx="{x}" cy="{y}" r="138" fill="none" stroke="{[CARAMEL, CARAMEL, CORAL, BLUE, TEAL][i]}" stroke-width="4"/>')
    body.append(f'<g transform="translate({x},{y}) scale(0.86)">{icon}</g>')
    body.append(f'<text x="{x}" y="{y+196}" text-anchor="middle" font-family="Inter" font-weight="800" font-size="32" fill="{INK}">{t}</text>')
    body.append(f'<text x="{x}" y="{y+232}" text-anchor="middle" font-family="Inter" font-weight="500" font-size="22" fill="{MUTED}">{sub}</text>')
    if i < 4:
        body.append(f'<path d="M{x+150},{y} L{xs[i+1]-158},{y}" stroke="{MUTED}" stroke-width="6" fill="none" stroke-linecap="round" marker-end="url(#ah)"/>')

body.append(f'<text x="960" y="920" text-anchor="middle" font-family="Inter" font-weight="700" font-size="30" fill="{INK}">Continuously evolving through <tspan fill="{TEAL}">Service Design</tspan></text>')

# title
body.append(f'<text x="80" y="104" font-family="Inter Display, Inter" font-weight="800" font-size="60" fill="{INK}">What is Service Design?</text>')
body.append(f'<text x="80" y="152" font-family="Inter" font-weight="500" font-size="26" fill="{MUTED}">Designing how value reaches people, from a raw commodity to a transformed everyday experience.</text>')

svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">{defs}{"".join(body)}</svg>'
open(sys.argv[1], "w").write(svg)
