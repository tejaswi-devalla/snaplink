const form = document.querySelector('#shorten-form');
const message = document.querySelector('#message');
const submitButton = document.querySelector('#submit-button');
const resultPanel = document.querySelector('#result-panel');
const shortUrlAnchor = document.querySelector('#short-url');
const destinationText = document.querySelector('#destination-url');
const managementTokenCode = document.querySelector('#management-token');
const statsButton = document.querySelector('#stats-button');
const disableButton = document.querySelector('#disable-button');
const shareButton = document.querySelector('#share-button');
const backupButton = document.querySelector('#download-backup-button');
const statsOutput = document.querySelector('#stats-output');
const historyList = document.querySelector('#history-list');
const historyEmpty = document.querySelector('#history-empty');
const importForm = document.querySelector('#import-form');
const toggleImportButton = document.querySelector('#toggle-import-button');
const cancelImportButton = document.querySelector('#cancel-import-button');
const importSubmitButton = document.querySelector('#import-submit-button');
const importBackupFile = document.querySelector('#import-backup-file');

if (importBackupFile) {
  importBackupFile.accept = '.txt,.json,text/plain,application/json';
}

const toast = document.querySelector('#toast');
const HISTORY_KEY = 'snaplink.savedLinks.v1';
const MAX_SAVED_LINKS = 250;

let currentLink = null;
let toastTimer = null;
let savedLinks = readSavedLinks();

document.querySelector('#year').textContent = new Date().getFullYear();

renderHistory();


// ============================================
// LINK STATUS
// ============================================

function getLinkStatus(link) {
  if (!link) return 'active';

  if (link.status === 'expired') {
    return 'expired';
  }

  if (
    link.is_active === false ||
    link.status === 'disabled'
  ) {
    return 'disabled';
  }

  const expiry = link.expires_at
    ? Date.parse(link.expires_at)
    : NaN;

  if (Number.isFinite(expiry) && expiry <= Date.now()) {
    return 'expired';
  }

  return 'active';
}


function statusText(status) {
  if (status === 'expired') return 'Expired';

  if (status === 'disabled') return 'Disabled';

  return 'Active';
}


// ============================================
// SAVE AND LOAD LINK HISTORY
// ============================================

function readSavedLinks() {
  try {
    const parsed = JSON.parse(
      localStorage.getItem(HISTORY_KEY) || '[]'
    );

    if (!Array.isArray(parsed)) {
      return [];
    }

    return parsed.filter((item) =>
      item &&
      typeof item.code === 'string' &&
      typeof item.management_token === 'string' &&
      item.management_token.length > 0 &&
      typeof item.short_url === 'string' &&
      typeof item.original_url === 'string'
    ).slice(0, MAX_SAVED_LINKS);

  } catch {
    return [];
  }
}


function persistSavedLinks() {
  try {
    localStorage.setItem(
      HISTORY_KEY,
      JSON.stringify(savedLinks.slice(0, MAX_SAVED_LINKS))
    );

    return true;

  } catch {
    showToast(
      'Browser storage is unavailable. Download a link backup to keep your management token.',
      'error'
    );

    return false;
  }
}


function rememberLink(link) {
  const record = {
    code: link.code,
    short_url: link.short_url,
    original_url: link.original_url,
    management_token: link.management_token,

    created_at:
      link.created_at || new Date().toISOString(),

    expires_at: link.expires_at || null,
    last_clicked_at: link.last_clicked_at || null,

    click_count: Number.isInteger(link.click_count)
      ? link.click_count
      : 0,

    is_active: link.is_active !== false,
    status: link.status || getLinkStatus(link),

    last_stats_checked_at:
      link.last_stats_checked_at || null,

    saved_at: new Date().toISOString()
  };

  savedLinks = [
    record,
    ...savedLinks.filter(
      (item) => item.code !== record.code
    )
  ].slice(0, MAX_SAVED_LINKS);

  persistSavedLinks();
  renderHistory();

  return record;
}


function updateSavedLink(code, patch) {
  savedLinks = savedLinks.map((item) =>
    item.code === code
      ? { ...item, ...patch }
      : item
  );

  persistSavedLinks();
  renderHistory();
}


function forgetSavedLink(code) {
  savedLinks = savedLinks.filter(
    (item) => item.code !== code
  );

  persistSavedLinks();
  renderHistory();

  showToast(
    `/${code} removed from this browser. The server link was not disabled.`,
    'success'
  );
}


