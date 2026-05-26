import random

class SchemaDrift:
    def __init__(self, probability: float):
        self.probability = probability

    def __call__(self, data: dict, drift_logger=None, run_number=1, api_source="api"):
        mutated, drift_type = self.apply_chaos(data, drift_logger, run_number, api_source)
        return mutated, drift_type

    def _split_column(self, data: dict, drift_logger=None, run_number=1, api_source="api"):
        mutated = {}
        drift_type = None
        for key, val in data.items():
            if ("name" in key or key == "canonical") and isinstance(val, str) and " " in val:
                parts = val.split(" ", 1)
                mutated["first_name"] = parts[0]
                mutated["last_name"] = parts[1]
                drift_type = "column_split"
                if drift_logger:
                    drift_logger.log_event(
                        api_source=api_source,
                        run_number=run_number,
                        chaos_strategy="schema",
                        chaos_level=self.probability,
                        drift_type="column_split",
                        original_field=key,
                        mutated_field="first_name,last_name",
                        metadata={"split_values": parts}
                    )
            elif key == "coordinates" and isinstance(val, dict):
                mutated["latitude"] = val.get("lat")
                mutated["longitude"] = val.get("lng")
                drift_type = "column_split"
                if drift_logger:
                    drift_logger.log_event(
                        api_source=api_source,
                        run_number=run_number,
                        chaos_strategy="schema",
                        chaos_level=self.probability,
                        drift_type="column_split",
                        original_field="coordinates",
                        mutated_field="latitude,longitude",
                        metadata={"split_keys": ["latitude", "longitude"]}
                    )
            else:
                mutated[key] = val
        if not drift_type:
            for key, val in data.items():
                if isinstance(val, str) and " " in val:
                    parts = val.split(" ", 1)
                    mutated = dict(data)
                    mutated.pop(key)
                    mutated[f"{key}_first"] = parts[0]
                    mutated[f"{key}_second"] = parts[1]
                    drift_type = "column_split"
                    break
        return mutated, drift_type

    def _merge_columns(self, data: dict, drift_logger=None, run_number=1, api_source="api"):
        mutated = dict(data)
        drift_type = None
        if "first_name" in mutated and "last_name" in mutated:
            f_name = mutated.pop("first_name")
            l_name = mutated.pop("last_name")
            mutated["full_name"] = f"{f_name} {l_name}"
            drift_type = "column_merge"
            if drift_logger:
                drift_logger.log_event(
                    api_source=api_source,
                    run_number=run_number,
                    chaos_strategy="schema",
                    chaos_level=self.probability,
                    drift_type="column_merge",
                    original_field="first_name,last_name",
                    mutated_field="full_name",
                    metadata={"merged_value": mutated["full_name"]}
                )
        elif "latitude" in mutated and "longitude" in mutated:
            lat = mutated.pop("latitude")
            lng = mutated.pop("longitude")
            mutated["location_coords"] = f"{lat},{lng}"
            drift_type = "column_merge"
            if drift_logger:
                drift_logger.log_event(
                    api_source=api_source,
                    run_number=run_number,
                    chaos_strategy="schema",
                    chaos_level=self.probability,
                    drift_type="column_merge",
                    original_field="latitude,longitude",
                    mutated_field="location_coords",
                    metadata={"merged_value": mutated["location_coords"]}
                )
        return mutated, drift_type

    def _split_units(self, data: dict, drift_logger=None, run_number=1, api_source="api"):
        mutated = {}
        drift_type = None
        for key, val in data.items():
            if "speed" in key and isinstance(val, (int, float)):
                mutated[f"{key}_value"] = val
                mutated[f"{key}_unit"] = "kph"
                drift_type = "unit_split"
                if drift_logger:
                    drift_logger.log_event(
                        api_source=api_source,
                        run_number=run_number,
                        chaos_strategy="schema",
                        chaos_level=self.probability,
                        drift_type="unit_split",
                        original_field=key,
                        mutated_field=f"{key}_value,{key}_unit",
                        metadata={"unit": "kph"}
                    )
            elif "temp" in key and isinstance(val, (int, float)):
                mutated[f"{key}_value"] = val
                mutated[f"{key}_unit"] = "celsius"
                drift_type = "unit_split"
                if drift_logger:
                    drift_logger.log_event(
                        api_source=api_source,
                        run_number=run_number,
                        chaos_strategy="schema",
                        chaos_level=self.probability,
                        drift_type="unit_split",
                        original_field=key,
                        mutated_field=f"{key}_value,{key}_unit",
                        metadata={"unit": "celsius"}
                    )
            elif "price" in key and isinstance(val, (int, float)):
                mutated[f"{key}_value"] = val
                mutated[f"{key}_unit"] = "USD"
                drift_type = "unit_split"
                if drift_logger:
                    drift_logger.log_event(
                        api_source=api_source,
                        run_number=run_number,
                        chaos_strategy="schema",
                        chaos_level=self.probability,
                        drift_type="unit_split",
                        original_field=key,
                        mutated_field=f"{key}_value,{key}_unit",
                        metadata={"unit": "USD"}
                    )
            else:
                mutated[key] = val
        if not drift_type:
            for key, val in data.items():
                if isinstance(val, (int, float)):
                    mutated = dict(data)
                    mutated.pop(key)
                    mutated[f"{key}_value"] = val
                    mutated[f"{key}_unit"] = "unit"
                    drift_type = "unit_split"
                    break
            else:
                mutated = dict(data)
        return mutated, drift_type

    def _flatten_nested(self, data: dict, drift_logger=None, run_number=1, api_source="api"):
        mutated = {}
        drift_type = None

        def flatten(obj, prefix=""):
            for k, v in obj.items():
                new_key = f"{prefix}{k}" if not prefix else f"{prefix}_{k}"
                if isinstance(v, dict):
                    flatten(v, new_key)
                else:
                    mutated[new_key] = v

        has_nesting = any(isinstance(v, dict) for v in data.values())

        if has_nesting:
            flatten(data)
            drift_type = "nested_flattening"
            if drift_logger:
                drift_logger.log_event(
                    api_source=api_source,
                    run_number=run_number,
                    chaos_strategy="schema",
                    chaos_level=self.probability,
                    drift_type="nested_flattening",
                    original_field="nested_schema",
                    mutated_field="flattened_schema",
                    metadata={"keys": list(mutated.keys())}
                )
        else:
            mutated = dict(data)
        return mutated, drift_type

    def _rename_keys(self, data: dict, drift_logger=None, run_number=1, api_source="api"):
        """Rename 1‑N keys using realistic variants."""
        intensity = int(round(self.probability * 100))
        n_renames = max(1, min(intensity, len(data)))
        keys = list(data.keys())
        chosen = random.sample(keys, min(n_renames, len(keys)))
        rename_map = {
            "address": "addr",
            "street_name": "streetName",
            "street_number": "streetNum",
            "price": "unit_price",
            "open_price": "openPx",
            "temperature": "tempC",
            "speed": "speed_kph",
            "wind_speed": "windKph",
            "capsule_serial": "capsuleId",
            "driver_name": "driver",
            "first_name": "firstName",
            "last_name": "lastName",
            "latitude": "lat",
            "longitude": "lng",
        }
        mutated = dict(data)
        drift_type = "renamed_keys"
        for k in chosen:
            new_key = rename_map.get(k, f"{k}_renamed")
            if new_key in mutated:
                new_key += "_2"
            mutated[new_key] = mutated.pop(k)
            if drift_logger:
                drift_logger.log_event(
                    api_source=api_source,
                    run_number=run_number,
                    chaos_strategy="schema",
                    chaos_level=self.probability,
                    drift_type=drift_type,
                    original_field=k,
                    mutated_field=new_key,
                    metadata={"intensity": intensity},
                )
        return mutated, drift_type

    def _nested_corruption(self, data: dict, drift_logger=None, run_number=1, api_source="api"):
        """Nest a flat field into an object, or flatten a nested object."""
        mutated = dict(data)
        drift_type = None
        keys = list(mutated.keys())
        if not keys:
            return mutated, None
        target_key = random.choice(keys)
        target_val = mutated[target_key]
        if isinstance(target_val, (str, int, float)) and not isinstance(target_val, bool):
            mutated[target_key] = {"raw": target_val}
            drift_type = "nested_corruption"
            if drift_logger:
                drift_logger.log_event(
                    api_source=api_source,
                    run_number=run_number,
                    chaos_strategy="schema",
                    chaos_level=self.probability,
                    drift_type=drift_type,
                    original_field=target_key,
                    mutated_field=f"{target_key}.raw",
                    metadata={"operation": "nest"}
                )
        elif isinstance(target_val, dict):
            for sub_key, sub_val in target_val.items():
                flat_key = f"{target_key}_{sub_key}"
                mutated[flat_key] = sub_val
            del mutated[target_key]
            drift_type = "nested_corruption"
            if drift_logger:
                drift_logger.log_event(
                    api_source=api_source,
                    run_number=run_number,
                    chaos_strategy="schema",
                    chaos_level=self.probability,
                    drift_type=drift_type,
                    original_field=f"{target_key}.*",
                    mutated_field=f"flattened_{target_key}",
                    metadata={"operation": "flatten"}
                )
        return mutated, drift_type

    def _apply_balanced_chaos(self, data: dict, drift_logger=None, run_number=1, api_source="api"):
        total_fields = len(data)
        if total_fields == 0:
            return data, None
        N = max(1, int(round(self.probability * total_fields)))
        N = min(N, total_fields)

        drift_types_pool = [
            "missing_keys",
            "extra_keys",
            "renamed_keys",
            "split_fields",
            "merged_fields",
            "nested_corruption",
            "value_contradiction"
        ]

        mutated = dict(data)
        used_keys = set()
        drift_type_log = None

        for _ in range(N):
            drift_type = random.choice(drift_types_pool)
            available = [k for k in mutated.keys() if k not in used_keys]
            if not available:
                break
            target_key = random.choice(available)
            used_keys.add(target_key)

            if drift_type == "missing_keys":
                del mutated[target_key]
                drift_type_log = "missing_keys"
            elif drift_type == "extra_keys":
                new_key = f"{target_key}_extra"
                mutated[new_key] = "dummy"
                drift_type_log = "extra_keys"
            elif drift_type == "renamed_keys":
                # use schema rename logic
                rename_map = {
                    "address": "addr",
                    "street_name": "streetName",
                    "street_number": "streetNum",
                    "price": "unit_price",
                    "open_price": "openPx",
                    "temperature": "tempC",
                    "speed": "speed_kph",
                    "wind_speed": "windKph",
                    "capsule_serial": "capsuleId",
                    "driver_name": "driver",
                    "first_name": "firstName",
                    "last_name": "lastName",
                    "latitude": "lat",
                    "longitude": "lng",
                }
                new_key = rename_map.get(target_key, f"{target_key}_renamed")
                if new_key in mutated:
                    new_key += "_2"
                mutated[new_key] = mutated.pop(target_key)
                drift_type_log = "renamed_keys"
            elif drift_type == "split_fields":
                mutated, _ = self._split_column(mutated, drift_logger, run_number, api_source)
                drift_type_log = "split_fields"
            elif drift_type == "merged_fields":
                if len(mutated) >= 2:
                    mutated, _ = self._merge_columns(mutated, drift_logger, run_number, api_source)
                    drift_type_log = "merged_fields"
                else:
                    # fallback rename
                    new_key = f"{target_key}_renamed"
                    mutated[new_key] = mutated.pop(target_key)
                    drift_type_log = "renamed_keys"
            elif drift_type == "nested_corruption":
                mutated, _ = self._nested_corruption(mutated, drift_logger, run_number, api_source)
                drift_type_log = "nested_corruption"
            elif drift_type == "value_contradiction":
                val = mutated[target_key]
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    mutated[target_key] = val * random.uniform(0.9, 1.1)
                elif isinstance(val, str):
                    mutated[target_key] = val + "_mutated"
                drift_type_log = "value_contradiction"

            if drift_logger:
                drift_logger.log_event(
                    api_source=api_source,
                    run_number=run_number,
                    chaos_strategy="schema",
                    chaos_level=self.probability,
                    drift_type=drift_type_log,
                    original_field=target_key,
                    mutated_field="(see metadata)",
                    metadata={"mutation_rate": self.probability}
                )

        return mutated, drift_type_log

    def apply_chaos(self, data: dict, drift_logger=None, run_number=1, api_source="api"):
        if self.probability <= 0.0:
            return data, None
        return self._apply_balanced_chaos(data, drift_logger, run_number, api_source)
