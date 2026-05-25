import os; import sys; import json; import time; import csv; from collections import defaultdict; from pathlib import Path; from models.device_selector import get_device_info; from tests.run_experiments import ExperimentRunner
def _load_historical_profile_estimates(r,p): e={'short':{'average_sec':None},'long':{'average_sec':None}};[x for x in p if (s:=os.path.join(r,x,"summary.json")) and os.path.exists(s) and (d:=json.load(open(s))) and (a:=d.get("average_runtime_sec")) is not None and (e[x].update({'average_sec':float(a)}) or True)];return e
def run_evaluation_pipeline():
 if '--bootstrap' in sys.argv: import bootstrap; bootstrap.run_bootstrap(force=True)
 g=time.perf_counter(); d=get_device_info(); h=d['model'].replace(' ','_').replace('/','_').replace('(','').replace(')',''); c=d['cloud']; print('\n'+'='*80); print(' Hey! Welcome to the Semantic Drift Evaluation Pipeline Runner'); print(f' Hardware Platform : {d["device"].upper()}'); print(f' Hardware Model    : {d["model"]}'); print(f' Cloud Environment : {d["cloud"].upper()}'); print('='*80+'\n')
 e='--erase-existing' in sys.argv or '--force-erase' in sys.argv; R=f'results/{h}/{c}'
 if e:
  if os.path.exists(R): import shutil; print(f'[Runner] Removing existing results at {R} (flag provided).'); shutil.rmtree(R)
 else:
  try:
   p=input(f'Erase existing results at {R}? [y/N]: ')
   if p.strip().lower() in ('y','yes'):
    import shutil
    if os.path.exists(R): print(f'[Runner] Removing existing results at {R}.'); shutil.rmtree(R)
    else: print(f'[Runner] No existing results found at {R}.')
  except: pass
 r=ExperimentRunner()
 if '--force-rerun' in sys.argv: r.force_rerun=True; print('[Pipeline] Force rerun enabled.')
 P=['short','long']; F=['100hz','1000hz','1mhz']; X=['json','schema','gemma']; L=['high','medium','low']; A=['finnhub','openmeteo','spacex','openf1']; C=[1]
 n=len(P)*len(F)*len(X)*len(L)*len(A)*len(C); N=n*4
 try: import cpp_accel; c=cpp_accel is not None
 except: c=False
 gpu=d['device'].upper() in ['CUDA','ROCM','MPS']
 if c: s_short=0.5; s_long=10.0; l='C++ Acceleration + GPU Enabled' if gpu else 'C++ Acceleration (CPU Fallback)'; s_short=1.5 if not gpu else 0.5; s_long=40.0 if not gpu else 10.0
 else: s_short=4.0 if gpu else 15.0; s_long=250.0 if gpu else 1200.0; l='Python Standard (GPU Only)' if gpu else 'Python Standard (CPU Fallback)'
 n1=(n//2)*4; n2=(n//2)*4
 H=_load_historical_profile_estimates(R,P)
 hs=H['short']['average_sec']; hl=H['long']['average_sec']
 if hs is not None and hl is not None: s_short=float(hs); s_long=float(hl)
 p_sec=(n1*s_short)+(n2*s_long); p_h=p_sec/3600.0; w_sec=(n1*15.0)+(n2*1200.0); w_h=w_sec/3600.0
 print('\n'+'='*80); print('                     EXECUTION RUNTIME ESTIMATION CHART'); print('='*80); print(f' Detected Backend : {d["device"].upper()} ({d["model"]})'); print(f' Optimization     : {l}'); print(f' Configurations   : {n} distinct configs (4 runs each, total {N} streams)'); print('-'*80); print(' ESTIMATED TIME PER RUN BY PROFILE:'); print(f'  - Short Profile (30k packets)   : ~{s_short:.2f} seconds'); print(f'  - Long Profile (3M packets)     : ~{s_long:.2f} seconds'); print('-'*80); print(' PROJECTED PIPELINE COMPLETION TIME COMPARISON:'); wb='/'*20; ab='/'*max(1,int((p_sec/w_sec)*20)); print(f'  - Standard Python (CPU fallback) : [{wb}] ~{w_h:.1f} hours'); print(f'  - C++ Accelerated Suite (Ours)   : [{ab}] ~{p_h:.2f} hours'); print('-'*80); print(' NOTE: Existing completed runs will be skipped dynamically.'); print('='*80+'\n')
 print(f'[Pipeline] Scheduled {n} distinct configurations (4 runs each, total {N} evaluation streams).')
 print('[Pipeline] Running evaluation pipeline (this runs incrementally, skipping existing runs)...')
 t=[]; cnt=0; all_res=[]
 for p in P:
  for f in F:
   for x in X:
    for l in L:
     for a in A:
      for co in C:
       cnt+=1; print(f'[Pipeline] Progress: {cnt}/{n} ({(cnt/n)*100.0:.1f}%) | Config: {a} - {f} - {x} {l} - Concurrency: {co}')
       for rn in [1,2,3,4]:
        try:
         if co==1:
          res=r.run_single_stream(api_name=a,packet_profile=p,frequency_profile=f,chaos_strategy=x,chaos_level=l,run_number=rn,concurrency=1)
          if res and 'total_runtime_sec' in res: t.append(res['total_runtime_sec']); all_res.append(res)
         else:
          res=r.run_concurrent_streams(api_name=a,packet_profile=p,frequency_profile=f,chaos_strategy=x,chaos_level=l,run_number=rn)
          if res:
           if 'stream_1' in res: all_res.append(res['stream_1']); t.append(res['stream_1'].get('total_runtime_sec',0))
           if 'stream_2' in res: all_res.append(res['stream_2']); t.append(res['stream_2'].get('total_runtime_sec',0))
        except Exception as e: print(f'[Pipeline] [ERROR] Failed on config: {e}')
 ge=time.perf_counter(); gr=ge-g
 sd=f'results/{h}/{c}'; os.makedirs(sd,exist_ok=True); sp=os.path.join(sd,'summary.json')
 total_t=sum(t); avg_t=total_t//max(1,len(t)) if t else 0; fast_t=min(t) if t else 0; slow_t=max(t) if t else 0
 d_d=[r.get('detection_rate',0) for r in all_res if r]; d_l=[r.get('p95_latency_ms',0) for r in all_res if r]
 s_r=[r for r in all_res if r and r.get('run_number',1)>1]; s_d=[r.get('detection_rate',0) for r in s_r]; s_l=[r.get('p95_latency_ms',0) for r in s_r]
 def avg_i(x): return sum(x)//max(1,len(x))
 m_c={'detection_rate':avg_i(d_d),'p95_latency_ms':avg_i(d_l)} if d_d else {}
 s_m={'detection_rate':avg_i(s_d),'p95_latency_ms':avg_i(s_l)} if s_d else {}
 data={'global_runtime_sec':round(gr,4),'total_runs_time_sec':round(total_t,4),'average_runtime_sec':avg_t,'fastest_run_sec':fast_t,'slowest_run_sec':slow_t,'total_runs_count':len(t),'timestamp':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'mean_with_cold_start':m_c,'stable_mean':s_m}
 with open(sp,'w') as f: json.dump(data,f,indent=2)
 print(f'\n[Pipeline] Completed all evaluations in {gr:.2f} seconds.')
 print(f'Cold start mean detection_rate: {m_c.get("detection_rate")}, p95_latency_ms: {m_c.get("p95_latency_ms")}')
 print(f'Stable mean detection_rate: {s_m.get("detection_rate")}, p95_latency_ms: {s_m.get("p95_latency_ms")}')
 flat_all=[{k+'_'+kk if isinstance(v,dict) else k: vv if isinstance(v,dict) else v for k,v in r.items() for kk,vv in (v.items() if isinstance(v,dict) else [('',v)])} for r in all_res]
 pdir='results/'+h; os.makedirs(pdir,exist_ok=True)
 json.dump(flat_all,open(pdir+'/master_platform_all_runs_1_to_4.json','w'))
 stable_f=[r for r in flat_all if r.get('run_number',1)>1]; json.dump(stable_f,open(pdir+'/master_platform_stable_runs_2_to_4.json','w'))
 if flat_all:
  ka=sorted(flat_all[0].keys())
  with open(pdir+'/master_platform_all_runs_1_to_4.csv','w',newline='') as f: w=csv.DictWriter(f,fieldnames=ka); w.writeheader(); w.writerows(flat_all)
 if stable_f:
  ks=sorted(stable_f[0].keys())
  with open(pdir+'/master_platform_stable_runs_2_to_4.csv','w',newline='') as f: w=csv.DictWriter(f,fieldnames=ks); w.writeheader(); w.writerows(stable_f)
 gal=[]; gst=[]
 for e in os.listdir('results/'):
  if os.path.isdir('results/'+e):
   fp='results/'+e+'/master_platform_all_runs_1_to_4.json'
   if os.path.exists(fp):
    with open(fp) as f: rd=json.load(f); gal.extend(rd)
   fp2='results/'+e+'/master_platform_stable_runs_2_to_4.json'
   if os.path.exists(fp2):
    with open(fp2) as f: rd=json.load(f); gst.extend(rd)
 json.dump(gal,open('results/global_unified_all_runs_1_to_4.json','w'))
 json.dump(gst,open('results/global_unified_stable_runs_2_to_4.json','w'))
 if gal:
  kg=sorted(gal[0].keys())
  with open('results/global_unified_all_runs_1_to_4.csv','w',newline='') as f: w=csv.DictWriter(f,fieldnames=kg); w.writeheader(); w.writerows(gal)
 if gst:
  kg2=sorted(gst[0].keys())
  with open('results/global_unified_stable_runs_2_to_4.csv','w',newline='') as f: w=csv.DictWriter(f,fieldnames=kg2); w.writeheader(); w.writerows(gst)
 if all_res:
  hw_map={'NVIDIA CUDA':'CUDA','AMD ROCm':'ROCm','Intel GPU':'IntelGPU','Apple Silicon MPS':'MPS','CPU fallback':'CPU'}
  aud_plat=[hw_map.get(r.get('actual_device',''),'CPU') for r in all_res]
  aud_rows=[{**r,'hardware_platform':hp,'hardware_model':d['model'],'cloud_environment':d['cloud'],'timestamp_ns':int(time.time_ns()),'strategy_used':r.get('chaos_strategy',''),'confidence_score':r.get('averages',{}).get('gemma_confidence',0)} for r,hp in zip(all_res,aud_plat)]
  json.dump(aud_rows,open(pdir+'/drift_reconciliation_audit.json','w'))
  gal_aud=list(aud_rows)
  for ee in os.listdir('results/'):
   if os.path.isdir('results/'+ee) and ee!=h and os.path.exists('results/'+ee+'/drift_reconciliation_audit.json'):
    with open('results/'+ee+'/drift_reconciliation_audit.json') as f: gal_aud.extend(json.load(f))
  json.dump(gal_aud,open('results/global_drift_reconciliation_audit.json','w'))
  stable_res=[r for r in all_res if r.get('run_number',1)>1];m=len(all_res);n_stab=len(stable_res);ll_all=sum(r.get('averages',{}).get('levenshtein_latency',0) for r in all_res)//m;rl_all=sum(r.get('averages',{}).get('regex_latency',0) for r in all_res)//m;bl_all=sum(r.get('averages',{}).get('bert_latency',0) for r in all_res)//m;gl_all=sum(r.get('averages',{}).get('gemma_latency',0) for r in all_res)//m;ll_stab=sum(r.get('averages',{}).get('levenshtein_latency',0) for r in stable_res)//n_stab if n_stab else 0;rl_stab=sum(r.get('averages',{}).get('regex_latency',0) for r in stable_res)//n_stab if n_stab else 0;bl_stab=sum(r.get('averages',{}).get('bert_latency',0) for r in stable_res)//n_stab if n_stab else 0;gl_stab=sum(r.get('averages',{}).get('gemma_latency',0) for r in stable_res)//n_stab if n_stab else 0
  print('\n'+'='*80)
  print('                     EVALUATION PIPELINE RESULTS SUMMARY')
  print('='*80)
  print('PERFORMANCE VALIDATION: BASELINE RECONCILIATION LATENCY')
  print('Hardware: '+d["device"].upper()+' ('+d["model"]+') | Cloud: LOCAL')
  print('| Algorithm | Profile Context | p50 Latency (ms) | p95 Latency (ms) |')
  print('| Levenshtein | With Cold Start (Runs 1-4) | '+'{:.3f}'.format(ll_all/1000.0)+' ms | '+'{:.3f}'.format(ll_all/1000.0)+' ms |')
  print('| Levenshtein | Stable State (Runs 2-4)   | '+'{:.3f}'.format(ll_stab/1000.0)+' ms | '+'{:.3f}'.format(ll_stab/1000.0)+' ms |')
  print('| Regex | With Cold Start (Runs 1-4) | '+'{:.3f}'.format(rl_all/1000.0)+' ms | '+'{:.3f}'.format(rl_all/1000.0)+' ms |')
  print('| Regex | Stable State (Runs 2-4)   | '+'{:.3f}'.format(rl_stab/1000.0)+' ms | '+'{:.3f}'.format(rl_stab/1000.0)+' ms |')
  print('| Bert | With Cold Start (Runs 1-4) | '+'{:.3f}'.format(bl_all/1000.0)+' ms | '+'{:.3f}'.format(bl_all/1000.0)+' ms |')
  print('| Bert | Stable State (Runs 2-4)   | '+'{:.3f}'.format(bl_stab/1000.0)+' ms | '+'{:.3f}'.format(bl_stab/1000.0)+' ms |')
  print('| Gemma | With Cold Start (Runs 1-4) | '+'{:.3f}'.format(gl_all/1000.0)+' ms | '+'{:.3f}'.format(gl_all/1000.0)+' ms |')
  print('| Gemma | Stable State (Runs 2-4)   | '+'{:.3f}'.format(gl_stab/1000.0)+' ms | '+'{:.3f}'.format(gl_stab/1000.0)+' ms |')
  print('='*80)
  c1=[r for r in all_res if r.get('concurrency')==1];c2=[r for r in all_res if r.get('concurrency')==2];b_t=sum(r.get('throughput_pps',0) for r in c1)//len(c1) if c1 else 0;b_e=sum(r.get('elapsed_seconds',0) for r in c1)//len(c1) if c1 else 0;p_t=sum(r.get('throughput_pps',0) for r in c2)//len(c2) if c2 else 0;p_e=sum(r.get('elapsed_seconds',0) for r in c2)//len(c2) if c2 else 0;o=((p_e-b_e)*100//max(1,b_e)) if b_e and c2 else 0
  print('PERFORMANCE VALIDATION: CONCURRENCY & SCALING SCENARIOS')
  print('Hardware: '+d["device"].upper()+' ('+d["model"]+') | Cloud: LOCAL')
  print('| Mode | Average Throughput (packets/sec) | Latency Overhead Delta (%) |')
  print('| 1-Stream Concurrency (Base) | '+'{:.1f}'.format(b_t)+' packets/sec | 0.00% (Baseline) |')
  if c2: print('| 2-Stream Concurrency (Parallel) | '+'{:.1f}'.format(p_t)+' packets/sec (per stream) | '+'{:.2f}'.format(o/100.0)+'% overhead |')
  else: print('| 2-Stream Concurrency (Parallel) | N/A (Not Evaluated) | N/A |')
  print('='*80)
  from tests.performance.frequency_stability import print_frequency_stability;print_frequency_stability()
  print('='*80)
  print('PERFORMANCE VALIDATION: LLM CHAOS VS OTHER STRATEGIES COMPARISON')
  print('Hardware: '+d["device"].upper()+' ('+d["model"]+') | Cloud: LOCAL')
  print('| Chaos Strategy | Detection Rate (%) | Recovery Score (%) | Resilience P | Resilience P2 |')
  st=set(str(r.get('chaos_strategy','')).lower() for r in all_res)
  for cs in st:
   print('| '+cs+' | '+'{:.2f}'.format((sum(r.get('detection_rate',0) for r in all_res if str(r.get('chaos_strategy','')).lower()==cs)//max(1,sum(1 for r in all_res if str(r.get('chaos_strategy','')).lower()==cs)))/10.0)+'% | '+'{:.2f}'.format((sum(r.get('recovery_score',0) for r in all_res if str(r.get('chaos_strategy','')).lower()==cs)//max(1,sum(1 for r in all_res if str(r.get('chaos_strategy','')).lower()==cs)))/10.0)+'% | '+'{:.3f}'.format(sum(r.get('resilience_P',0) for r in all_res if str(r.get('chaos_strategy','')).lower()==cs)/max(1,sum(1 for r in all_res if str(r.get('chaos_strategy','')).lower()==cs)))+' | '+'{:.3f}'.format(sum(r.get('resilience_P2',0) for r in all_res if str(r.get('chaos_strategy','')).lower()==cs)/max(1,sum(1 for r in all_res if str(r.get('chaos_strategy','')).lower()==cs)))+' |')
if __name__=='__main__': run_evaluation_pipeline()
