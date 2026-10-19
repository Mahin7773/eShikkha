/* small UI helpers: toasts, confirm dialogs, tabs, quiz timer */
(function () {
  'use strict';

  // toasts
  document.querySelectorAll('.toast').forEach(function (toast, i) {
    var close = function () {
      toast.classList.add('hide');
      setTimeout(function () { toast.remove(); }, 260);
    };
    var btn = toast.querySelector('button');
    if (btn) btn.addEventListener('click', close);
    var isError = toast.classList.contains('toast-error');
    setTimeout(close, (isError ? 9000 : 5000) + i * 400);
  });

  // <form data-confirm="..."> asks before submitting
  var dialog = document.getElementById('confirm-dialog');
  if (dialog && typeof dialog.showModal === 'function') {
    var pending = null;
    document.addEventListener('submit', function (e) {
      var form = e.target;
      if (!form.matches('form[data-confirm]') || form.dataset.confirmed === '1') return;
      e.preventDefault();
      pending = { form: form, submitter: e.submitter };
      dialog.querySelector('[data-confirm-title]').textContent = form.dataset.confirmTitle || 'Are you sure?';
      dialog.querySelector('[data-confirm-message]').textContent = form.dataset.confirm;
      var ok = dialog.querySelector('[data-confirm-ok]');
      ok.textContent = form.dataset.confirmButton || 'Confirm';
      ok.className = 'btn ' + (form.dataset.confirmTone === 'primary' ? 'btn-primary' : 'btn-danger');
      dialog.showModal();
      ok.focus();
    }, true);
    dialog.addEventListener('close', function () {
      if (dialog.returnValue === 'ok' && pending) {
        pending.form.dataset.confirmed = '1';
        if (pending.form.requestSubmit) pending.form.requestSubmit(pending.submitter || undefined);
        else pending.form.submit();
      }
      pending = null;
      dialog.returnValue = '';
    });
  }

  // <form data-once> disables its buttons after the first submit
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (e.defaultPrevented || !form.matches('form[data-once]')) return;
    if (form.dataset.submitting === '1') { e.preventDefault(); return; }
    form.dataset.submitting = '1';
    form.querySelectorAll('button[type=submit], button:not([type])').forEach(function (b) {
      b.setAttribute('aria-disabled', 'true');
      if (b.dataset.loading) b.textContent = b.dataset.loading;
    });
  });

  // tabs
  document.querySelectorAll('[data-tabs]').forEach(function (tablist) {
    var tabs = Array.prototype.slice.call(tablist.querySelectorAll('[role=tab]'));
    var select = function (tab) {
      tabs.forEach(function (t) {
        var selected = t === tab;
        t.setAttribute('aria-selected', selected ? 'true' : 'false');
        t.tabIndex = selected ? 0 : -1;
        var panel = document.getElementById(t.getAttribute('aria-controls'));
        if (panel) panel.hidden = !selected;
      });
    };
    tabs.forEach(function (tab, idx) {
      tab.addEventListener('click', function () { select(tab); });
      tab.addEventListener('keydown', function (e) {
        var next = null;
        if (e.key === 'ArrowRight') next = tabs[(idx + 1) % tabs.length];
        if (e.key === 'ArrowLeft') next = tabs[(idx - 1 + tabs.length) % tabs.length];
        if (next) { e.preventDefault(); select(next); next.focus(); }
      });
    });
  });

  // <button data-toggle="#id"> toggles .open on the target
  document.querySelectorAll('[data-toggle]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var target = document.querySelector(btn.dataset.toggle);
      if (!target) return;
      var open = target.classList.toggle('open');
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
      if (open) { var input = target.querySelector('input'); if (input) input.focus(); }
    });
  });

  // close dropdowns on outside click / Escape
  document.addEventListener('click', function (e) {
    document.querySelectorAll('details.dropdown[open]').forEach(function (d) {
      if (!d.contains(e.target)) d.removeAttribute('open');
    });
  });
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    document.querySelectorAll('details.dropdown[open]').forEach(function (d) {
      d.removeAttribute('open');
      var s = d.querySelector('summary'); if (s) s.focus();
    });
  });

  // filter forms submit on change
  document.querySelectorAll('form[data-autosubmit]').forEach(function (form) {
    form.addEventListener('change', function () { form.submit(); });
  });

  // quiz timer, auto-submits at the deadline
  var quiz = document.getElementById('quiz-form');
  if (quiz) {
    var answered = false;
    quiz.addEventListener('change', function () { answered = true; });
    var submitting = false;
    quiz.addEventListener('submit', function () { submitting = true; });
    window.addEventListener('beforeunload', function (e) {
      if (answered && !submitting) { e.preventDefault(); e.returnValue = ''; }
    });

    var timer = document.getElementById('quiz-timer');
    if (timer && quiz.dataset.deadline) {
      var deadline = new Date(quiz.dataset.deadline).getTime();
      var skew = Date.now() - new Date(quiz.dataset.serverNow).getTime();
      var out = timer.querySelector('[data-time]');
      var tick = function () {
        var left = Math.max(0, Math.floor((deadline - (Date.now() - skew)) / 1000));
        var m = Math.floor(left / 60), s = left % 60;
        out.textContent = m + ':' + (s < 10 ? '0' : '') + s;
        timer.classList.toggle('warn', left <= 120 && left > 30);
        timer.classList.toggle('danger', left <= 30);
        if (left === 0) {
          clearInterval(handle);
          if (!submitting) { submitting = true; quiz.submit(); }
        }
      };
      var handle = setInterval(tick, 1000);
      tick();
    }
  }
})();
