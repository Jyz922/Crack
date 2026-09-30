"""Generate dark and light benchmark ranking, breakdown, and architecture SVG diagrams in mini-harness style.

Text and spacing are chosen to reduce overflow in the generated SVGs.
"""

import os
from pathlib import Path


def generate_benchmark_svg(dark_mode: bool = False) -> str:
    bg = "#0d1117" if dark_mode else "#ffffff"
    fg = "#f0f6fc" if dark_mode else "#1f2328"
    muted = "#8b949e" if dark_mode else "#59636e"
    border = "#30363d" if dark_mode else "#d1d9e0"
    panel = "#161b22" if dark_mode else "#f6f8fa"
    accent = "#58a6ff" if dark_mode else "#0969da"

    metrics = [
        ("Detection accuracy", "82.84%", "1,864 / 2,250"),
        ("Pun precision", "89.11%", "1,391 / 1,561"),
        ("Pun recall", "86.56%", "1,391 / 1,607"),
        ("Pun F1", "87.82%", "from reported precision and recall"),
        ("Negative controls classified ONE_SENSE_ONLY", "73.56%", "473 / 643"),
    ]
    rows = []
    for i, (label, value, count) in enumerate(metrics):
        y = 152 + i * 48
        rows.append(f"""
    <rect x="32" y="{y}" width="896" height="40" rx="6" fill="{panel}"/>
    <text x="50" y="{y+25}" fill="{fg}" font-size="14">{label}</text>
    <text x="700" y="{y+25}" fill="{accent}" font-size="14" font-weight="700" text-anchor="end">{value}</text>
    <text x="910" y="{y+25}" fill="{muted}" font-size="12" text-anchor="end">{count}</text>
""")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="960" height="470" viewBox="0 0 960 470" role="img" aria-labelledby="title description">
  <title id="title">CRACK reported SemEval run summary</title>
  <desc id="description">Reported classification metrics from a local SemEval-2017 Task 7 run. The run records are not included in a clean Git checkout; this is not a leaderboard comparison.</desc>
  <rect x="0.5" y="0.5" width="959" height="469" rx="14" fill="{bg}" stroke="{border}"/>
  <g font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif" font-variant-numeric="tabular-nums">
    <text x="32" y="42" fill="{accent}" font-size="12" font-weight="700" letter-spacing="1.4">REPORTED LOCAL RUN</text>
    <text x="32" y="82" fill="{fg}" font-size="26" font-weight="700">SemEval-2017 Task 7 · detection</text>
    <text x="32" y="110" fill="{muted}" font-size="13">Arithmetic checked against locally available records; model-call provenance is not independently verified.</text>
    {''.join(rows)}
    <text x="32" y="430" fill="{muted}" font-size="12">Not a state-of-the-art claim. See docs/benchmark_audit.md for limitations.</text>
  </g>
</svg>
"""


def generate_breakdown_svg(dark_mode: bool = False) -> str:
    bg = "#0d1117" if dark_mode else "#ffffff"
    fg = "#f0f6fc" if dark_mode else "#1f2328"
    muted = "#8b949e" if dark_mode else "#59636e"
    border = "#30363d" if dark_mode else "#d1d9e0"
    panel = "#161b22" if dark_mode else "#f6f8fa"
    accent = "#58a6ff" if dark_mode else "#0969da"
    warn = "#d29922" if dark_mode else "#9a6700"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="960" height="360" viewBox="0 0 960 360" role="img" aria-labelledby="title description">
  <title id="title">CRACK evaluation status</title>
  <desc id="description">The saved SemEval detection arithmetic is internally consistent but its run provenance is incomplete. The current curated corpus does not have a valid full-set score.</desc>
  <rect x="0.5" y="0.5" width="959" height="359" rx="14" fill="{bg}" stroke="{border}"/>
  <g font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif">
    <text x="32" y="42" fill="{accent}" font-size="12" font-weight="700" letter-spacing="1.4">EVALUATION STATUS</text>
    <text x="32" y="82" fill="{fg}" font-size="26" font-weight="700">Read scores with their evidence</text>
    <rect x="32" y="112" width="432" height="190" rx="10" fill="{panel}" stroke="{border}"/>
    <text x="56" y="150" fill="{fg}" font-size="17" font-weight="700">SemEval-2017 · 2,250 items</text>
    <text x="56" y="184" fill="{muted}" font-size="14">Detection counts and F1 arithmetic match</text>
    <text x="56" y="207" fill="{muted}" font-size="14">the local run records.</text>
    <text x="56" y="252" fill="{warn}" font-size="13" font-weight="700">Run records are not tracked by Git.</text>
    <text x="56" y="274" fill="{muted}" font-size="12">Model-call provenance remains unverified.</text>
    <rect x="496" y="112" width="432" height="190" rx="10" fill="{panel}" stroke="{border}"/>
    <text x="520" y="150" fill="{fg}" font-size="17" font-weight="700">Curated corpus · 60 items</text>
    <text x="520" y="184" fill="{muted}" font-size="14">Four outputs were copied; eight saved</text>
    <text x="520" y="207" fill="{muted}" font-size="14">outputs refer to different text.</text>
    <text x="520" y="252" fill="{warn}" font-size="13" font-weight="700">No full-corpus accuracy is reported.</text>
    <text x="520" y="274" fill="{muted}" font-size="12">Details: docs/benchmark_audit.md</text>
    <text x="32" y="334" fill="{muted}" font-size="12">Age and safety judgments are exploratory estimates, not validated child-safety guarantees.</text>
  </g>
</svg>
"""


