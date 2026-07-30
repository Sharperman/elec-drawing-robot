#!/usr/bin/env python3
"""Git init and push for elec-drawing-robot"""
import subprocess, sys, os

ROOT = r"C:\Users\li_hk\WorkBuddy\2026-05-21-08-46-52\elec-drawing-robot"
os.chdir(ROOT)

def run(cmd, check=True):
    print(f"\n[RUN] {' '.join(cmd)}")
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    out = (r.stdout + r.stderr).strip()
    if out:
        print(out)
    if check and r.returncode != 0:
        print(f"FAILED (exit {r.returncode})")
        sys.exit(1)
    return r

# Step 1: git init
if not os.path.exists(os.path.join(ROOT, ".git")):
    run(["git", "init"])

# Step 2: git add
run(["git", "add", "."])

# Step 3: git commit
run(["git", "commit", "-m", "feat: initial commit with CI/CD workflows"], check=False)

# Step 4: set branch to main
run(["git", "branch", "-M", "main"])

# Step 5: add remote (if not exists)
r = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True, cwd=ROOT)
if r.returncode != 0:
    run(["git", "remote", "add", "origin", "git@github.com:Sharperman/elec-drawing-robot.git"])

# Step 6: push
print("\n[PUSH] Pushing to GitHub...")
r = subprocess.run(["git", "push", "-u", "origin", "main"], capture_output=True, text=True, cwd=ROOT)
out = (r.stdout + r.stderr).strip()
print(out)
if r.returncode == 0:
    print("\n=== PUSH SUCCESS! ===")
    # Create develop branch
    run(["git", "checkout", "-b", "develop"])
    run(["git", "push", "-u", "origin", "develop"])
    print("\n=== ALL DONE ===")
else:
    # Try HTTPS fallback
    print("SSH failed, trying HTTPS...")
    run(["git", "remote", "remove", "origin"], check=False)
    run(["git", "remote", "add", "origin", "https://github.com/Sharperman/elec-drawing-robot.git"])
    r2 = subprocess.run(["git", "push", "-u", "origin", "main"], capture_output=True, text=True, cwd=ROOT)
    print((r2.stdout + r2.stderr).strip())
    if r2.returncode == 0:
        print("\n=== PUSH SUCCESS via HTTPS! ===")
        run(["git", "checkout", "-b", "develop"])
        run(["git", "push", "-u", "origin", "develop"])
        print("\n=== ALL DONE ===")
    else:
        print("\n=== PUSH FAILED ===")
        print("Please run git-init-and-push.bat manually (double-click in Explorer)")
        sys.exit(1)
