"""Put release compatibility changes in one reviewable branch/PR; never push main directly."""
import json
import subprocess


def run(*args, **kw):
    return subprocess.run(args, text=True, check=True, **kw)


def main():
    paths = ["compatibility.json", "toolchains.json", "calibration"]
    changes = run("git","status","--porcelain","--",*paths,capture_output=True).stdout
    if not changes:
        print("No compatibility changes"); return
    branch = "automation/app-compatibility"
    run("git","config","user.name","github-actions[bot]")
    run("git","config","user.email","41898282+github-actions[bot]@users.noreply.github.com")
    run("git","switch","-c",branch)
    run("git","add","--",*paths)
    run("git","commit","-m","registry: record measured app-release compatibility")
    # The dedicated automation branch may be replaced by its newer projection; no owner branch
    # or main is rewritten. Existing branch protection still applies normally.
    run("gh","auth","setup-git")
    remote = subprocess.run(["git","ls-remote","--exit-code","--heads","origin",branch],capture_output=True,text=True)
    if remote.returncode not in (0,2):
        raise RuntimeError(remote.stderr)
    expected = remote.stdout.split()[0] if remote.returncode == 0 else ""
    run("git","push",f"--force-with-lease=refs/heads/{branch}:{expected}","origin",branch)
    existing = json.loads(run("gh","pr","list","--head",branch,"--state","open","--json","number",capture_output=True).stdout)
    if not existing:
        body = ("Re-lints each current HUD with immutable app-release simulators in every shipped language. "
                "Records language failures, compatibility ceilings and measured per-size headroom. "
                "Author issues carry the lint evidence. Original package bytes remain unchanged.\n")
        run("gh","pr","create","--head",branch,"--title","Update app-release compatibility","--body-file","-",input=body)
    # Token-created pushes do not start push/PR workflows. Dispatch the read-only gate explicitly.
    run("gh","workflow","run","registry.yml","--ref",branch,"-f","publish=false")



if __name__ == "__main__":
    main()
