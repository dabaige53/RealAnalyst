# Demo Metadata Evidence

This file is the public, non-sensitive evidence note used by the demo retail
metadata fixtures. It exists so dictionary and mapping examples can point to a
real source artifact instead of a missing placeholder.

## Scope

- Dataset: `demo.retail.orders`
- Dictionary: `demo.retail.dictionary`
- Mapping: `demo.retail.orders.mapping`

## Evidence Notes

- `total_revenue` is represented as the sum of the demo order-level `revenue`
  field.
- `region` is represented as the sales region attached to each demo order.
- The demo intentionally keeps tax and shipping inclusion unresolved so
  metadata validation can exercise `needs_review` paths without private data.
