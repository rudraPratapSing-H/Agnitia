#!/usr/bin/env python3
"""
Build the Final PowerPoint Deck (Task 3.12 - Member 4)
Full 12-slide deck per the battle plan's outline (section 13): slides 1-4 (Checkpoint 1),
5 (live demo cue), 6-8 (Checkpoint 2), and the new 9-12 (numbers, comparison, roadmap,
credits). Same dark theme as build_deck.py.

NOTE: slide 7 (evidence/proof) and the "Live demo" cue stay as styled text cards, not real
screenshots -- task 3.12 asks for "screenshots from the cp2 build," which needs a live,
tagged cp2 build to capture from. Swap in real screenshots once that build exists; see the
manual follow-ups list in the session summary.
"""

from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt

from build_deck import (
    SLIDE_WIDTH, SLIDE_HEIGHT,
    TEXT_PRIMARY, TEXT_MUTED,
    ACCENT_CYAN, ACCENT_RED, ACCENT_AMBER, ACCENT_GREEN, ACCENT_PURPLE,
    apply_dark_background, add_header, create_card,
    build_slide_1, build_slide_2, build_slide_3, build_slide_4,
)
from build_cp2_deck import build_slide_6_architecture, build_slide_7_evidence, build_slide_8_safety


def build_slide_5_live_demo(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    apply_dark_background(slide)
    add_header(slide, tag_text="AGNITIA • LIVE DEMO", headline_text="Live demo.")
    create_card(slide, Inches(0.8), Inches(2.6), Inches(11.733), Inches(3.5), border_color=ACCENT_CYAN)
    tb = slide.shapes.add_textbox(Inches(1.1), Inches(3.2), Inches(11.1), Inches(2.5))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "Switch to the app -- follow demo/checklist.md."
    p.font.size = Pt(28)
    p.font.bold = True
    p.font.color.rgb = TEXT_PRIMARY


def build_slide_9_numbers(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    apply_dark_background(slide)
    add_header(
        slide,
        tag_text="AGNITIA • RESULTS",
        headline_text="56 alerts became 1 incident, and recovery took 38 seconds instead of about 45 minutes.",
    )
    numbers = [("56 -> 1", "Alerts collapsed into one incident", ACCENT_PURPLE),
               ("~45 min -> 38s", "Manual triage vs. Agnitia's measured recovery", ACCENT_GREEN)]
    card_width = Inches(5.6)
    gap = Inches(0.53)
    left0 = Inches(0.8)
    for i, (big, small, color) in enumerate(numbers):
        left = left0 + i * (card_width + gap)
        create_card(slide, left, Inches(2.6), card_width, Inches(3.5), border_color=color)
        tb = slide.shapes.add_textbox(left + Inches(0.3), Inches(3.1), card_width - Inches(0.6), Inches(2.6))
        tf = tb.text_frame
        tf.word_wrap = True
        p1 = tf.paragraphs[0]
        p1.text = big
        p1.font.size = Pt(54)
        p1.font.bold = True
        p1.font.color.rgb = color
        p2 = tf.add_paragraph()
        p2.text = small
        p2.font.size = Pt(24)
        p2.font.color.rgb = TEXT_PRIMARY


def build_slide_10_comparison(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    apply_dark_background(slide)
    add_header(
        slide,
        tag_text="AGNITIA • HOW WE COMPARE",
        headline_text="Others group alerts or explain errors; Agnitia also fixes them in the right order.",
    )
    rows = [
        ("Capability", "Alert managers", "Enterprise observability AI", "Agnitia"),
        ("Groups an alert storm into one incident", "Yes", "Yes", "Yes, by the dependency graph"),
        ("Root cause with cited, machine-checked evidence", "Mostly no", "Partly", "Yes, every citation verified"),
        ("Multi-step recovery in dependency order", "No", "Via custom workflows", "Built in"),
        ("Needs its own full observability stack", "No", "Yes, priced per host/GB", "No; reads Kubernetes directly"),
        ("Predicts the crash before it happens", "Rarely", "Some", "Yes, for resource exhaustion"),
    ]
    top = Inches(2.3)
    row_h = Inches(0.75)
    col_lefts = [Inches(0.8), Inches(5.3), Inches(7.9), Inches(10.5)]
    col_widths = [Inches(4.5), Inches(2.6), Inches(2.6), Inches(2.63)]
    for r, row in enumerate(rows):
        is_header = r == 0
        for c, text in enumerate(row):
            tb = slide.shapes.add_textbox(col_lefts[c], top + r * row_h, col_widths[c], row_h)
            tf = tb.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = text
            p.font.size = Pt(18 if not is_header else 20)
            p.font.bold = is_header or c == 3
            p.font.color.rgb = ACCENT_CYAN if is_header else (ACCENT_GREEN if c == 3 else TEXT_PRIMARY)


def build_slide_11_roadmap(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    apply_dark_background(slide)
    add_header(
        slide,
        tag_text="AGNITIA • WHO PAYS, WHAT'S NEXT",
        headline_text="Built for teams running Kubernetes without a 24/7 reliability team.",
    )
    create_card(slide, Inches(0.8), Inches(2.5), Inches(5.6), Inches(4.5), border_color=ACCENT_CYAN)
    tb1 = slide.shapes.add_textbox(Inches(1.1), Inches(2.7), Inches(5.0), Inches(4.1))
    tf1 = tb1.text_frame
    tf1.word_wrap = True
    p1 = tf1.paragraphs[0]
    p1.text = "WHO PAYS"
    p1.font.size = Pt(26)
    p1.font.bold = True
    p1.font.color.rgb = ACCENT_CYAN
    for line in ["Small teams running Kubernetes", "without a 24/7 SRE rotation.", "Per-cluster pricing, starting", "with Indian SaaS startups."]:
        p = tf1.add_paragraph()
        p.text = line
        p.font.size = Pt(24)
        p.font.color.rgb = TEXT_PRIMARY

    create_card(slide, Inches(6.8), Inches(2.5), Inches(5.7), Inches(4.5), border_color=ACCENT_AMBER)
    tb2 = slide.shapes.add_textbox(Inches(7.1), Inches(2.7), Inches(5.1), Inches(4.1))
    tf2 = tb2.text_frame
    tf2.word_wrap = True
    p2 = tf2.paragraphs[0]
    p2.text = "ROADMAP"
    p2.font.size = Pt(26)
    p2.font.bold = True
    p2.font.color.rgb = ACCENT_AMBER
    for line in ["Auto-discovered dependency maps", "(service mesh / OpenTelemetry).", "More fault types beyond the four demoed.", "Slack and PagerDuty integrations."]:
        p = tf2.add_paragraph()
        p.text = line
        p.font.size = Pt(24)
        p.font.color.rgb = TEXT_PRIMARY


def build_slide_12_credits(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    apply_dark_background(slide)
    add_header(slide, tag_text="AGNITIA", headline_text="Built in 18 hours.")
    create_card(slide, Inches(0.8), Inches(2.6), Inches(11.733), Inches(3.8), border_color=ACCENT_GREEN)
    tb = slide.shapes.add_textbox(Inches(1.1), Inches(2.9), Inches(11.1), Inches(3.3))
    tf = tb.text_frame
    tf.word_wrap = True
    roles = [
        "Member 1 -- Frontend: mission control UI, dependency map, approval flow",
        "Member 2 -- Backend & simulator: FastAPI, event bus, executor, crash predictor",
        "Member 3 -- AI agents: diagnose/plan/verify pipeline, citations, autonomy, memory",
        "Member 4 -- Content & integrations: scenarios, Telegram bot, decks, rehearsal",
        "",
        "Thank you. (QR code to the demo video goes here.)",
    ]
    for i, line in enumerate(roles):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = line
        p.font.size = Pt(24)
        p.font.color.rgb = TEXT_MUTED if line == "" else TEXT_PRIMARY


def main():
    prs = Presentation()
    prs.slide_width = SLIDE_WIDTH
    prs.slide_height = SLIDE_HEIGHT

    build_slide_1(prs)
    build_slide_2(prs)
    build_slide_3(prs)
    build_slide_4(prs)
    build_slide_5_live_demo(prs)
    build_slide_6_architecture(prs)
    build_slide_7_evidence(prs)
    build_slide_8_safety(prs)
    build_slide_9_numbers(prs)
    build_slide_10_comparison(prs)
    build_slide_11_roadmap(prs)
    build_slide_12_credits(prs)

    repo_root = Path(__file__).resolve().parent.parent
    demo_dir = repo_root / "demo"
    out = demo_dir / "final-deck.pptx"
    prs.save(str(out))
    print(f"Saved the {len(prs.slides._sldIdLst)}-slide final deck to: {out.name}")


if __name__ == "__main__":
    main()
