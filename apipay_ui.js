// KENGURU ApiPay V6 — hard override of the legacy manual Kaspi flow.
(() => {
  if (window.__KENGURU_APIPAY_V6__) return;
  window.__KENGURU_APIPAY_V6__ = true;
  console.log('[KENGURU] APIPAY UI V6 ACTIVE');

  let poll = null;
  const $ = id => document.getElementById(id);

  function lang(){ return (typeof uiLang !== 'undefined' ? uiLang : 'kk'); }
  function text(kk, ru){ return lang() === 'ru' ? ru : kk; }
  function key(t){ return 'kng_apipay_v6_' + t; }

  function disableLegacyPayment(){
    const card = $('payCard');
    if (!card) return;
    const link = card.querySelector('.payBox a');
    if (link) {
      link.removeAttribute('href');
      link.textContent = text('ApiPay шоты жасалуда…', 'Создаём счёт ApiPay…');
    }
    const img = card.querySelector('.payBox img');
    if (img) {
      img.removeAttribute('src');
      img.alt = 'ApiPay QR';
      img.style.minHeight = '220px';
    }
  }

  function showInvoice(p, t){
    const card = $('payCard');
    if (!card) return;
    const img = card.querySelector('.payBox img');
    const link = card.querySelector('.payBox a');
    const btn = $('paidBtn');

    if (img && p.qr_image_url) {
      img.src = p.qr_image_url;
      img.style.minHeight = '';
    }
    if (link && p.qr_token_url) {
      link.href = p.qr_token_url;
      link.target = '_blank';
      link.rel = 'noopener';
      link.textContent = text('Kaspi арқылы төлеу', 'Открыть оплату в Kaspi');
    }
    if (btn) btn.textContent = text('Төлемді тексеру', 'Проверить оплату');

    try { localStorage.setItem(key(t), JSON.stringify(p)); } catch(e) {}
  }

  async function status(t){
    if (!t) return;
    try {
      const r = await fetch('/api/status/' + encodeURIComponent(t), {cache:'no-store'});
      if (!r.ok) return;
      const s = await r.json();
      if (s.payment_status === 'paid') {
        if (poll) { clearInterval(poll); poll = null; }
        if (typeof token !== 'undefined') token = t;
        if (typeof checkStatus === 'function') await checkStatus();
      }
    } catch(e) {}
  }

  function pollStart(t){
    if (poll) clearInterval(poll);
    poll = setInterval(() => status(t), 3000);
    status(t);
  }

  async function invoice(t){
    const r = await fetch('/api/apipay/create/' + encodeURIComponent(t), {
      method:'POST', cache:'no-store'
    });
    if (!r.ok) {
      let msg = '';
      try { msg = await r.text(); } catch(e) {}
      alert(text('ApiPay қатесі: ', 'Ошибка ApiPay: ') + msg);
      return;
    }
    const p = await r.json();
    if (p.paid) { await status(t); return; }
    if (!p.invoice_id) {
      alert(text('ApiPay шот нөмірін қайтармады', 'ApiPay не вернул номер счёта'));
      return;
    }
    showInvoice(p, t);
    pollStart(t);
  }

  // HARD RESET: cloning removes the old app.js submit listener completely.
  const oldForm = $('regForm');
  if (oldForm) {
    const form = oldForm.cloneNode(true);
    oldForm.parentNode.replaceChild(form, oldForm);

    const langSelect = $('lang');
    if (langSelect && typeof applyLang === 'function') {
      langSelect.addEventListener('change', e => {
        if (typeof uiLang !== 'undefined') uiLang = e.target.value;
        applyLang();
      });
    }

    form.addEventListener('submit', async e => {
      e.preventDefault();

      const data = {
        lang: $('lang').value,
        full_name: $('full_name').value.trim(),
        phone: $('phone').value.trim(),
        region: $('region').value,
        locality: $('locality').value.trim(),
        school: $('school').value.trim(),
        grade: +$('grade').value
      };

      const r = await fetch('/api/register', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify(data)
      });

      if (!r.ok) {
        let msg=''; try{msg=await r.text()}catch(e){}
        alert(text('Өтінімді сақтау мүмкін болмады. ', 'Не удалось сохранить заявку. ') + msg);
        return;
      }

      const j = await r.json();
      if (typeof token !== 'undefined') token = j.token;
      localStorage.setItem('kng_token', j.token);

      if (typeof showOnly === 'function') showOnly('payCard');
      disableLegacyPayment();
      await invoice(j.token);
    });
  }

  // HARD RESET: remove the old "I paid" / payment-mark listener too.
  const oldPaid = $('paidBtn');
  if (oldPaid) {
    const btn = oldPaid.cloneNode(true);
    oldPaid.parentNode.replaceChild(btn, oldPaid);
    btn.textContent = text('Төлемді тексеру', 'Проверить оплату');
    btn.addEventListener('click', e => {
      e.preventDefault();
      status(localStorage.getItem('kng_token') || '');
    });
  }

  // Never allow the legacy fixed Kaspi URL while V6 is active.
  disableLegacyPayment();

  const savedToken = localStorage.getItem('kng_token') || '';
  if (savedToken) {
    try {
      const p = JSON.parse(localStorage.getItem(key(savedToken)) || 'null');
      if (p) { showInvoice(p, savedToken); pollStart(savedToken); }
    } catch(e) {}
  }
})();
