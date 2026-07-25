import json

print("Updating master_benchmark_results.json with classical routing baselines...")

output_path = "data/reports/master_benchmark_results.json"
master_data = json.load(open(output_path))

classical_path = "data/reports/classical_router_benchmark_results.json"
classical_data = json.load(open(classical_path))

# Add classical_routers block
master_data["classical_routers"] = classical_data

# Also add to global_summary for unified master table lookup
master_data["global_summary"]["logistic_regression_cpu"] = {
    "routing_accuracy": f"{classical_data['logistic_regression_cpu']['mean_routing_accuracy']:.2f}% ± {classical_data['logistic_regression_cpu']['std_routing_accuracy']:.2f}%",
    "ci_95_routing_accuracy": f"[{classical_data['logistic_regression_cpu']['ci_95_routing_accuracy'][0]}%, {classical_data['logistic_regression_cpu']['ci_95_routing_accuracy'][1]}%]",
    "leave_one_api_out_acc": f"{classical_data['logistic_regression_cpu']['leave_one_api_out_acc']:.2f}%",
    "inference_latency_ms": classical_data['logistic_regression_cpu']['inference_latency_ms_per_packet'],
    "throughput_pps": round(1000.0 / classical_data['logistic_regression_cpu']['inference_latency_ms_per_packet'], 1),
    "hardware": "Local CPU (16 Cores)"
}

master_data["global_summary"]["random_forest_cpu"] = {
    "routing_accuracy": f"{classical_data['gradient_boosted_cpu']['mean_routing_accuracy']:.2f}% ± {classical_data['gradient_boosted_cpu']['std_routing_accuracy']:.2f}%",
    "ci_95_routing_accuracy": f"[{classical_data['gradient_boosted_cpu']['ci_95_routing_accuracy'][0]}%, {classical_data['gradient_boosted_cpu']['ci_95_routing_accuracy'][1]}%]",
    "leave_one_api_out_acc": f"{classical_data['gradient_boosted_cpu']['leave_one_api_out_acc']:.2f}%",
    "inference_latency_ms": classical_data['gradient_boosted_cpu']['inference_latency_ms_per_packet'],
    "throughput_pps": round(1000.0 / classical_data['gradient_boosted_cpu']['inference_latency_ms_per_packet'], 1),
    "hardware": "Local CPU (16 Cores)"
}

with open(output_path, "w") as f:
    json.dump(master_data, f, indent=2)

print(f"SUCCESS: Integrated classical router metrics into {output_path}!")
