import requests
import datetime
from proxmoxer import ProxmoxAPI
import smtplib
from email.message import EmailMessage

# --- CONFIGURATION ---
PBS_HOST = "pbs.example.com"     # e.g., "pbs.example.com"
PBS_USER = "example@pbs"
PBS_PASSWORD = "password"
PBS_PORT = 8007  # Default Proxmox Backup Server port
VERIFY_SSL = True  # Set to True if you have a valid certificate
SKIP_STORES   = {"example-datastore"}

# --- CONNECT TO PBS ---
proxmox = ProxmoxAPI(
    host=PBS_HOST,
    port=PBS_PORT,
    user=PBS_USER,
    password=PBS_PASSWORD,
    verify_ssl=VERIFY_SSL,
    service="pbs",  # Use "pbs" for Proxmox Backup Server
)

# ── SMTP SETTINGS ───────────────────────────────────────────────────────────────
SMTP_HOST     = "smtp.example.com"
SMTP_PORT     = 587                # 465 for SSL, 587 for STARTTLS
SMTP_USER     = "bob@example.com"
SMTP_PASSWORD = "password"
FROM_EMAIL    = "bob@example.com"
TO_EMAIL      = "bob@example.com"

# ── COLLECT REPORT LINES ────────────────────────────────────────────────────────
report_lines: list[str] = []
def log(line: str) -> None:
    """Send line to console and store for e-mail later."""
    print(line)
    report_lines.append(line)



# --- DATE THRESHOLD ---
now = datetime.datetime.now(datetime.timezone.utc)
cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=2)

log(f"Checking backups on PBS at {PBS_HOST} (cut-off: {cutoff.strftime('%Y-%m-%d %H:%M UTC')})\n")

# --- FETCH DATASTORES ---
datastores = proxmox.admin.datastore.get()

datastore_list = proxmox.admin.datastore.get()

print(f"Checking backups on PBS at {PBS_HOST}...\n")

for store in datastore_list:
    name = store['store']
    if name in SKIP_STORES:
        continue


    backups = proxmox.admin.datastore(name).snapshots.get()
    last_backup_times = {}

    for backup in backups:
        backup_id = f"{backup['backup-type']}/{backup['backup-id']}"
        if isinstance(backup['backup-time'], str):
            timestamp = datetime.datetime.strptime(backup['backup-time'], "%Y-%m-%dT%H:%M:%SZ")
            timestamp = timestamp.replace(tzinfo=datetime.timezone.utc)
        else:
            timestamp = datetime.datetime.fromtimestamp(backup['backup-time'], tz=datetime.timezone.utc)


        if backup_id not in last_backup_times or timestamp > last_backup_times[backup_id]:
            last_backup_times[backup_id] = timestamp

    warned = False
    for backup_id, last_time in last_backup_times.items():
        if last_time < cutoff:
            if not warned: log(f"Datastore: {name}")
            log(f"  ⚠️  WARNING: {backup_id} last backup was on {last_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
            warned = True

# ── SEND MAIL ───────────────────────────────────────────────────────────────────
subject = f"PBS backup report for {PBS_HOST} – {now.strftime('%Y-%m-%d')}"
body    = "\n".join(report_lines)

msg = EmailMessage()
msg["Subject"] = subject
msg["From"]    = FROM_EMAIL
msg["To"]      = TO_EMAIL
msg.set_content(body)

try:
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
        smtp.starttls()                 # comment out if you use port 465/SSL
        smtp.login(SMTP_USER, SMTP_PASSWORD)
        smtp.send_message(msg)
    log(f"\n📧 Report mailed to {TO_EMAIL}")
except Exception as e:
    log(f"\n❌ Failed to send e-mail: {e}")

