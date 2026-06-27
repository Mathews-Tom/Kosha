---
type: Playbook
title: Diagnose a revenue drop
description: Steps to triage when daily revenue falls more than 15% week-over-week.
tags: [revenue, oncall, diagnostics]
timestamp: 2026-06-27T10:00:00Z
---

# Trigger
Run this when someone reports — or a monitor detects — a >15% WoW drop in
daily revenue from the [orders table](/tables/orders.md).

# Steps
1. Break the drop down by `channel` using the query in [orders](/tables/orders.md).
2. Check whether the decline correlates with [peak-season returns](/concepts/peak-season-returns.md).
3. Segment by new vs returning via [customer lifetime value](/concepts/customer-lifetime-value.md).
4. If one channel dominates the drop, escalate to that channel's owner.

# Citations
[1] [Internal revenue runbook](https://wiki.acme.internal/revenue/runbook)
