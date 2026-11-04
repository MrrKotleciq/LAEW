"""Manual browser fixture: real UI assets, in-memory API, no LAEW runtime or models.

Run with `python tests/ui/knowledge_fixture.py`; open the printed loopback URL.
Nothing is written to a knowledge vault, database, or vector collection.
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ASSETS = Path(__file__).resolve().parents[2] / 'laew' / 'ui'
PROPOSAL = {
    'id': 'fixture-note', 'title': 'Online identification — RLS',
    'summary': 'Confirmed reusable technical findings from an isolated conversation.',
    'proposal_type': 'create', 'status': 'pending_review', 'version': 1,
    'target': '@knowledge/topics/online-identification.md', 'index_status': 'not_written',
    'content': '---\nname: Online identification\ndescription: Confirmed RLS findings\ntype: docs\nscope: global\nstatus: active\ntags: []\n---\n\n# Online identification\n\nUse persistent excitation.\n',
    'sources': [{'conversation_id': 'fixture-conversation', 'event_id': 'fixture-user', 'source_type': 'user_fact', 'evidence': 'Tested with persistent excitation.'}],
    'matches': [], 'needs_target_decision': False,
}


class Handler(BaseHTTPRequestHandler):
    def reply(self, value):
        raw = json.dumps(value).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/api/knowledge/state':
            project = parse_qs(parsed.query).get('project_id', [None])[0]
            self.reply({'settings': {'extraction_enabled': True, 'interval_completed_turns': 5},
                        'proposals': [] if project else [PROPOSAL],
                        'status': {'fixture': True, 'pending_index_updates': 0},
                        'extraction_model': {'provider': 'fixture', 'model': 'no-inference'}})
            return
        path = ASSETS / ('index.html' if parsed.path == '/' else parsed.path.lstrip('/'))
        if path.parent != ASSETS or not path.is_file():
            self.send_error(404)
            return
        text = path.read_text(encoding='utf-8')
        if path.name == 'index.html':
            text = text.replace('<script src="/app.js" defer></script>', '')
            text = text.replace('<script src="/settings.js" defer></script>', '')
            text = text.replace('</body>', '''<script>
document.addEventListener('DOMContentLoaded',()=>{
 let project=null;
 const review=window.LAEWKnowledge.create({project:()=>project,conversation:()=> 'fixture-conversation'});
 review.refresh();
 document.querySelector('#active-project-name').textContent='Isolated browser fixture';
 document.querySelector('#nav-settings').onclick=()=>{document.querySelector('#settings-view').hidden=false;document.querySelector('#chat-view').hidden=true;};
 const switcher=document.createElement('button');switcher.id='fixture-scope';switcher.textContent='Switch fixture scope';switcher.onclick=()=>{project=project?null:'fixture-project';review.refresh();};document.querySelector('.topbar').append(switcher);
});</script></body>''')
        raw = text.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', {'html': 'text/html', 'css': 'text/css', 'js': 'text/javascript'}[path.suffix[1:]])
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
        action = self.path.rsplit('/', 1)[-1]
        if action == 'preview':
            self.reply(PROPOSAL | {'diff': '+ Use persistent excitation.', 'stale': False})
        elif action == 'edit':
            PROPOSAL['content'] = body['content']
            PROPOSAL['version'] += 1
            self.reply(PROPOSAL)
        elif action == 'decide':
            PROPOSAL['status'] = {'approve': 'applied', 'reject': 'rejected', 'defer': 'deferred'}[body['action']]
            PROPOSAL['version'] += 1
            self.reply(PROPOSAL)
        else:
            self.reply({'message': 'Fixture operation completed without external side effects.'})


if __name__ == '__main__':
    server = ThreadingHTTPServer(('127.0.0.1', 18766), Handler)
    print('Isolated Knowledge UI fixture: http://127.0.0.1:18766', flush=True)
    server.serve_forever()
