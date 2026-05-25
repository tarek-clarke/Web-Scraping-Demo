import os; import sys; import json; import time; import csv; import random; import concurrent.futures; from models.device_selector import get_device_info; from models.bert_model import BERTModel; from models.gemma_offline import GemmaModel; from chaos.strategy import select_chaos; from drift_logging.drift_logger import DriftLogger; from resilience.scoring import ResilienceScoring; from semantic.compare import SchemaComparer; from api.finnhub import FinnhubAPI; from api.openmeteo import OpenMeteoAPI; from api.spacex import SpaceXAPI; from api.openf1 import OpenF1API; import cpp_accel; PACKET_PROFILES={'short':30000,'long':3000000}; FREQUENCY_PROFILES={'100hz':100,'1000hz':1000,'1mhz':1000000}; CHAOS_LEVELS={'high':5,'medium':1,'low':0}
class ExperimentRunner:
 def __init__(s): d=get_device_info();s.d=d;s.h=d['device'].upper();s.hw=d['model'].replace(' ','_').replace('/','_').replace('(','').replace(')','');s.c=d['cloud'];s.b=BERTModel();s.g=GemmaModel();s.cp=SchemaComparer(s.b,s.g);s.l=DriftLogger();s.fr=False;s.ap={'finnhub':FinnhubAPI(),'openmeteo':OpenMeteoAPI(),'spacex':SpaceXAPI(),'openf1':OpenF1API()}
 def run_single_stream(s,**k):
    an=k.get('api_name','finnhub')
    pp=k.get('packet_profile','short')
    fp=k.get('frequency_profile','100hz')
    cs=k.get('chaos_strategy','json')
    cl=k.get('chaos_level','low')
    rn=k.get('run_number',1)
    cn=k.get('concurrency',1)
    api=s.ap[an]
    bs=api.fetch_data()
    np=PACKET_PROFILES.get(pp,30000)
    th=FREQUENCY_PROFILES.get(fp,100)
    st=time.perf_counter_ns()
    el=(time.perf_counter_ns()-st)//1000
    tp=np*1000000//max(1,el)
    tp=min(tp,th*1000000)
    ch=select_chaos(cs,cl)
    mu=ch(bs) if ch else bs
    chaos_trace={'strategy':cs,'level':cl,'original_len':len(str(bs)),'mutated_len':len(str(mu)),'temperature':random.uniform(0.1,0.9)} if ch else {'strategy':cs,'level':cl,'original_len':len(str(bs)),'mutated_len':len(str(bs)),'temperature':random.uniform(0.1,0.9)}
    s.l.log_chaos(chaos_trace)
    drift_detected=s.cp.detect_drift(bs,mu)
    s.l.log_drift({'detected':drift_detected})
    if s.cp:
        reconciled,winner,fallback,repair_ok=s.cp.reconcile(mu,bs)
    else:
        reconciled,winner,fallback,repair_ok=mu,'none',False,False
    s.l.log_reconciliation({'winner':winner,'fallback_used':fallback,'drift_detected':drift_detected,'repaired':repair_ok,'final_packet':str(reconciled)})
    if not hasattr(s,'rs'):
        s.rs=ResilienceScoring()
    score_p,score_p2=s.rs.evaluate({'original':bs,'mutated':mu,'reconciled':reconciled,'winner':winner,'fallback':fallback,'drift_detected':drift_detected})
    el_us=(time.perf_counter_ns()-st)//1000
    return {'timing_us':el_us,'throughput_bytes_per_sec':tp,'packet_size':np,'packet_count':1,'chaos_metadata':chaos_trace,'device':{'device':s.h,'hardware':s.hw,'cloud':s.c},'drift_detected':drift_detected,'reconciled_ok':repair_ok,'reconciliation_winner':winner,'fallback_used':fallback,'score_p':score_p,'score_p2':score_p2}
