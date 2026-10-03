#!/usr/bin/env python3
"""
Job Sender - sends your job application email with CV attached.
100% free: uses only Python's standard library + your own email account's SMTP.

Folder layout (put this script inside "job sender/"):

    job sender/
        send_job_mail.py
        mailbody.txt
        mailsubject.txt
        receiveremailid.txt      <- one email per line (or comma separated)
        cv/
            maincv.pdf

Setup (once):
    1. Gmail -> turn on 2-Step Verification.
    2. Create an App Password: https://myaccount.google.com/apppasswords
    3. Set two environment variables (or create a file named .env next to this script):

         SENDER_EMAIL=youraddress@gmail.com
         APP_PASSWORD=abcdefghijklmnop

Run:
    python send_job_mail.py            -> sends the mail(s)
    python send_job_mail.py --dry-run  -> shows what would be sent, sends nothing

Other providers: set SMTP_HOST / SMTP_PORT (defaults: smtp.gmail.com / 465).
  Outlook: smtp.office365.com / 587     Yahoo: smtp.mail.yahoo.com / 465
"""

import mimetypes
import os
import re
import smtplib
import ssl
import sys
import time
from email.message import EmailMessage
from pathlib import Path

BASE = Path(__file__).resolve().parent
BODY_FILE = BASE / "mailbody.txt"
SUBJECT_FILE = BASE / "mailsubject.txt"
RECEIVER_FILE = BASE / "receiveremailid.txt"
CV_FILE = BASE / "cv" / "maincv.pdf"
SENT_LOG = BASE / "sent_log.txt"  # remembers who already got a mail

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def load_env_file():
    """Read KEY=VALUE lines from .env (if present) without overriding real env vars."""
    env_path = BASE / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def read_text(path: Path) -> str:
    if not path.exists():
        sys.exit(f"ERROR: missing file: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        sys.exit(f"ERROR: file is empty: {path}")
    return text


def read_receivers() -> list[str]:
    raw = read_text(RECEIVER_FILE)
    parts = [p.strip() for p in re.split(r"[,\n;]+", raw) if p.strip()]
    good, seen = [], set()
    for p in parts:
        if not EMAIL_RE.match(p):
            print(f"  skipping invalid email: {p}")
            continue
        if p.lower() not in seen:
            seen.add(p.lower())
            good.append(p)
    if not good:
        sys.exit("ERROR: no valid receiver email found.")
    return good


def already_sent() -> set[str]:
    if not SENT_LOG.exists():
        return set()
    return {l.strip().lower() for l in SENT_LOG.read_text(encoding="utf-8").splitlines() if l.strip()}


def build_message(sender, receiver, subject, body) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = receiver
    msg["Subject"] = " ".join(subject.splitlines())  # subject must be one line
    msg.set_content(body)

    if not CV_FILE.exists():
        sys.exit(f"ERROR: CV not found: {CV_FILE}")
    ctype, _ = mimetypes.guess_type(CV_FILE.name)
    maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
    msg.add_attachment(
        CV_FILE.read_bytes(),
        maintype=maintype,
        subtype=subtype,
        filename=CV_FILE.name,
    )
    return msg


def main():
    dry_run = "--dry-run" in sys.argv
    resend = "--resend" in sys.argv  # ignore sent_log

    load_env_file()
    subject = read_text(SUBJECT_FILE)
    body = read_text(BODY_FILE)
    receivers = read_receivers()

    if not resend:
        done = already_sent()
        skipped = [r for r in receivers if r.lower() in done]
        receivers = [r for r in receivers if r.lower() not in done]
        for r in skipped:
            print(f"  already sent earlier, skipping: {r}  (use --resend to force)")
        if not receivers:
            print("Nothing new to send.")
            return

    sender = os.environ.get("SENDER_EMAIL")
    password = os.environ.get("APP_PASSWORD")
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "465"))

    print(f"Subject : {subject}")
    print(f"To      : {', '.join(receivers)}")
    print(f"CV      : {CV_FILE.name} ({CV_FILE.stat().st_size // 1024} KB)" if CV_FILE.exists() else "CV      : NOT FOUND")

    if dry_run:
        print("\n--- body ---\n" + body + "\n--- dry run, nothing sent ---")
        return

    if not sender or not password:
        sys.exit("ERROR: set SENDER_EMAIL and APP_PASSWORD (env vars or .env file).")

    context = ssl.create_default_context()
    try:
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, context=context, timeout=30)
        else:
            server = smtplib.SMTP(host, port, timeout=30)
            server.starttls(context=context)
        with server:
            server.login(sender, password.replace(" ", ""))
            for i, receiver in enumerate(receivers):
                try:
                    server.send_message(build_message(sender, receiver, subject, body))
                    print(f"  sent -> {receiver}")
                    with SENT_LOG.open("a", encoding="utf-8") as f:
                        f.write(receiver + "\n")
                except Exception as e:
                    print(f"  FAILED -> {receiver}: {e}")
                if i < len(receivers) - 1:
                    time.sleep(5)  # small gap between mails, looks less spammy
    except smtplib.SMTPAuthenticationError:
        sys.exit("ERROR: login failed. Use an App Password, not your normal password.")
    except Exception as e:
        sys.exit(f"ERROR: could not send: {e}")

    print("Done.")


if __name__ == "__main__":
    main()
