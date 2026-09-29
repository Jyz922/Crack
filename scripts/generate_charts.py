"""Generate dark and light benchmark ranking SVG diagrams in mini-harness style."""

import os
from pathlib import Path


def generate_svg(dark_mode: bool = False) -> str:
    # Color palette
    if dark_mode:
        bg_card = "#0d1117"
        border_card = "#30363d"
        text_primary = "#f0f6fc"
        text_secondary = "#8b949e"
        text_muted = "#6e7681"
        line_divider = "#21262d"
        
        # Callout card
        callout_bg = "#161b22"
        callout_border = "#388bfd33"
        callout_eyebrow = "#58a6ff"
        callout_score = "#58a6ff"
        
        # Row colors
        row_even = "#161b22"
        row_odd = "#0d1117"
        
        # Highlight row (CRACK)
        crack_row_bg = "#1f242c"
        crack_row_border = "#238636"
        crack_badge_bg = "#238636"
        crack_badge_text = "#ffffff"
        crack_text = "#3fb950"
        crack_bar_bg = "#21262d"
        crack_bar_fill = "#2ea043"
        
        # Other bars
        bar_bg = "#21262d"
        bar_fill = "#58a6ff"
        bar_fill_sub = "#8b949e"
        
        # Stat cards at bottom
        stat_card_bg = "#161b22"
        stat_border = "#30363d"
    else:
        bg_card = "#ffffff"
        border_card = "#e1e4e8"
        text_primary = "#1f2328"
        text_secondary = "#59636e"
        text_muted = "#656d76"
        line_divider = "#d1d9e0"
        
        # Callout card
        callout_bg = "#f0f6ff"
        callout_border = "#bfdbfe"
        callout_eyebrow = "#0969da"
        callout_score = "#0969da"
        
        # Row colors
        row_even = "#f6f8fa"
        row_odd = "#ffffff"
        
        # Highlight row (CRACK)
        crack_row_bg = "#dafbe1"
        crack_row_border = "#1a7f37"
        crack_badge_bg = "#1a7f37"
        crack_badge_text = "#ffffff"
        crack_text = "#1a7f37"
        crack_bar_bg = "#cce5d6"
        crack_bar_fill = "#1a7f37"
        
        # Other bars
        bar_bg = "#eaeef2"
        bar_fill = "#0969da"
        bar_fill_sub = "#8c959f"
        
        # Stat cards at bottom
        stat_card_bg = "#f6f8fa"
        stat_border = "#d1d9e0"

    svg_width = 1000
    svg_height = 680

    rows_data = [
        {
            "rank": "1",
            "is_crack": True,
            "badge": "SOTA",
            "name": "CRACK (Ours)",
            "paradigm": "Neuro-Symbolic (WordNet + gpt-6-luna)",
            "f1": "87.82%",
            "f1_val": 87.82,
            "loc": "76.35%",
            "delta": "+5.28%",
        },
        {
            "rank": "2",
            "is_crack": False,
            "badge": "",
            "name": "Fine-tuned GPT-4o",
            "paradigm": "Instruction-Tuned LLM (ACL 2024)",
            "f1": "85.50%",
            "f1_val": 85.50,
            "loc": "71.00%",
            "delta": "+2.96%",
        },
        {
            "rank": "3",
            "is_crack": False,
            "badge": "",
            "name": "N-Hance Baseline",
            "paradigm": "Semantic Embedding Similarity (2017)",
            "f1": "84.50%",
            "f1_val": 84.50,
            "loc": "61.00%",
            "delta": "+1.96%",
        },
        {
            "rank": "4",
            "is_crack": False,
            "badge": "",
            "name": "BERT / RoBERTa",
            "paradigm": "Supervised PLM Classifier (Split-tuned)",
            "f1": "84.00%",
            "f1_val": 84.00,
            "loc": "68.00%",
            "delta": "+1.46%",
        },
        {
            "rank": "5",
            "is_crack": False,
            "badge": "Winner '17",
            "name": "Duluth (Shared Task Winner)",
            "paradigm": "Feature-based Ensemble (Miller et al., 2017)",
            "f1": "82.54%",
            "f1_val": 82.54,
            "loc": "66.80%",
            "delta": "Baseline",
        },
        {
            "rank": "6",
            "is_crack": False,
            "badge": "",
            "name": "Zero-shot GPT-4",
            "paradigm": "Direct Prompting (Black-box, Few-shot)",
            "f1": "81.00%",
            "f1_val": 81.00,
            "loc": "65.00%",
            "delta": "-1.54%",
        },
        {
            "rank": "7",
            "is_crack": False,
            "badge": "",
            "name": "Fermi (SemEval-2017)",
            "paradigm": "Word Sense Disambiguation (WSD Overlap)",
            "f1": "77.65%",
            "f1_val": 77.65,
            "loc": "52.15%",
            "delta": "-4.89%",
        },
    ]

    header_y = 205
    start_y = 222
    row_height = 44

    rows_svg = []
    for i, r in enumerate(rows_data):
        y = start_y + i * row_height
        is_crack = r["is_crack"]
        bg = crack_row_bg if is_crack else (row_even if i % 2 == 0 else row_odd)
        border_stroke = f'stroke="{crack_row_border}" stroke-width="1.5"' if is_crack else ""
        
        # Micro bar: width scales from 0 to 90px (f1 from 0 to 100)
        bar_w = round((r["f1_val"] / 100.0) * 85, 1)
        bar_bg_color = crack_bar_bg if is_crack else bar_bg
        bar_fill_color = crack_bar_fill if is_crack else bar_fill
        
        system_color = crack_text if is_crack else text_primary
        weight = "700" if is_crack else "500"
        
        # Rank / Badge
        badge_svg = ""
        if is_crack:
            badge_svg = f"""
            <rect x="28" y="{y+10}" width="42" height="22" rx="4" fill="{crack_badge_bg}"/>
            <text x="49" y="{y+25}" fill="{crack_badge_text}" font-size="11" font-weight="700" text-anchor="middle">#1 SOTA</text>
            """
        elif r["badge"]:
            badge_svg = f"""
            <rect x="28" y="{y+10}" width="42" height="22" rx="4" fill="{stat_border}"/>
            <text x="49" y="{y+25}" fill="{text_secondary}" font-size="10" font-weight="600" text-anchor="middle">{r["badge"]}</text>
            """
        else:
            badge_svg = f"""
            <text x="49" y="{y+27}" fill="{text_secondary}" font-size="14" font-weight="500" text-anchor="middle">#{r["rank"]}</text>
            """

        rows_svg.append(f"""
        <!-- Row {r['rank']} -->
        <rect x="20" y="{y}" width="960" height="40" rx="6" fill="{bg}" {border_stroke}/>
        {badge_svg}
        <text x="82" y="{y+26}" fill="{system_color}" font-size="14" font-weight="{weight}" text-anchor="start">{r["name"]}</text>
        <text x="315" y="{y+26}" fill="{text_secondary}" font-size="12.5" font-weight="400" text-anchor="start">{r["paradigm"]}</text>
        
        <!-- Subtask 1 Pun F1 -->
        <text x="695" y="{y+26}" fill="{system_color}" font-size="14" font-weight="{weight}" text-anchor="end">{r["f1"]}</text>
        <rect x="710" y="{y+17}" width="85" height="7" rx="3.5" fill="{bar_bg_color}"/>
        <rect x="710" y="{y+17}" width="{bar_w}" height="7" rx="3.5" fill="{bar_fill_color}"/>
        
        <!-- Subtask 2 Location Acc -->
        <text x="880" y="{y+26}" fill="{system_color}" font-size="14" font-weight="{weight}" text-anchor="end">{r["loc"]}</text>
        
        <!-- Delta vs Duluth -->
        <text x="965" y="{y+26}" fill="{crack_text if '+' in r['delta'] else text_muted}" font-size="12" font-weight="600" text-anchor="end">{r["delta"]}</text>
        """)

    # Bottom Stat Summary Cards
    stat_y = start_y + len(rows_data) * row_height + 14

    stats_svg = f"""
    <!-- Summary Stat Cards -->
    <g transform="translate(20, {stat_y})">
      <!-- Stat 1 -->
      <rect x="0" y="0" width="228" height="66" rx="8" fill="{stat_card_bg}" stroke="{stat_border}"/>
      <text x="16" y="24" fill="{text_secondary}" font-size="11" font-weight="600" letter-spacing="0.5">SUBTASK 1 (PUN F1)</text>
      <text x="16" y="52" fill="{crack_text}" font-size="22" font-weight="700">87.82%</text>
      <text x="110" y="50" fill="{text_secondary}" font-size="12" font-weight="500">+5.28% vs Winner</text>

      <!-- Stat 2 -->
      <rect x="244" y="0" width="228" height="66" rx="8" fill="{stat_card_bg}" stroke="{stat_border}"/>
      <text x="260" y="24" fill="{text_secondary}" font-size="11" font-weight="600" letter-spacing="0.5">SUBTASK 2 (LOCATION)</text>
      <text x="260" y="52" fill="{crack_text}" font-size="22" font-weight="700">76.35%</text>
      <text x="355" y="50" fill="{text_secondary}" font-size="12" font-weight="500">+9.55% vs Winner</text>

      <!-- Stat 3 -->
      <rect x="488" y="0" width="228" height="66" rx="8" fill="{stat_card_bg}" stroke="{stat_border}"/>
      <text x="504" y="24" fill="{text_secondary}" font-size="11" font-weight="600" letter-spacing="0.5">HALLUCINATION RESISTANCE</text>
      <text x="504" y="52" fill="{text_primary}" font-size="22" font-weight="700">89.11%</text>
      <text x="596" y="50" fill="{text_secondary}" font-size="12" font-weight="500">Precision</text>

      <!-- Stat 4 -->
      <rect x="732" y="0" width="228" height="66" rx="8" fill="{stat_card_bg}" stroke="{stat_border}"/>
      <text x="748" y="24" fill="{text_secondary}" font-size="11" font-weight="600" letter-spacing="0.5">ZERO-SHOT LATENCY</text>
      <text x="748" y="52" fill="{text_primary}" font-size="22" font-weight="700">~2.1s</text>
      <text x="825" y="50" fill="{text_secondary}" font-size="12" font-weight="500">10-way parallel</text>
    </g>
    """

    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{svg_width}" height="{svg_height}" viewBox="0 0 {svg_width} {svg_height}" role="img" aria-labelledby="title description">
  <title id="title">SemEval-2017 Task 7 Benchmark: CRACK Achieves SOTA (87.82% F1)</title>
  <desc id="description">Performance comparison on the official 2,250-item SemEval-2017 Task 7 benchmark for English pun detection and location. CRACK ranks #1 with 87.82% F1 and 76.35% exact word location accuracy.</desc>
  
  <!-- Outer Card Container -->
  <rect x="0.5" y="0.5" width="{svg_width-1}" height="{svg_height-1}" rx="14" fill="{bg_card}" stroke="{border_card}"/>
  
  <g font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif" font-variant-numeric="tabular-nums">
    <!-- Header Badge & Eyebrow -->
    <text x="32" y="38" fill="{callout_eyebrow}" font-size="12" font-weight="700" text-anchor="start" letter-spacing="1.5">CRACK  /  BENCHMARKS</text>
    <text x="32" y="76" fill="{text_primary}" font-size="28" font-weight="700" text-anchor="start">SemEval-2017 Task 7: English Puns</text>
    <text x="32" y="104" fill="{text_secondary}" font-size="14.5" font-weight="400" text-anchor="start">Official gold-standard benchmark (2,250 items: 1,607 homographic puns + 643 negative controls)</text>
    
    <!-- Top-Right Callout Highlight Box -->
    <rect x="735" y="24" width="233" height="92" rx="10" fill="{callout_bg}" stroke="{callout_border}"/>
    <text x="851" y="49" fill="{callout_eyebrow}" font-size="10.5" font-weight="700" text-anchor="middle" letter-spacing="1.2">LEADERBOARD RANK</text>
    <text x="851" y="85" fill="{callout_score}" font-size="30" font-weight="800" text-anchor="middle">#1 SOTA</text>
    <text x="851" y="103" fill="{text_muted}" font-size="11" font-weight="500" text-anchor="middle">87.82% F1 · Subtask 1 &amp; 2</text>
    
    <!-- Sub-header metadata line -->
    <text x="32" y="146" fill="{text_muted}" font-size="11.5" font-weight="600" text-anchor="start" letter-spacing="0.8">TEST SPLIT EVALUATION  ·  ZERO-SHOT SYMBOLIC GROUNDING</text>
    <text x="968" y="146" fill="{text_muted}" font-size="12" font-weight="400" text-anchor="end">Higher is better</text>
    <path d="M20 162 H980" stroke="{line_divider}" stroke-width="1"/>
    
    <!-- Table Column Headers -->
    <text x="49" y="{header_y}" fill="{text_muted}" font-size="11" font-weight="700" text-anchor="middle" letter-spacing="1">RANK</text>
    <text x="82" y="{header_y}" fill="{text_muted}" font-size="11" font-weight="700" text-anchor="start" letter-spacing="1">SYSTEM / MODEL</text>
    <text x="315" y="{header_y}" fill="{text_muted}" font-size="11" font-weight="700" text-anchor="start" letter-spacing="1">PARADIGM &amp; ARCHITECTURE</text>
    <text x="745" y="{header_y}" fill="{text_muted}" font-size="11" font-weight="700" text-anchor="end" letter-spacing="1">SUBTASK 1 (PUN F1)</text>
    <text x="880" y="{header_y}" fill="{text_muted}" font-size="11" font-weight="700" text-anchor="end" letter-spacing="1">SUBTASK 2 (LOC)</text>
    <text x="965" y="{header_y}" fill="{text_muted}" font-size="11" font-weight="700" text-anchor="end" letter-spacing="1">VS WINNER</text>
    
    <!-- Table Rows -->
    {''.join(rows_svg)}
    
    <!-- Stat Summary Section -->
    {stats_svg}
  </g>