// ============================================
// MESSAGES AND TOAST NOTIFICATIONS
// ============================================

function showMessage(text, kind = 'error') {
  message.textContent = text;

  message.classList.toggle(
    'success',
    kind === 'success'
  );

  message.hidden = false;
}


function hideMessage() {
  message.hidden = true;
  message.textContent = '';
}


function showToast(text, kind = 'success') {
  if (!toast) return;

  window.clearTimeout(toastTimer);

  toast.textContent = text;

  toast.className =
    `toast ${
      kind === 'error'
        ? 'toast-error'
        : 'toast-success'
    }`;

  toast.hidden = false;

  toastTimer = window.setTimeout(() => {
    toast.hidden = true;
  }, 4200);
}


// ============================================
// API REQUEST HELPER
// ============================================

async function apiRequest(url, options = {}) {
  const response = await fetch(url, {
    ...options,

    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {})
    }
  });

  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    let detail = 'Request failed. Please try again.';

    if (typeof payload.detail === 'string') {
      detail = payload.detail;

    } else if (
      Array.isArray(payload.detail) &&
      payload.detail.length
    ) {
      detail = payload.detail
        .map((item) => item.msg || 'Invalid request')
        .join('; ');
    }

    throw new Error(detail);
  }

  return payload;
}


// ============================================
// DISPLAY THE CREATED OR IMPORTED LINK
// ============================================

function fillResultPanel(link) {
  currentLink = link;

  shortUrlAnchor.href = link.short_url;
  shortUrlAnchor.textContent = link.short_url;

  destinationText.textContent = link.original_url;

  managementTokenCode.textContent =
    link.management_token;

  const status = getLinkStatus(link);

  disableButton.disabled = status !== 'active';

  disableButton.textContent =
    status === 'expired'
      ? 'Link expired'
      : status === 'disabled'
        ? 'Link disabled'
        : 'Disable link';

  resultPanel.hidden = false;
  statsOutput.hidden = true;
}


// ============================================
// CREATE A SHORT LINK
// ============================================

form.addEventListener('submit', async (event) => {
  event.preventDefault();

  hideMessage();
  statsOutput.hidden = true;

  submitButton.disabled = true;

  submitButton.querySelector(
    'span:first-child'
  ).textContent = 'Creating your link…';

  const url = document.querySelector('#url').value.trim();

  const alias = document.querySelector('#alias').value.trim();

  const expiry = document.querySelector('#expiry').value;

  const payload = { url };

  if (alias) {
    payload.custom_alias = alias;
  }

  if (expiry) {
    payload.expires_at = new Date(expiry).toISOString();
  }

  try {
    const data = await apiRequest('/api/v1/links', {
      method: 'POST',
      body: JSON.stringify(payload)
    });

    const link = rememberLink(data);

    fillResultPanel(link);

    showMessage(
      'Your short link was created and saved in this browser.',
      'success'
    );

    showToast(
      'Short link created. Download a backup to keep its private token safe.',
      'success'
    );

    resultPanel.scrollIntoView({
      behavior: 'smooth',
      block: 'start'
    });

    form.reset();

  } catch (error) {
    showMessage(
      error.message ||
      'Could not create your link. Please try again.'
    );

  } finally {
    submitButton.disabled = false;

    submitButton.querySelector(
      'span:first-child'
    ).textContent = 'Generate short link';
  }
});


// ============================================
// COPY SHORT URL OR MANAGEMENT TOKEN
// ============================================

async function copyText(value, button, doneLabel) {
  try {
    await navigator.clipboard.writeText(value);

    const oldLabel = button.textContent;

    button.textContent = doneLabel;

    setTimeout(() => {
      button.textContent = oldLabel;
    }, 1500);

  } catch {
    showMessage(
      'Clipboard access is unavailable. Select and copy the text manually.'
    );
  }
}


document.querySelector('#copy-button').addEventListener(
  'click',
  () => {
    if (currentLink) {
      copyText(
        currentLink.short_url,
        document.querySelector('#copy-button'),
        'Copied!'
      );
    }
  }
);


document.querySelector('#copy-token-button').addEventListener(
  'click',
  () => {
    if (currentLink) {
      copyText(
        currentLink.management_token,
        document.querySelector('#copy-token-button'),
        'Copied!'
      );
    }
  }
);


// ============================================
// SHARE A SHORT LINK
// ============================================

