"""Runs a real child-process kill/restart test and captures HTTP responses."""
import json,os,signal,sqlite3,subprocess,sys,time,urllib.request,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent
out=ROOT/'evidence';out.mkdir(exist_ok=True)
runtime=ROOT/'runtime'/'verification'
if runtime.exists(): raise SystemExit('Verification runtime already exists. Choose a fresh copy to preserve evidence.')
env=dict(os.environ,MONITOR_RUNTIME=str(runtime),MONITOR_MODE='demo',MONITOR_PORT='5071')
url='http://127.0.0.1:5071'
def get():
 with urllib.request.urlopen(url+'/api/status',timeout=2) as f:return json.load(f)
def wait_for(predicate,timeout=55):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  try:
   s=get()
   if predicate(s):return s
  except (OSError,ValueError):pass
  time.sleep(.15)
 raise AssertionError('Timed out waiting for required state')
supervisor=subprocess.Popen([sys.executable,str(ROOT/'supervisor.py')],env=env)
results={}
try:
 if True:
  def capture(name,s):
   with urllib.request.urlopen(url,timeout=2) as response:
    html=response.read().decode()
   assert 'Unattended temperature monitor' in html
   (out/(name+'.html')).write_text(html)
   (out/(name+'.json')).write_text(json.dumps(s,indent=2))
  s=wait_for(lambda s:s['health']=='HEALTHY');capture('01_dashboard_running',s)
  s=wait_for(lambda s:s['alert']);capture('02_alert_active',s)
  s=wait_for(lambda s:not s['alert'] and s['cursor']>=12);capture('03_alert_cleared',s)
  s=wait_for(lambda s:s['data_status']=='MISSING');capture('04_missing',s)
  s=wait_for(lambda s:s['data_status']=='STALE' and s['health']=='FAILED');capture('05_stale_failed',s)
  s=wait_for(lambda s:s['health']=='HEALTHY' and s['cursor']>=30);capture('06_before_interruption',s)
  old_pid=s['pid']
  with sqlite3.connect(runtime/'monitor.db') as c:
   before=c.execute('SELECT * FROM live_readings ORDER BY id').fetchall()
   archive_before=c.execute('SELECT * FROM sensor_readings ORDER BY record_id').fetchall()
  started=time.monotonic();os.kill(old_pid,signal.SIGKILL)
  s=wait_for(lambda s:s['pid']!=old_pid and s['health']=='HEALTHY',timeout=12)
  elapsed=time.monotonic()-started;capture('07_recovered_healthy',s)
  with sqlite3.connect(runtime/'monitor.db') as c:
   after=c.execute('SELECT * FROM live_readings ORDER BY id').fetchall()
   archive_after=c.execute('SELECT * FROM sensor_readings ORDER BY record_id').fetchall()
   integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
  assert before==after[:len(before)] and archive_before==archive_after and integrity=='ok'
  results=dict(passed=True,old_pid=old_pid,new_pid=s['pid'],recovery_seconds=elapsed,rows_before=len(before),rows_after=len(after),history_rows=len(archive_after),history_unchanged=True,prior_live_rows_unchanged=True,sqlite_integrity=integrity,final_health=s['health'],restart_count=s['restarts'],test_method='SIGKILL of actual Flask child; supervisor stayed alive; HTTP dashboard and API verified')
finally:
 supervisor.terminate()
 try:supervisor.wait(timeout=10)
 except subprocess.TimeoutExpired:supervisor.kill();supervisor.wait()
 if runtime.exists():
  for name in ('supervisor.jsonl','application_console.log'):shutil.copyfile(runtime/name,out/name)
  with sqlite3.connect(runtime/'monitor.db') as c,sqlite3.connect(out/'verified_monitor.db') as dest:
   c.backup(dest)
   records=c.execute('SELECT timestamp,kind,details FROM events ORDER BY id').fetchall()
  (out/'application_events.jsonl').write_text(''.join(json.dumps(dict(timestamp=t,kind=k,details=json.loads(d)))+'\n' for t,k,d in records))
(out/'recovery_result.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
