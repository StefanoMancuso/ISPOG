/**
 * ISPOG - bug report endpoint (plan, F6b)
 *
 * Google Apps Script web app that receives a report from the desktop app and e-mails it,
 * with its zip attachment, to the maintainer.
 *
 * Deploy: Deploy > New deployment > Web app; Execute as: Me; Who has access: Anyone.
 * Update: Deploy > Manage deployments > Edit > Version: New version (the URL stays the same).
 *
 * Request: POST, body = JSON
 *   { token, version, summary, email, comment, error, filename, zip }   (zip = base64)
 * Reply: always HTTP 200 (Apps Script cannot set a status); body = JSON
 *   { "status": "ok" }  or  { "status": "error", "reason": "..." }
 */

const TOKEN = 'ispog-c9261c2fe7321e7c';   // spam filter, not a secret: it ships in the app
const RECIPIENT = 'stefanomancuso88@gmail.com';
const SUBJECT_TAG = '[ISPOG report]';      // used by the Gmail filter
const MAX_ZIP_BYTES = 15 * 1024 * 1024;    // MailApp: 25 MB per message, attachments included
const MAX_REPORTS_PER_DAY = 30;            // MailApp (free account): about 100 e-mails per day
const MAX_FIELD_CHARS = 5000;

function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    if (data.token !== TOKEN) {
      return reply_('error', 'forbidden');
    }
    if (!takeDailySlot_()) {
      return reply_('error', 'daily limit reached');
    }
    const bytes = Utilities.base64Decode(data.zip || '');
    if (bytes.length === 0 || bytes.length > MAX_ZIP_BYTES) {
      return reply_('error', 'attachment missing or too large');
    }
    const zip = Utilities.newBlob(bytes, 'application/zip', safeFileName_(data.filename));

    const message = {
      to: RECIPIENT,
      subject: SUBJECT_TAG + ' ' + field_(data.version, 30) + ' - ' + field_(data.summary, 120),
      body: [
        'From: ' + (field_(data.email, 200) || 'anonymous'),
        'Version: ' + field_(data.version, 30),
        '',
        'What were you doing?',
        field_(data.comment, MAX_FIELD_CHARS) || '-',
        '',
        'Error:',
        field_(data.error, MAX_FIELD_CHARS) || '-',
      ].join('\n'),
      attachments: [zip],
    };
    if (isEmail_(data.email)) {
      message.replyTo = data.email;     // answer the tester directly from Gmail
    }
    MailApp.sendEmail(message);
    return reply_('ok');
  } catch (err) {
    return reply_('error', String(err).slice(0, 200));
  }
}

/** Health check: opening the URL in a browser shows this text. */
function doGet() {
  return ContentService.createTextOutput('ISPOG report endpoint');
}

/** Run once from the editor to authorize MailApp and check that e-mail arrives. */
function sendTestEmail() {
  MailApp.sendEmail(RECIPIENT, SUBJECT_TAG + ' test', 'The ISPOG report endpoint can send e-mail.');
}

function reply_(status, reason) {
  const body = reason ? { status: status, reason: reason } : { status: status };
  return ContentService.createTextOutput(JSON.stringify(body))
    .setMimeType(ContentService.MimeType.JSON);
}

/** Counts today's reports; false once the daily limit is reached. */
function takeDailySlot_() {
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const props = PropertiesService.getScriptProperties();
    const key = 'reports-' + Utilities.formatDate(new Date(), 'Etc/UTC', 'yyyy-MM-dd');
    const count = Number(props.getProperty(key) || 0);
    if (count >= MAX_REPORTS_PER_DAY) {
      return false;
    }
    props.setProperty(key, String(count + 1));
    return true;
  } finally {
    lock.releaseLock();
  }
}

function field_(value, maxChars) {
  return String(value || '').slice(0, maxChars);
}

function safeFileName_(name) {
  const clean = String(name || '').replace(/[^\w.\-]+/g, '_').slice(0, 80);
  return /\.zip$/i.test(clean) ? clean : 'ispog_report.zip';
}

function isEmail_(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(value || ''));
}
