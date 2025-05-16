import subprocess

def format_code():
    subprocess.run(["ruff", "format", "."], check=True)

def lint_code():
    subprocess.run(["ruff", "check", "."], check=True)

def lint_fix_code():
    subprocess.run(["ruff", "check", "--fix", "."], check=True) 