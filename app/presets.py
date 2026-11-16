"""Demo prompts and structured presets for showcasing PaisaPlan."""

CHAT_DEMO_PROMPTS = [
    {
        "label": "🎓 Entry-Level Earner",
        "description": "Balanced starter budget with rent, utilities, and a 10-month savings goal.",
        "prompt": (
            "I earn 45,000 a month. Rent is 14,000 and utilities are 2,500. "
            "Prioritize food and transport, and help me save 60,000 in 10 months."
        ),
    },
    {
        "label": "🏠 Young Professional",
        "description": "Higher income with multiple fixed bills and ranked priorities.",
        "prompt": (
            "My monthly salary is 95,000. Fixed costs: rent 28,000, internet 1,500, gym 2,000. "
            "Priorities are food, savings, and entertainment. I want to save 2,40,000 in 12 months."
        ),
    },
    {
        "label": "✂️ What-If: Cut Food Spend",
        "description": "Tests What-If reallocation (requires an active budget first).",
        "prompt": "What if I cut food spending by 3,000?",
    },
    {
        "label": "🛍️ What-If: Extra Shopping",
        "description": "Tests whether extra spending safely deducts from savings.",
        "prompt": "What if I spend 4,000 more on shopping?",
    },
    {
        "label": "🛡️ Guardrail: Missing Income",
        "description": "Verifies the pipeline asks for income instead of hallucinating one.",
        "prompt": "My rent is 15,000 and I want to save 50,000 in 5 months.",
    },
    {
        "label": "🚫 Infeasible Goal Check",
        "description": "Tests solver infeasibility detection when savings target exceeds income.",
        "prompt": "I earn 30,000 a month, rent is 18,000, and I want to save 2,00,000 in 6 months.",
    },
]

DEFAULT_CATEGORIES = [
    "food",
    "transport",
    "healthcare",
    "education",
    "entertainment",
    "shopping",
]

FORM_PRESETS = {
    "Custom": {
        "income": 60000,
        "rent": 18000,
        "utilities": 3000,
        "other_fixed": 0,
        "savings_amount": 100000,
        "savings_months": 10,
        "priorities": ["food", "transport"],
    },
    "Student / First Job (₹45k)": {
        "income": 45000,
        "rent": 14000,
        "utilities": 2500,
        "other_fixed": 1000,
        "savings_amount": 60000,
        "savings_months": 10,
        "priorities": ["food", "transport", "education"],
    },
    "Mid-Career Family (₹1.2L)": {
        "income": 120000,
        "rent": 35000,
        "utilities": 6000,
        "other_fixed": 8000,
        "savings_amount": 360000,
        "savings_months": 12,
        "priorities": ["food", "healthcare", "education", "transport"],
    },
}