def generate_architecture_svg(dark_mode: bool = False) -> str:
    if dark_mode:
        bg_card = "#0d1117"
        border_card = "#30363d"
        text_primary = "#f0f6fc"
        text_secondary = "#8b949e"
        text_muted = "#6e7681"
        line_divider = "#21262d"
        
        col_bg = "#161b22"
        col_border = "#30363d"
        item_bg = "#0d1117"
        item_border = "#21262d"
        
        c1_pill_bg = "#1f6feb33"
        c1_pill_text = "#58a6ff"
        c1_border = "#388bfd44"
        
        c2_pill_bg = "#a371f733"
        c2_pill_text = "#bc8cff"
        c2_border = "#8957e544"
        
        c3_pill_bg = "#23863633"
        c3_pill_text = "#3fb950"
        c3_border = "#2ea04344"
        
        fork_bg = "#f8514922"
        fork_text = "#ff7b72"
        fork_border = "#f8514955"
        
        banner_bg = "#161b22"
        banner_border = "#30363d"
        banner_pill_bg = "#238636"
        banner_pill_text = "#ffffff"
    else:
        bg_card = "#ffffff"
        border_card = "#e1e4e8"
        text_primary = "#1f2328"
        text_secondary = "#59636e"
        text_muted = "#656d76"
        line_divider = "#d1d9e0"
        
        col_bg = "#f6f8fa"
        col_border = "#d1d9e0"
        item_bg = "#ffffff"
        item_border = "#e1e4e8"
        
        c1_pill_bg = "#ddf4ff"
        c1_pill_text = "#0969da"
        c1_border = "#54aeff66"
        
        c2_pill_bg = "#fbefff"
        c2_pill_text = "#8250df"
        c2_border = "#c297ff66"
        
        c3_pill_bg = "#dafbe1"
        c3_pill_text = "#1a7f37"
        c3_border = "#4ac26b66"
        
        fork_bg = "#ffebe9"
        fork_text = "#cf222e"
        fork_border = "#ff818266"
        
        banner_bg = "#f6f8fa"
        banner_border = "#d1d9e0"
        banner_pill_bg = "#1a7f37"
        banner_pill_text = "#ffffff"

    svg_width = 1000
    svg_height = 730

    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{svg_width}" height="{svg_height}" viewBox="0 0 {svg_width} {svg_height}" role="img" aria-labelledby="arch-title arch-desc">
  <title id="arch-title">CRACK pipeline architecture (L0-L8)</title>
  <desc id="arch-desc">Hierarchical diagram of the CRACK humor evaluation system across 3 distinct phases: deterministic lexical foundation, constrained LLM reasoning, and developmental safety evaluation.</desc>
  
  <!-- Outer Card -->
  <rect x="0.5" y="0.5" width="{svg_width-1}" height="{svg_height-1}" rx="14" fill="{bg_card}" stroke="{border_card}"/>
  
  <g font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif" font-variant-numeric="tabular-nums">
    <!-- Header -->
    <text x="32" y="38" fill="{c1_pill_text}" font-size="12" font-weight="700" text-anchor="start" letter-spacing="1.5">CRACK  /  SYSTEM PIPELINE</text>
    <text x="32" y="74" fill="{text_primary}" font-size="26" font-weight="700" text-anchor="start">CRACK Pipeline Architecture (L0–L8)</text>
    <text x="32" y="100" fill="{text_secondary}" font-size="13.5" font-weight="400" text-anchor="start">Lexical retrieval, model-assisted reasoning, and age-related estimates</text>
    
    <!-- Top Input Bar -->
    <g transform="translate(20, 118)">
      <rect x="0" y="0" width="960" height="42" rx="7" fill="{col_bg}" stroke="{col_border}"/>
      <rect x="14" y="10" width="56" height="22" rx="4" fill="{c1_pill_bg}" stroke="{c1_border}"/>
      <text x="42" y="25" fill="{c1_pill_text}" font-size="11" font-weight="700" text-anchor="middle">INPUT</text>
      <text x="82" y="26" fill="{text_primary}" font-size="13" font-weight="600">Raw Joke Text + Target Ages (e.g. 6, 8, 10, 12)</text>
      <text x="940" y="26" fill="{text_muted}" font-size="11.5" text-anchor="end">Single unified CLI / Python entrypoint</text>
    </g>

    <!-- Column 1: Stage 1 Deterministic Foundation -->
    <g transform="translate(20, 174)">
      <rect x="0" y="0" width="306" height="474" rx="10" fill="{col_bg}" stroke="{c1_border}" stroke-width="1.2"/>
      
      <!-- Stage Header -->
      <rect x="14" y="14" width="138" height="22" rx="4" fill="{c1_pill_bg}"/>
      <text x="83" y="29" fill="{c1_pill_text}" font-size="10.5" font-weight="700" text-anchor="middle">STAGE 1 · SYMBOLIC</text>
      <text x="14" y="58" fill="{text_primary}" font-size="17" font-weight="700">Lexical Foundation</text>
      <text x="14" y="76" fill="{text_secondary}" font-size="12">No LLM calls in this stage</text>
      
      <!-- Block 1: L0 -->
      <rect x="12" y="94" width="282" height="74" rx="6" fill="{item_bg}" stroke="{item_border}"/>
      <text x="24" y="116" fill="{text_primary}" font-size="13" font-weight="700">L0-pre — Input validation</text>
      <text x="24" y="134" fill="{text_secondary}" font-size="11.5">Checks text length and content</text>
      <text x="24" y="152" fill="{text_muted}" font-size="11">Scope decision follows analysis</text>

      <!-- Block 2: L1 -->
      <rect x="12" y="178" width="282" height="74" rx="6" fill="{item_bg}" stroke="{item_border}"/>
      <text x="24" y="200" fill="{text_primary}" font-size="13" font-weight="700">L1 — Syntactic &amp; Genre Routing</text>
      <text x="24" y="218" fill="{text_secondary}" font-size="11.5">Tokenize text and detect structure</text>
      <text x="24" y="236" fill="{text_muted}" font-size="11">Routes: QA, Dialogue, One-Liner, Decl</text>

      <!-- Block 3: L2 -->
      <rect x="12" y="262" width="282" height="74" rx="6" fill="{item_bg}" stroke="{item_border}"/>
      <text x="24" y="284" fill="{text_primary}" font-size="13" font-weight="700">L2 — Symbolic Sense Retrieval</text>
      <text x="24" y="302" fill="{text_secondary}" font-size="11.5">WordNet 3.0 Synsets + SemCor</text>
      <text x="24" y="320" fill="{text_muted}" font-size="11">Word-level AoA lookup</text>

      <!-- Block 4: L3 -->
      <rect x="12" y="346" width="282" height="74" rx="6" fill="{item_bg}" stroke="{item_border}"/>
      <text x="24" y="368" fill="{text_primary}" font-size="13" font-weight="700">L3 — Candidate Ranking</text>
      <text x="24" y="386" fill="{text_secondary}" font-size="11.5">Contrast (0.70) + Balance (0.30)</text>
      <text x="24" y="404" fill="{c1_pill_text}" font-size="11" font-weight="600">Extracts Top-8 candidates -&gt;</text>
    </g>

    <!-- Connector 1 -> 2 -->
    <path d="M331 411 H342 M337 407 L342 411 L337 415" stroke="{c1_pill_text}" stroke-width="2" fill="none"/>

    <!-- Column 2: Stage 2 Constrained LLM Reasoning -->
    <g transform="translate(347, 174)">
      <rect x="0" y="0" width="306" height="474" rx="10" fill="{col_bg}" stroke="{c2_border}" stroke-width="1.2"/>
      
      <!-- Stage Header -->
      <rect x="14" y="14" width="132" height="22" rx="4" fill="{c2_pill_bg}"/>
      <text x="80" y="29" fill="{c2_pill_text}" font-size="10.5" font-weight="700" text-anchor="middle">STAGE 2 · NEURAL</text>
      <text x="14" y="58" fill="{text_primary}" font-size="17" font-weight="700">Constrained Reasoning</text>
      <text x="14" y="76" fill="{text_secondary}" font-size="12">Verbatim Quote Grounding</text>
      
      <!-- Block 1: L4 -->
      <rect x="12" y="94" width="282" height="106" rx="6" fill="{item_bg}" stroke="{item_border}"/>
      <text x="24" y="116" fill="{text_primary}" font-size="13" font-weight="700">L4 — Bidirectional Anchoring</text>
      <text x="24" y="134" fill="{text_secondary}" font-size="11.5">Requires non-empty quotes for</text>
      <text x="24" y="150" fill="{text_secondary}" font-size="11.5">both Sense A &amp; Sense B</text>
      <!-- Safe short-circuit pill with generous inner padding -->
      <rect x="22" y="162" width="238" height="24" rx="4" fill="{fork_bg}" stroke="{fork_border}"/>
      <text x="141" y="178" fill="{fork_text}" font-size="10.5" font-weight="700" text-anchor="middle">ONE_SENSE_ONLY → skips L5/L6</text>

      <!-- Block 2: L5 -->
      <rect x="12" y="210" width="282" height="106" rx="6" fill="{item_bg}" stroke="{item_border}"/>
      <text x="24" y="232" fill="{text_primary}" font-size="13" font-weight="700">L5 — Incongruity Resolution</text>
      <text x="24" y="250" fill="{text_secondary}" font-size="11.5">QA: Polarity, Causal, Event Fit</text>
      <text x="24" y="268" fill="{text_secondary}" font-size="11.5">Dialogue: Speaker mismatch</text>
      <text x="24" y="286" fill="{text_muted}" font-size="11">Definitional: Resegmentation</text>

      <!-- Block 3: L6 -->
      <rect x="12" y="326" width="282" height="94" rx="6" fill="{item_bg}" stroke="{item_border}"/>
      <text x="24" y="348" fill="{text_primary}" font-size="13" font-weight="700">L6 — Sense Distinctness</text>
      <text x="24" y="366" fill="{text_secondary}" font-size="11.5">Paraphrase ablation test</text>
      <text x="24" y="384" fill="{text_secondary}" font-size="11.5">Filters polysemous synonyms</text>
      <text x="24" y="402" fill="{c2_pill_text}" font-size="11" font-weight="600">SENSES_DISTINCT -&gt; To L7</text>
    </g>

    <!-- Connector 2 -> 3 -->
    <path d="M658 411 H669 M664 407 L669 411 L664 415" stroke="{c2_pill_text}" stroke-width="2" fill="none"/>

    <!-- Column 3: Stage 3 Cognitive & Safety -->
    <g transform="translate(674, 174)">
      <rect x="0" y="0" width="306" height="474" rx="10" fill="{col_bg}" stroke="{c3_border}" stroke-width="1.2"/>
      
      <!-- Stage Header -->
      <rect x="14" y="14" width="144" height="22" rx="4" fill="{c3_pill_bg}"/>
      <text x="86" y="29" fill="{c3_pill_text}" font-size="10.5" font-weight="700" text-anchor="middle">STAGE 3 · COGNITIVE</text>
      <text x="14" y="58" fill="{text_primary}" font-size="17" font-weight="700">Safety &amp; Assessment</text>
      <text x="14" y="76" fill="{text_secondary}" font-size="12">Multi-Age Developmental Model</text>
      
      <!-- Block 1: L7 -->
      <rect x="12" y="94" width="282" height="96" rx="6" fill="{item_bg}" stroke="{item_border}"/>
      <text x="24" y="116" fill="{text_primary}" font-size="13" font-weight="700">L7 — Comprehension Model</text>
      <text x="24" y="134" fill="{text_secondary}" font-size="11.5">Dual-Sense AoA evaluation</text>
      <text x="24" y="152" fill="{text_secondary}" font-size="11.5">Metalinguistic floor matching</text>
      <text x="24" y="170" fill="{text_muted}" font-size="11">Verdicts for Ages 6, 8, 10, 12</text>

      <!-- Block 2: L8 -->
      <rect x="12" y="200" width="282" height="96" rx="6" fill="{item_bg}" stroke="{item_border}"/>
      <text x="24" y="222" fill="{text_primary}" font-size="13" font-weight="700">L8 — Two-Axis Appropriateness</text>
      <text x="24" y="240" fill="{text_secondary}" font-size="11.5">Axis 1: Surface content (safety)</text>
      <text x="24" y="258" fill="{text_secondary}" font-size="11.5">Axis 2: Inference depth (adult)</text>
      <text x="24" y="276" fill="{text_muted}" font-size="11">Returns appropriateness estimates</text>

      <!-- Block 3: Output with ample right padding -->
      <rect x="12" y="306" width="282" height="114" rx="6" fill="{c3_pill_bg}" stroke="{c3_border}"/>
      <text x="24" y="328" fill="{c3_pill_text}" font-size="12.5" font-weight="700">L0-post · FINAL CLASSIFICATION</text>
      <text x="24" y="348" fill="{text_primary}" font-size="11.5" font-weight="600">• Wordplay Classification</text>
      <text x="24" y="366" fill="{text_primary}" font-size="11.5" font-weight="600">• Pun Location &amp; Anchors</text>
      <text x="24" y="384" fill="{text_primary}" font-size="11.5" font-weight="600">• Target-Age Appropriateness</text>
      <text x="24" y="402" fill="{text_secondary}" font-size="11">Structured run trace (when saved)</text>
    </g>

    <!-- Pipeline note -->
    <g transform="translate(20, 660)">
      <rect x="0" y="0" width="960" height="50" rx="7" fill="{banner_bg}" stroke="{banner_border}"/>
      <rect x="14" y="13" width="124" height="24" rx="4" fill="{banner_pill_bg}"/>
      <text x="76" y="29" fill="{banner_pill_text}" font-size="11" font-weight="700" text-anchor="middle">STAGED ANALYSIS</text>
      <text x="150" y="29" fill="{text_primary}" font-size="12" font-weight="700">Early exits:</text>
      <text x="290" y="29" fill="{text_secondary}" font-size="11.5">Stages can stop when prerequisites fail; no token-saving estimate is reported.</text>
    </g>
  </g>
