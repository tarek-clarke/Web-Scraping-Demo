#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <string>
#include <vector>
#include <map>
#include <random>
#include <algorithm>
#include <chrono>
#include <iostream>
#include <regex>

namespace py = pybind11;

// Myers' bit-parallel Levenshtein Distance (extremely fast for strings <= 64 chars)
int levenshtein_scalar(const std::string& s1, const std::string& s2) {
    int len1 = s1.size();
    int len2 = s2.size();
    std::vector<int> col(len2 + 1), prevCol(len2 + 1);
    for (int i = 0; i <= len2; i++) prevCol[i] = i;
    for (int i = 0; i < len1; i++) {
        col[0] = i + 1;
        for (int j = 0; j < len2; j++) {
            col[j + 1] = std::min({ prevCol[1 + j] + 1, col[j] + 1, prevCol[j] + (s1[i] == s2[j] ? 0 : 1) });
        }
        col.swap(prevCol);
    }
    return prevCol[len2];
}

int levenshtein_myers(const std::string& s1, const std::string& s2) {
    int n = s1.size();
    int m = s2.size();
    if (n == 0) return m;
    if (m == 0) return n;
    if (n > 64) return levenshtein_scalar(s1, s2);
    
    unsigned long long peq[256] = {0};
    for (int i = 0; i < n; i++) {
        peq[(unsigned char)s1[i]] |= (1ULL << i);
    }
    
    unsigned long long pv = ~0ULL;
    unsigned long long mv = 0ULL;
    int dist = n;
    
    for (int i = 0; i < m; i++) {
        unsigned long long eq = peq[(unsigned char)s2[i]];
        unsigned long long xv = eq | mv;
        unsigned long long jh = (((eq & pv) + pv) ^ pv) | eq;
        unsigned long long ph = pv & jh;
        unsigned long long mh = mv | ~(pv | jh);
        
        unsigned long long ph_sh = (ph << 1) | 1ULL;
        unsigned long long mh_sh = (mh << 1);
        
        pv = mh_sh | ~(ph_sh | xv);
        mv = ph_sh & xv;
        
        if (ph_sh & (1ULL << (n - 1))) {
            dist++;
        }
        if (mh_sh & (1ULL << (n - 1))) {
            dist--;
        }
    }
    return dist;
}

// Typo generation helper
std::string introduce_typo(const std::string& text, std::mt19937& rng) {
    if (text.length() < 3) return text;
    std::string result = text;
    std::uniform_int_distribution<int> dist_type(0, 2);
    std::uniform_int_distribution<int> dist_idx(0, text.length() - 1);
    std::uniform_int_distribution<int> dist_char(0, 25);
    
    int mutation_type = dist_type(rng); // 0: delete, 1: insert, 2: swap
    int idx = dist_idx(rng);
    
    if (mutation_type == 0 && text.length() > 2) {
        result.erase(idx, 1);
    } else if (mutation_type == 1) {
        char random_char = 'a' + dist_char(rng);
        result.insert(idx, 1, random_char);
    } else if (mutation_type == 2 && idx < text.length() - 1) {
        std::swap(result[idx], result[idx+1]);
    }
    return result;
}

// Case conversions
std::vector<std::string> split_snake(const std::string& s) {
    std::vector<std::string> elems;
    std::string item;
    for (char c : s) {
        if (c == '_') {
            if (!item.empty()) {
                elems.push_back(item);
                item.clear();
            }
        } else {
            item += c;
        }
    }
    if (!item.empty()) elems.push_back(item);
    return elems;
}

std::string capitalize(const std::string& s) {
    if (s.empty()) return s;
    std::string res = s;
    res[0] = std::toupper(res[0]);
    return res;
}

std::string to_camel_case(const std::string& s) {
    auto parts = split_snake(s);
    if (parts.empty()) return s;
    std::string res = parts[0];
    for (size_t i = 1; i < parts.size(); ++i) {
        res += capitalize(parts[i]);
    }
    return res;
}

