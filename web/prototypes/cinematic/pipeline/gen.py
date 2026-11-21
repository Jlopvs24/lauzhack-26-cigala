"""Image gen via OpenRouter. usage: gen.py MODEL OUT.png PROMPT_FILE [INPUT_IMAGE] [ASPECT]"""
import sys, os, json, base64, time, urllib.request
model, out, pf = sys.argv[1], sys.argv[2], sys.argv[3]
inp = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != '-' else None
aspect = sys.argv[5] if len(sys.argv) > 5 else None
key = None
for line in open(os.environ['ENVF'], encoding='utf-8'):
    if line.startswith('OPENROUTER_API_KEY='): key = line.split('=',1)[1].strip().strip('"')
prompt = open(pf, encoding='utf-8').read()
content = [{"type": "text", "text": prompt}]
if inp:
    b = base64.b64encode(open(inp,'rb').read()).decode()
    mime = 'image/png' if inp.endswith('png') else 'image/jpeg'
    content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b}"}})
body = {"model": model, "messages": [{"role": "user", "content": content}], "modalities": ["image", "text"], "usage": {"include": True}}
if aspect: body["image_config"] = {"aspect_ratio": aspect}
req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(body).encode(),
    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
t = time.time()
r = json.load(urllib.request.urlopen(req, timeout=300))
msg = r["choices"][0]["message"]
imgs = msg.get("images") or []
cost = r.get("usage", {}).get("cost")
if not imgs:
    print("NO IMAGE", msg.get("content", "")[:300]); 
else:
    url = imgs[0]["image_url"]["url"]
    open(out, 'wb').write(base64.b64decode(url.split(',',1)[1]))
print(f"{out} cost={cost} t={time.time()-t:.1f}s")
with open(os.path.join(os.path.dirname(pf), 'costs.log'), 'a') as f:
    f.write(f"{time.strftime('%H:%M:%S')} {model} {os.path.basename(out)} {cost}\n")
