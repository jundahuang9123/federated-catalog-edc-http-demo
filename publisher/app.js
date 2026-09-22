const el = id => document.getElementById(id);
let csrf = '', rdf = '', filename = '', busy = false;
const update = () => { el('publish').disabled = !csrf || !rdf || busy; };
fetch('/session').then(r => r.json()).then(data => { csrf = data.csrf; el('message').textContent = 'Choose a file and enter your connection details.'; update(); }).catch(() => { el('message').textContent = 'Local sender unavailable. Reload this page.'; });
el('file').addEventListener('change', async () => {
  rdf = ''; filename = ''; update(); el('result').hidden = true;
  const file = el('file').files[0];
  el('preview').textContent = 'Choose a file to preview it.';
  if (!file) { el('file-info').textContent = 'No file selected'; return; }
  if (file.size > 2000000 || !file.size) { el('file-info').textContent = 'Choose a nonempty file up to 2 MB.'; return; }
  try {
    const text = new TextDecoder('utf-8', {fatal:true}).decode(await file.arrayBuffer());
    if (el('file').files[0] !== file) return;
    rdf = text; filename = file.name;
    el('file-info').textContent = `${filename} · ${file.size.toLocaleString()} bytes`;
    el('preview').textContent = text.slice(0,16000) + (text.length > 16000 ? '\n… Preview truncated; the entire file will be sent.' : '');
  } catch { el('file-info').textContent = 'Unable to read this file as UTF-8.'; }
  update();
});
el('publish-form').addEventListener('submit', async event => {
  event.preventDefault(); if(busy || !rdf) return;
  busy = true; update(); el('message').textContent = 'Sending your snapshot…'; el('result').hidden = true;
  try {
    const response = await fetch('/publish', {method:'POST', headers:{'Content-Type':'application/json','X-Publisher-CSRF':csrf}, body:JSON.stringify({url:el('url').value, token:el('token').value, rdf, filename})});
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || 'Local sender failed.');
    const accepted = result.status >= 200 && result.status < 300 && result.response?.accepted === true;
    el('message').textContent = accepted ? `Accepted — HTTP ${result.status}. Refresh the catalog to see your snapshot.` : `Not accepted — HTTP ${result.status}. Review the response below.`;
    el('result').textContent = JSON.stringify(result,null,2); el('result').hidden = false;
  } catch(error) { el('message').textContent = error.message; }
  finally { busy = false; update(); }
});