std::string to_pascal_case(const std::string& s) {
    auto parts = split_snake(s);
    std::string res;
    for (const auto& part : parts) {
        res += capitalize(part);
    }
    return res;
}

std::string to_kebab_case(const std::string& s) {
    std::string res = s;
    std::replace(res.begin(), res.end(), '_', '-');
    return res;
}

std::string apply_case_drift(const std::string& key, std::mt19937& rng) {
    if (key.find('_') == std::string::npos) return key;
    std::uniform_int_distribution<int> dist_case(0, 2);
    int case_style = dist_case(rng);
    if (case_style == 0) return to_camel_case(key);
    if (case_style == 1) return to_pascal_case(key);
    return to_kebab_case(key);
}

// Synonyms mapping
std::map<std::string, std::vector<std::string>> synonyms = {
    {"price", {"cost", "charge", "amount", "monetary_value", "rate"}},
    {"temperature", {"temp", "thermal_level", "degrees", "heat_index"}},
    {"speed", {"velocity", "pace", "rate_of_speed", "tempo"}},
    {"active", {"enabled", "running", "live", "operational"}},
    {"name", {"label", "identifier", "title", "designation"}},
    {"value", {"measure", "reading", "result", "magnitude"}},
    {"timestamp", {"time", "date_time", "epoch", "recorded_at"}},
    {"wind_speed", {"wind_velocity", "wind_pace", "breeze_speed"}},
    {"capsule_serial", {"capsule_id", "serial_number", "hardware_tag"}},
    {"driver_name", {"driver_label", "driver_title", "pilot_name"}}
};

std::string rename_field(const std::string& key, std::mt19937& rng) {
    for (const auto& pair : synonyms) {
        if (key.find(pair.first) != std::string::npos || pair.first.find(key) != std::string::npos) {
            std::uniform_int_distribution<int> dist_syn(0, pair.second.size() - 1);
            return pair.second[dist_syn(rng)];
        }
    }
    return key + "_drifted";
}

// Flat nesting helper
void flatten_dict(py::dict input, py::dict output, const std::string& prefix = "") {
    for (auto item : input) {
        std::string key = py::str(item.first);
        std::string new_key = prefix.empty() ? key : prefix + "_" + key;
        if (py::isinstance<py::dict>(item.second)) {
            flatten_dict(py::cast<py::dict>(item.second), output, new_key);
        } else {
            output[py::str(new_key)] = item.second;
        }
    }
}

