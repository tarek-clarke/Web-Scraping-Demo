import os
import sys
import json
import time
import csv
import random
import concurrent.futures
from uuid import uuid4
from models.device_selector import get_device_info
from models.model_registry import get_shared_bert_model, get_shared_gemma_model, clear_shared_model_cache
from chaos.strategy import select_chaos
from drift_logging.drift_logger import DriftLogger
from resilience.scoring import ResilienceScoring
from semantic.compare import SchemaComparer
from api.finnhub import FinnhubAPI
from api.openmeteo import OpenMeteoAPI
from api.spacex import SpaceXAPI
from api.openf1 import OpenF1API
try:
    import cpp_accel
except ImportError:
    cpp_accel = None

PACKET_PROFILES = {'10k': 10000, '1m': 1000000}
FREQUENCY_PROFILES = {'100hz': 100, '1mhz': 1000000}
CHAOS_LEVELS = {'high': 5, 'medium': 1, 'low': 0}

class ExperimentRunner:
    def __init__(self):
        d = get_device_info()
        self.d = d
        self.h = d['model']
        self.hw = d['model'].replace(' ', '_').replace('/', '_').replace('(', '').replace(')', '')
        self.c = d['cloud']
        self.b = get_shared_bert_model()
        self.g = get_shared_gemma_model()
        self.cp = SchemaComparer(self.b, self.g)
        self.l = DriftLogger(base_dir=os.path.join("logs", self.hw))
        self.fr = False
        self.baseline_mode = False
        self.ablation_modes = []  # empty = full pipeline; can set ['no_bert','no_gemma','no_regex','no_levenshtein']
        self.ap = {
            'finnhub': FinnhubAPI(),
            'openmeteo': OpenMeteoAPI(),
            'spacex': SpaceXAPI(),
            'openf1': OpenF1API()
        }

    def run_single_stream(self, **k):
        an = k.get('api_name', 'finnhub')
        pp = k.get('packet_profile', '10k')
        fp = k.get('frequency_profile', '100hz')
        cs = k.get('chaos_strategy', 'json')
        cl = k.get('chaos_level', 'low')
        rn = k.get('run_number', 1)
        cn = k.get('concurrency', 1)
        run_id = k.get('run_id', uuid4().hex)
        preflight = k.get('preflight', {})
        api = self.ap[an]
        bs = api.fetch_data()
        np_val = PACKET_PROFILES.get(pp, 10000)
        th = FREQUENCY_PROFILES.get(fp, 100)
        st = time.perf_counter_ns()

        # Generate event_id for this chaos event
        event_id = uuid4().hex

        # Baseline mode: no chaos — measure false positive rate
        if self.baseline_mode:
            mu = bs
            drift_type = None
        else:
            ch = select_chaos(cs, cl)
            if callable(ch):
                result_tuple = ch(bs, drift_logger=self.l, run_number=rn,
                                  api_source=an, run_id=run_id, event_id=event_id)
                if isinstance(result_tuple, tuple) and len(result_tuple) == 3:
                    mu, drift_type, event_id_out = result_tuple
                    event_id = event_id_out or event_id
                elif isinstance(result_tuple, tuple) and len(result_tuple) == 2:
                    mu, drift_type = result_tuple
                else:
                    mu, drift_type = bs, None
            else:
                mu, drift_type = bs, None

        el = (time.perf_counter_ns() - st) // 1000
        tp = np_val * 1000000 // max(1, el)
        tp = min(tp, th * 1000000)

        chaos_metadata = {
            'strategy': cs,
            'level': cl,
            'original_len': len(str(bs)),
            'mutated_len': len(str(mu)),
            'temperature': random.uniform(0.1, 0.9),
            'drift_type': drift_type,
            'event_id': event_id,
            'run_id': run_id
        }
        self.l.log_chaos(chaos_metadata)

        # Detect drift and reconcile using SchemaComparer.process
        process_result = self.cp.process(mu, bs)
        drift_detected = process_result['drift_detected']
        drift_types = process_result['drift_types']
        drift_type_count = process_result['drift_type_count']
        repair_rate = process_result['repair_rate']
        recovery_score = process_result['recovery_score']
        reconciled_ok = process_result['reconciled_ok']
        winner = process_result['reconciliation_winner']
        fallback_used = process_result['fallback_used']
        fallback_reason = process_result.get('fallback_reason')
        best_confidence = process_result['best_confidence']
        method_used = process_result.get('method_used', 'none')
        algorithm_results = process_result.get('algorithm_results', {})
        model_source = process_result.get('model_source', {})

        # Determine if internet was used for this run
        internet_used = any(
            src == "internet" for src in model_source.values()
        )

        # Compute resilience metrics
        elapsed_us = (time.perf_counter_ns() - st) // 1000
        total_runtime_sec = elapsed_us / 1_000_000.0
        p95_latency_ms = elapsed_us / 1000.0
        throughput_pps = 1.0 / max(1e-9, total_runtime_sec)
        target_hz = th

        detection_rate = 1.0 if drift_detected else 0.0
        resilience = ResilienceScoring.calculate_scores(
            throughput_pps=throughput_pps,
            target_hz=target_hz,
            detection_rate=detection_rate,
            recovery_score=recovery_score,
            p95_latency_ms=p95_latency_ms,
            baseline_p95_ms=10.0
        )
        resilience_P = resilience['P']
        resilience_P2 = resilience['P2']

        # Build output result dictionary with full traceability
        result = {
            'timing_us': elapsed_us,
            'throughput_bytes_per_sec': tp,
            'throughput_pps': throughput_pps,
            'packet_size': np_val,
            'packet_count': 1,
            'run_id': run_id,
            'event_id': event_id,
            'chaos_metadata': chaos_metadata,
            'device': {'device': self.h, 'hardware': self.hw, 'cloud': self.c},
            'drift_detected': drift_detected,
            'drift_types': drift_types,
            'drift_type_count': drift_type_count,
            'reconciled_ok': reconciled_ok,
            'reconciliation_winner': winner,
            'method_used': method_used,
            'translation_method': method_used,
            'algorithm_results': algorithm_results,
            'model_source': model_source,
            'internet_used': internet_used,
            'fallback_used': fallback_used,
            'fallback_reason': fallback_reason,
            'repair_rate': repair_rate,
            'recovery_score': recovery_score,
            'resilience_P': resilience_P,
            'resilience_P2': resilience_P2,
            'detection_rate': detection_rate,
            'p95_latency_ms': p95_latency_ms,
            'total_runtime_sec': total_runtime_sec,
            'run_number': rn,
            'concurrency': cn,
            'api_name': an,
            'packet_profile': pp,
            'frequency_profile': fp,
            'chaos_strategy': cs,
            'chaos_level': cl,
            'elapsed_seconds': total_runtime_sec,
            'averages': {
                'levenshtein_latency': algorithm_results.get('levenshtein', {}).get('latency_ms', 0),
                'regex_latency': algorithm_results.get('regex', {}).get('latency_ms', 0),
                'bert_latency': algorithm_results.get('bert', {}).get('latency_ms', 0),
                'gemma_latency': algorithm_results.get('gemma', {}).get('latency_ms', 0),
                'gemma_confidence': best_confidence
            },
            'actual_device': self.hw,
            'target_hz': th,
            'preflight': preflight,
            'cpu_name': self.d.get('cpu_name', 'Unknown'),
            'cpu_cores': self.d.get('cpu_cores', 1),
            'ram_gb': self.d.get('ram_gb', 0),
            'motherboard': self.d.get('motherboard', 'Unknown'),
            'os_name': self.d.get('os_name', 'Unknown'),
            'os_version': self.d.get('os_version', 'Unknown'),
        }
        if hasattr(self.cp, "clear_caches"):
            self.cp.clear_caches()
        clear_shared_model_cache()
        return result
