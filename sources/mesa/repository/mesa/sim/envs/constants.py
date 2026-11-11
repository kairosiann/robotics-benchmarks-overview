"""Shared semantic constants for the sim environments and predicates."""

# World-frame z height (meters) above which an object counts as "lifted" off
# the tabletop. Used by the `lifted` predicate (e.g. handoff tasks, where the
# pick object must be raised before the cross-arm transfer).
LIFT_HEIGHT_THRESHOLD = 1.0
