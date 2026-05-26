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
            # no suitable field, force split on any string field
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
        # Merge first_name and last_name if present
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
        # Merge latitude and longitude if present
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
            # fallback: force split on any numeric field
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

    def apply_chaos(self, data: dict, drift_logger=None, run_number=1, api_source="api"):
        """
        Applies schema structural drift (split, merge, unit split, flattening).
        Logs every event via drift_logger.
        Returns (mutated_data, drift_type).
        """
        if random.random() >= self.probability:
            # even if probability fails, force mutation
            options = ["split", "merge", "units", "flatten"]
            drift_option = random.choice(options)
            if drift_option == "split":
                return self._split_column(data, drift_logger, run_number, api_source)
            elif drift_option == "merge":
                return self._merge_columns(data, drift_logger, run_number, api_source)
            elif drift_option == "units":
                return self._split_units(data, drift_logger, run_number, api_source)
            else:
                return self._flatten_nested(data, drift_logger, run_number, api_source)

        drift_option = random.choice(["split", "merge", "units", "flatten"])

        if drift_option == "split":
            return self._split_column(data, drift_logger, run_number, api_source)
        elif drift_option == "merge":
            return self._merge_columns(data, drift_logger, run_number, api_source)
        elif drift_option == "units":
            return self._split_units(data, drift_logger, run_number, api_source)
        else:
            return self._flatten_nested(data, drift_logger, run_number, api_source)
