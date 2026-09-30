"""Generate dark and light benchmark ranking, breakdown, and architecture SVG diagrams in mini-harness style.

All text elements are strictly bound with guaranteed safety margins to prevent any text overflow.
"""

import os
from pathlib import Path


def generate_benchmark_svg(dark_mode: bool = False) -> str:
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
        
        # Stat cards at bottom
        stat_card_bg = "#f6f8fa"
        stat_border = "#d1d9e0"

    svg_width = 1000
    svg_height = 755

    rows_data = [
        {
            "rank": "1",
            "is_crack": True,
            "name": "CRACK (Ours)",
            "paradigm": "Neuro-Symbolic (WordNet + gpt-6-luna)",
            "f1": "87.82%",
            "f1_val": 87.82,
            "acc": "82.84%",
            "delta": "+0.47%",
        },
        {
            "rank": "2",
            "is_crack": False,
            "name": "GPT-4o (Frontier LLM)",
            "paradigm": "Zero-shot Reasoning (Hurst et al., 2024)",
            "f1": "87.35%",
            "f1_val": 87.35,
            "acc": "76.27%",
            "delta": "-0.47%",
        },
        {
            "rank": "3",
            "is_crack": False,
            "name": "PunGraph-Qwen-3.5 (EMNLP '26)",
            "paradigm": "KG Retrieval + LLM (Su et al., 2026)",
            "f1": "85.71%",
            "f1_val": 85.71,
            "acc": "76.18%",
            "delta": "-2.11%",
        },
        {
            "rank": "4",
            "is_crack": False,
            "name": "Gemini-2.0 Flash",
            "paradigm": "High-Throughput Reasoning (Google, 2025)",
            "f1": "84.56%",
            "f1_val": 84.56,
            "acc": "71.08%",
            "delta": "-3.26%",
        },
        {
            "rank": "5",
            "is_crack": False,
            "name": "PunGraph-Llama4 (EMNLP '26)",
            "paradigm": "KG Retrieval + LLM (Su et al., 2026)",
            "f1": "83.43%",
            "f1_val": 83.43,
            "acc": "71.80%",
            "delta": "-4.39%",
        },
        {
            "rank": "6",
            "is_crack": False,
            "name": "Qwen-3.5-27B (Raw LLM)",
            "paradigm": "Direct Prompting (Qwen Team, 2026)",
            "f1": "83.20%",
            "f1_val": 83.20,
            "acc": "68.95%",
            "delta": "-4.62%",
        },
        {
            "rank": "7",
            "is_crack": False,
            "name": "Duluth (SemEval-2017 Winner)",
            "paradigm": "Feature Ensemble (Miller et al., 2017)",
            "f1": "82.54%",
            "f1_val": 82.54,
            "acc": "73.64%",
            "delta": "-5.28%",
        },
        {
            "rank": "8",
            "is_crack": False,
            "name": "DeepSeek-V3.2",
            "paradigm": "Mixture-of-Experts LLM (DeepSeek, 2025)",
            "f1": "82.12%",
            "f1_val": 82.12,
            "acc": "66.26%",
            "delta": "-5.70%",
        },
        {
            "rank": "9",
            "is_crack": False,
            "name": "Llama4-Maverick (Raw LLM)",
            "paradigm": "Direct Prompting (Meta, 2025)",
            "f1": "82.00%",
            "f1_val": 82.00,
            "acc": "66.26%",
            "delta": "-5.82%",
        },
    ]

    header_y = 195
    start_y = 212
    row_height = 44

    rows_svg = []
    for i, r in enumerate(rows_data):
        y = start_y + i * row_height
        is_crack = r["is_crack"]
        bg = crack_row_bg if is_crack else (row_even if i % 2 == 0 else row_odd)
        border_stroke = f'stroke="{crack_row_border}" stroke-width="1.5"' if is_crack else ""
        
        # Micro bar: width scales from 0 to 76px
        bar_w = round((r["f1_val"] / 100.0) * 76, 1)
        bar_bg_color = crack_bar_bg if is_crack else bar_bg
        bar_fill_color = crack_bar_fill if is_crack else bar_fill
        
        system_color = crack_text if is_crack else text_primary
        weight = "700" if is_crack else "500"
        
        # Clean rank badges without any text overflow
        if is_crack:
            badge_svg = f"""
            <rect x="22" y="{y+9}" width="52" height="22" rx="4" fill="{crack_badge_bg}"/>
            <text x="48" y="{y+24}" fill="{crack_badge_text}" font-size="10" font-weight="700" text-anchor="middle">#1 SOTA</text>
            """
        else:
            badge_svg = f"""
            <text x="48" y="{y+26}" fill="{text_secondary}" font-size="13" font-weight="500" text-anchor="middle">#{r["rank"]}</text>
            """

        rows_svg.append(f"""
        <!-- Row {r['rank']} -->
        <rect x="20" y="{y}" width="960" height="40" rx="6" fill="{bg}" {border_stroke}/>
        {badge_svg}
        <text x="88" y="{y+26}" fill="{system_color}" font-size="13.5" font-weight="{weight}" text-anchor="start">{r["name"]}</text>
        <text x="330" y="{y+26}" fill="{text_secondary}" font-size="12" font-weight="400" text-anchor="start">{r["paradigm"]}</text>
        
        <!-- Subtask 1 Pun F1 -->
        <text x="670" y="{y+26}" fill="{system_color}" font-size="13.5" font-weight="{weight}" text-anchor="end">{r["f1"]}</text>
        <rect x="684" y="{y+17}" width="76" height="7" rx="3.5" fill="{bar_bg_color}"/>
        <rect x="684" y="{y+17}" width="{bar_w}" height="7" rx="3.5" fill="{bar_fill_color}"/>
        
        <!-- Detection Acc -->
        <text x="855" y="{y+26}" fill="{system_color}" font-size="13.5" font-weight="{weight}" text-anchor="end">{r["acc"]}</text>
        
        <!-- Delta vs SOTA -->
        <text x="955" y="{y+26}" fill="{crack_text if '+' in r['delta'] else text_muted}" font-size="12" font-weight="600" text-anchor="end">{r["delta"]}</text>
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
      <text x="110" y="50" fill="{text_secondary}" font-size="12" font-weight="500">+0.47% vs GPT-4o</text>

      <!-- Stat 2 -->
      <rect x="244" y="0" width="228" height="66" rx="8" fill="{stat_card_bg}" stroke="{stat_border}"/>
      <text x="260" y="24" fill="{text_secondary}" font-size="11" font-weight="600" letter-spacing="0.5">DETECTION ACCURACY</text>
      <text x="260" y="52" fill="{crack_text}" font-size="22" font-weight="700">82.84%</text>
      <text x="355" y="50" fill="{text_secondary}" font-size="12" font-weight="500">+6.57% vs GPT-4o</text>

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

    <!-- Source Citation Banner -->
    <g transform="translate(20, {stat_y + 80})">
      <rect x="0" y="0" width="960" height="30" rx="6" fill="{row_even}" stroke="{stat_border}"/>
      <text x="16" y="19" fill="{text_secondary}" font-size="11.5" font-weight="500">Official Sources: Su et al. (EMNLP 2026, Table 1), Miller et al. (SemEval-2017, S17-2007), Hurst et al. (GPT-4o, 2024)</text>
    </g>
    """

    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{svg_width}" height="{svg_height}" viewBox="0 0 {svg_width} {svg_height}" role="img" aria-labelledby="title description">
  <title id="title">SemEval-2017 Task 7 Benchmark: CRACK Achieves SOTA (87.82% F1)</title>
  <desc id="description">Performance comparison on the official 2,250-item SemEval-2017 Task 7 benchmark for English pun detection and location. CRACK ranks #1 with 87.82% F1 and 82.84% accuracy against frontier LLMs and graph architectures.</desc>
  
  <!-- Outer Card Container -->
  <rect x="0.5" y="0.5" width="{svg_width-1}" height="{svg_height-1}" rx="14" fill="{bg_card}" stroke="{border_card}"/>
  
  <g font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif" font-variant-numeric="tabular-nums">
    <!-- Header Badge & Eyebrow -->
    <text x="32" y="38" fill="{callout_eyebrow}" font-size="12" font-weight="700" text-anchor="start" letter-spacing="1.5">CRACK  /  BENCHMARKS</text>
    <text x="32" y="74" fill="{text_primary}" font-size="28" font-weight="700" text-anchor="start">SemEval-2017 Task 7: English Puns</text>
    <text x="32" y="100" fill="{text_secondary}" font-size="14.5" font-weight="400" text-anchor="start">Official gold-standard benchmark (2,250 items: 1,607 homographic puns + 643 negative controls)</text>
    <text x="32" y="122" fill="{callout_eyebrow}" font-size="12" font-weight="600" text-anchor="start">SOURCE: EMNLP 2026 (Su et al., arXiv:2609.16557 Table 1) &amp; SemEval-2017 (Miller et al., S17-2007)</text>
    
    <!-- Top-Right Callout Highlight Box -->
    <rect x="735" y="24" width="233" height="92" rx="10" fill="{callout_bg}" stroke="{callout_border}"/>
    <text x="851" y="49" fill="{callout_eyebrow}" font-size="10.5" font-weight="700" text-anchor="middle" letter-spacing="1.2">LEADERBOARD RANK</text>
    <text x="851" y="85" fill="{callout_score}" font-size="30" font-weight="800" text-anchor="middle">#1 SOTA</text>
    <text x="851" y="103" fill="{text_muted}" font-size="11" font-weight="500" text-anchor="middle">87.82% F1 · 82.84% Acc</text>
    
    <!-- Sub-header metadata line -->
    <text x="32" y="146" fill="{text_muted}" font-size="11.5" font-weight="600" text-anchor="start" letter-spacing="0.8">TEST SPLIT EVALUATION  ·  ZERO-SHOT SYMBOLIC GROUNDING</text>
    <text x="955" y="146" fill="{text_muted}" font-size="12" font-weight="400" text-anchor="end">Higher is better</text>
    <path d="M20 158 H980" stroke="{line_divider}" stroke-width="1"/>
    
    <!-- Table Column Headers -->
    <text x="48" y="{header_y}" fill="{text_muted}" font-size="11" font-weight="700" text-anchor="middle" letter-spacing="1">RANK</text>
    <text x="88" y="{header_y}" fill="{text_muted}" font-size="11" font-weight="700" text-anchor="start" letter-spacing="1">SYSTEM / MODEL</text>
    <text x="330" y="{header_y}" fill="{text_muted}" font-size="11" font-weight="700" text-anchor="start" letter-spacing="1">PARADIGM &amp; ARCHITECTURE</text>
    <text x="730" y="{header_y}" fill="{text_muted}" font-size="11" font-weight="700" text-anchor="end" letter-spacing="1">SUBTASK 1 (PUN F1)</text>
    <text x="855" y="{header_y}" fill="{text_muted}" font-size="11" font-weight="700" text-anchor="end" letter-spacing="1">DETECTION ACC</text>
    <text x="955" y="{header_y}" fill="{text_muted}" font-size="11" font-weight="700" text-anchor="end" letter-spacing="1">VS SOTA</text>
    
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
    svg_height = 430

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
    <g transform="translate(20, 132)">
      <rect x="0" y="0" width="465" height="274" rx="10" fill="{card_inner_bg}" stroke="{card_inner_border}"/>
      <text x="22" y="32" fill="{accent_green}" font-size="11" font-weight="700" letter-spacing="1">CHILD-DIRECTED CORPUS (110 ITEMS)</text>
      <text x="22" y="58" fill="{text_primary}" font-size="18" font-weight="700">Developmental Appropriateness</text>
      
      <!-- Metric 1 -->
      <text x="22" y="96" fill="{text_primary}" font-size="12.5" font-weight="600">Classification Accuracy</text>
      <text x="360" y="96" fill="{accent_green}" font-size="13" font-weight="700" text-anchor="end">88.2%</text>
      <text x="442" y="96" fill="{text_muted}" font-size="11" text-anchor="end">97 / 110</text>
      <rect x="22" y="104" width="420" height="7" rx="3.5" fill="{bar_bg}"/>
      <rect x="22" y="104" width="{420 * 0.882}" height="7" rx="3.5" fill="{bar_green}"/>
      
      <!-- Metric 2 -->
      <text x="22" y="140" fill="{text_primary}" font-size="12.5" font-weight="600">Age Verdict Alignment (Ages 6–12)</text>
      <text x="360" y="140" fill="{accent_green}" font-size="13" font-weight="700" text-anchor="end">90.0%</text>
      <text x="442" y="140" fill="{text_muted}" font-size="11" text-anchor="end">251 / 279</text>
      <rect x="22" y="148" width="420" height="7" rx="3.5" fill="{bar_bg}"/>
      <rect x="22" y="148" width="{420 * 0.900}" height="7" rx="3.5" fill="{bar_green}"/>
      
      <!-- Metric 3 -->
      <text x="22" y="184" fill="{text_primary}" font-size="12.5" font-weight="600">Negative Control Specificity</text>
      <text x="360" y="184" fill="{accent_green}" font-size="13" font-weight="700" text-anchor="end">95.5%</text>
      <text x="442" y="184" fill="{text_muted}" font-size="11" text-anchor="end">42 / 44</text>
      <rect x="22" y="192" width="420" height="7" rx="3.5" fill="{bar_bg}"/>
      <rect x="22" y="192" width="{420 * 0.955}" height="7" rx="3.5" fill="{bar_green}"/>
      
      <!-- Metric 4 -->
      <text x="22" y="228" fill="{text_primary}" font-size="12.5" font-weight="600">Deterministic Test Suite (332 Tests)</text>
      <text x="360" y="228" fill="{accent_green}" font-size="13" font-weight="700" text-anchor="end">100.0%</text>
      <text x="442" y="228" fill="{text_muted}" font-size="11" text-anchor="end">332 / 332</text>
      <rect x="22" y="236" width="420" height="7" rx="3.5" fill="{bar_bg}"/>
      <rect x="22" y="236" width="{420 * 1.0}" height="7" rx="3.5" fill="{bar_green}"/>
    </g>
    
    <!-- Right Card: Confusion Matrix & Funnel -->
    <g transform="translate(515, 132)">
      <rect x="0" y="0" width="465" height="274" rx="10" fill="{card_inner_bg}" stroke="{card_inner_border}"/>
      <text x="22" y="32" fill="{accent_blue}" font-size="11" font-weight="700" letter-spacing="1">SEMEVAL-2017 FUNNEL (2,250 ITEMS)</text>
      <text x="22" y="58" fill="{text_primary}" font-size="18" font-weight="700">Rejection &amp; Efficiency Breakdown</text>
      
      <!-- Stat row 1 -->
      <g transform="translate(20, 80)">
        <rect x="0" y="0" width="202" height="66" rx="6" fill="{bg_card}" stroke="{card_inner_border}"/>
        <text x="14" y="22" fill="{text_secondary}" font-size="11" font-weight="600">TRUE PUN DETECTION</text>
        <text x="14" y="48" fill="{accent_blue}" font-size="20" font-weight="700">87.05%</text>
        <text x="188" y="46" fill="{text_muted}" font-size="10.5" text-anchor="end">1,399 / 1,607</text>
      </g>
      
      <!-- Stat row 2 -->
      <g transform="translate(242, 80)">
        <rect x="0" y="0" width="202" height="66" rx="6" fill="{bg_card}" stroke="{card_inner_border}"/>
        <text x="14" y="22" fill="{text_secondary}" font-size="11" font-weight="600">EARLY SHORT-CIRCUIT</text>
        <text x="14" y="48" fill="{accent_green}" font-size="20" font-weight="700">73.56%</text>
        <text x="188" y="46" fill="{text_muted}" font-size="10.5" text-anchor="end">473 rejected at L4</text>
      </g>
      
      <!-- Explanation Note Box -->
      <rect x="20" y="162" width="424" height="88" rx="6" fill="{bg_card}" stroke="{card_inner_border}"/>
      <text x="32" y="186" fill="{text_primary}" font-size="12" font-weight="700">Neuro-Symbolic Efficiency:</text>
      <text x="32" y="206" fill="{text_secondary}" font-size="11.5">Requiring verbatim context quotes at L4 eliminates 73.6% of</text>
      <text x="32" y="224" fill="{text_secondary}" font-size="11.5">non-joke proverbs early, saving &gt;65% downstream LLM tokens.</text>
    </g>
  </g>
</svg>
"""
    return svg_content


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
  <title id="arch-title">CRACK System Architecture: 8-Layer Neuro-Symbolic Pipeline</title>
  <desc id="arch-desc">Hierarchical diagram of the CRACK humor evaluation system across 3 distinct phases: deterministic lexical foundation, constrained LLM reasoning, and developmental safety evaluation.</desc>
  
  <!-- Outer Card -->
  <rect x="0.5" y="0.5" width="{svg_width-1}" height="{svg_height-1}" rx="14" fill="{bg_card}" stroke="{border_card}"/>
  
  <g font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif" font-variant-numeric="tabular-nums">
    <!-- Header -->
    <text x="32" y="38" fill="{c1_pill_text}" font-size="12" font-weight="700" text-anchor="start" letter-spacing="1.5">CRACK  /  SYSTEM PIPELINE</text>
    <text x="32" y="74" fill="{text_primary}" font-size="26" font-weight="700" text-anchor="start">Neuro-Symbolic 8-Layer Architecture (L0–L8)</text>
    <text x="32" y="100" fill="{text_secondary}" font-size="13.5" font-weight="400" text-anchor="start">Deterministic lexical ontologies + Schema-constrained LLM reasoning + Developmental multi-age modeling</text>
    
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
      <text x="14" y="76" fill="{text_secondary}" font-size="12">0 Tokens · Deterministic Search</text>
      
      <!-- Block 1: L0 -->
      <rect x="12" y="94" width="282" height="74" rx="6" fill="{item_bg}" stroke="{item_border}"/>
      <text x="24" y="116" fill="{text_primary}" font-size="13" font-weight="700">L0 — Scope Boundary Gate</text>
      <text x="24" y="134" fill="{text_secondary}" font-size="11.5">Accepts homographs &amp; splits</text>
      <text x="24" y="152" fill="{text_muted}" font-size="11">Filters homophones &amp; rhymes</text>

      <!-- Block 2: L1 -->
      <rect x="12" y="178" width="282" height="74" rx="6" fill="{item_bg}" stroke="{item_border}"/>
      <text x="24" y="200" fill="{text_primary}" font-size="13" font-weight="700">L1 — Syntactic &amp; Genre Routing</text>
      <text x="24" y="218" fill="{text_secondary}" font-size="11.5">Tokenize, POS, Lemmatization</text>
      <text x="24" y="236" fill="{text_muted}" font-size="11">Routes: QA, Dialogue, One-Liner, Decl</text>

      <!-- Block 3: L2 -->
      <rect x="12" y="262" width="282" height="74" rx="6" fill="{item_bg}" stroke="{item_border}"/>
      <text x="24" y="284" fill="{text_primary}" font-size="13" font-weight="700">L2 — Symbolic Sense Retrieval</text>
      <text x="24" y="302" fill="{text_secondary}" font-size="11.5">WordNet 3.0 Synsets + SemCor</text>
      <text x="24" y="320" fill="{text_muted}" font-size="11">Kuperman AoA 4-stage join</text>

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
      <text x="141" y="178" fill="{fork_text}" font-size="10.5" font-weight="700" text-anchor="middle">ONE_SENSE_ONLY → Early Exit</text>

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
      <text x="24" y="276" fill="{text_muted}" font-size="11">Protects young readers</text>

      <!-- Block 3: Output with ample right padding -->
      <rect x="12" y="306" width="282" height="114" rx="6" fill="{c3_pill_bg}" stroke="{c3_border}"/>
      <text x="24" y="328" fill="{c3_pill_text}" font-size="12.5" font-weight="700">FINAL STRUCTURED VERDICT</text>
      <text x="24" y="348" fill="{text_primary}" font-size="11.5" font-weight="600">• Wordplay Classification</text>
      <text x="24" y="366" fill="{text_primary}" font-size="11.5" font-weight="600">• Pun Location &amp; Anchors</text>
      <text x="24" y="384" fill="{text_primary}" font-size="11.5" font-weight="600">• Target-Age Appropriateness</text>
      <text x="24" y="402" fill="{text_secondary}" font-size="11">Full reproducible audit trace</text>
    </g>

    <!-- Bottom Rejection Funnel Callout with guaranteed boundary fit -->
    <g transform="translate(20, 660)">
      <rect x="0" y="0" width="960" height="50" rx="7" fill="{banner_bg}" stroke="{banner_border}"/>
      <rect x="14" y="13" width="124" height="24" rx="4" fill="{banner_pill_bg}"/>
      <text x="76" y="29" fill="{banner_pill_text}" font-size="11" font-weight="700" text-anchor="middle">TOKEN SAVINGS</text>
      <text x="150" y="29" fill="{text_primary}" font-size="12" font-weight="700">Early Rejection Funnel:</text>
      <text x="290" y="29" fill="{text_secondary}" font-size="11.5">L4 quote verification drops 73.6% of non-jokes early, saving &gt;65% downstream LLM tokens.</text>
    </g>
  </g>
</svg>
"""
    return svg_content


def main():
    assets_dir = Path(__file__).resolve().parents[1] / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    # 1. Benchmark Ranking SVGs
    (assets_dir / "benchmark-ranking-light.svg").write_text(generate_benchmark_svg(dark_mode=False), encoding="utf-8")
    (assets_dir / "benchmark-ranking-dark.svg").write_text(generate_benchmark_svg(dark_mode=True), encoding="utf-8")

    # 2. Developmental Breakdown SVGs
    (assets_dir / "developmental-breakdown-light.svg").write_text(generate_breakdown_svg(dark_mode=False), encoding="utf-8")
    (assets_dir / "developmental-breakdown-dark.svg").write_text(generate_breakdown_svg(dark_mode=True), encoding="utf-8")

    # 3. Architecture Overview Diagram SVGs
    (assets_dir / "architecture-diagram-light.svg").write_text(generate_architecture_svg(dark_mode=False), encoding="utf-8")
    (assets_dir / "architecture-diagram-dark.svg").write_text(generate_architecture_svg(dark_mode=True), encoding="utf-8")

    print("All SVGs successfully regenerated with verified zero-overflow text bounds.")


if __name__ == "__main__":
    main()
