/**
 * RenewOps – Main JavaScript Module
 * Shared utilities, API client, navbar, toast notifications
 */

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
const API_BASE = '/api/v1';

// ---------------------------------------------------------------------------
// API Client
// ---------------------------------------------------------------------------
const api = {
  async get(path) {
    const r = await fetch(API_BASE + path);
    if (!r.ok) throw new Error(`GET ${path} → ${r.status}`);
    return r.json();
  },
  async post(path, body) {
    const r = await fetch(API_BASE + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail || `POST ${path} → ${r.status}`);
    }
    return r.json();
  },
  async patch(path, body) {
    const r = await fetch(API_BASE + path, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail || `PATCH ${path} → ${r.status}`);
    }
    return r.json();
  },
  async del(path) {
    const r = await fetch(API_BASE + path, { method: 'DELETE' });
    if (!r.ok) throw new Error(`DELETE ${path} → ${r.status}`);
    return r.status === 204 ? null : r.json();
  },
};

// ---------------------------------------------------------------------------
// Toast
// ---------------------------------------------------------------------------
function showToast(message, type = 'success') {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  const colors = { success: '#10b981', danger: '#ef4444', warning: '#f59e0b', info: '#3b82f6' };
  const t = document.createElement('div');
  t.className = 'toast show align-items-center border-0 text-white mb-2';
  t.style.background = colors[type] || colors.info;
  t.style.minWidth = '280px';
  t.innerHTML = `
    <div class="d-flex">
      <div class="toast-body fw-500">${message}</div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
    </div>`;
  container.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

// ---------------------------------------------------------------------------
// Currency & date helpers
// ---------------------------------------------------------------------------
function formatCurrency(amount, currency = 'INR') {
  if (amount == null) return '—';
  const num = parseFloat(amount);
  if (currency === 'INR') {
    return '₹' + num.toLocaleString('en-IN', { maximumFractionDigits: 0 });
  }
  return new Intl.NumberFormat('en-US', { style: 'currency', currency, maximumFractionDigits: 0 }).format(num);
}

function formatDate(d) {
  if (!d) return '—';
  return new Date(d).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

function daysUntil(d) {
  if (!d) return null;
  return Math.ceil((new Date(d) - new Date()) / 86400000);
}

function daysUntilLabel(d) {
  const n = daysUntil(d);
  if (n == null) return '—';
  if (n < 0) return `<span class="text-danger fw-600">${Math.abs(n)}d overdue</span>`;
  if (n === 0) return `<span class="text-danger fw-600">Today</span>`;
  if (n <= 7) return `<span class="text-danger fw-600">In ${n}d</span>`;
  if (n <= 30) return `<span class="text-warning fw-600">In ${n}d</span>`;
  return `<span class="text-muted">In ${n}d</span>`;
}

// ---------------------------------------------------------------------------
// Badge helpers
// ---------------------------------------------------------------------------
function statusBadge(s) {
  const map = { Active: 'active', Inactive: 'inactive', Cancelled: 'cancelled', Paused: 'paused' };
  const cls = map[s] || 'inactive';
  return `<span class="badge badge-status-${cls} rounded-pill px-2 py-1">${s}</span>`;
}

function decisionBadge(d) {
  const map = { 'Renew': 'renew', 'Cancel': 'cancel', 'Under Review': 'review', 'Undecided': 'undecided' };
  const cls = map[d] || 'undecided';
  return `<span class="badge badge-decision-${cls} rounded-pill px-2 py-1">${d}</span>`;
}

function riskBadge(risk) {
  if (!risk) return '';
  const cls = risk.category.toLowerCase();
  const pct = risk.score;
  const barColor = cls === 'high' ? '#ef4444' : cls === 'medium' ? '#f59e0b' : '#10b981';
  return `
    <div class="d-flex align-items-center gap-2">
      <span class="badge risk-${cls} rounded-pill px-2 py-1">${risk.category}</span>
      <div class="risk-bar-wrap"><div class="risk-bar" style="width:${pct}%;background:${barColor}"></div></div>
      <small class="text-muted">${pct}</small>
    </div>`;
}

// ---------------------------------------------------------------------------
// Mark active nav link
// ---------------------------------------------------------------------------
function markActiveNav() {
  const path = window.location.pathname;
  const isDashboardPath = ['/', '/main', '/dashboard', '/index.html'].includes(path);
  document.querySelectorAll('#sidebar .nav-link').forEach(a => {
    const href = a.getAttribute('href');
    const isDashboardLink = href === '/' || href === '/index.html' || href === '/main';
    a.classList.toggle('active', (isDashboardLink && isDashboardPath) || href === path);
  });
}

// ---------------------------------------------------------------------------
// Subscription form helpers (shared between create & edit)
// ---------------------------------------------------------------------------
function buildFormBody(form) {
  const fd = new FormData(form);
  const body = {};
  for (const [k, v] of fd.entries()) {
    if (v === '') continue;  // skip empties
    body[k] = v;
  }
  // Parse booleans & numbers
  if ('amount' in body) body.amount = parseFloat(body.amount);
  if ('auto_renewal' in body) body.auto_renewal = body.auto_renewal === 'true';
  return body;
}

// ---------------------------------------------------------------------------
// Render sidebar (injected by each page)
// ---------------------------------------------------------------------------
function renderSidebar() {
  const html = `
    <div class="brand">Renew<span>Ops</span></div>
    <nav class="mt-2">
      <a class="nav-link" href="/"><i class="bi bi-grid-1x2"></i> Dashboard</a>
      <a class="nav-link" href="/subscriptions.html"><i class="bi bi-collection"></i> Subscriptions</a>
      <a class="nav-link" href="/renewals.html"><i class="bi bi-calendar-check"></i> Upcoming Renewals</a>
      <a class="nav-link" href="/risk.html"><i class="bi bi-shield-exclamation"></i> Renewal Risk</a>
      <a class="nav-link" href="/analytics.html"><i class="bi bi-bar-chart-line"></i> Spending Analytics</a>
    </nav>`;
  const el = document.getElementById('sidebar');
  if (el) { el.innerHTML = html; markActiveNav(); }
}

document.addEventListener('DOMContentLoaded', renderSidebar);

