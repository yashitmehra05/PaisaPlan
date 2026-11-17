"""Reusable Streamlit rendering components for PaisaPlan."""

from html import escape
from typing import Any, Dict, List, Optional
import pandas as pd
import streamlit as st


def extract_allocation(result: Any) -> Dict[str, float]:
    """Safely extract category -> amount mapping from various solver result shapes."""
    if not isinstance(result, dict):
        return {}
    for key in ("allocation", "budget", "plan", "categories"):
        candidate = result.get(key)
        if isinstance(candidate, dict) and candidate:
            return {
                str(k): float(v)
                for k, v in candidate.items()
                if isinstance(v, (int, float))
            }
    return {}


def build_allocation_dataframe(
    allocation: Dict[str, float],
    previous_allocation: Optional[Dict[str, float]] = None,
) -> pd.DataFrame:
    """Build a clean DataFrame for tables, charts, and optional What-If deltas."""
    rows = []
    total = sum(allocation.values()) or 1.0
    for cat, amt in allocation.items():
        row: Dict[str, Any] = {
            "Category": cat.replace("_", " ").title(),
            "Monthly (₹)": round(amt, 2),
            "Share (%)": round((amt / total) * 100, 1),
        }
        if previous_allocation and cat in previous_allocation:
            diff = round(amt - previous_allocation[cat], 2)
            row["Change (₹)"] = f"{diff:+,.0f}" if diff != 0 else "0"
        rows.append(row)
    return pd.DataFrame(rows)


def render_provenance_segments(segments: List[Dict[str, Any]]) -> None:
    """Render explanation segments with [CERTAIN] vs [ESTIMATE] badges."""
    if not segments:
        return

    st.markdown("##### Verified Explanation & Provenance")
    for seg in segments:
        raw_label = str(seg.get("label", "certain")).strip().lower()
        text = escape(str(seg.get("text", "")).strip())
        if not text:
            continue

        if raw_label == "estimate":
            st.markdown(
                f'<div class="provenance-card provenance-estimate">'
                f'<span class="provenance-badge badge-estimate">ESTIMATE</span>{text}'
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="provenance-card provenance-certain">'
                f'<span class="provenance-badge badge-certain">CERTAIN</span>{text}'
                f"</div>",
                unsafe_allow_html=True,
            )


def render_status_badge(status: str) -> None:
    """Display a compact status pill indicating pipeline outcome."""
    normalized = (status or "unknown").lower()
    if normalized in {"ok", "solved", "success", "planned", "whatif"}:
        css_cls = "status-ok"
        label = f"Status: {status}"
    elif normalized in {"need_info", "clarify", "missing_income", "infeasible"}:
        css_cls = "status-warn"
        label = f"Status: {status}"
    else:
        css_cls = "status-err"
        label = f"Status: {status}"

    st.markdown(f'<span class="status-pill {css_cls}">{escape(label)}</span>', unsafe_allow_html=True)


def render_reply_card(
    reply: Dict[str, Any],
    previous_result: Optional[Dict[str, Any]] = None,
) -> None:
    """Render full structured output from pipe.handle() or pipe.plan()."""
    status = str(reply.get("status", ""))
    message = reply.get("message", "")
    result = reply.get("result")
    problem = reply.get("problem")
    explanation = reply.get("explanation") or {}
    segments = explanation.get("segments") or []

    if status:
        render_status_badge(status)

    if message:
        st.markdown(message)

    # 1. Provenance-tagged explanation
    if segments:
        render_provenance_segments(segments)

    # 2. Solver metrics & allocation breakdown
    allocation = extract_allocation(result)
    prev_allocation = extract_allocation(previous_result)

    if allocation:
        st.markdown("##### Monthly Budget Allocation")

        income = None
        if isinstance(result, dict) and isinstance(result.get("income"), (int, float)):
            income = result["income"]
        elif isinstance(problem, dict) and isinstance(problem.get("income"), (int, float)):
            income = problem["income"]

        total_allocated = sum(allocation.values())
        savings_val = allocation.get("savings")

        m_cols = st.columns(3)
        m_cols[0].metric(
            "Monthly Income",
            f"₹{income:,.0f}" if income is not None else f"₹{total_allocated:,.0f}",
        )
        m_cols[1].metric(
            "Monthly Savings",
            f"₹{savings_val:,.0f}" if savings_val is not None else "—",
            delta=(
                f"{savings_val - prev_allocation['savings']:+,.0f}"
                if savings_val is not None and "savings" in prev_allocation and savings_val != prev_allocation["savings"]
                else None
            ),
        )
        m_cols[2].metric(
            "Categories Solved",
            str(len(allocation)),
        )

        df = build_allocation_dataframe(allocation, prev_allocation if prev_allocation else None)
        chart_col, table_col = st.columns([3, 2])
        with chart_col:
            st.bar_chart(df.set_index("Category")["Monthly (₹)"])
        with table_col:
            st.dataframe(df, hide_index=True, use_container_width=True)

    # The collapsible raw solver & problem inspection block has been removed as requested.