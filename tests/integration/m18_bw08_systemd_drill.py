"""Run only in a disposable Debian systemd VM with an approved fixture payload.

The payload directory contains the two pinned wheels and the reviewed Core writer
module as core_writer.py. The guest must have a real systemd PID 1, cgroup v2,
and a /run/laew-bw08-disposable sentinel with the value bw08-qemu.
"""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile
from grp import getgrnam
from pwd import getpwnam

if __name__ != "__main__" or len(sys.argv) != 2:
    raise SystemExit("Invoke this drill explicitly with the VM payload directory.")
sentinel = Path("/run/laew-bw08-disposable")
if (os.geteuid() != 0 or not sentinel.is_file() or sentinel.read_text().strip() != "bw08-qemu"
        or Path("/proc/1/comm").read_text().strip() != "systemd"
        or not Path("/sys/fs/cgroup/cgroup.controllers").is_file()):
    raise SystemExit("This drill requires a fresh disposable Debian systemd VM.")
base = Path("/fixture")
bits = Path(sys.argv[1])
if base.exists():
    raise SystemExit("The fixture root already exists.")
base.mkdir(mode=0o755)

def sh(*args,check=True,**kw):
    return subprocess.run(list(map(str,args)),check=check,text=True,capture_output=True,**kw)
def put(path,obj,mode=0o600):
    path.write_text(json.dumps(obj),encoding="utf-8")
    path.chmod(mode)
def owner(path,user,mode):
    account=getpwnam(user)
    os.chown(path,account.pw_uid,account.pw_gid)
    path.chmod(mode)
