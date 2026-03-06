#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import argparse
import asyncio
import subprocess
import time
from backend.core.containers import main_container

class GitLifecycleManager:
    """Manages the full cycle: Branch -> PR -> Merge -> Deletion."""
    def __init__(self, repo_url, token, project_root):
        self.repo_url = repo_url
        self.token = token
        self.project_root = project_root
        self.base_branch = "main"

    def log(self, msg):
        print(f"\033[94m[GIT_LIFECYCLE]\033[0m {msg}", flush=True)

    def run(self, cmd, desc, ignore_error=False):
        env = os.environ.copy()
        env["GITHUB_TOKEN"] = self.token
        res = subprocess.run(cmd, cwd=self.project_root, capture_output=True, text=True, env=env)
        if res.returncode == 0:
            return True
        elif not ignore_error:
            self.log(f"❌ Error in {desc}: {res.stderr.strip()}")
        return False

    def setup(self, create_if_missing=False, org=None, repo_name=None):
        self.project_root.mkdir(parents=True, exist_ok=True)
        if not (self.project_root / ".git").exists():
            self.run(["git", "init"], "Init")

        if create_if_missing and repo_name:
            self.log(f"🚀 Checking/Creating repository {repo_name} on GitHub...")
            env = os.environ.copy()
            env["GITHUB_TOKEN"] = self.token
            # Use 'gh' directly for creation
            repo_path = f"{org}/{repo_name}" if org else repo_name
            subprocess.run(["gh", "repo", "create", repo_path, "--private", "--confirm"],
                           cwd=self.project_root, capture_output=True, text=True, env=env)

        auth_url = self.repo_url.replace("https://", f"https://{self.token}@")
        self.run(["git", "remote", "remove", "origin"], "Reset remote", True)
        self.run(["git", "remote", "add", "origin", auth_url], "Add remote")
        self.run(["git", "branch", "-M", self.base_branch], "Rename branch")

    def handle_task_completion(self, task_id, file_path, task_desc, issue_number=None, agent=None, version="v0.1.0"):
        branch = f"feat/{task_id.lower()}"
        self.log(f"🛠️ Processing task {task_id} ({file_path}) -> Version {version}...")

        # 1. Create branch and commit
        self.run(["git", "checkout", "-b", branch], f"Create branch {branch}", True)
        self.run(["git", "add", file_path], f"Add {file_path}")

        # Use simple commit for local, full PR body later
        self.run(["git", "commit", "-m", f"feat: implement {task_id}"], "Commit")
        if self.run(["git", "push", "origin", branch, "--force"], f"Push {branch}"):

            # 2. Secretary Agent: Generate professional description
            self.log(f"📝 Secretary Agent drafting PR description for {version}...")
            # ... (prompt logic remains same)
            pr_body = f"Completed task {task_id}." # Fallback

            if agent:
                try:
                    from backend.utils.core.llm.prompt_loader import PromptLoader
                    loader = PromptLoader()
                    prompts = loader.load_prompt_sync("domains/auto_generation/secretary.yaml")

                    system = prompts.get("pr_description", {}).get("system", "")
                    user_template = prompts.get("pr_description", {}).get("user", "")

                    user = user_template.format(
                        task_id=task_id,
                        task_desc=task_desc,
                        file_path=file_path
                    )

                    res, _ = agent.llm_manager.get_client("writer").chat([
                        {"role": "system", "content": system},
                        {"role": "user", "content": user}
                    ])
                    pr_body = res.get("content", pr_body).strip()
                except Exception as e:
                    self.log(f"⚠️ Secretary Error: {e}")

            # 3. Create PR and MERGE immediately
            self.log(f"🚀 Creating PR and Merging {task_id}...")

            env = os.environ.copy()
            env["GITHUB_TOKEN"] = self.token

            if issue_number:
                pr_body += f"\n\nCloses #{issue_number}"

            # Title with version
            pr_title = f"{version} | {task_id}: Implementation"

            pr_res = subprocess.run(["gh", "pr", "create", "--title", pr_title, "--body", pr_body, "--head", branch, "--base", self.base_branch],
                                    cwd=self.project_root, capture_output=True, text=True, env=env)

            if pr_res.returncode == 0:
                # 4. PR Merge
                if self.run(["gh", "pr", "merge", "--merge", "--delete-branch"], f"Merge PR {task_id}"):
                    self.log(f"✅ Task {task_id} integrated. Tagging as {version}.")

                    # NEW: Semantic Tag
                    # Fetch tags to ensure we have the latest state
                    self.run(["git", "fetch", "--tags"], "Fetch tags", True)
                    
                    # Force update the tag if it exists (moving the tag to the new commit)
                    # Alternatively, we could increment, but for this task flow, moving the tag to the latest completion of that step is acceptable behavior for "v0.1.X" tracking.
                    self.run(["git", "tag", "-f", "-a", version, "-m", f"Release {version}: {task_id}"], f"Tag {version}")
                    self.run(["git", "push", "origin", version, "--force"], f"Push tag {version}")

                    # 5. Return to main and update
                    self.run(["git", "checkout", self.base_branch], "Back to main")
                    self.run(["git", "pull", "origin", self.base_branch], "Update main")
            else:
                self.log(f"⚠️ PR creation failed: {pr_res.stderr.strip()}")
                self.run(["git", "checkout", self.base_branch], "Back to main")

    def sync_ollash_manifest(self, content):
        """Force-pushes the OLLASH.md manifest directly to the main branch."""
        self.log("🧠 Syncing OLLASH.md manifest to main...")
        manifest_path = self.project_root / "OLLASH.md"

        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(content)

        current_branch = subprocess.run(["git", "branch", "--show-current"], cwd=self.project_root, capture_output=True, text=True).stdout.strip()

        # Flux: Stash -> Switch to main -> Add/Commit -> Push -> Switch back
        # Using a safer approach: push local file directly to origin/main
        if current_branch != self.base_branch:
            # Add to git tracking if not already there
            self.run(["git", "add", "OLLASH.md"], "Track manifest")
            # We can't push a single file easily without checkout, so we do a quick jump
            self.run(["git", "stash"], "Stash changes")
            self.run(["git", "checkout", self.base_branch], "Switch to main")
            self.run(["git", "pull", "origin", self.base_branch], "Sync main")

            with open(manifest_path, "w", encoding="utf-8") as f: # Re-write in main
                f.write(content)

            self.run(["git", "add", "OLLASH.md"], "Add manifest")
            self.run(["git", "commit", "-m", "chore: update Ollash project manifest 🤖"], "Commit manifest", True)
            self.run(["git", "push", "origin", self.base_branch], "Push manifest")

            self.run(["git", "checkout", current_branch], "Return to feat branch")
            self.run(["git", "stash", "pop"], "Restore work", True)
        else:
            self.run(["git", "add", "OLLASH.md"], "Add manifest")
            self.run(["git", "commit", "-m", "chore: update Ollash project manifest 🤖"], "Commit manifest", True)
            self.run(["git", "push", "origin", self.base_branch], "Push manifest")