async function shareLink(link) {
  if (!link) return;

  try {
    if (navigator.share) {
      await navigator.share({
        title: 'SnapLink',
        text: 'Here is a link to check out:',
        url: link.short_url
      });

      showToast(
        'Share action completed.',
        'success'
      );

    } else {
      await navigator.clipboard.writeText(
        link.short_url
      );

      showToast(
        'Sharing is not supported here, so the link was copied instead.',
        'success'
      );
    }

  } catch (error) {
    if (error && error.name === 'AbortError') {
      return;
    }

    try {
      await navigator.clipboard.writeText(
        link.short_url
      );

      showToast(
        'Link copied so you can share it.',
        'success'
      );

    } catch {
      showToast(
        'Could not open sharing or copy the link. Copy the short URL manually.',
        'error'
      );
    }
  }
}


shareButton.addEventListener('click', () => {
  shareLink(currentLink);
});


// ============================================
// DOWNLOAD A TXT BACKUP
// The same TXT file can be imported later.
// ============================================

function downloadBackup(link, button = null) {
  if (!link || !link.management_token) {
    showToast(
      'This link has no saved management token. Import it using your original token first.',
      'error'
    );

    return;
  }

  // Data required to restore the link.
  const backup = {
    format: 'SnapLink link backup',
    version: 1,

    exported_at: new Date().toISOString(),

    code: link.code,
    short_url: link.short_url,
    original_url: link.original_url,

    created_at: link.created_at || null,
    expires_at: link.expires_at || null,

    management_token: link.management_token,

    security_note:
      'Keep this file private. The management token grants access to private analytics and link controls.'
  };

  // Human-readable details.
  // The JSON section is retained so SnapLink can import
  // this exact TXT file without manual copying.

  const backupText = [
    '====================================',
    '         SNAPLINK LINK BACKUP',
    '====================================',
    '',

    `Short Code: ${backup.code}`,
    `Short URL: ${backup.short_url}`,
    `Original URL: ${backup.original_url}`,

    `Created At: ${backup.created_at || 'Unknown'}`,
    `Expires At: ${backup.expires_at || 'Never'}`,

    `Management Token: ${backup.management_token}`,

    '',

    '====================================',
    'IMPORTANT SECURITY INFORMATION',
    '====================================',

    'Keep this file private and secure.',
    'Your management token may provide access to link management functions.',
    'Do not share this file with other people.',

    '',

    '====================================',
    'IMPORT DATA - DO NOT DELETE',
    '====================================',

    '--- IMPORT DATA (keep intact) ---',

    JSON.stringify(backup, null, 2),

    ''
  ].join('\n');

  // Create the downloadable TXT file.

  const blob = new Blob(
    [backupText],
    {
      type: 'text/plain;charset=utf-8'
    }
  );

  const objectUrl = URL.createObjectURL(blob);

  const anchor = document.createElement('a');

  anchor.href = objectUrl;

  const safeCode = String(link.code).replace(
    /[^A-Za-z0-9_-]/g,
    '_'
  );

  anchor.download =
    `snaplink-${safeCode}-backup.txt`;

  document.body.appendChild(anchor);

  anchor.click();

  anchor.remove();

  window.setTimeout(() => {
    URL.revokeObjectURL(objectUrl);
  }, 1000);

  showToast(
    `Backup downloaded for /${link.code}. Keep the file private.`,
    'success'
  );

  if (button) {
    const oldLabel = button.textContent;

    button.textContent = 'Downloaded';

    setTimeout(() => {
      button.textContent = oldLabel;
    }, 1500);
  }
}


backupButton.addEventListener('click', () => {
  downloadBackup(currentLink, backupButton);
});


// ============================================
// FETCH ANALYTICS
// ============================================

async function fetchStats(link) {
  const stats = await apiRequest(
    `/api/v1/links/${encodeURIComponent(link.code)}/stats`,
    {
      headers: {
        'X-Management-Token': link.management_token
      }
    }
  );

  const updated = {
    ...link,

    click_count: stats.click_count,
    created_at: stats.created_at,
    expires_at: stats.expires_at,
    last_clicked_at: stats.last_clicked_at,

    is_active: stats.is_active,

    status:
      stats.status ||
      getLinkStatus({
        ...link,
        ...stats
      }),

    last_stats_checked_at: new Date().toISOString()
  };

  savedLinks = savedLinks.some(
    (item) => item.code === updated.code
  )
    ? savedLinks.map(
        (item) =>
          item.code === updated.code
            ? updated
            : item
      )
    : [updated, ...savedLinks].slice(0, MAX_SAVED_LINKS);

  persistSavedLinks();

  if (
    currentLink &&
    currentLink.code === updated.code
  ) {
    currentLink = updated;

    const status = getLinkStatus(updated);

    disableButton.disabled = status !== 'active';

    disableButton.textContent =
      status === 'expired'
        ? 'Link expired'
        : status === 'disabled'
          ? 'Link disabled'
          : 'Disable link';
  }

  return {
    ...stats,
    status: stats.status || updated.status
  };
}


