document.addEventListener('submit', event => {
  const prompt = event.target.dataset.confirm;
  if (prompt && !window.confirm(prompt)) event.preventDefault();
});

const drawer = document.querySelector('.nav-drawer');
const menuToggle = document.querySelector('[data-drawer-open]');
const compact = matchMedia('(max-width: 767px)');
if (drawer && menuToggle) {
  menuToggle.addEventListener('click', () => {
    drawer.showModal();
    menuToggle.setAttribute('aria-expanded', 'true');
  });
  drawer.addEventListener('close', () => menuToggle.setAttribute('aria-expanded', 'false'));
  drawer.addEventListener('click', event => {
    if (event.target === drawer) drawer.close();
  });
  compact.addEventListener('change', event => {
    if (!event.matches && drawer.open) drawer.close();
  });
}

const board = document.querySelector('[data-board]');
if (board) {
  const tabList = board.querySelector('.status-tabs');
  const tabs = Array.from(tabList?.querySelectorAll('[data-tab]') || []);
  function selectTab(tab) {
    board.dataset.selectedLane = tab.dataset.tab;
    for (const item of tabs) {
      item.setAttribute('aria-selected', String(item === tab));
      item.tabIndex = item === tab ? 0 : -1;
    }
    board.querySelectorAll('[data-lane]').forEach(lane => {
      const selected = lane.dataset.lane === tab.dataset.tab;
      lane.hidden = compact.matches && !selected;
      if (compact.matches) {
        lane.setAttribute('role', 'tabpanel');
        lane.setAttribute('aria-labelledby', 'status-' + lane.dataset.lane);
      } else {
        lane.removeAttribute('role');
        lane.setAttribute('aria-labelledby', 'lane-title-' + lane.dataset.lane);
      }
    });
  }
  if (tabList) {
    selectTab(tabs[0]);
    compact.addEventListener('change', () => selectTab(tabs.find(tab => tab.dataset.tab === board.dataset.selectedLane)));
    tabList.addEventListener('click', event => {
      const tab = event.target.closest('[data-tab]');
      if (tab) selectTab(tab);
    });
    tabList.addEventListener('keydown', event => {
      const index = tabs.indexOf(event.target);
      if (index < 0) return;
      const targets = {ArrowLeft: (index + tabs.length - 1) % tabs.length,
        ArrowRight: (index + 1) % tabs.length, Home: 0, End: tabs.length - 1};
      if (!(event.key in targets)) return;
      event.preventDefault();
      const tab = tabs[targets[event.key]];
      selectTab(tab);
      tab.focus();
    });
  }
  function canRefresh() {
    const focused = document.activeElement;
    return (!board.contains(focused) || tabList?.contains(focused))
      && !board.querySelector('details[open]');
  }
  const dialog = document.querySelector('[data-order-dialog]');
  board.addEventListener('click', async event => {
    const link = event.target.closest('[data-order-detail]');
    if (!dialog || !link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    try {
      const response = await fetch(link.href + '?fragment=1', {signal: AbortSignal.timeout(8000)});
      if (!response.ok || response.redirected) throw new Error();
      dialog.querySelector('[data-dialog-content]').innerHTML = await response.text();
      if (!dialog.open) dialog.showModal();
    } catch {
      location.assign(link.href);
    }
  });
  const status = document.querySelector('[data-connection]');
  const alerts = document.querySelector('[data-alert-list]');
  const alertPanel = document.querySelector('[data-alerts]');
  const counter = document.querySelector('[data-count]');
  const sound = document.querySelector('[data-sound]');
  const observed = new Set();
  let audio;
  let unread = 0;
  document.querySelector('[data-alert-toggle]').addEventListener('click', () => {
    alertPanel.hidden = !alertPanel.hidden;
    unread = 0;
    counter.textContent = unread;
  });
  sound?.addEventListener('click', async () => {
    const context = audio || new AudioContext();
    await context.resume();
    audio = audio ? null : context;
    sound.textContent = audio ? 'Desativar som' : 'Ativar som';
    if (!audio) await context.close();
  });
  function notify(message) {
    if (!alerts.querySelector('[data-notice]')) alerts.replaceChildren();
    const item = document.createElement('li');
    item.dataset.notice = '';
    item.textContent = message;
    alerts.prepend(item);
    if (alerts.children.length > 20) alerts.lastElementChild.remove();
    counter.textContent = ++unread;
    if (audio?.state === 'running') {
      const oscillator = audio.createOscillator();
      const volume = audio.createGain();
      volume.gain.value = 0.055;
      oscillator.frequency.value = 660;
      oscillator.connect(volume).connect(audio.destination);
      oscillator.start();
      oscillator.stop(audio.currentTime + 0.15);
    }
  }
  function scan(container, initial = false) {
    container.querySelectorAll('[data-order]').forEach(card => {
      const {order, stage, number} = card.dataset;
      const event = order + ':' + stage;
      if (!observed.has(event) && !initial && (stage === '0' || stage === '2' || (stage === '1' && !!board.querySelector('.kitchen')))) {
        notify(stage === '2' ? 'Pedido #' + number + ' pronto' : 'Novo pedido #' + number);
        card.classList.add('arrived');
      }
      observed.add(event);
    });
  }
  scan(board, true);
  async function refresh() {
    try {
      if (canRefresh()) {
        const response = await fetch(board.dataset.board, {cache: 'no-store', signal: AbortSignal.timeout(10000)});
        if (!response.ok || response.redirected) throw new Error();
        const next = document.createElement('template');
        next.innerHTML = await response.text();
        if (canRefresh()) {
          scan(next.content);
          if (tabList) {
            const counts = next.content.querySelectorAll('.status-tabs button span');
            tabs.forEach((tab, index) => {
              tab.querySelector('span').textContent = counts[index].textContent;
            });
            const current = board.querySelector('.kanban');
            const nextLanes = next.content.querySelector('.kanban');
            const position = current.scrollLeft;
            current.replaceWith(nextLanes);
            selectTab(tabs.find(tab => tab.dataset.tab === board.dataset.selectedLane));
            nextLanes.scrollLeft = position;
          } else {
            board.replaceChildren(next.content);
          }
        }
      }
      status.textContent = 'Atualização automática';
    } catch {
      status.textContent = 'Conexão indisponível. Tentando novamente…';
    } finally {
      setTimeout(refresh, 4000);
    }
  }
  setTimeout(refresh, 4000);
}