def main():
    main_container.wire(modules=[__name__, "backend.agents.auto_agent"])
    p = argparse.ArgumentParser()
    p.add_argument("--description", required=True); p.add_argument("--name", default="MagicCloneJS")
    p.add_argument("--repo-url", default=None); p.add_argument("--github-token", default=None)
    p.add_argument("--git-auto-create", action="store_true", help="Create GitHub repository if it doesn't exist")
    p.add_argument("--num-refine-loops", type=int, default=1); p.add_argument("--maintenance-interval", type=int, choices=range(1, 25), help="Enable maintenance mode every N hours (1-24)")
    p.add_argument("--debug", action="store_true", help="Enable debug logging (shows Ollama JSON)")
    args, _ = p.parse_known_args()

    # Configure log level based on debug flag
    import logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    main_container.core.logging.structured_logger()._logger.setLevel(log_level)

    start_time = time.time()
    try:
        print(f"DEBUG: Calling auto_agent factory...")
        agent = main_container.auto_agent_module.auto_agent()
        print(f"DEBUG: agent type: {type(agent)}")
        print(f"DEBUG: agent value: {agent}")
        if asyncio.iscoroutine(agent) or isinstance(agent, asyncio.Future):
             print("DEBUG: agent is a coroutine or future, this is unexpected in sync code.")
        
        project_root = agent.generated_projects_dir / args.name
        git_manager = GitLifecycleManager(args.repo_url, args.github_token, project_root) if args.repo_url and args.github_token else None

        # Parse org from URL
        org = None
        if args.repo_url:
            from urllib.parse import urlparse
            parsed = urlparse(args.repo_url)
            parts = [p for p in parsed.path.strip("/").split("/") if p]
            org = parts[0] if len(parts) >= 2 else None

        if git_manager: git_manager.setup(create_if_missing=args.git_auto_create, org=org, repo_name=args.name)

        def on_event(event_type, event_data):
            if event_type == "phase_complete" and str(event_data.get("phase")) == "1":
                if git_manager: git_manager.log("📝 Secretary Agent drafting initial vision description...")
                initial_msg = "Initial project vision and README"
                try:
                    from backend.utils.core.llm.prompt_loader import PromptLoader
                    loader = PromptLoader()
                    prompts = loader.load_prompt_sync("domains/auto_generation/vision.yaml")

                    system = prompts.get("initial_vision", {}).get("system", "")
                    user_template = prompts.get("initial_vision", {}).get("user", "")

                    user = user_template.format(
                        project_name=args.name,
                        project_description=args.description
                    )

                    res, _ = agent.llm_manager.get_client("writer").chat([
                        {"role": "system", "content": system},
                        {"role": "user", "content": user}
                    ])
                    initial_msg = res.get("content", initial_msg).strip()
                except: pass

                if git_manager: git_manager.run(["git", "add", "README.md"], "Add README")
                if git_manager: git_manager.run(["git", "commit", "-m", initial_msg], "Initial Commit")
                if git_manager: git_manager.run(["git", "push", "-u", "origin", "main", "--force"], "Initial Push")

            if event_type == "agent_board_update" and event_data.get("new_status") == "done":
                task_id = event_data.get("task_id")
                backlog = getattr(agent.phase_context, "backlog", [])

                # Calculate Semantic Version (v0.1.X)
                # Count already finished tasks + current one
                done_count = len([t for t in backlog if t.get("status") == "done"])
                version = f"v0.1.{done_count}"

                task = next((t for t in backlog if t["id"] == task_id), None)
                if task:
                    # Get issue number from context mapping
                    issue_mapping = getattr(agent.phase_context, "issue_mapping", {})
                    issue_number = issue_mapping.get(task_id)

                    # Store current version in context for manifest
                    agent.phase_context.current_version = version

                    if git_manager: git_manager.handle_task_completion(
                        task_id=task_id,
                        file_path=task["file_path"],
                        task_desc=task.get("description", "No description"),
                        issue_number=issue_number,
                        agent=agent,
                        version=version
                    )

                    # NEW: Update and Sync OLLASH.md manifest
                    try:
                        import nest_asyncio
                        nest_asyncio.apply()
                        loop = asyncio.get_event_loop()
                        manifest_content = loop.run_until_complete(agent._update_ollash_manifest(current_task_id=task_id))
                        if manifest_content:
                            if git_manager: git_manager.sync_ollash_manifest(manifest_content)
                    except Exception as e:
                        if git_manager: git_manager.log(f"⚠️ Manifest Sync Error: {e}")
        agent.phase_context.event_publisher.subscribe("phase_complete", on_event)
        agent.phase_context.event_publisher.subscribe("agent_board_update", on_event)

        # Initial Run
        agent.run(
            project_description=args.description,
            project_name=args.name,
            num_refine_loops=args.num_refine_loops,
            github_integration=bool(args.github_token),
            github_token=args.github_token
        )

        # Display Final Summary
        duration = time.time() - start_time
        print(f"\n\033[92m{'=' * 60}")
        print(f"✅ PROJECT GENERATION COMPLETE")
        print(f"⏱️  Total Duration: {duration/60:.2f} minutes")
        if hasattr(agent, 'token_tracker'):
            print(agent.token_tracker.get_session_summary())
        print(f"{'=' * 60}\033[0m\n")

        # Maintenance Mode

        if args.maintenance_interval:
            from backend.utils.core.system.task_scheduler import get_scheduler
            scheduler = get_scheduler()

            async def maintenance_job(tid, tdata):
                if git_manager: git_manager.log(f"⏰ Maintenance cycle started (Every {args.maintenance_interval}h)")
                # Run the agent in maintenance mode (only refinement/audit)
                agent.run(
                    project_description=args.description,
                    project_name=args.name,
                    num_refine_loops=args.num_refine_loops,
                    maintenance_mode=True,
                    github_integration=bool(args.github_token),
                    github_token=args.github_token
                )

            scheduler.set_callback(maintenance_job)
            scheduler.schedule_task("maintenance_loop", {
                "name": f"Maintenance: {args.name}",
                "schedule": "custom",
                "cron": f"0 */{args.maintenance_interval} * * *",
                "agent": "orchestrator"
            })

            if git_manager: git_manager.log(f"🚀 Continuous Maintenance scheduled every {args.maintenance_interval} hours. Press Ctrl+C to stop.")
            while True:
                time.sleep(10)

    except Exception as e: print(f"FATAL: {e}")

if __name__ == "__main__": main()
