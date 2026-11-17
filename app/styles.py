"""Custom CSS and visual styling helpers for the PaisaPlan Streamlit UI."""

CUSTOM_CSS = """
<style>
/* Main container spacing */
.block-container {
    padding-top: 1.75rem;
    padding-bottom: 2.5rem;
}

/* Provenance cards for solver-verified vs LLM-estimated text */
.provenance-card {
    padding: 12px 16px;
    border-radius: 8px;
    margin-bottom: 10px;
    line-height: 1.5;
    font-size: 0.95rem;
}

.provenance-certain {
    background-color: #ecfdf5;
    border-left: 5px solid #10b981;
    color: #064e3b;
}

.provenance-estimate {
    background-color: #fffbeb;
    border-left: 5px solid #f59e0b;
    color: #78350f;
}

.provenance-badge {
    display: inline-block;
    font-size: 0.72rem;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 4px;
    margin-right: 10px;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    vertical-align: middle;
}

.badge-certain {
    background-color: #10b981;
    color: #ffffff;
}

.badge-estimate {
    background-color: #f59e0b;
    color: #ffffff;
}

/* Status pill */
.status-pill {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 600;
    margin-bottom: 8px;
}

.status-ok {
    background-color: #dcfce7;
    color: #166534;
}

.status-warn {
    background-color: #fef3c7;
    color: #92400e;
}

.status-err {
    background-color: #fee2e2;
    color: #991b1b;
}

/* --- FIX FOR SELECTBOX CURSOR & RED OUTLINE --- */

/* 1. Hide the text cursor everywhere inside dropdowns */
div[data-baseweb="select"] input,
div[data-baseweb="select"] * {
    caret-color: transparent !important;
    cursor: pointer !important;
}

/* 2. Kill the red focus border globally on selectboxes and their wrappers */
div[data-baseweb="select"] > div,
div[data-baseweb="select"] > div:focus,
div[data-baseweb="select"] > div:focus-within,
div[data-baseweb="select"] > div:hover {
    border-color: rgba(255, 255, 255, 0.2) !important; /* Default dark gray */
    box-shadow: none !important;
    outline: none !important;
}

/* 3. Fix for Streamlit's newest baseweb wrapper structure */
.stSelectbox div[data-baseweb="select"] > div {
    background-color: transparent !important;
}

/* 4. Remove the red border on general inputs in the sidebar */
section[data-testid="stSidebar"] input {
    border-color: rgba(255, 255, 255, 0.2) !important;
    box-shadow: none !important;
}
</style>
"""