// ============================================
// DISPLAY ANALYTICS
// ============================================

function addStatRows(container, stats) {
  const created = stats.created_at
    ? new Date(stats.created_at).toLocaleString()
    : 'Unknown';

  const lastClicked = stats.last_clicked_at
    ? new Date(stats.last_clicked_at).toLocaleString()
    : 'Not visited yet';

  const status =
    stats.status || getLinkStatus(stats);

  const rows = [
    ['Total clicks', String(stats.click_count)],

    ['Created', created],

    ['Last click', lastClicked],

    ['Status', statusText(status)],

    [
      'Expires',
      stats.expires_at
        ? new Date(stats.expires_at).toLocaleString()
        : 'Never'
    ]
  ];

  container.replaceChildren();

  for (const [label, value] of rows) {
    const row = document.createElement('div');

    const strong = document.createElement('strong');

    strong.textContent = `${label}: `;

    row.append(
      strong,
      document.createTextNode(value)
    );

    container.append(row);
  }
}


// ============================================
// ANALYTICS BUTTON
// ============================================

statsButton.addEventListener('click', async () => {
  if (!currentLink) return;

  statsButton.disabled = true;

  try {
    const stats = await fetchStats(currentLink);

    addStatRows(statsOutput, stats);

    statsOutput.hidden = false;

    showToast(
      'Analytics refreshed.',
      'success'
    );

  } catch (error) {
    showToast(
      error.message || 'Could not load link stats.',
      'error'
    );

  } finally {
    statsButton.disabled = false;
  }
});


// ============================================
// DISABLE A LINK
// ============================================

async function disableLink(
  link,
  triggerButton = disableButton
) {
  if (
    !link ||
    getLinkStatus(link) !== 'active'
  ) {
    return;
  }

  const confirmed = confirm(
    `Disable /${link.code}? Visitors will no longer be redirected.`
  );

  if (!confirmed) return;

  triggerButton.disabled = true;

  try {
    await apiRequest(
      `/api/v1/links/${encodeURIComponent(link.code)}`,
      {
        method: 'DELETE',

        headers: {
          'X-Management-Token': link.management_token
        }
      }
    );

    const disabled = {
      ...link,
      is_active: false,
      status: 'disabled'
    };

    if (
      currentLink &&
      currentLink.code === link.code
    ) {
      currentLink = disabled;

      disableButton.textContent = 'Link disabled';

      disableButton.disabled = true;

      if (!statsOutput.hidden) {
        try {
          const stats = await fetchStats(currentLink);

          addStatRows(statsOutput, stats);

        } catch {
          // The disable operation succeeded.
        }
      }
    }

    updateSavedLink(
      link.code,
      {
        is_active: false,
        status: 'disabled'
      }
    );

    showToast(
      `Link /${link.code} disabled successfully.`,
      'success'
    );

    if (
      currentLink &&
      currentLink.code === link.code
    ) {
      showMessage(
        `Link /${link.code} has been disabled.`,
        'success'
      );
    }

  } catch (error) {
    showToast(
      error.message || 'Could not disable the link.',
      'error'
    );

  } finally {
    if (triggerButton === disableButton) {
      const status = getLinkStatus(currentLink);

      disableButton.disabled = status !== 'active';

      disableButton.textContent =
        status === 'expired'
          ? 'Link expired'
          : status === 'disabled'
            ? 'Link disabled'
            : 'Disable link';
    }
  }
}


disableButton.addEventListener('click', async () => {
  if (currentLink) {
    await disableLink(currentLink);
  }
});


// ============================================
// RENDER SAVED LINK HISTORY
// ============================================

