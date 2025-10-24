import io, json
from pathlib import Path
from neo_agent.intake_app import create_app
app = create_app(base_dir=Path.cwd())
payload = {
  "intake_version":"v3.0",
  "identity": {"agent_id":"AGENT-PRB-001","display_name":"PRB Test Agent","owners":["CAIO","CPA"]},
  "context": {"naics":{"code":"541110","title":"Offices of Lawyers","level":6,"lineage":[]}, "region":["CA"]},
  "role": {"function_code":"legal_compliance","role_code":"AIA-P","role_title":"Legal & Compliance Lead","objectives":["Ensure compliance"]},
  "governance_eval": {"gates": {"PRI_min":0.95,"hallucination_max":0.02,"audit_min":0.9}}
}
body = json.dumps(payload).encode('utf-8')
env={'REQUEST_METHOD':'POST','PATH_INFO':'/save','QUERY_STRING':'','SERVER_NAME':'testserver','SERVER_PORT':'80','wsgi.version':(1,0),'wsgi.url_scheme':'http','wsgi.input':io.BytesIO(body),'CONTENT_LENGTH':str(len(body))}
sh=[]
resp=b''.join(app.wsgi_app(env, lambda s,h: sh.append((s,h))))
print(sh[0][0])
print(resp.decode('utf-8'))
