import os, threading, time, traceback
from flask import Flask, jsonify, render_template
import monitor as m
app=Flask(__name__)
@app.get('/')
def dashboard(): return render_template('dashboard.html',d=m.snapshot())
@app.get('/api/status')
def status(): return jsonify(m.snapshot())
@app.get('/health')
def health():
    d=m.snapshot();return jsonify(health=d['health'],pid=d['pid'],restarts=d['restarts'])
def worker():
    try:
        rows=m.sequence(os.environ.get('MONITOR_MODE','history'))
        due=time.monotonic()
        while True:
            with m.connect() as c: s=dict(c.execute('SELECT * FROM state').fetchone())
            if time.monotonic()>=due:
                if s['cursor']>=len(rows):
                    m.tick(next_cycle=True)
                else: m.tick(rows[s['cursor']],advance=True)
                due=time.monotonic()+m.INTERVAL
            else: m.tick()
            time.sleep(.2)
    except Exception:
        try:
            with m.connect() as c:m.event(c,'APPLICATION_ERROR',traceback=traceback.format_exc())
        finally: os._exit(1) # allow supervisor to restart the complete application
if __name__=='__main__':
    m.initialize();m.startup()
    threading.Thread(target=worker,daemon=True).start()
    app.run(host='127.0.0.1',port=int(os.environ.get('MONITOR_PORT','5071')),debug=False,use_reloader=False)
