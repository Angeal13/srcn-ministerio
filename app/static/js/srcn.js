/* SRCN — Frontend JS */
'use strict';

// ── DNI Lookup ────────────────────────────────────────────────
function initDniLookup() {
  const input = document.getElementById('dni-lookup-input');
  const result = document.getElementById('dni-lookup-result');
  if (!input || !result) return;

  let debounceTimer;
  input.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    const val = input.value.trim();
    if (val.length < 3) { result.style.display = 'none'; return; }
    debounceTimer = setTimeout(() => fetchDni(val), 400);
  });

  function fetchDni(dni) {
    fetch(`/sujetos/verificar-dni?dni=${encodeURIComponent(dni)}`)
      .then(r => r.json())
      .then(data => {
        result.style.display = 'block';
        result.className = 'dni-result';
        if (!data.encontrado) {
          result.classList.add('unknown');
          result.innerHTML = '⚪ Sin antecedentes locales. Consulta en curso con nodo provincial…';
        } else if (data.warrant_activo) {
          result.classList.add('warrant');
          result.innerHTML = `🚨 <strong>WARRANT ACTIVO</strong> — ${data.nombre}<br>
            <span style="font-size:.75rem">Expediente: ${data.expediente} · Provincia emisora: ${data.provincia_emisora} · Urgencia: ${data.nivel_urgencia?.toUpperCase()}</span>`;
          // Pre-fill hidden warrant_id if available
          const wInput = document.getElementById('warrant_id_hidden');
          if (wInput && data.warrant_uuid) wInput.value = data.warrant_uuid;
        } else {
          result.classList.add('clear');
          result.innerHTML = `✅ <strong>SIN WARRANT ACTIVO</strong> — ${data.nombre} (${data.expediente}) · Riesgo: ${data.nivel_riesgo}`;
        }
      })
      .catch(() => { result.style.display = 'none'; });
  }
}

// ── Autocomplete Sujeto ───────────────────────────────────────
function initSujetoAutocomplete() {
  const input = document.getElementById('sujeto-search');
  const list  = document.getElementById('sujeto-autocomplete');
  const hidden = document.getElementById('sujeto_id');
  if (!input || !list) return;

  let timer;
  input.addEventListener('input', () => {
    clearTimeout(timer);
    const q = input.value.trim();
    if (q.length < 2) { list.innerHTML = ''; list.style.display = 'none'; return; }
    timer = setTimeout(() => {
      fetch(`/sujetos/buscar-ajax?q=${encodeURIComponent(q)}`)
        .then(r => r.json())
        .then(data => {
          list.innerHTML = '';
          if (!data.length) { list.style.display = 'none'; return; }
          data.forEach(s => {
            const li = document.createElement('div');
            li.className = 'autocomplete-item';
            li.innerHTML = `
              <span class="font-mono text-xs text-dim">${s.numero_expediente}</span>
              <strong>${s.nombre}</strong>
              ${s.es_buscado ? '<span class="badge red" style="margin-left:.4rem">BUSCADO</span>' : ''}
              <span class="text-xs text-muted" style="margin-left:.5rem">${s.dni || ''}</span>`;
            li.addEventListener('click', () => {
              input.value = `${s.nombre} — ${s.numero_expediente}`;
              if (hidden) hidden.value = s.id;
              list.style.display = 'none';
            });
            list.appendChild(li);
          });
          list.style.display = 'block';
        });
    }, 300);
  });

  document.addEventListener('click', e => {
    if (!list.contains(e.target) && e.target !== input) {
      list.style.display = 'none';
    }
  });
}

// ── Intranet status ───────────────────────────────────────────
function checkIntranetStatus() {
  const dot = document.getElementById('intranet-dot');
  if (!dot) return;
  fetch('/red/estado-json')
    .then(r => r.json())
    .then(d => { dot.classList.toggle('offline', !d.ok); })
    .catch(() => dot.classList.add('offline'));
}

// ── Flash dismiss ─────────────────────────────────────────────
function initFlashDismiss() {
  document.querySelectorAll('.alert-banner .dismiss').forEach(btn => {
    btn.addEventListener('click', () => btn.closest('.alert-banner').remove());
  });
}

// ── Confirm dialogs ───────────────────────────────────────────
function initConfirm() {
  document.querySelectorAll('[data-confirm]').forEach(el => {
    el.addEventListener('click', e => {
      if (!confirm(el.dataset.confirm)) e.preventDefault();
    });
  });
}

// ── Init ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initDniLookup();
  initSujetoAutocomplete();
  initFlashDismiss();
  initConfirm();
  checkIntranetStatus();
  // Refresh intranet status every 30s
  setInterval(checkIntranetStatus, 30000);
});
