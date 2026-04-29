import sys, json, re
sys.path.insert(0, '.')
from app import app
with app.test_client() as c:
    resp = c.get('/')
    html = resp.data.decode('utf-8')

m = re.search(r'data-filter-categories="([^"]+)"', html)
if m:
    val = m.group(1).replace('&quot;', '"')
    cats = json.loads(val)
    print('Device-related filter cats:', [c for c in cats if 'Device' in c or 'device' in c])
    print('Device_PANEL_Device Model in filter_cats:', 'Device_PANEL_Device Model' in cats)
else:
    print('No data-filter-categories found in HTML')

# Check if device-model-block exists
if 'id="device-model-block"' in html:
    print('device-model-block div: FOUND')
else:
    print('device-model-block div: NOT FOUND')

# Check data-col in device-model-block sentinel
m2 = re.search(r'id="device-model-block".*?data-col="([^"]*)"', html, re.DOTALL)
if m2:
    print('Sentinel data-col:', repr(m2.group(1)))
else:
    print('Sentinel data-col: NOT FOUND')

# Check checkbox values/ids in device-model-block
checkboxes = re.findall(r'class="value-filter form-check-input"[^>]*value="([^"]*)"[^>]*id="([^"]*)"', html)
dm_checkboxes = [cb for cb in checkboxes if 'Device' in cb[1] or 'Device' in cb[0]]
print('Device model checkboxes:', dm_checkboxes)
