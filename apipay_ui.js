// KENGURU — ApiPay dynamic QR payment UI
// Loaded AFTER app.js. Capture listeners override the old manual-payment flow.
(() => {
  let payPoll = null;

  function cacheKey(t){ return 'kng_apipay_' + t; }

  function applyInvoice(p, t){
    const card = document.getElementById('payCard');
    if (!card) return;

    const img = card.querySelector('.payBox img');
    const link = card.querySelector('.payBox a');
    const paid = document.getElementById('paidBtn');

    if (p.qr_image_url && img) img.src = p.qr_image_url;

    if (link) {
      if (p.qr_token_url) {
        link.href = p.qr_token_url;
        link.target = '_blank';
        link.rel = 'noopener';
      } else {
        link.removeAttribute('href');
      }
      link.textContent = uiLang === 'ru' ? 'Открыть оплату в Kaspi' : 'Kaspi арқылы төлеу';
    }

    if (paid) {
      paid.textContent = uiLang === 'ru' ? 'Проверить оплату' : 'Төлемді тексеру';
    }

    try { localStorage.setItem(cacheKey(t), JSON.stringify(p)); } catch(e) {}
  }

  async function checkPayment(t){
    if (!t) return;
    const r = await fetch('/api/status/' + encodeURIComponent(t), {cache:'no-store'});
    if (!r.ok) return;
    const s = await r.json();

    if (s.payment_status === 'paid') {
      if (payPoll) { clearInterval(payPoll); payPoll = null; }
      token = t;
      await checkStatus();
    }
  }

  function startPolling(t){
    if (payPoll) clearInterval(payPoll);
    payPoll = setInterval(() => checkPayment(t).catch(()=>{}), 3000);
    checkPayment(t).catch(()=>{});
  }

  async function createInvoice(t){
    const r = await fetch('/api/apipay/create/' + encodeURIComponent(t), {
      method: 'POST',
      cache: 'no-store'
    });

    if (!r.ok) {
      const msg = await r.text();
      alert((uiLang === 'ru' ? 'Ошибка ApiPay: ' : 'ApiPay қатесі: ') + msg);
      return false;
    }

    const p = await r.json();

    if (p.paid) {
      await checkPayment(t);
      return true;
    }

    if (!p.invoice_id) {
      alert(uiLang === 'ru' ? 'ApiPay не вернул номер счёта' : 'ApiPay шот нөмірін қайтармады');
      return false;
    }

    applyInvoice(p, t);
    startPolling(t);
    return true;
  }

  const form = document.getElementById('regForm');
  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      e.stopImmediatePropagation();

      const data = {
        lang: byId('lang').value,
        full_name: byId('full_name').value.trim(),
        phone: byId('phone').value.trim(),
        region: byId('region').value,
        locality: byId('locality').value.trim(),
        school: byId('school').value.trim(),
        grade: +byId('grade').value
      };

      const r = await fetch('/api/register', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify(data)
      });

      if (!r.ok) {
        alert(uiLang === 'kk' ? 'Өтінімді сақтау мүмкін болмады' : 'Не удалось сохранить заявку');
        return;
      }

      const j = await r.json();
      token = j.token;
      localStorage.setItem('kng_token', token);
      showOnly('payCard');

      // Never leave the old fixed Kaspi link active while ApiPay invoice is being created.
      const oldLink = document.querySelector('#payCard .payBox a');
      if (oldLink) {
        oldLink.removeAttribute('href');
        oldLink.textContent = uiLang === 'ru' ? 'Создаём счёт…' : 'Төлем шоты жасалуда…';
      }

      await createInvoice(token);
    }, true);
  }

  const paid = document.getElementById('paidBtn');
  if (paid) {
    paid.addEventListener('click', async (e) => {
      e.preventDefault();
      e.stopImmediatePropagation();
      await checkPayment(token);
    }, true);
  }

  // Restore a dynamic invoice after reload.
  if (token) {
    try {
      const saved = JSON.parse(localStorage.getItem(cacheKey(token)) || 'null');
      if (saved) {
        applyInvoice(saved, token);
        startPolling(token);
      }
    } catch(e) {}
  }
})();
