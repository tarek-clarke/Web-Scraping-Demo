# Cross-Domain Translation Matrix

The table below summarizes mappings observed from recent domain test runs. Use the dashboard to trigger new runs and expand this matrix automatically.

| Original Field | Translated Field | Domain | Confidence |
|---|---|---|---:|
| `post_engagement_metric` | `post_engagement` | social-media | 0.92 |
| `follower_cnt` | `user_follower_count` | social-media | 0.89 |
| `closing_price` | `closing_price` | finance | 1.00 |
| `daily_vol` | `daily_volume` | finance | 0.94 |
| `gas_reserve_pct` | `fuel_reserve_percentage` | automotive | 0.98 |
| `oil_temp` | `lubricant_temperature` | automotive | 0.97 |
| `pulse_bpm` | `heart_rate` | healthcare | 0.95 |
| `spo2_saturation` | `blood_oxygen_pct` | healthcare | 0.93 |
| `item_price_cents` | `price` | ecommerce | 0.90 |
| `qty_sold` | `units_sold` | ecommerce | 0.88 |

## Notes

- Table generated from JSON results in `docs/data/domain-tests/` (timestamped files).
- Confidence scores reflect Tier 2 BERT semantic inference probability.
