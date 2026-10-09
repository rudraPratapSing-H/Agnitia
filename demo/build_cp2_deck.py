#!/usr/bin/env python3
"""
Build Checkpoint 2 PowerPoint Deck (Task 2.16 - Member 4)
Adds slides 6-8 from the battle plan's 12-slide outline (section 13) on top of the
Checkpoint 1 deck: the architecture diagram, the evidence/proof slide, and the safety
slide (allow-list, approval gate, autonomy levels, audit log). Same dark theme as
build_deck.py (16:9, no text under 24pt, one visual per slide, jargon explained inline).
"""

from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.shapes import MSO_SHAPE

from build_deck import (
    SLIDE_WIDTH, SLIDE_HEIGHT,
    TEXT_PRIMARY, TEXT_MUTED,
    ACCENT_CYAN, ACCENT_RED, ACCENT_AMBER, ACCENT_GREEN, ACCENT_PURPLE,
    apply_dark_background, add_header, create_card,
    build_slide_1, build_slide_2, build_slide_3, build_slide_4,
)


def build_slide_6_architecture(prs):
    # Slide 6: "Five AI agents, one dependency map, and a human in control."
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    apply_dark_background(slide)
    add_header(
        slide,
        tag_text="AGNITIA • CHECKPOINT 2 • ARCHITECTURE",
        headline_text="Five AI agents, one dependency map, and a human in control.",
        jargon_text="*Jargon: Agent = one focused AI step (e.g. \"diagnose\") in a larger pipeline.",
    )

    layers = [
        ("TIER 1 • REACT OPERATOR UI", "Live dependency map • Evidence drawer • Approval modal with config diff", ACCENT_CYAN),
        ("TIER 2 • FIVE-AGENT PIPELINE", "Triage -> Diagnose -> Plan -> Approve -> Verify, streamed live over WebSocket", ACCENT_PURPLE),
        ("TIER 3 • FASTAPI + CLUSTER ADAPTER", "Topology graph, playbook executor, audit log, simulator or real Kubernetes", ACCENT_GREEN),
    ]
    top_pos = Inches(2.5)
    layer_height = Inches(1.3)
    layer_gap = Inches(0.25)
    for i, (title, desc, color) in enumerate(layers):
        curr_top = top_pos + i * (layer_height + layer_gap)
        create_card(slide, Inches(0.8), curr_top, Inches(11.733), layer_height, border_color=color)
        tb = slide.shapes.add_textbox(Inches(1.1), curr_top + Inches(0.15), Inches(11.1), layer_height - Inches(0.3))
        tf = tb.text_frame
        tf.word_wrap = True
        p_t = tf.paragraphs[0]
        p_t.text = title
        p_t.font.size = Pt(26)
        p_t.font.bold = True
        p_t.font.color.rgb = color
        p_d = tf.add_paragraph()
        p_d.text = desc
        p_d.font.size = Pt(24)
        p_d.font.color.rgb = TEXT_PRIMARY


def build_slide_7_evidence(prs):
    # Slide 7: "Every claim comes with proof the AI can't fake."
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    apply_dark_background(slide)
    add_header(
        slide,
        tag_text="AGNITIA • CHECKPOINT 2 • VERIFIED EVIDENCE",
        headline_text="Every claim comes with proof the AI can't fake.",
        jargon_text="*Jargon: Exit code 137 = the system stopped the program for using too much memory.",
    )

    create_card(slide, Inches(0.8), Inches(2.4), Inches(11.733), Inches(4.5), border_color=ACCENT_GREEN)
    tb = slide.shapes.add_textbox(Inches(1.1), Inches(2.6), Inches(11.1), Inches(4.1))
    tf = tb.text_frame
    tf.word_wrap = True

    p0 = tf.paragraphs[0]
    p0.text = "Evidence Drawer — Root cause: postgres (confidence 97%)"
    p0.font.size = Pt(26)
    p0.font.bold = True
    p0.font.color.rgb = ACCENT_GREEN

    rows = [
        ("VERIFIED", "log  postgres-0:42", "FATAL: out of memory (allocated 67108864 bytes, limit 67108864 bytes)"),
        ("VERIFIED", "k8s_event  postgres-0", "Reason: OOMKilled, Exit Code: 137"),
        ("VERIFIED", "metric  postgres-0", "mem_mb: 64.0 / limit 64.0"),
        ("NOT FOUND — confidence -0.2", "log  (planted)", "a citation that doesn't exist in the raw log is caught, not trusted"),
    ]
    for tag, source, text in rows:
        p = tf.add_paragraph()
        p.text = f"[{tag}]  {source} — “{text}”"
        p.font.size = Pt(24)
        p.font.color.rgb = ACCENT_RED if "NOT FOUND" in tag else TEXT_PRIMARY

    p_note = tf.add_paragraph()
    p_note.text = "Every citation is checked against the raw log/event/metric data before it reaches a human."
    p_note.font.size = Pt(24)
    p_note.font.color.rgb = TEXT_MUTED


