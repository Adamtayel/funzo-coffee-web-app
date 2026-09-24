/**
 * Funzo — rebuild the website when the menu sheet changes.
 *
 * Paste this whole file into the sheet: Extensions > Apps Script > Code.gs.
 * Setup steps are in README.md, section 4.
 *
 * Why two rebuilds per burst of edits: Google republishes the sheet's CSV a
 * few minutes after an edit, not instantly. The first rebuild (~1 min after
 * the owner stops typing) usually already has the new prices; the second
 * (~6 min) guarantees it. Edits made in quick succession reset the timer, so
 * changing ten prices costs two deploys, not ten.
 */

const DEPLOY_HOOK = 'PASTE_VERCEL_DEPLOY_HOOK_URL_HERE';

const FAST_DELAY_MS = 60 * 1000;
const SAFE_DELAY_MS = 6 * 60 * 1000;

// ---------------------------------------------------------------- ui strings
// Owner-facing labels shown inside the Google Sheet. Content, not code.
const MENU_TITLE = 'الموقع';
const MENU_ITEM = 'حدّث الموقع دلوقتي';
const TOAST_DONE = 'الموقع بيتحدث — هيظهر خلال دقيقة.';
const TOAST_QUEUED = 'اتسجل التعديل — الموقع هيتحدث خلال دقيقة.';

// ---------------------------------------------------------------- triggers

/** Installable "On edit" trigger points here. */
function onMenuEdit() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(10 * 1000)) return;
  try {
    clearPendingDeploys_();
    ScriptApp.newTrigger('deployFromTimer').timeBased().after(FAST_DELAY_MS).create();
    ScriptApp.newTrigger('deployFromTimer').timeBased().after(SAFE_DELAY_MS).create();
  } finally {
    lock.releaseLock();
  }
  SpreadsheetApp.getActive().toast(TOAST_QUEUED);
}

/** Adds the manual "update now" menu when the sheet opens. */
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu(MENU_TITLE)
    .addItem(MENU_ITEM, 'deployNow')
    .addToUi();
}

function deployNow() {
  deploy_();
  SpreadsheetApp.getActive().toast(TOAST_DONE);
}

function deployFromTimer(e) {
  deploy_();
  // One-shot timers stay listed after firing; remove this one.
  ScriptApp.getProjectTriggers()
    .filter(function (t) { return e && t.getUniqueId() === e.triggerUid; })
    .forEach(function (t) { ScriptApp.deleteTrigger(t); });
}

// ---------------------------------------------------------------- helpers

function deploy_() {
  UrlFetchApp.fetch(DEPLOY_HOOK, { method: 'post', muteHttpExceptions: true });
}

function clearPendingDeploys_() {
  ScriptApp.getProjectTriggers()
    .filter(function (t) { return t.getHandlerFunction() === 'deployFromTimer'; })
    .forEach(function (t) { ScriptApp.deleteTrigger(t); });
}
