import io, json, re
from pathlib import Path
from neo_agent.intake_app import create_app
app = create_app(base_dir=Path.cwd())
# call /save to ensure copy into generated_profiles
payload = json.loads(Path('agent_profile.json').read_text(encoding='utf-8'))
body = json.dumps(payload).encode('utf-8')
env={'REQUEST_METHOD':'POST','PATH_INFO':'/save','QUERY_STRING':'','SERVER_NAME':'testserver','SERVER_PORT':'80','wsgi.version':(1,0),'wsgi.url_scheme':'http','wsgi.input':io.BytesIO(body),'CONTENT_LENGTH':str(len(body))}
sh=[]
resp=b''.join(app.wsgi_app(env, lambda s,h: sh.append((s,h))))
print(sh[0][0])
print('profile_dir exists:', (Path('generated_profiles')).exists())
prof=json.loads(Path('agent_profile.json').read_text(encoding='utf-8'))
name=(prof.get('identity') or {}).get('display_name') or (prof.get('agent') or {}).get('name') or 'agent'
version=(prof.get('agent') or {}).get('version','1.0.0').replace('.','-')
slug=re.sub(r'[^a-z0-9\-]+','-', (name or '').lower().strip()).strip('-') or 'agent'
slug=f"{slug}-{version}"
print('slug=', slug)
print('slug dir exists:', (Path('generated_profiles')/slug).exists())
print('profile copy exists:', (Path('generated_profiles')/slug/'agent_profile.json').exists())
