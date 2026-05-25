# Attention Model

## Purpose

The cockpit should help the TPM see what needs attention.

This is different from showing every open task.

Attention is about operational relevance, not just priority.

## Initial Attention Signals

Items may need attention when they are:

- blocked
- overdue
- stale
- missing an owner
- missing a next step
- linked to a high risk
- linked to an unresolved dependency
- waiting on a decision
- not updated recently

## Phase 1 Behavior

Phase 1 should use simple rules.

Examples:

- Work item is overdue
- Dependency has not been updated recently
- Risk is open and high severity
- Decision is pending
- Item has no owner

## Design Principle

The attention view should help a TPM answer:

> What do I need to look at today?