const product = document.querySelector('[data-product]');
if (product) {
  const qty = product.elements.qty;
  function update() {
    const extras = Array.from(product.querySelectorAll('[data-price]:checked'));
    const cents = extras.reduce((sum, el) => sum + Number(el.dataset.price), Number(product.dataset.product));
    product.querySelector('[data-total]').textContent = (cents * Number(qty.value) / 100).toLocaleString('pt-BR', {style:'currency', currency:'BRL'});
  }
  product.addEventListener('input', update);
  product.querySelectorAll('[data-step]').forEach(button => button.addEventListener('click', () => {
    qty.value = Math.max(1, Math.min(20, Number(qty.value) + Number(button.dataset.step)));
    update();
  }));
}
const phone = document.querySelector('input[name="phone"]');
phone?.addEventListener('input', () => {
  const digits = phone.value.replace(/\D/g, '').slice(0, 11);
  phone.value = digits.replace(/^(\d{2})(\d)/, '($1) $2').replace(/(\d{5})(\d)/, '$1-$2');
});
const resend = document.querySelector('[data-wait]');
if (resend) {
  let left = Number(resend.dataset.wait);
  function tick() {
    resend.disabled = left > 0;
    resend.textContent = left > 0 ? 'Reenviar SMS em ' + left + ' s' : 'Reenviar SMS';
    if (left-- > 0) setTimeout(tick, 1000);
  }
  tick();
}
const address = document.querySelector('[data-address]');
if (address) {
  const fields = document.querySelector('[data-address-fields]');
  function toggle() {
    fields.hidden = fields.disabled = address.value !== 'new';
  }
  address.addEventListener('change', toggle);
  toggle();
}
const tracker = document.querySelector('[data-tracker]');
if (tracker) {
  async function refresh() {
    try {
      const response = await fetch(tracker.dataset.tracker, {
        cache: 'no-store',
        signal: AbortSignal.timeout(10000)
      });
      if (!response.ok) throw new Error();
      const data = await response.json();
      tracker.querySelector('[data-status]').textContent = data.status;
      tracker.querySelector('[data-reason]').textContent = data.reason;
      tracker.querySelectorAll('li').forEach((item, index) => item.classList.toggle('passed', index <= data.stage));
      tracker.querySelector('[data-connection]').textContent = '';
      if (data.finished && !new URLSearchParams(location.search).has('detalhes')) {
        location.replace(tracker.dataset.done);
        return;
      }
    } catch {
      tracker.querySelector('[data-connection]').textContent = 'Sem atualização no momento. Tentando novamente…';
    }
    setTimeout(refresh, 5000);
  }
  setTimeout(refresh, 5000);
}
