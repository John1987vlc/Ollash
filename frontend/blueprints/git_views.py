from flask import Blueprint, render_template, jsonify, request
import subprocess
import os

from pydantic import ValidationError

from frontend.schemas.git_schemas import GitCommitRequest

bp = Blueprint("git", __name__, url_prefix="/git")


# Helper to run git commands
def run_git(args, cwd=None):
    try:
        if cwd is None:
            cwd = os.getcwd()
        result = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True, check=False)
        return {"stdout": result.stdout, "stderr": result.stderr, "code": result.returncode}
    except Exception as e:
        return {"error": str(e)}


@bp.route("/")
def git_dashboard():
    return render_template("pages/git.html")


@bp.route("/api/status")
def get_status():
    status = run_git(["status", "--short"])
    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"])

    files = []
    if status.get("stdout"):
        for line in status["stdout"].splitlines():
            if not line.strip():
                continue
            parts = line.strip().split()
            if len(parts) >= 2:
                files.append({"status": parts[0], "file": parts[1]})

    return jsonify({"branch": branch.get("stdout", "").strip(), "files": files, "clean": len(files) == 0})


@bp.route("/api/diff")
def get_diff():
    file_path = request.args.get("file")
    if not file_path:
        return jsonify({"error": "No file specified"}), 400

    diff = run_git(["diff", "HEAD", "--", file_path])
    return jsonify({"diff": diff.get("stdout", "")})


@bp.route("/api/commit", methods=["POST"])
def commit_changes():
    try:
        body = GitCommitRequest.model_validate(request.get_json() or {})
    except ValidationError as exc:
        return jsonify({"status": "error", "error": exc.errors()}), 422

    # Stage
    run_git(["add"] + body.files)

    # Commit
    res = run_git(["commit", "-m", body.message])

    if res.get("code") == 0:
        return jsonify({"status": "success", "output": res.get("stdout")})
    return jsonify({"status": "error", "error": res.get("stderr")}), 500


@bp.route("/api/log")
def get_log():
    log = run_git(["log", "-n", "5", "--pretty=format:%h - %s (%cr) <%an>"])
    return jsonify({"log": log.get("stdout", "").splitlines()})
