# Cross-Domain Translation Table

The table below summarizes mappings observed from recent domain test runs. Use the dashboard to trigger new runs and expand this table automatically.

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
| `temp_c` | `temperature_celsius` | weather | 0.96 |
| `wind_speed_kph` | `wind_speed_kph` | weather | 0.94 |
| `alt_m` | `altitude_meters` | aerospace | 0.97 |
| `vel_mps` | `velocity_meters_per_second` | aerospace | 0.95 |
| `v_rms` | `voltage_rms` | smart-grid | 0.98 |
| `f_hz` | `frequency_hertz` | smart-grid | 0.96 |
| `goal_cnt` | `goals_scored` | hockey | 0.95 |
| `assist_cnt` | `assists` | hockey | 0.93 |
| `shots_on_target` | `shots_on_goal` | soccer | 0.96 |
| `possession_pct` | `possession_percentage` | soccer | 0.98 |
| `td_run` | `rushing_touchdowns` | football | 0.94 |
| `yd_gain` | `yards_gained` | football | 0.92 |
| `fg_pct` | `field_goal_percentage` | basketball | 0.97 |
| `reb_cnt` | `rebounds` | basketball | 0.95 |
| `hr_cnt` | `home_runs` | baseball | 0.96 |
| `era_val` | `earned_run_average` | baseball | 0.94 |
| `item_price_cents` | `price` | ecommerce | 0.90 |
| `qty_sold` | `units_sold` | ecommerce | 0.88 |

## Notes

- Table generated from JSON results in `docs/data/domain-tests/` (timestamped files).
- Confidence scores reflect Tier 2 BERT semantic inference probability.