function renderHistory() {
  historyList.replaceChildren();

  historyEmpty.hidden = savedLinks.length > 0;

  for (const link of savedLinks) {
    const status = getLinkStatus(link);

    const card = document.createElement('article');

    card.className = 'history-card';

    const top = document.createElement('div');

    top.className = 'history-card-top';

    const titleWrap = document.createElement('div');

    titleWrap.className = 'history-title-wrap';

    const shortLink = document.createElement('a');

    shortLink.className = 'history-short-link';

    shortLink.href = link.short_url;

    shortLink.target = '_blank';

    shortLink.rel = 'noopener noreferrer';

    shortLink.textContent = link.short_url;

    const destination = document.createElement('div');

    destination.className = 'history-destination';

    destination.textContent = link.original_url;

    titleWrap.append(shortLink, destination);

    const badge = document.createElement('span');

    badge.className = `history-badge ${status}`;

    badge.textContent = statusText(status);

    top.append(titleWrap, badge);

    const metadata = document.createElement('div');

    metadata.className = 'history-metadata';

    metadata.textContent =
      `Created ${
        link.created_at
          ? new Date(link.created_at).toLocaleString()
          : 'date unknown'
      } · ${Number(link.click_count || 0)} click(s) last saved`;

    const actions = document.createElement('div');

    actions.className = 'history-actions';

    const statsBtn = document.createElement('button');

    statsBtn.type = 'button';

    statsBtn.className = 'secondary-button';

    statsBtn.textContent = 'View analytics';

    const shareBtn = document.createElement('button');

    shareBtn.type = 'button';

    shareBtn.className = 'secondary-button';

    shareBtn.textContent = 'Share link';

    const backupBtn = document.createElement('button');

    backupBtn.type = 'button';

    backupBtn.className = 'secondary-button';

    backupBtn.textContent = 'Download backup';

    const disableBtn = document.createElement('button');

    disableBtn.type = 'button';

    disableBtn.className = 'danger-button';

    disableBtn.textContent =
      status === 'expired'
        ? 'Expired'
        : status === 'disabled'
          ? 'Disabled'
          : 'Disable link';

    disableBtn.disabled = status !== 'active';

    const removeBtn = document.createElement('button');

    removeBtn.type = 'button';

    removeBtn.className = 'text-button history-remove';

    removeBtn.textContent = 'Remove from browser';

    actions.append(
      statsBtn,
      shareBtn,
      backupBtn,
      disableBtn,
      removeBtn
    );

    const statsBox = document.createElement('div');

    statsBox.className = 'history-stats';

    statsBox.hidden = true;

    // View analytics for a saved link.
    statsBtn.addEventListener(
      'click',
      async () => {
        statsBtn.disabled = true;

        statsBtn.textContent = 'Loading…';

        try {
          const latest =
            savedLinks.find(
              (item) => item.code === link.code
            ) || link;

          const stats = await fetchStats(latest);

          addStatRows(statsBox, stats);

          statsBox.hidden = false;

          metadata.textContent =
            `Created ${
              stats.created_at
                ? new Date(stats.created_at).toLocaleString()
                : 'date unknown'
            } · ${stats.click_count} click(s) · refreshed just now`;

          const latestStatus =
            stats.status ||
            getLinkStatus({
              ...latest,
              ...stats
            });

          badge.textContent = statusText(latestStatus);

          badge.className =
            `history-badge ${latestStatus}`;

          disableBtn.textContent =
            latestStatus === 'expired'
              ? 'Expired'
              : latestStatus === 'disabled'
                ? 'Disabled'
                : 'Disable link';

          disableBtn.disabled =
            latestStatus !== 'active';

          showToast(
            `Analytics loaded for /${link.code}.`,
            'success'
          );

        } catch (error) {
          showToast(
            error.message ||
              'Could not load analytics. If this is an older link, import it with its management token.',
            'error'
          );

        } finally {
          statsBtn.disabled = false;

          statsBtn.textContent = 'View analytics';
        }
      }
    );

    // Share the saved link.
    shareBtn.addEventListener('click', () => {
      shareLink(link);
    });

    // Download a TXT backup of the saved link.
    backupBtn.addEventListener('click', () => {
      downloadBackup(link, backupBtn);
    });

    // Disable the saved link.
    disableBtn.addEventListener(
      'click',
      async () => {
        await disableLink(link, disableBtn);
      }
    );

    // Remove the link only from this browser's history.
    removeBtn.addEventListener('click', () => {
      const confirmed = confirm(
        `Remove /${link.code} from this browser? This does not delete or disable the server link. Keep your backup if you may need its management token later.`
      );

      if (confirmed) {
        forgetSavedLink(link.code);
      }
    });

    card.append(
      top,
      metadata,
      actions,
      statsBox
    );

    historyList.append(card);
  }
}


