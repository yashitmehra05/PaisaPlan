# CSP Formulation

## Variables
food, transport, entertainment, other

## Domain
Rupee amounts in steps of 500, between a minimum and maximum per category.

## Hard constraints
- Total spend <= income
- Rent and education are fixed (solver cannot change them)
- Savings goal must be met

## Soft constraints
User's priority order (to be added in the next version)