import json,time
from urllib.request import Request,build_opener,HTTPCookieProcessor
from http.cookiejar import CookieJar
from pathlib import Path
from uuid import uuid4
import argparse
parser=argparse.ArgumentParser(description='Opt-in read-only public conversational verification; consumes the shared Free AI allowance.')
parser.add_argument('--live',action='store_true')
if not parser.parse_args().live: raise SystemExit('Pass --live only when the shared Free allowance is available.')
root=Path(__file__).resolve().parents[1]
(root/'.local').mkdir(exist_ok=True)
base='https://stockpilot-ai-p89q.onrender.com'
jar=CookieJar(); client=build_opener(HTTPCookieProcessor(jar))
def api(path,data=None):
    headers={'Content-Type':'application/json','User-Agent':'StockPilotAI/1.0','Origin':base}
    csrf=next((c.value for c in jar if c.name=='csrftoken'),'')
    headers['X-CSRFToken']=csrf
    request=Request(base+'/api/v1/'+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
    with client.open(request,timeout=110) as response:return json.load(response)
status=api('auth/session/'); assert status['registration_enabled'] is False
api('auth/demo/',{})
business=next(b for b in api('businesses/') if b['name']=='Juniper Market Supply · Demo')
root=f"businesses/{business['id']}/assistant/"
thread=api(root+'conversations/',{})['id']
questions=['What can I do to improve my business?','How is my business performing?','Why is my profit decreasing?','What products should I restock?','How can I increase my sales?','Which products are hurting my profitability?','What should I focus on next week?','Can you explain that in simpler terms?','What about last month?','Hello, what can you help me with?','If shelf space is tight, how would you decide which items deserve it?']
results=[]
for question in questions:
    answer=api(root+f'conversations/{thread}/messages/',{'text':question,'request_id':str(uuid4())})
    results.append({'question':question,'answer':answer['answer'],'proposal':bool(answer['proposal'])})
    (root/'.local/phase9-public-conversations.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    assert answer['answer']['mode']=='provider',answer['answer']['text']
    assert 'Try a question about sales' not in answer['answer']['text']
    assert not answer['proposal']
    print('PASS:',question,flush=True)
    for _ in range(3): time.sleep(22)
print('ALL PUBLIC CONVERSATIONS PASSED',flush=True)
