# Cross-Domain Translation Matrix

The table below summarizes mappings observed from recent domain test runs (see `docs/data/domain-tests/`). Rows list detected original field names and the mapped canonical field per domain run.

| Original Field | social-media | finance | automotive | healthcare | ecommerce |
|---|---:|---:|---:|---:|---:|
| post_engagement_metric | `post_engagement` | - | - | - | - |
| follower_cnt | `user_follower_count` | - | - | - | - |
| closing_price | - | `closing_price` | - | - | - |
| daily_vol | - | `daily_volume` | - | - | - |
| gas_reserve_pct | - | - | `fuel_reserve_percentage` | - | - |
| oil_temp | - | - | `lubricant_temperature` | - | - |
| pulse_bpm | - | - | - | `heart_rate` | - |
| spo2_saturation | - | - | - | `blood_oxygen_pct` | - |
| item_price_cents | - | - | - | - | `price` |
| qty_sold | - | - | - | - | `units_sold` |

## Notes

- Table generated from JSON results in `docs/data/domain-tests/` (timestamped files).
- A dash (`-`) indicates no mapping observed for that original term in the given domain run.
- Use the dashboard to trigger more runs and expand this matrix automatically.
