# Airline Metadata Example

This is a domain example, not a default RealAnalyst workflow.

Use it only when a dataset actually belongs to airline or transport operations. Keep real carrier names, route strategies, source IDs, and private benchmarks out of public metadata.

Example terms:

| Term | Generic Definition |
| --- | --- |
| Passenger load factor | Passenger demand divided by available seat capacity. |
| Available seat kilometers | Available seats multiplied by travel distance. |
| Revenue passenger kilometers | Paying passengers multiplied by travel distance. |
| Segment | One operated leg or market segment, depending on the dataset definition. |

When converting these terms into `metadata/datasets/*.yaml`, include evidence, confidence, and `needs_review` for any inferred business definition.
