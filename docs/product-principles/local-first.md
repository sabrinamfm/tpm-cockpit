# Local-First

## Principle

TPM Cockpit should work locally first.

The application should not require a cloud account, hosted database, or external service to be useful.

## Why This Matters

TPM work can include sensitive operational information.

A local-first model allows the user to:

- keep real work data private
- experiment safely
- use the app without company infrastructure
- update the code without overwriting saved data

## Implementation Rule

The app code can be version-controlled.

The real workspace data must remain local and gitignored.