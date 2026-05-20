import random

class SchemaDrift:
    def __init__(self, probability: float):
        self.probability = probability

    def _split_column(self, data: dict, drift_logger=None, run_number=1, api_source="api") -> dict:
        mutated = {}
        for key, val in data.items():
            if ("name" in key or key == "canonical") and isinstance(val, str) and " " in val:
                # Split full_name / canonical into first_name and last_name
                parts = val.split(" ", 1)
                mutated["first_name"] = parts[0]
                mutated["last_name"] = parts[1]
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
                # Split coordinates dict into lat and lng
                mutated["latitude"] = val.get("lat")
                mutated["longitude"] = val.get("lng")
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
        return mutated

    def _merge_columns(self, data: dict, drift_logger=None, run_number=1, api_source="api") -> dict:
        mutated = dict(data)
        
        # Merge first_name and last_name if present
        if "first_name" in mutated and "last_name" in mutated:
            f_name = mutated.pop("first_name")
            l_name = mutated.pop("last_name")
            mutated["full_name"] = f"{f_name} {l_name}"
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
        if "latitude" in mutated and "longitude" in mutated:
            lat = mutated.pop("latitude")
            lng = mutated.pop("longitude")
            mutated["location_coords"] = f"{lat},{lng}"
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
                
        return mutated

    def _split_units(self, data: dict, drift_logger=None, run_number=1, api_source="api") -> dict:
        mutated = {}
        for key, val in data.items():
            if "speed" in key and isinstance(val, (int, float)):
                # Split speed into speed_value and speed_unit
                mutated[f"{key}_value"] = val
                mutated[f"{key}_unit"] = "kph"
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
                # Split temp into temp_value and temp_unit
                mutated[f"{key}_value"] = val
                mutated[f"{key}_unit"] = "celsius"
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
        return mutated

    def _flatten_nested(self, data: dict, drift_logger=None, run_number=1, api_source="api") -> dict:
        mutated = {}
        
        def flatten(obj, prefix=""):
            for k, v in obj.items():
                new_key = f"{prefix}{k}" if not prefix else f"{prefix}_{k}"
                if isinstance(v, dict):
                    flatten(v, new_key)
                else:
                    mutated[new_key] = v
                    
        # Check if there is nesting
        has_nesting = any(isinstance(v, dict) for v in data.values())
        
        if has_nesting:
            flatten(data)
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
            # If no nesting, artificially nest something first, or return as is
            mutated = dict(data)
            
        return mutated

    def apply_chaos(self, data: dict, drift_logger=None, run_number=1, api_source="api") -> dict:
        """
        Applies schema structural drift (split, merge, unit split, flattening).
        Logs every event via drift_logger.
        """
        if random.random() >= self.probability:
            return data
            
        drift_option = random.choice(["split", "merge", "units", "flatten"])
        
        if drift_option == "split":
            return self._split_column(data, drift_logger, run_number, api_source)
        elif drift_option == "merge":
            return self._merge_columns(data, drift_logger, run_number, api_source)
        elif drift_option == "units":
            return self._split_units(data, drift_logger, run_number, api_source)
        else: # flatten
            return self._flatten_nested(data, drift_logger, run_number, api_source)