def hd(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

sh("groupadd","bw08gate")
for name in ("bw08writer","bw08worker","bw08external"):
    sh("useradd","-M","-U",name)
for name in ("bw08writer","bw08worker"):
    sh("usermod","-aG","bw08gate",name)
sh(sys.executable,"-m","venv","--copies","--without-pip",base/"venv")
py=base/"venv/bin/python"
site=Path(sh(py,"-I","-B","-c","import sysconfig; print(sysconfig.get_path('purelib'))").stdout.strip())
for glob in ("laew_backup_worker-0.2.0-*.whl","pyyaml-6.0.3-*.whl"):
    (wheel,)=bits.glob(glob)
    if glob.startswith("laew"):
        assert hd(wheel)=="b44a1445b6a7dca11dbe088352b3e65d13775030433fd22d828d26ca82fd958e"
    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(site)
sys.path.insert(0,str(site))
import yaml
from laew.backup.controller import run_controller
from laew.backup.capture import package_python_sha256
from laew.backup.archive import verify_archive
from laew.backup.managed import read_gate

state=base/"state"; state.mkdir()
owner(state,"bw08worker",0o700)
private={}
for n in ("ops","media","review"):
    p=state/n; p.mkdir(); owner(p,"bw08worker",0o700); private[n]=p
source=base/"sources"; source.mkdir()
install=source/"app"
(install/"runtime/sessions").mkdir(parents=True)
(install/"manifests").mkdir()
vault=source/"vault"; vault.mkdir(); owner(vault,"bw08writer",0o755)
root_core=base/"reviewed-core"; root_core.mkdir()
shutil.copyfile(bits/"core_writer.py", root_core/"writer.py")
(root_core/"__init__.py").write_text("# synthetic source release\n")
manifest=install/"manifests/system.yaml"
manifest.write_text(yaml.safe_dump({
    "version":"1","system_name":"fixture","stage":"test",
    "workspace":{"root":".","allowed_paths":[],"restricted_paths":[],"ignored_patterns":[]},
    "models":{"roles":{n:{} for n in ("primary","embedding","reviewer")}},
    "tools":{"categories":{"filesystem":{"policy":"read_only_by_default"},"git":{"policy":"inspection_first"},
             "terminal":{"policy":"safe_command_allowlist","allowlist":[]},"web":{"policy":"read_only"}}},
    "memory":{"session":{"storage":"runtime/sessions"},"second_brain":{}},"rag":{"pipeline":{}}
}))
gate_dir=base/"gate"; gate_dir.mkdir()
gate_group=getgrnam("bw08gate").gr_gid
os.chown(gate_dir,0,gate_group);gate_dir.chmod(0o2750)
gate=gate_dir/"gate.json"
(gate_dir/"installation.lock").touch(mode=0o600)
fence_dir=base/"fence-dir"; fence_dir.mkdir()
fence=fence_dir/"installation.lock"; fence.touch()
os.chown(fence,0,gate_group);fence.chmod(0o660)
profile=private["ops"]/"profile.json"
put(profile,dict(schema_version=1,profile_id="fixture",host_id="native-guest",manifest_path=str(manifest),
   launch_cwd=str(install),workspace_root=str(source),vault=str(vault),destination=str(private["media"]),fence=str(fence),
   config_files={},memory_enabled=False,knowledge_enabled=False,memory_storage=None,knowledge_storage=None))
owner(profile,"bw08worker",0o600)
release=private["review"]/"release.json"
put(release,dict(schema_version=1,profile_id="fixture",host_id="native-guest",core_release="synthetic",
    core_package_root=str(root_core),core_package_python_sha256=package_python_sha256(root_core),
    worker_package_python_sha256=package_python_sha256(site/"laew"),profile_sha256=hd(profile),manifest_sha256=hd(manifest)))
owner(release,"bw08worker",0o600)
def cli(*args):
    out=sh("runuser","-u","bw08worker","--",py,"-I","-B","-m","laew.backup_worker",*args,"--profile",profile)
    return json.loads(out.stdout)
assert cli("control","initialize","--managed","--apply")["state"]=="disabled"
view=cli("control","view")
proposal=private["ops"]/"proposal.json"
put(proposal,dict(schema_version=1,operation="settings",revision=view["revision"],enabled=True,directory=str(private["media"]),
                  host="",port=None,user="",remote_directory="",key=""))
owner(proposal,"bw08worker",0o600)
assert cli("control","apply","--proposal",proposal,"--apply")["state"]=="enabled"

writer=base/"writer.py"
writer.write_text("""import signal,sys,subprocess,time
from pathlib import Path
import importlib.util
spec = importlib.util.spec_from_file_location('laew.backup.writer', '/fixture/reviewed-core/writer.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.enroll_writer_process()
child=subprocess.Popen(['/usr/bin/sleep','600'])
def leave(*args):
    child.terminate()
    child.wait(timeout=4)
    sys.exit(0)
signal.signal(signal.SIGTERM,leave)
Path('/fixture/sources/vault/writer.txt').write_text('fixture writer ready')
while True: time.sleep(1)
""")
runner=base/"worker.py"
runner.write_text("""import os,signal,sys,time
from pathlib import Path
if Path('/fixture/fail-worker').exists(): os.kill(os.getpid(),signal.SIGKILL)
if Path('/fixture/pause-worker').exists(): time.sleep(8)
from laew.backup_worker import main
sys.exit(main(sys.argv[1:]))
""")
wunit="bw08-writer.service"
bunit="bw08-worker.service"
units=Path("/etc/systemd/system")
for name in (wunit,bunit): assert not (units/name).exists()
common="NoNewPrivileges=yes\nDelegate=no\nRestart=no\nKillMode=mixed\nTimeoutStopSec=10s\n"
(units/wunit).write_text("[Service]\nType=exec\nUser=bw08writer\n"+common+f"Environment=LAEW_INSTALLATION_FENCE={fence} LAEW_MANAGED_WRITER_GATE={gate} LAEW_MANAGED_WRITER_UNIT={wunit}\nExecStart={py} -I -B {writer}\n")
(units/bunit).write_text("[Service]\nType=oneshot\nRemainAfterExit=no\nUser=bw08worker\n"+common+f"ExecStart={py} -I -B {runner} managed-create --profile {profile} --gate {gate} --provenance {release} --apply\n")
sh("systemctl","daemon-reload")
config=gate_dir/"config.json"
put(config,dict(schema_version=1,profile=str(profile),writer_services=[wunit],worker_service=bunit,
                unit_sha256={unit:hashlib.sha256(sh("systemctl","cat","--",unit).stdout.encode()).hexdigest() for unit in (wunit,bunit)}))
def current():
    return read_gate(gate)[0]["phase"]
def active():
    return sh("systemctl","is-active",wunit,check=False).stdout.strip()
def wait(predicate):
    deadline=time.monotonic()+30
    while not predicate():
        assert time.monotonic()<deadline
        time.sleep(.1)
def receipts():
    return {p.name for p in private["media"].glob("*.receipt.json")}

run_controller(config,"initialize")
sh("systemctl","start",wunit)
wait(lambda:(vault/"writer.txt").exists())
assert sh("runuser","-u","bw08external","--","test","-w",vault,check=False).returncode!=0
ident=run_controller(config,"capture")
assert active()=="active" and current()=="open"
assert verify_archive(private["media"],ident)["host_id"]=="native-guest"
print("native systemd controller capture and resume=passed",flush=True)
previous=receipts()
fault=base/"fail-worker";fault.touch()
try:
    run_controller(config,"capture")
except subprocess.CalledProcessError: pass
else: raise AssertionError("killed worker returned success")
assert receipts()==previous and active()=="inactive" and current()=="held"
sh("systemctl","reset-failed",bunit)
fault.unlink()
run_controller(config,"recover")
assert active()=="active" and current()=="open"
print("native worker SIGKILL leaves gate latched and no receipt; explicit recovery resumes=passed",flush=True)

pause=base/"pause-worker";pause.touch()
controller=subprocess.Popen([str(py),"-I","-B","-m","laew.backup.controller","capture","--config",str(config)])
wait(lambda:current()=="held")
wait(lambda:sh("systemctl","show",bunit,"-p","ActiveState","--value").stdout.strip()=="activating")
controller.kill();controller.wait()
assert current()=="held"
try:
    run_controller(config,"recover")
except ValueError: pass
else: raise AssertionError("resumed while orphan worker alive")
assert active()=="inactive" and current()=="held"
wait(lambda:sh("systemctl","show",bunit,"-p","ActiveState","--value").stdout.strip()=="inactive")
assert len(receipts())==len(previous)+1
run_controller(config,"recover")
assert active()=="active" and current()=="open"
pause.unlink()
sh("systemctl","stop",wunit)
print("native controller SIGKILL retains gate until worker terminal=passed",flush=True)