// Main C++ packet loop and mutations compiler
py::dict run_packet_loop(
    py::dict base_packet, 
    int n_packets, 
    std::string strategy, 
    float level, 
    py::object gemma_injector, 
    std::string api_source, 
    int run_number,
    py::list canonical_keys
) {
    // Collect canonical key strings
    std::vector<std::string> canon_keys;
    for (auto k : canonical_keys) {
        canon_keys.push_back(py::str(k));
    }
    
    std::mt19937 rng(1337 + run_number); // Seed deterministic RNG
    std::uniform_real_distribution<float> dist_prob(0.0f, 1.0f);
    
    int total_drift_events = 0;
    int drift_events_detected = 0;
    
    // Batched logs to avoid high-frequency callbacks to Python
    std::vector<py::dict> batched_logs;
    
    // Outcomes for Levenshtein and Regex reconciler calculations in C++
    py::list reconciler_outcomes;
    
    // Run packet iterations
    for (int i = 0; i < n_packets; ++i) {
        bool should_mutate = dist_prob(rng) < level;
        
        py::dict mutated;
        bool drifted = false;
        std::string drift_type = "";
        std::string original_field = "";
        std::string mutated_field = "";
        py::dict log_metadata;
        
        if (strategy == "gemma" && should_mutate) {
            // For GPU-bound Gemma chaos, we safe-callback to Python (reacquiring GIL if released)
            py::gil_scoped_acquire acquire;
            try {
                // Call Python Gemma apply_chaos helper
                mutated = gemma_injector.attr("apply_chaos")(base_packet, py::none(), run_number, api_source);
                drifted = true;
                drift_type = "gemma_semantic_drift";
            } catch (py::error_already_set& e) {
                mutated = py::dict(base_packet);
            }
        }
        else if (strategy == "json" && should_mutate) {
            mutated = py::dict(base_packet);
            
            // Collect keys to mutate
            std::vector<std::string> keys;
            for (auto item : mutated) {
                keys.push_back(py::str(item.first));
            }
            
            for (const auto& key : keys) {
                if (dist_prob(rng) < level) {
                    drifted = true;
                    std::uniform_int_distribution<int> json_drift_opt(0, 2);
                    int drift_opt = json_drift_opt(rng);
                    
                    std::string new_key = key;
                    if (drift_opt == 0) {
                        new_key = apply_case_drift(key, rng);
                        drift_type = "case_drift";
                    } else if (drift_opt == 1) {
                        new_key = rename_field(key, rng);
                        drift_type = "synonym_rename";
                    } else {
                        new_key = introduce_typo(key, rng);
                        drift_type = "typo_rename";
                    }
                    
                    if (new_key != key) {
                        py::object val = mutated[py::str(key)];
                        mutated.attr("pop")(py::str(key));
                        mutated[py::str(new_key)] = val;
                        original_field = key;
                        mutated_field = new_key;
                        log_metadata["mutation_rate"] = level;
                        break; // Trigger one structural drift per packet to be clean
                    }
                }
                
                // Value mutations
                if (dist_prob(rng) < level) {
                    py::object val = mutated[py::str(key)];
                    if (py::isinstance<py::float_>(val) || py::isinstance<py::int_>(val)) {
                        drifted = true;
                        drift_type = "numeric_perturbation";
                        double numeric_val = py::cast<double>(val);
                        double noise = (dist_prob(rng) * 0.2f - 0.1f); // +/- 10%
                        double new_val = numeric_val * (1.0 + noise);
                        mutated[py::str(key)] = py::cast(new_val);
                        original_field = key + "_value";
                        mutated_field = key + "_value";
                        log_metadata["original_value"] = numeric_val;
                        log_metadata["mutated_value"] = new_val;
                        break;
                    } else if (py::isinstance<py::str>(val)) {
                        drifted = true;
                        drift_type = "value_typo";
                        std::string string_val = py::cast<std::string>(val);
                        std::string new_val = introduce_typo(string_val, rng);
                        mutated[py::str(key)] = py::cast(new_val);
                        original_field = key + "_value";
                        mutated_field = key + "_value";
                        log_metadata["original_value"] = string_val;
                        log_metadata["mutated_value"] = new_val;
                        break;
                    }
                }
            }
        }
        else if (strategy == "schema" && should_mutate) {
            mutated = py::dict(base_packet);
            std::uniform_int_distribution<int> schema_drift_opt(0, 3);
            int drift_opt = schema_drift_opt(rng);
            drifted = true;
            
            if (drift_opt == 0) { // split column
                drift_type = "column_split";
                bool split_done = false;
                std::vector<std::string> keys;
                for (auto item : mutated) keys.push_back(py::str(item.first));
                
                for (const auto& key : keys) {
                    py::object val = mutated[py::str(key)];
                    if ((key.find("name") != std::string::npos || key == "canonical") && py::isinstance<py::str>(val)) {
                        std::string str_val = py::cast<std::string>(val);
                        size_t space_idx = str_val.find(' ');
                        if (space_idx != std::string::npos) {
                            mutated.attr("pop")(py::str(key));
                            mutated[py::str("first_name")] = py::cast(str_val.substr(0, space_idx));
                            mutated[py::str("last_name")] = py::cast(str_val.substr(space_idx + 1));
                            original_field = key;
                            mutated_field = "first_name,last_name";
                            split_done = true;
                            break;
                        }
                    } else if (key == "coordinates" && py::isinstance<py::dict>(val)) {
                        py::dict coord_dict = py::cast<py::dict>(val);
                        mutated.attr("pop")(py::str("coordinates"));
                        mutated[py::str("latitude")] = coord_dict.contains("lat") ? coord_dict["lat"] : py::none();
                        mutated[py::str("longitude")] = coord_dict.contains("lng") ? coord_dict["lng"] : py::none();
                        original_field = "coordinates";
                        mutated_field = "latitude,longitude";
                        split_done = true;
                        break;
                    }
                }
                if (!split_done) drifted = false; // Fallback
            }
            else if (drift_opt == 1) { // merge column
                drift_type = "column_merge";
                if (mutated.contains("first_name") && mutated.contains("last_name")) {
                    std::string f = py::cast<std::string>(mutated["first_name"]);
                    std::string l = py::cast<std::string>(mutated["last_name"]);
                    mutated.attr("pop")("first_name");
                    mutated.attr("pop")("last_name");
                    mutated["full_name"] = py::cast(f + " " + l);
                    original_field = "first_name,last_name";
                    mutated_field = "full_name";
                } else if (mutated.contains("latitude") && mutated.contains("longitude")) {
                    double lat = py::cast<double>(mutated["latitude"]);
                    double lng = py::cast<double>(mutated["longitude"]);
                    mutated.attr("pop")("latitude");
                    mutated.attr("pop")("longitude");
                    mutated["location_coords"] = py::cast(std::to_string(lat) + "," + std::to_string(lng));
                    original_field = "latitude,longitude";
                    mutated_field = "location_coords";
                } else {
                    drifted = false;
                }
            }
            else if (drift_opt == 2) { // units split
                drift_type = "unit_split";
                bool unit_done = false;
                std::vector<std::string> keys;
                for (auto item : mutated) keys.push_back(py::str(item.first));
                
                for (const auto& key : keys) {
                    py::object val = mutated[py::str(key)];
                    if (py::isinstance<py::float_>(val) || py::isinstance<py::int_>(val)) {
                        if (key.find("speed") != std::string::npos) {
                            mutated[py::str(key + "_value")] = val;
                            mutated[py::str(key + "_unit")] = py::cast("kph");
                            original_field = key;
                            mutated_field = key + "_value," + key + "_unit";
                            unit_done = true;
                            break;
                        } else if (key.find("temp") != std::string::npos) {
                            mutated[py::str(key + "_value")] = val;
                            mutated[py::str(key + "_unit")] = py::cast("celsius");
                            original_field = key;
                            mutated_field = key + "_value," + key + "_unit";
                            unit_done = true;
                            break;
                        } else if (key.find("price") != std::string::npos) {
                            mutated[py::str(key + "_value")] = val;
                            mutated[py::str(key + "_unit")] = py::cast("USD");
                            original_field = key;
                            mutated_field = key + "_value," + key + "_unit";
                            unit_done = true;
                            break;
                        }
                    }
                }
                if (!unit_done) drifted = false;
            }
            else { // nested flatten
                drift_type = "nested_flattening";
                bool has_nesting = false;
                for (auto item : mutated) {
                    if (py::isinstance<py::dict>(item.second)) {
                        has_nesting = true;
                        break;
                    }
                }
                if (has_nesting) {
                    py::dict flat;
                    flatten_dict(mutated, flat);
                    mutated = flat;
                    original_field = "nested_schema";
                    mutated_field = "flattened_schema";
                } else {
                    drifted = false;
                }
            }
        }
        else {
            mutated = py::dict(base_packet);
        }
        
        if (drifted) {
            total_drift_events++;
            
            // Check mutated keys against canonical ones to find the drifted key
            std::string drifted_key = "";
            for (auto item : mutated) {
                std::string k_str = py::cast<std::string>(py::str(item.first));
                if (std::find(canon_keys.begin(), canon_keys.end(), k_str) == canon_keys.end()) {
                    drifted_key = k_str;
                    break;
                }
            }
            
            // Log structure batching
            py::dict log_entry;
            log_entry["drift_type"] = drift_type;
            log_entry["original_field"] = original_field.empty() ? "unknown" : original_field;
            log_entry["mutated_field"] = mutated_field.empty() ? "unknown" : mutated_field;
            log_entry["metadata"] = log_metadata;
            batched_logs.push_back(log_entry);
            
            // Evaluate reconcilers in C++ (only sample evaluation for ultra-high speed)
            if (!drifted_key.empty() && (total_drift_events <= 100 || i % 50 == 0)) {
                drift_events_detected++;
                
                // Levenshtein C++
                std::string best_lev_match = canon_keys[0];
                int min_lev_dist = 9999;
                auto t0 = std::chrono::high_resolution_clock::now();
                for (const auto& canon : canon_keys) {
                    int dist = levenshtein_myers(canon, drifted_key);
                    if (dist < min_lev_dist) {
                        min_lev_dist = dist;
                        best_lev_match = canon;
                    }
                }
                auto t1 = std::chrono::high_resolution_clock::now();
                double lev_lat = std::chrono::duration<double, std::milli>(t1 - t0).count();
                double max_len = std::max(best_lev_match.length(), drifted_key.length());
                double lev_conf = max_len > 0 ? (1.0 - (double)min_lev_dist / max_len) : 1.0;
                
                // Regex C++ matching
                std::string best_regex_match = "unknown";
                double regex_conf = 0.0;
                auto tr0 = std::chrono::high_resolution_clock::now();
                for (const auto& canon : canon_keys) {
                    try {
                        std::regex r(canon, std::regex_constants::icase);
                        if (std::regex_search(drifted_key, r)) {
                            best_regex_match = canon;
                            regex_conf = 1.0;
                            break;
                        }
                    } catch (const std::regex_error&) {}
                }
                auto tr1 = std::chrono::high_resolution_clock::now();
                double regex_lat = std::chrono::duration<double, std::milli>(tr1 - tr0).count();
                
                // Aggregate outcomes to Python reconciler processing structures
                py::dict entry;
                entry["drifted_key"] = drifted_key;
                
                py::dict lev_res;
                lev_res["match"] = best_lev_match;
                lev_res["confidence"] = lev_conf;
                lev_res["latency_ms"] = lev_lat;
                entry["levenshtein"] = lev_res;
                
                py::dict regex_res;
                regex_res["match"] = best_regex_match;
                regex_res["confidence"] = regex_conf;
                regex_res["latency_ms"] = regex_lat;
                entry["regex"] = regex_res;
                
                reconciler_outcomes.append(entry);
            }
        }
    }
    
    py::dict results;
    results["total_drift_events"] = total_drift_events;
    results["drift_events_detected"] = drift_events_detected;
    results["batched_logs"] = py::cast(batched_logs);
    results["reconciler_outcomes"] = reconciler_outcomes;
    
    return results;
}

PYBIND11_MODULE(cpp_accel, m) {
    m.doc() = "C++ Acceleration Layer for Semantic Drift Evaluation Framework";
    
    m.def("levenshtein_cpp", &levenshtein_myers, "Calculates Levenshtein distance using bit-parallel Myers' algorithm.",
          py::arg("s1"), py::arg("s2"));
          
    m.def("run_packet_loop", &run_packet_loop, "Executes optimized high-performance C++ packet mutation loop",
          py::arg("base_packet"),
          py::arg("n_packets"),
          py::arg("strategy"),
          py::arg("level"),
          py::arg("gemma_injector"),
          py::arg("api_source"),
          py::arg("run_number"),
          py::arg("canonical_keys"));
}
