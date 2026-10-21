import streamlit as st

st.title("PaisaPlan")
st.caption("AI-powered budget allocator")

income = st.number_input("Monthly income (₹)", min_value=0, step=500)
rent = st.number_input("Rent (₹)", min_value=0, step=500)
education = st.number_input("Education (₹)", min_value=0, step=500)
savings = st.number_input("Savings goal (₹)", min_value=0, step=500)

if st.button("Generate budget"):
    st.info("Solver not connected yet")