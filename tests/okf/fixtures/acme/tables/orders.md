---
type: BigQuery Table
title: Orders
description: One row per completed customer order across all channels.
resource: https://console.cloud.google.com/bigquery?p=acme&d=sales&t=orders
tags: [sales, orders, revenue]
timestamp: 2026-06-27T10:00:00Z
---

# Schema

| Column        | Type      | Description                                |
|---------------|-----------|--------------------------------------------|
| `order_id`    | STRING    | Globally unique order identifier.          |
| `customer_id` | STRING    | FK into [customers](/tables/customers.md). |
| `channel`     | STRING    | One of `web`, `app`, `store`.              |
| `total_usd`   | NUMERIC   | Order total in US dollars.                 |
| `placed_at`   | TIMESTAMP | When the customer submitted the order.     |

Part of how we measure [customer lifetime value](/concepts/customer-lifetime-value.md).

# Citations
[1] [Orders table in BigQuery](https://console.cloud.google.com/bigquery?p=acme&d=sales&t=orders)