def build_slide_8_safety(prs):
    # Slide 8: "The AI can only do what we allow, and it asks before anything risky."
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    apply_dark_background(slide)
    add_header(
        slide,
        tag_text="AGNITIA • CHECKPOINT 2 • SAFETY",
        headline_text="The AI can only do what we allow, and it asks before anything risky.",
        jargon_text="*Jargon: Allow-list = a fixed set of actions the AI is permitted to run; nothing else is possible.",
    )

    cols = [
        ("ALLOW-LIST", [
            "patch_memory_limit", "patch_cpu_limit", "rollout_restart",
            "rollback_deployment", "scale_replicas", "wait_for_ready", "verify_health",
            "Nothing that deletes.",
        ], ACCENT_CYAN),
        ("APPROVAL GATE", [
            "High-risk steps (resource/config changes)",
            "always wait for a human — on screen",
            "or from a phone via Telegram.",
            "",
            "Autonomy levels 1-3 set how much",
            "runs on its own vs. waits.",
        ], ACCENT_AMBER),
        ("AUDIT LOG", [
            "Every decision is recorded:",
            "who approved, what ran, what it",
            "verified, and any rollback —",
            "one entry per action, in order.",
        ], ACCENT_GREEN),
    ]
    col_width = Inches(3.75)
    col_gap = Inches(0.24)
    start_left = Inches(0.8)
    for i, (title, items, color) in enumerate(cols):
        left = start_left + i * (col_width + col_gap)
        create_card(slide, left, Inches(2.5), col_width, Inches(4.5), border_color=color)
        tb = slide.shapes.add_textbox(left + Inches(0.2), Inches(2.7), col_width - Inches(0.4), Inches(4.1))
        tf = tb.text_frame
        tf.word_wrap = True
        p_t = tf.paragraphs[0]
        p_t.text = title
        p_t.font.size = Pt(26)
        p_t.font.bold = True
        p_t.font.color.rgb = color
        for item in items:
            p_i = tf.add_paragraph()
            p_i.text = f"• {item}" if item else ""
            p_i.font.size = Pt(22 if item else 10)
            p_i.font.color.rgb = TEXT_PRIMARY


def main():
    repo_root = Path(__file__).resolve().parent.parent
    demo_dir = repo_root / "demo"

    # New slides on their own (what task 2.16 actually asked for).
    new_only = Presentation()
    new_only.slide_width = SLIDE_WIDTH
    new_only.slide_height = SLIDE_HEIGHT
    build_slide_6_architecture(new_only)
    build_slide_7_evidence(new_only)
    build_slide_8_safety(new_only)
    out_new = demo_dir / "cp2-slides-6-8.pptx"
    new_only.save(str(out_new))

    # Combined deck: cp1-deck's 4 slides, then these 3 new ones -- one file to present from.
    combined = Presentation()
    combined.slide_width = SLIDE_WIDTH
    combined.slide_height = SLIDE_HEIGHT
    build_slide_1(combined)
    build_slide_2(combined)
    build_slide_3(combined)
    build_slide_4(combined)
    build_slide_6_architecture(combined)
    build_slide_7_evidence(combined)
    build_slide_8_safety(combined)
    out_combined = demo_dir / "cp2-deck.pptx"
    combined.save(str(out_combined))

    print(f"Saved new slides 6-8 to: {out_new.name}")
    print(f"Saved the combined Checkpoint 2 deck (cp1's 4 slides + new 6-8) to: {out_combined.name}")


if __name__ == "__main__":
    main()
