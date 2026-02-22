from flask import Blueprint, render_template, jsonify, request
import subprocess
import os

git_bp = Blueprint('git', __name__, url_prefix='/git')

# Helper to run git commands
def run_git(args, cwd=None):
    try:
        if cwd is None:
            cwd = os.getcwd()
        result = subprocess.run(
            ['git'] + args, 
            cwd=cwd, 
            capture_output=True, 
            text=True, 
            check=False
        )
        return {"stdout": result.stdout, "stderr": result.stderr, "code": result.returncode}
    except Exception as e:
        return {"error": str(e)}

@git_bp.route('/')
def git_dashboard():
    return render_template('pages/git.html')

@git_bp.route('/api/status')
def get_status():
    status = run_git(['status', '--short'])
    branch = run_git(['rev-parse', '--abbrev-ref', 'HEAD'])
    
    files = []
    if status.get('stdout'):
        for line in status['stdout'].splitlines():
            if not line.strip(): continue
            parts = line.strip().split()
            if len(parts) >= 2:
                files.append({"status": parts[0], "file": parts[1]})
                
    return jsonify({
        "branch": branch.get('stdout', '').strip(),
        "files": files,
        "clean": len(files) == 0
    })

@git_bp.route('/api/diff')
def get_diff():
    file_path = request.args.get('file')
    if not file_path:
        return jsonify({"error": "No file specified"}), 400
        
    diff = run_git(['diff', 'HEAD', '--', file_path])
    return jsonify({"diff": diff.get('stdout', '')})

@git_bp.route('/api/commit', methods=['POST'])
def commit_changes():
    data = request.json
    message = data.get('message', 'Update from Ollash')
    files = data.get('files', ['.']) # Default to all
    
    # Stage
    run_git(['add'] + files)
    
    # Commit
    res = run_git(['commit', '-m', message])
    
    if res.get('code') == 0:
        return jsonify({"status": "success", "output": res.get('stdout')})
    return jsonify({"status": "error", "error": res.get('stderr')}), 500

@git_bp.route('/api/log')
def get_log():
    log = run_git(['log', '-n', '5', '--pretty=format:%h - %s (%cr) <%an>'])
    return jsonify({"log": log.get('stdout', '').splitlines()})
