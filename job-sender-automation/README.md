# Job Sender Automation

A free, open-source toolkit to automate job applications by email.
Pure Python standard library - no paid APIs, nothing to install.

- `send_job_mail.py` - sends your application (subject + body + CV) to every address in `receiveremailid.txt`.
- `find_mail.py` - finds company contact emails for a city (Chennai, Dubai, Singapore...) using OpenStreetMap and each company's public website, and adds them to `receiveremailid.txt`.
- `find_company_emails.py` - optional: finds public emails from a list of company websites you already have.

## Project layout

```
job-sender-automation/
├── send_job_mail.py
├── find_mail.py
├── find_company_emails.py
├── mailsubject.txt          <- your subject (copy from mailsubject.txt.example)
├── mailbody.txt             <- your mail body (copy from mailbody.txt.example)
├── receiveremailid.txt      <- receivers, one per line (filled by find_mail.py)
├── cv/
│   └── maincv.pdf           <- your CV
├── .env                     <- your email login (copy from .env.example)
└── sent_log.txt             <- auto-created, remembers who already got a mail
```

Your personal files (`.env`, `mailbody.txt`, `mailsubject.txt`, `receiveremailid.txt`, `sent_log.txt`, CV) are listed in `.gitignore`, so they are never uploaded to GitHub.

## Setup

Requires Python 3.9+.

1. Copy the example files and edit them:
   ```
   cp .env.example .env
   cp mailsubject.txt.example mailsubject.txt
   cp mailbody.txt.example mailbody.txt
   ```
   (On Windows, copy the files in File Explorer and rename them.)
2. Put your CV at `cv/maincv.pdf`.
3. Gmail: turn on 2-Step Verification, then create an **App Password** at https://myaccount.google.com/apppasswords and put it in `.env`:
   ```
   SENDER_EMAIL=youraddress@gmail.com
   APP_PASSWORD=abcdefghijklmnop
   ```
   Other providers: set `SMTP_HOST` and `SMTP_PORT` in `.env` (Outlook: `smtp.office365.com` / `587`, Yahoo: `smtp.mail.yahoo.com` / `465`).

## Usage

### 1. Find companies by location

```
python find_mail.py
```

It asks for a location (e.g. `Dubai`), how many emails you want, and an optional keyword. Leave the keyword blank for the best results. Found addresses are appended to `receiveremailid.txt` and details saved to `companies_found.csv`. Run it again for another city and the list grows. Addresses already in the list or in `sent_log.txt` are skipped.

Open `receiveremailid.txt` and delete any address you don't want before sending.

### 2. Send the applications

```
python send_job_mail.py --dry-run   # preview only, nothing is sent
python send_job_mail.py             # send
python send_job_mail.py --resend    # ignore sent_log.txt and send again
```

Each mail goes out separately with a 5 second gap, with `cv/maincv.pdf` attached.

### Optional: you already have company websites

Put one website per line in `companies.txt`, then run `python find_company_emails.py`. Results go to `found_emails.csv`.

## Tips to keep your mail out of spam

- Send from your own real Gmail account via an App Password (this is what the script does).
- Use a specific subject, e.g. `Application for Python Developer - Your Name`.
- Keep the body short, plain text, no links, no hype words, no ALL CAPS.
- Name the CV clearly and keep it under 1 MB.
- Personalize the company and role in each mail.
- Send about 10-15 mails per day, not 50 at once, to protect your account.
- Send a test mail to a second address of yours first.

## How company search works

`find_mail.py` uses the free OpenStreetMap services (Nominatim for the city, Overpass for company offices), splits large cities into small areas so queries stay light, and then reads each company's own public pages (home, careers, contact, about) for a published email. It respects `robots.txt`, waits between requests, and prefers `careers@`, `jobs@`, `hr@` style addresses.

Limits: OpenStreetMap is a volunteer map, so coverage varies by city, and many companies publish no email at all. You may get fewer results than requested.

## Responsible use

- Only email addresses that are published for business or recruitment contact.
- Send relevant job applications, not bulk marketing. Some countries have rules on unsolicited email (GDPR, CAN-SPAM, etc.).
- Don't spam the same company; one follow-up after a week or so is enough.
- Never commit your `.env` or App Password.

## License

MIT - see `LICENSE`.
