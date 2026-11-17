import os
import sys
import urllib.request

# ---------------------------------------------------------
# Project path setup (MUST be before ANY other imports)
# ---------------------------------------------------------
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import streamlit as st

# ---------------------------------------------------------
# Page configuration (MUST be the first Streamlit command)
# ---------------------------------------------------------
st.set_page_config(
    page_title="PaisaPlan — AI Constraint Budget Planner",
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------
# Project imports (UPDATED TO model_pp)
# ---------------------------------------------------------
from model_pp.ollama_client import make_chat
from model_pp.pipeline import Pipeline

try:
    from app.styles import CUSTOM_CSS
    from app.presets import (
        CHAT_DEMO_PROMPTS,
        DEFAULT_CATEGORIES,
        FORM_PRESETS,
    )
    from app.components import render_reply_card

except ModuleNotFoundError:
    from styles import CUSTOM_CSS
    from presets import CHAT_DEMO_PROMPTS, DEFAULT_CATEGORIES, FORM_PRESETS
    from components import render_reply_card


# ---------------------------------------------------------
# Apply custom CSS
# ---------------------------------------------------------
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------
# Ollama connection
# ---------------------------------------------------------
def check_ollama_health(
    base_url: str = "http://127.0.0.1:11434"
) -> bool:

    try:
        with urllib.request.urlopen(
            f"{base_url}/api/tags",
            timeout=1.5
        ) as response:

            return response.status == 200

    except Exception:
        return False


# ---------------------------------------------------------
# Pipeline creation and caching
# ---------------------------------------------------------
@st.cache_resource
def get_pipeline(model_name: str) -> Pipeline:

    return Pipeline(make_chat(model_name))


# ---------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------
def init_session_state():

    defaults = {
        "chat_history": [],
        "active_problem": None,
        "previous_result": None,
        "selected_model": "paisaplan",
        "queued_prompt": None,
    }

    for key, value in defaults.items():

        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()


# ---------------------------------------------------------
# Sidebar
# ---------------------------------------------------------
with st.sidebar:

    st.title("💸 PaisaPlan")

    st.caption(
        "Neuro-Symbolic Personal Finance & CSP Budget Solver"
    )

    # Ollama status
    ollama_online = check_ollama_health()

    if ollama_online:

        st.success("● Ollama Connected (Local LLM Ready)")

    else:

        st.warning("● Ollama Offline — Form Mode Available")

    # Model selection
    model_name = st.selectbox(
        "Active LLM Model",
        options=[
            "paisaplan",
            "llama3.2:3b",
        ],
        index=0,
        key="sidebar_model_selectbox_v2",
        help=(
            "paisaplan is the fine-tuned GGUF model; "
            "llama3.2:3b is the base comparison model."
        ),
    )

    st.session_state.selected_model = model_name

    pipe = get_pipeline(model_name)

    st.divider()

    # Demo prompts (Now inside an expander so they are hidden by default)
    with st.expander("⚡ One-Click Demo Prompts"):
        for idx, item in enumerate(CHAT_DEMO_PROMPTS):
            if st.button(
                item["label"],
                help=item["description"],
                use_container_width=True,
                key=f"demo_btn_v2_{idx}",
            ):
                st.session_state.queued_prompt = item["prompt"]
                st.rerun()

    st.divider()

    # Reset session
    if st.button(
        "🗑️ Reset Session & Active Budget",
        use_container_width=True,
        key="reset_session_btn_v2",
    ):

        st.session_state.chat_history = []
        st.session_state.active_problem = None
        st.session_state.previous_result = None
        st.session_state.queued_prompt = None

        st.rerun()

    st.divider()

    # Guardrails
    st.markdown(
        """
        **Neuro-Symbolic Guardrails**

        - <span class="provenance-badge badge-certain">
          CERTAIN</span> Numbers computed by the CSP solver.

        - <span class="provenance-badge badge-estimate">
          ESTIMATE</span> LLM narrative checked against hallucination filters.
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------
# Main header
# ---------------------------------------------------------
st.title("PaisaPlan Budget Assistant")

st.caption(
    "Enter your monthly income, fixed bills, spending priorities, "
    "and savings goals in natural language — or test What-If "
    "changes against a mathematically verified constraint solver."
)


# ---------------------------------------------------------
# Navigation tabs
# ---------------------------------------------------------
tab_chat, tab_form = st.tabs(
    [
        "💬 Natural Language Chat & What-If",
        "📋 Structured Form Planner (Offline Fallback)",
    ]
)


# =========================================================
# TAB 1: CHAT + WHAT-IF SIMULATOR
# =========================================================
with tab_chat:

    # Show active budget
    if st.session_state.active_problem:

        inc = st.session_state.active_problem.get("income")

        st.info(
            "Active Budget Context Loaded"
            + (
                f" (Income: ₹{inc:,.0f}/month)"
                if isinstance(inc, (int, float))
                else ""
            )
            + " — You can now ask What-If questions like "
            "'What if I cut food by 2,000?'"
        )

    # Display chat history
    for idx, entry in enumerate(st.session_state.chat_history):

        with st.chat_message(entry["role"]):

            if entry["role"] == "user":

                st.markdown(entry["content"])

            else:
                # Display which model answered this specific prompt
                model_used = entry.get("model_name", "Unknown Model")
                st.caption(f"🤖 Answered by: **{model_used}**")
                
                render_reply_card(
                    entry["reply"],
                    previous_result=entry.get("previous_result"),
                )

    # Chat input
    prompt = st.chat_input(
        "Describe your budget (e.g., 'I earn 60,000, rent is "
        "18,000, prioritize food, save 1,00,000 in 10 months')..."
    )

    # Handle demo prompts
    if st.session_state.queued_prompt is not None:

        prompt = st.session_state.queued_prompt
        st.session_state.queued_prompt = None

    # Process prompt
    if prompt:

        st.session_state.chat_history.append(
            {
                "role": "user",
                "content": prompt,
            }
        )

        with st.chat_message("user"):

            st.markdown(prompt)

        with st.chat_message("assistant"):

            # Display the model name while it's loading
            st.caption(f"🤖 Generating response using: **{st.session_state.selected_model}**")

            with st.spinner(
                "Parsing constraints & solving optimal allocation..."
            ):

                prev_res = st.session_state.previous_result

                try:

                    reply = pipe.handle(
                        prompt,
                        problem=st.session_state.active_problem,
                    )

                except Exception as exc:

                    reply = {
                        "status": "error",
                        "message": (
                            f"Could not connect to Ollama (`{exc}`). "
                            "Please start Ollama or switch to the "
                            "**Structured Form Planner** tab."
                        ),
                        "problem": st.session_state.active_problem,
                        "result": None,
                        "explanation": {
                            "segments": []
                        },
                    }

                # Update active problem
                if reply.get("problem") is not None:

                    st.session_state.active_problem = reply["problem"]

                # Update previous result
                if reply.get("result") is not None:

                    st.session_state.previous_result = reply["result"]

                # Display response
                render_reply_card(
                    reply,
                    previous_result=prev_res,
                )

                # Save assistant response (WITH MODEL NAME)
                st.session_state.chat_history.append(
                    {
                        "role": "assistant",
                        "reply": reply,
                        "previous_result": prev_res,
                        "model_name": st.session_state.selected_model,
                    }
                )


# =========================================================
# TAB 2: STRUCTURED FORM PLANNER
# =========================================================
with tab_form:

    st.subheader("Structured Constraint Budget Form")

    st.caption(
        "Calls pipe.plan(form_data) directly on the CSP solver — "
        "works even when Ollama is offline, provided the solver "
        "does not require the LLM."
    )

    # Callback function to update session state when dropdown changes
    def update_form_from_preset():
        selected = st.session_state.form_preset_selectbox_v2
        p = FORM_PRESETS[selected]
        
        st.session_state.form_income_v2 = int(p["income"])
        st.session_state.form_rent_v2 = int(p["rent"])
        st.session_state.form_utilities_v2 = int(p["utilities"])
        st.session_state.form_other_fixed_v2 = int(p["other_fixed"])
        st.session_state.form_savings_amount_v2 = int(p["savings_amount"])
        st.session_state.form_savings_months_v2 = int(p["savings_months"])
        st.session_state.form_priorities_v2 = p["priorities"]

    # Sample profile selection
    preset_choice = st.selectbox(
        "Load Sample Profile",
        options=list(FORM_PRESETS.keys()),
        key="form_preset_selectbox_v2",
        on_change=update_form_from_preset,
    )

    # Budget form
    with st.form("structured_budget_form_v2"):

        col1, col2 = st.columns(2)

        with col1:

            income = st.number_input(
                "Monthly Income (₹)",
                min_value=0,
                step=1000,
                key="form_income_v2",
            )

            rent = st.number_input(
                "Monthly Rent (₹)",
                min_value=0,
                step=500,
                key="form_rent_v2",
            )

            utilities = st.number_input(
                "Utilities & Bills (₹)",
                min_value=0,
                step=500,
                key="form_utilities_v2",
            )

            other_fixed = st.number_input(
                "Other Fixed Commitments (₹)",
                min_value=0,
                step=500,
                key="form_other_fixed_v2",
            )

        with col2:

            savings_amount = st.number_input(
                "Total Savings Target (₹)",
                min_value=0,
                step=5000,
                key="form_savings_amount_v2",
            )

            savings_months = st.number_input(
                "Months to Reach Goal",
                min_value=1,
                step=1,
                key="form_savings_months_v2",
            )

            priorities = st.multiselect(
                "Spending Priorities (Highest to Lowest)",
                options=DEFAULT_CATEGORIES,
                key="form_priorities_v2",
            )

        submitted = st.form_submit_button(
            "Solve Optimal Budget",
            type="primary",
        )

    # Process form submission
    if submitted:

        fixed_costs = {}

        if rent > 0:
            fixed_costs["rent"] = int(rent)

        if utilities > 0:
            fixed_costs["utilities"] = int(utilities)

        if other_fixed > 0:
            fixed_costs["other_fixed"] = int(other_fixed)

        form_data = {
            "income": int(income),
            "fixed_costs": fixed_costs,
            "priorities": priorities,
            "savings_goal": (
                {
                    "amount": int(savings_amount),
                    "months": int(savings_months),
                }
                if savings_amount > 0
                else None
            ),
        }

        prev_res = st.session_state.previous_result

        with st.spinner(
            "Solving optimal allocation from structured form..."
        ):

            try:

                reply = pipe.plan(form_data)

            except Exception as exc:

                reply = {
                    "status": "error",
                    "message": (
                        f"Could not connect to Ollama (`{exc}`). "
                        "Please start Ollama or switch to the "
                        "**Natural Language Chat** tab."
                    ),
                    "problem": None,
                    "result": None,
                    "explanation": {
                        "segments": []
                    },
                }

            # Update state
            if reply.get("problem") is not None:

                st.session_state.active_problem = reply["problem"]

            if reply.get("result") is not None:

                st.session_state.previous_result = reply["result"]

            # Display result
            render_reply_card(
                reply,
                previous_result=prev_res,
            )

            # Save result in chat history
            st.session_state.chat_history.append(
                {
                    "role": "assistant",
                    "reply": reply,
                    "previous_result": prev_res,
                    "model_name": f"{st.session_state.selected_model} (Form Mode)",
                }
            )