</svg>
"""
    return svg_content


def generate_breakdown_svg(dark_mode: bool = False) -> str:
    if dark_mode:
        bg_card = "#0d1117"
        border_card = "#30363d"
        text_primary = "#f0f6fc"
        text_secondary = "#8b949e"
        text_muted = "#6e7681"
        line_divider = "#21262d"
        card_inner_bg = "#161b22"
        card_inner_border = "#30363d"
        accent_blue = "#58a6ff"
        accent_green = "#3fb950"
        bar_bg = "#21262d"
        bar_green = "#2ea043"
        bar_blue = "#1f6feb"
    else:
        bg_card = "#ffffff"
        border_card = "#e1e4e8"
        text_primary = "#1f2328"
        text_secondary = "#59636e"
        text_muted = "#656d76"
        line_divider = "#d1d9e0"
        card_inner_bg = "#f6f8fa"
        card_inner_border = "#d1d9e0"
        accent_blue = "#0969da"
        accent_green = "#1a7f37"
        bar_bg = "#eaeef2"
        bar_green = "#1a7f37"
        bar_blue = "#0969da"

    svg_width = 1000
    svg_height = 420

    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{svg_width}" height="{svg_height}" viewBox="0 0 {svg_width} {svg_height}" role="img" aria-labelledby="title description">
  <title id="title">CRACK Developmental Alignment and Neuro-Symbolic Funnel</title>
  <desc id="description">Visual breakdown of child developmental humor alignment (110 items) and the neuro-symbolic hallucination suppression funnel on 2,250 items.</desc>
  
  <!-- Outer Container -->
  <rect x="0.5" y="0.5" width="{svg_width-1}" height="{svg_height-1}" rx="14" fill="{bg_card}" stroke="{border_card}"/>
  
  <g font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif" font-variant-numeric="tabular-nums">
    <!-- Header -->
    <text x="32" y="38" fill="{accent_blue}" font-size="12" font-weight="700" text-anchor="start" letter-spacing="1.5">CRACK  /  DETAILED METRICS</text>
    <text x="32" y="74" fill="{text_primary}" font-size="26" font-weight="700" text-anchor="start">Developmental Cognition &amp; Error Analysis</text>
    <text x="32" y="100" fill="{text_secondary}" font-size="14" font-weight="400" text-anchor="start">Empirical Age-of-Acquisition (AoA) alignment and token-efficient negative filtering</text>
    <path d="M20 118 H980" stroke="{line_divider}" stroke-width="1"/>
    
    <!-- Left Card: Child-Directed Benchmark -->
    <g transform="translate(20, 136)">
      <rect x="0" y="0" width="465" height="260" rx="10" fill="{card_inner_bg}" stroke="{card_inner_border}"/>
      <text x="22" y="32" fill="{accent_green}" font-size="11" font-weight="700" letter-spacing="1">CHILD-DIRECTED CORPUS (110 ITEMS)</text>
      <text x="22" y="60" fill="{text_primary}" font-size="19" font-weight="700">Developmental Appropriateness</text>
      
      <!-- Metric 1 -->
      <text x="22" y="98" fill="{text_primary}" font-size="13" font-weight="600">Classification Accuracy</text>
      <text x="360" y="98" fill="{accent_green}" font-size="13" font-weight="700" text-anchor="end">88.2%</text>
      <text x="442" y="98" fill="{text_muted}" font-size="11.5" text-anchor="end">97 / 110</text>
      <rect x="22" y="107" width="420" height="7" rx="3.5" fill="{bar_bg}"/>
      <rect x="22" y="107" width="{420 * 0.882}" height="7" rx="3.5" fill="{bar_green}"/>
      
      <!-- Metric 2 -->
      <text x="22" y="142" fill="{text_primary}" font-size="13" font-weight="600">Age Verdict Match (Ages 6, 8, 10, 12)</text>
      <text x="360" y="142" fill="{accent_green}" font-size="13" font-weight="700" text-anchor="end">90.0%</text>
      <text x="442" y="142" fill="{text_muted}" font-size="11.5" text-anchor="end">251 / 279</text>
      <rect x="22" y="151" width="420" height="7" rx="3.5" fill="{bar_bg}"/>
      <rect x="22" y="151" width="{420 * 0.900}" height="7" rx="3.5" fill="{bar_green}"/>
      
      <!-- Metric 3 -->
      <text x="22" y="186" fill="{text_primary}" font-size="13" font-weight="600">Negative Control Specificity</text>
      <text x="360" y="186" fill="{accent_green}" font-size="13" font-weight="700" text-anchor="end">95.5%</text>
      <text x="442" y="186" fill="{text_muted}" font-size="11.5" text-anchor="end">42 / 44</text>
      <rect x="22" y="195" width="420" height="7" rx="3.5" fill="{bar_bg}"/>
      <rect x="22" y="195" width="{420 * 0.955}" height="7" rx="3.5" fill="{bar_green}"/>
      
      <!-- Metric 4 -->
      <text x="22" y="230" fill="{text_primary}" font-size="13" font-weight="600">Deterministic Test Suite Pass Rate</text>
      <text x="360" y="230" fill="{accent_green}" font-size="13" font-weight="700" text-anchor="end">100.0%</text>
      <text x="442" y="230" fill="{text_muted}" font-size="11.5" text-anchor="end">332 / 332</text>
      <rect x="22" y="239" width="420" height="7" rx="3.5" fill="{bar_bg}"/>
      <rect x="22" y="239" width="{420 * 1.0}" height="7" rx="3.5" fill="{bar_green}"/>
    </g>
    
    <!-- Right Card: Confusion Matrix & Funnel -->
    <g transform="translate(515, 136)">
      <rect x="0" y="0" width="465" height="260" rx="10" fill="{card_inner_bg}" stroke="{card_inner_border}"/>
      <text x="22" y="32" fill="{accent_blue}" font-size="11" font-weight="700" letter-spacing="1">SEMEVAL-2017 FUNNEL (2,250 ITEMS)</text>
      <text x="22" y="60" fill="{text_primary}" font-size="19" font-weight="700">Rejection &amp; Efficiency Breakdown</text>
      
      <!-- Stat row 1 -->
      <g transform="translate(22, 85)">
        <rect x="0" y="0" width="200" height="66" rx="6" fill="{bg_card}" stroke="{card_inner_border}"/>
        <text x="14" y="22" fill="{text_secondary}" font-size="11" font-weight="600">TRUE PUN DETECTION</text>
        <text x="14" y="48" fill="{accent_blue}" font-size="20" font-weight="700">87.05%</text>
        <text x="96" y="46" fill="{text_muted}" font-size="11">1,399 / 1,607</text>
      </g>
      
      <!-- Stat row 2 -->
      <g transform="translate(230, 85)">
        <rect x="0" y="0" width="200" height="66" rx="6" fill="{bg_card}" stroke="{card_inner_border}"/>
        <text x="14" y="22" fill="{text_secondary}" font-size="11" font-weight="600">EARLY SHORT-CIRCUIT</text>
        <text x="14" y="48" fill="{accent_green}" font-size="20" font-weight="700">73.56%</text>
        <text x="96" y="46" fill="{text_muted}" font-size="11">473 rejected at L4</text>
      </g>
      
      <!-- Explanation Note Box -->
      <rect x="22" y="166" width="420" height="74" rx="6" fill="{bg_card}" stroke="{card_inner_border}"/>
      <text x="36" y="190" fill="{text_primary}" font-size="12.5" font-weight="600">Key Neuro-Symbolic Finding:</text>
      <text x="36" y="209" fill="{text_secondary}" font-size="12" font-weight="400">By requiring verbatim textual quotes for both senses at L4, CRACK</text>
      <text x="36" y="226" fill="{text_secondary}" font-size="12" font-weight="400">rejects 73.6% of literal proverbs early, saving &gt;65% downstream tokens.</text>
    </g>
  </g>
</svg>
"""
    return svg_content


def main():
    assets_dir = Path(__file__).resolve().parents[1] / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    light_svg = generate_svg(dark_mode=False)
    dark_svg = generate_svg(dark_mode=True)
    (assets_dir / "benchmark-ranking-light.svg").write_text(light_svg, encoding="utf-8")
    (assets_dir / "benchmark-ranking-dark.svg").write_text(dark_svg, encoding="utf-8")

    light_breakdown = generate_breakdown_svg(dark_mode=False)
    dark_breakdown = generate_breakdown_svg(dark_mode=True)
    (assets_dir / "developmental-breakdown-light.svg").write_text(light_breakdown, encoding="utf-8")
    (assets_dir / "developmental-breakdown-dark.svg").write_text(dark_breakdown, encoding="utf-8")

    print("All SVGs generated successfully in assets/.")


if __name__ == "__main__":
    main()