</svg>
"""
    return svg_content


def main():
    assets_dir = Path(__file__).resolve().parents[1] / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    # 1. Reported SemEval summary SVGs
    (assets_dir / "benchmark-leaderboard-light.svg").write_text(generate_benchmark_svg(dark_mode=False), encoding="utf-8")
    (assets_dir / "benchmark-leaderboard-dark.svg").write_text(generate_benchmark_svg(dark_mode=True), encoding="utf-8")
    (assets_dir / "benchmark-ranking-light.svg").write_text(generate_benchmark_svg(dark_mode=False), encoding="utf-8")
    (assets_dir / "benchmark-ranking-dark.svg").write_text(generate_benchmark_svg(dark_mode=True), encoding="utf-8")

    # 2. Developmental Breakdown SVGs
    (assets_dir / "developmental-breakdown-light.svg").write_text(generate_breakdown_svg(dark_mode=False), encoding="utf-8")
    (assets_dir / "developmental-breakdown-dark.svg").write_text(generate_breakdown_svg(dark_mode=True), encoding="utf-8")

    # 3. Architecture Overview Diagram SVGs
    (assets_dir / "architecture-diagram-light.svg").write_text(generate_architecture_svg(dark_mode=False), encoding="utf-8")
    (assets_dir / "architecture-diagram-dark.svg").write_text(generate_architecture_svg(dark_mode=True), encoding="utf-8")

    print("SVG files regenerated.")


if __name__ == "__main__":
    main()