// ============================================
// OPEN AND CLOSE IMPORT FORM
// ============================================

toggleImportButton.addEventListener('click', () => {
  importForm.hidden = !importForm.hidden;

  if (!importForm.hidden) {
    document.querySelector('#import-code').focus();
  }
});


cancelImportButton.addEventListener('click', () => {
  importForm.reset();

  importForm.hidden = true;
});


// ============================================
// IMPORT A TXT OR JSON BACKUP FILE
// ============================================

importBackupFile.addEventListener(
  'change',
  async () => {
    const file =
      importBackupFile.files &&
      importBackupFile.files[0];

    if (!file) return;

    try {
      const rawText = await file.text();

      let parsed;

      // First, try parsing the file as JSON.
      // This supports older SnapLink JSON backups.
      try {
        parsed = JSON.parse(rawText);

      } catch {
        // Otherwise, look for the structured JSON section
        // embedded inside the human-readable TXT file.

        const marker =
          '--- IMPORT DATA (keep intact) ---';

        const markerIndex = rawText.indexOf(marker);

        if (markerIndex === -1) {
          throw new Error(
            'This does not look like a SnapLink backup. Choose a SnapLink TXT or JSON backup.'
          );
        }

        const jsonText = rawText
          .slice(markerIndex + marker.length)
          .trim();

        parsed = JSON.parse(jsonText);
      }

      // Validate the backup.
      if (
        !parsed ||
        parsed.format !== 'SnapLink link backup' ||
        !parsed.code ||
        !parsed.management_token
      ) {
        throw new Error(
          'Invalid backup. The short code or management token is missing.'
        );
      }

      // Automatically fill in the import fields.
      document.querySelector('#import-code').value =
        parsed.code;

      document.querySelector('#import-token').value =
        parsed.management_token;

      showToast(
        'Backup loaded! Click "Verify and import link" to restore it.',
        'success'
      );

    } catch (error) {
      showToast(
        error.message || 'Could not read the backup file.',
        'error'
      );

      importBackupFile.value = '';
    }
  }
);


// ============================================
// VERIFY AND IMPORT AN EXISTING LINK
// ============================================

importForm.addEventListener(
  'submit',
  async (event) => {
    event.preventDefault();

    const code = document
      .querySelector('#import-code')
      .value
      .trim();

    const token = document
      .querySelector('#import-token')
      .value
      .trim();

    if (!/^[A-Za-z0-9_-]{4,32}$/.test(code)) {
      showToast(
        'Enter a valid short code.',
        'error'
      );

      return;
    }

    if (!token) {
      showToast(
        'Enter the management token.',
        'error'
      );

      return;
    }

    importSubmitButton.disabled = true;

    importSubmitButton.textContent = 'Verifying…';

    try {
      const temporary = {
        code,

        short_url:
          `${window.location.origin}/${encodeURIComponent(code)}`,

        original_url: '',

        management_token: token
      };

      // Verify the supplied code and token with the backend.
      const stats = await apiRequest(
        `/api/v1/links/${encodeURIComponent(code)}/stats`,
        {
          headers: {
            'X-Management-Token': token
          }
        }
      );

      // Restore the link details returned by the server.
      const imported = {
        ...temporary,

        original_url: stats.original_url,

        created_at: stats.created_at,

        expires_at: stats.expires_at,

        last_clicked_at: stats.last_clicked_at,

        click_count: stats.click_count,

        is_active: stats.is_active,

        status: stats.status,

        last_stats_checked_at: new Date().toISOString()
      };

      // Save the verified link in browser history.
      const saved = rememberLink(imported);

      fillResultPanel(saved);

      addStatRows(statsOutput, stats);

      statsOutput.hidden = false;

      importForm.reset();

      importForm.hidden = true;

      showToast(
        `/${code} imported. Its analytics are now available in My saved links.`,
        'success'
      );

    } catch (error) {
      showToast(
        error.message ||
          'Could not import this link. Check the short code and management token.',
        'error'
      );

    } finally {
      importSubmitButton.disabled = false;

      importSubmitButton.textContent =
        'Verify and import link →';
    }
  }
);