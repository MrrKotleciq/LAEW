from configparser import ConfigParser
from pathlib import Path
import xml.etree.ElementTree as ET


EXAMPLES = Path(__file__).resolve().parents[2] / "docs/examples/m18"


def test_windows_worker_template_verifies_only_and_is_disabled():
    root = ET.parse(EXAMPLES / "laew-backup-worker-verify-task.xml.example").getroot()
    ns = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
    get = lambda name: root.findtext(name, namespaces=ns)
    assert get("t:Settings/t:Enabled") == "false"
    assert get("t:Triggers/t:CalendarTrigger/t:Enabled") == "false"
    assert get("t:Settings/t:StartWhenAvailable") == "false"
    assert get("t:Settings/t:WakeToRun") == "false"
    assert get("t:Settings/t:MultipleInstancesPolicy") == "IgnoreNew"
    assert get("t:Principals/t:Principal/t:RunLevel") == "LeastPrivilege"
    action = get("t:Actions/t:Exec/t:Arguments")
    assert "-I -m laew.backup_worker backup verify --id" in action
    assert all(word not in action for word in ("--apply", "create", "prune"))


def test_debian_worker_template_verifies_only_with_no_install_target():
    service, timer = ConfigParser(), ConfigParser()
    service.read(EXAMPLES / "laew-backup-worker-verify.service.example")
    timer.read(EXAMPLES / "laew-backup-worker-verify.timer.example")
    settings = service["Service"]
    assert settings["User"] == "APPROVED_BACKUP_USER"
    assert settings["Type"] == "oneshot" and settings["Restart"] == "no"
    assert settings.getboolean("NoNewPrivileges") and settings.getboolean("PrivateNetwork")
    action = settings["ExecStart"]
    assert "-I -m laew.backup_worker backup verify --id" in action
    assert all(word not in action for word in ("--apply", "create", "prune"))
    assert timer["Timer"]["Persistent"] == timer["Timer"]["WakeSystem"] == "false"
    assert "Install" not in timer
