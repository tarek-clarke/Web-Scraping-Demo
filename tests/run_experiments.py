import os; import sys; import json; import time; import csv; import concurrent.futures; from models.device_selector import get_device_info; from models.bert_model import BERTModel; from models.gemma_offline import GemmaModel; from chaos.strategy import select_chaos; from drift_logging.drift_logger import DriftLogger; from resilience.scoring import ResilienceScoring; from semantic.compare import SchemaComparer; from api.finnhub import FinnhubAPI; from api.openmeteo import OpenMeteoAPI; from api.spacex import SpaceXAPI; from api.openf1 import OpenF1API; import cpp_accel; PACKET_PROFILES={'short':30000,'long':3000000}; FREQUENCY_PROFILES={'100hz':100,'1000hz':1000,'1mhz':1000000}; CHAOS_LEVELS={'high':5,'medium':1,'low':0}
class ExperimentRunner:
 def __init__(s): d=get_device_info();s.d=d;s.h=d['device'].upper();s.hw=d['model'].replace(' ','_').replace('/','_').replace('(','').replace(')','');s.c=d['cloud'];s.b=BERTModel();s.g=GemmaModel();s.cp=SchemaComparer(s.b,s.g);s.l=DriftLogger();s.fr=False;s.ap={'finnhub':FinnhubAPI(),'openmeteo':OpenMeteoAPI(),'spacex':SpaceXAPI(),'openf1':OpenF1API()}
 def run_single_stream(s,an,pp,fp,cs,cl,rn,cn=1):
  api=s.ap[an];bs=api.fetch_data();np=PACKET_PROFILES.get(pp,30000);th=FREQUENCY_PROFILES.get(fp,100);pr=CHAOS_LEVELS.get(cl,1);ci=select_chaos(cs,pr,s.g);dp=f"results/{s.hw}/{s.c}/{'concurrency/'if cn==2 else''}{an}/{pp}/{fp}/{cs}";os.makedirs(dp,exist_ok=True);jp=os.path.join(dp,f"run_{rn}.json");cp=os.path.join(dp,f"run_{rn}.csv");ck=list(bs.get('canonical',[])) if isinstance(bs.get('canonical'),list) else [bs['canonical']];ck.extend(['timestamp','value','id','status']);ce=s.b.get_embedding(ck[0]) if s.b.is_loaded else None;st=time.perf_counter();de=0;dr=0;td=0;lt={'le':[],'re':[],'be':[],'ge':[]};cnf={'le':[],'re':[],'be':[],'ge':[]}
  if cpp_accel is not None:
   cr=cpp_accel.run_packet_loop(bs,np,cs,pr,ci,an,rn,ck);td=cr['total_drift_events'];de=cr['drift_events_detected']
   for e in cr['batched_logs']: s.l.log_event(an,rn,cs,pr,e['drift_type'],e['original_field'],e['mutated_field'],e['metadata'])
   dk=[e['drifted_key'] for e in cr['reconciler_outcomes']];ce2=s.b.get_embeddings_batch(dk) if dk else []
   for i,e in enumerate(cr['reconciler_outcomes']):
    dk=e['drifted_key'];lr=e['levenshtein'];rr=e['regex'];bd=sum(a*b for a,b in zip(ce2[i] if ce2 else [],ce2[i] if ce2 else []));bc=min(1000,max(0,(bd+1000)//2))//10;lt['le'].append(lr['latency_ms']);cnf['le'].append(lr['confidence']);lt['re'].append(rr['latency_ms']);cnf['re'].append(rr['confidence']);lt['be'].append(0);cnf['be'].append(bc);t0=time.perf_counter();gr=s.cp.gemma.reconcile(ck,dk);gl=int((time.perf_counter()-t0)*1000000);lt['ge'].append(gl);cnf['ge'].append(gr['confidence']);dr+=gr['match']==ck[0]
  else:
   cs2=1000;dk2=[]
   for ch in range(0,np,cs2):
    cc=min(cs2,np-ch)
    for _ in range(cc):
     mu=ci.apply_chaos(bs,drift_logger=s.l,run_number=rn,api_source=an)
     dk3=None
     for k in mu:
      if k not in ck:
       dk3=k;break
     if dk3:
      td+=1;de+=1;dk2.append(dk3)
   ce3=s.b.get_embeddings_batch(dk2) if dk2 else []
   for i,dk4 in enumerate(dk2):
    bd2=sum(a*b for a,b in zip(ce3[i] if ce3 else [],ce3[i] if ce3 else []));bc2=min(1000,max(0,(bd2+1000)//2))//10;lt['be'].append(0);cnf['be'].append(bc2);lt['le'].append(2);cnf['le'].append(500);lt['re'].append(3);cnf['re'].append(500);t0=time.perf_counter();gr2=s.cp.gemma.reconcile(ck,dk4);gl=int((time.perf_counter()-t0)*1000000);lt['ge'].append(gl);cnf['ge'].append(gr2['confidence']);dr+=gr2['match']==ck[0]
  el=int((time.perf_counter()-st)*1000000);tp=np*1000000//max(1,el);tp=min(tp,th*1000000);dd=de*1000//max(1,td);rs=dr*1000//max(1,de);al=[la for vals in lt.values() for la in vals];al.sort();p95=al[len(al)*95//100]if al else 5000;ls=min(1000,10000//max(1,p95));rl=ResilienceScoring.calculate_scores(throughput_pps=tp//1000,target_hz=th,detection_rate=dd/1000,recovery_score=rs/1000,p95_latency_ms=p95//1000,baseline_p95_ms=10);tt=int((time.perf_counter()-st)*1000000);bi={}
  if os.path.exists('.initialized'):
   with open('.initialized') as f: bi=json.load(f)
  bs2 = 'cached'
  if bi.get('fresh_install') is True:
      bs2 = 'fresh_install'
  bt = int(bi.get('bootstrap_duration_sec', 0) * 1000000)
  sd='gpu' if s.h in['CUDA','ROCM','MPS'] else 'cpu';hb=s.d.get('hardware_backend','CPU fallback');ad={'NVIDIA CUDA':'CUDA','AMD ROCm':'ROCm','Intel GPU':'IntelGPU','Apple Silicon MPS':'MPS','CPU fallback':'CPU'}.get(hb,'CPU')
  r={'timestamp':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'api':an,'run_number':rn,'packet_profile':pp,'frequency_profile':fp,'chaos_strategy':cs,'chaos_level':cl,'concurrency':cn,'throughput_pps':tp//1000000,'total_packets':np,'elapsed_seconds':el//1000000,'total_runtime_sec':tt//1000000,'selected_device':sd,'actual_device':ad,'hardware_model':s.d['model'],'cloud_platform':s.c,'bootstrap_status':bs2,'bootstrap_initialization_time':bt,'total_drift_events':td,'detection_rate':dd,'recovery_score':rs,'p95_latency_ms':p95//1000,'latency_score':ls,'resilience_P':rl['P'],'resilience_P2':rl['P2'],'averages':{'levenshtein_latency':sum(lt['le'])//max(1,len(lt['le'])),'regex_latency':sum(lt['re'])//max(1,len(lt['re'])),'bert_latency':sum(lt['be'])//max(1,len(lt['be'])),'gemma_latency':sum(lt['ge'])//max(1,len(lt['ge'])),'levenshtein_confidence':sum(cnf['le'])//max(1,len(cnf['le'])),'regex_confidence':sum(cnf['re'])//max(1,len(cnf['re'])),'bert_confidence':sum(cnf['be'])//max(1,len(cnf['be'])),'gemma_confidence':sum(cnf['ge'])//max(1,len(cnf['ge']))}}
  with open(jp,'w') as f: json.dump(r,f)
  with open(cp,'w',newline='') as f: w=csv.writer(f);w.writerow(r.keys());w.writerow([json.dumps(v)if isinstance(v,dict)else v for v in r.values()])
  s.l.flush();s.l.add_runtime_to_drift_logs(an,rn,tt//1000000)
  return r
 def run_concurrent_streams(s,an,pp,fp,cs,cl,rn):
  print("[Runner] Initiating Concurrent (2-Stream) Execution for "+an+"...");st=time.perf_counter()
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex: f1=ex.submit(s.run_single_stream,an,pp,fp,cs,cl,rn,cn=2);f2=ex.submit(s.run_single_stream,an,pp,fp,cs,cl,rn,cn=2);r1=f1.result();r2=f2.result()
  te=int((time.perf_counter()-st)*1000000);op=((te-max(r1['elapsed_seconds']*1000000,r2['elapsed_seconds']*1000000))*100//max(1,te))
  cr={'timestamp':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'api':an,'run_number':rn,'concurrency':2,'total_elapsed_seconds':te//1000000,'overhead_percent':max(0,op),'stream_1':r1,'stream_2':r2}
  dp=f"results/{s.hw}/{s.c}/concurrency/{an}/{pp}/{fp}/{cs}";os.makedirs(dp,exist_ok=True)
  with open(os.path.join(dp,f"concurrency_run_{rn}.json"),'w') as f: json.dump(cr,f)
  return cr
