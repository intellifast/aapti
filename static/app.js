addEventListener('DOMContentLoaded', () => {
  if (window.lucide) lucide.createIcons();
  const body = document.body;
  const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const slug = value => String(value || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');

  document.querySelector('.menu-toggle')?.addEventListener('click', () => body.classList.toggle('nav-open'));
  document.querySelectorAll('[data-modal-open]').forEach(button => button.addEventListener('click', () => document.querySelector('#createModal')?.classList.add('open')));
  document.querySelectorAll('[data-modal-close]').forEach(button => button.addEventListener('click', () => document.querySelector('#createModal')?.classList.remove('open')));
  document.querySelectorAll('[data-ai-open]').forEach(button => button.addEventListener('click', () => document.querySelector('.ai-panel')?.classList.add('open')));
  document.querySelectorAll('[data-ai-close]').forEach(button => button.addEventListener('click', () => document.querySelector('.ai-panel')?.classList.remove('open')));

  const notificationsButton = document.querySelector('[data-notifications-open]');
  const notificationsPopover = document.querySelector('.notifications-popover');
  const profileButton = document.querySelector('[data-profile-open]');
  const profilePopover = document.querySelector('.profile-popover');
  const closePopovers = () => document.querySelectorAll('.top-popover.open').forEach(popover => popover.classList.remove('open'));
  notificationsButton?.addEventListener('click', event => {
    event.stopPropagation();
    const opening = !notificationsPopover?.classList.contains('open');
    closePopovers();
    if (opening) notificationsPopover?.classList.add('open');
  });
  profileButton?.addEventListener('click', event => {
    event.stopPropagation();
    const opening = !profilePopover?.classList.contains('open');
    closePopovers();
    if (opening) profilePopover?.classList.add('open');
  });
  document.addEventListener('click', event => {
    if (!event.target.closest('.top-popover') && !event.target.closest('[data-notifications-open]') && !event.target.closest('[data-profile-open]')) closePopovers();
  });
  document.querySelector('[data-notifications-read]')?.addEventListener('click', async () => {
    const response = await fetch('/notifications/read', {method: 'POST'});
    if (!response.ok) return;
    document.querySelectorAll('.notification-item.unread').forEach(item => item.classList.remove('unread'));
    document.querySelector('.notification-dot')?.remove();
    const unread = document.querySelector('.popover-head small');
    if (unread) unread.textContent = '0 unread';
  });

  const dashboardFilterButton = document.querySelector('[data-dashboard-filter]');
  const dashboardFilter = document.querySelector('.dashboard-filter');
  dashboardFilterButton?.addEventListener('click', () => {
    dashboardFilter?.classList.toggle('open');
    dashboardFilter?.querySelector('input')?.focus();
  });
  dashboardFilter?.querySelector('input')?.addEventListener('input', event => {
    const query = event.target.value.trim().toLowerCase();
    document.querySelectorAll('.activity-card tbody tr').forEach(row => row.hidden = !row.textContent.toLowerCase().includes(query));
  });

  const workspace = document.querySelector('[data-record-workspace]');
  if (workspace) {
    const rows = [...workspace.querySelectorAll('[data-record-row]')];
    const records = rows.map(row => ({
      row,
      title: row.dataset.title,
      client: row.dataset.client || 'No client',
      owner: row.dataset.owner || 'Unassigned',
      status: row.dataset.status || 'Not started',
      priority: row.dataset.priority || 'Medium',
      due: row.dataset.due,
      url: row.dataset.url,
    }));
    const viewButtons = [...workspace.querySelectorAll('[data-view-mode]')];
    const views = [...workspace.querySelectorAll('[data-record-view]')];
    const board = workspace.querySelector('[data-record-view="board"]');
    const calendar = workspace.querySelector('[data-record-view="calendar"]');
    const filterInput = workspace.querySelector('.toolbar-search input');
    let currentView = 'list';
    let calendarDate = new Date();

    const filteredRecords = () => {
      const query = filterInput.value.trim().toLowerCase();
      return records.filter(record => [record.title, record.client, record.owner, record.status, record.priority, record.due].join(' ').toLowerCase().includes(query));
    };

    const renderBoard = items => {
      const groups = new Map();
      items.forEach(record => {
        if (!groups.has(record.status)) groups.set(record.status, []);
        groups.get(record.status).push(record);
      });
      board.innerHTML = items.length ? `<div class="board-grid">${[...groups.entries()].map(([status, cards]) => `
        <section class="board-column">
          <header><span class="status ${slug(status)}">${escapeHtml(status)}</span><b>${cards.length}</b></header>
          <div>${cards.map(record => `<a class="board-card" href="${escapeHtml(record.url)}"><strong>${escapeHtml(record.title)}</strong><p>${escapeHtml(record.client)}</p><div><span class="priority ${slug(record.priority)}">${escapeHtml(record.priority)}</span><small>${record.due ? `Due ${escapeHtml(record.due)}` : 'No due date'}</small></div></a>`).join('')}</div>
        </section>`).join('')}</div>` : '<div class="view-empty"><strong>No matching records</strong><p>Try a different filter.</p></div>';
    };

    const renderCalendar = items => {
      const year = calendarDate.getFullYear();
      const month = calendarDate.getMonth();
      const firstDay = new Date(year, month, 1);
      const daysInMonth = new Date(year, month + 1, 0).getDate();
      const startOffset = (firstDay.getDay() + 6) % 7;
      const monthName = firstDay.toLocaleDateString(undefined, {month: 'long', year: 'numeric'});
      const byDate = new Map();
      items.filter(record => record.due).forEach(record => {
        if (!byDate.has(record.due)) byDate.set(record.due, []);
        byDate.get(record.due).push(record);
      });
      const cells = [];
      for (let i = 0; i < startOffset; i += 1) cells.push('<div class="calendar-day outside"></div>');
      for (let day = 1; day <= daysInMonth; day += 1) {
        const key = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        const events = byDate.get(key) || [];
        const today = key === new Date().toISOString().slice(0, 10);
        cells.push(`<div class="calendar-day ${today ? 'today' : ''}"><span>${day}</span><div>${events.map(record => `<a href="${escapeHtml(record.url)}" title="${escapeHtml(record.title)}"><i class="priority-dot ${slug(record.priority)}"></i>${escapeHtml(record.title)}</a>`).join('')}</div></div>`);
      }
      calendar.innerHTML = `<div class="calendar-toolbar"><button type="button" data-calendar-prev aria-label="Previous month"><i data-lucide="chevron-left"></i></button><strong>${escapeHtml(monthName)}</strong><button type="button" data-calendar-today>Today</button><button type="button" data-calendar-next aria-label="Next month"><i data-lucide="chevron-right"></i></button></div><div class="calendar-weekdays">${['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].map(day => `<span>${day}</span>`).join('')}</div><div class="calendar-grid">${cells.join('')}</div>`;
      calendar.querySelector('[data-calendar-prev]').addEventListener('click', () => { calendarDate = new Date(year, month - 1, 1); renderCalendar(filteredRecords()); lucide.createIcons(); });
      calendar.querySelector('[data-calendar-next]').addEventListener('click', () => { calendarDate = new Date(year, month + 1, 1); renderCalendar(filteredRecords()); lucide.createIcons(); });
      calendar.querySelector('[data-calendar-today]').addEventListener('click', () => { calendarDate = new Date(); renderCalendar(filteredRecords()); lucide.createIcons(); });
      lucide.createIcons();
    };

    const refreshView = () => {
      const items = filteredRecords();
      rows.forEach(row => row.hidden = !items.some(record => record.row === row));
      if (currentView === 'board') renderBoard(items);
      if (currentView === 'calendar') renderCalendar(items);
    };
    viewButtons.forEach(button => button.addEventListener('click', () => {
      currentView = button.dataset.viewMode;
      viewButtons.forEach(item => {
        const selected = item === button;
        item.classList.toggle('active', selected);
        item.setAttribute('aria-selected', selected ? 'true' : 'false');
      });
      views.forEach(view => view.hidden = view.dataset.recordView !== currentView);
      refreshView();
    }));
    filterInput.addEventListener('input', refreshView);
  }

  const projectForm = document.querySelector('[data-project-form]');
  if (projectForm) {
    const clientSelect = projectForm.querySelector('[data-project-client]');
    const serviceSelect = projectForm.querySelector('[data-project-services]');
    const hint = projectForm.querySelector('[data-project-service-hint]');
    const refreshProjectServices = () => {
      const clientId = clientSelect.value;
      const options = [...serviceSelect.options];
      const matched = options.filter(option => clientId && (option.dataset.clients || '').split(',').includes(clientId));
      options.forEach(option => {
        const available = !clientId || !matched.length || matched.includes(option);
        option.disabled = !available;
        if (!available) option.selected = false;
      });
      hint.textContent = !clientId
        ? 'Select a client to see their services.'
        : matched.length
          ? `${matched.length} configured service${matched.length === 1 ? '' : 's'} available for this client.`
          : 'No services are configured for this older client, so all services remain available.';
    };
    clientSelect.addEventListener('change', refreshProjectServices);
    refreshProjectServices();
  }

  const taskForm = document.querySelector('[data-task-form]');
  if (taskForm) {
    const projectSelect = taskForm.querySelector('[data-task-project]');
    const serviceSelect = taskForm.querySelector('[data-task-service]');
    const stageSelect = taskForm.querySelector('[data-task-stage]');
    const serviceOptions = [...serviceSelect.options].slice(1).map(option => ({ value: option.value, text: option.textContent }));
    const stageOptions = [...stageSelect.options].slice(1).map(option => ({ value: option.value, text: option.textContent, service: option.dataset.service }));
    const optionIds = option => (option?.dataset.services || '').split(',').filter(Boolean);
    const replaceOptions = (select, placeholder, options, datasetKey) => {
      select.innerHTML = '';
      select.add(new Option(placeholder, ''));
      options.forEach(item => {
        const option = new Option(item.text, item.value);
        if (datasetKey) option.dataset[datasetKey] = item[datasetKey];
        select.add(option);
      });
    };
    const refreshTaskStages = () => {
      const serviceId = serviceSelect.value;
      const currentStage = stageSelect.value;
      const stages = serviceId ? stageOptions.filter(option => option.service === serviceId) : [];
      replaceOptions(stageSelect, serviceId ? 'Workflow stage' : 'Select service first', stages, 'service');
      stageSelect.disabled = !serviceId;
      if (stages.some(option => option.value === currentStage)) stageSelect.value = currentStage;
    };
    const refreshTaskServices = () => {
      const serviceIds = optionIds(projectSelect.selectedOptions[0]);
      const currentService = serviceSelect.value;
      const services = projectSelect.value ? serviceOptions.filter(option => serviceIds.includes(option.value)) : [];
      replaceOptions(serviceSelect, projectSelect.value ? 'Service / workstream' : 'Select project first', services);
      serviceSelect.disabled = !projectSelect.value || !serviceIds.length;
      if (services.some(option => option.value === currentService)) serviceSelect.value = currentService;
      refreshTaskStages();
    };
    projectSelect.addEventListener('change', refreshTaskServices);
    serviceSelect.addEventListener('change', refreshTaskStages);
    refreshTaskServices();
  }

  const taskWorkspace = document.querySelector('[data-task-workspace]');
  if (taskWorkspace) {
    const taskRows = [...taskWorkspace.querySelectorAll('[data-task-row]')];
    const tasks = taskRows.map(row => ({
      id: row.dataset.id,
      title: row.dataset.title,
      client: row.dataset.client || 'No client',
      project: row.dataset.project || 'Independent work',
      service: row.dataset.service || 'General',
      stage: row.dataset.stage || 'Unstaged',
      owner: row.dataset.owner || 'Unassigned',
      status: row.dataset.status || 'Not started',
      priority: row.dataset.priority || 'Medium',
      progress: Number(row.dataset.progress || 0),
      hours: row.dataset.hours || '1',
      approval: row.dataset.approval === '1',
      due: row.dataset.due,
      url: row.dataset.url || '#',
    }));
    const buttons = [...taskWorkspace.querySelectorAll('[data-task-view-mode]')];
    const views = [...taskWorkspace.querySelectorAll('[data-task-view]')];
    const board = taskWorkspace.querySelector('[data-task-view="board"]');
    const calendar = taskWorkspace.querySelector('[data-task-view="calendar"]');
    let calendarDate = new Date();

    const renderTaskBoard = () => {
      const preferred = ['Not started', 'Working', 'Internal Review', 'Client Review', 'Approved', 'Completed'];
      const statuses = [...preferred.filter(status => tasks.some(task => task.status === status)), ...new Set(tasks.map(task => task.status).filter(status => !preferred.includes(status)))];
      board.innerHTML = tasks.length ? `<div class="board-grid">${statuses.map(status => {
        const cards = tasks.filter(task => task.status === status);
        return `<section class="board-column"><header><span class="status ${slug(status)}">${escapeHtml(status)}</span><b>${cards.length}</b></header><div>${cards.map(task => `<a class="board-card" href="${escapeHtml(task.url)}"><strong>${escapeHtml(task.title)}</strong><p>${escapeHtml(task.client)} · ${escapeHtml(task.project)}</p><div><span class="priority ${slug(task.priority)}">${escapeHtml(task.priority)}</span><small>${escapeHtml(task.owner)}</small></div><div class="board-card-foot"><small>${task.due ? `Due ${escapeHtml(task.due)}` : 'No due date'}</small><b>${task.progress}%</b></div></a>`).join('')}</div></section>`;
      }).join('')}</div>` : '<div class="view-empty"><strong>No work yet</strong><p>Create a task or service-driven project.</p></div>';
    };

    const renderTaskCalendar = () => {
      const year = calendarDate.getFullYear();
      const month = calendarDate.getMonth();
      const firstDay = new Date(year, month, 1);
      const daysInMonth = new Date(year, month + 1, 0).getDate();
      const startOffset = (firstDay.getDay() + 6) % 7;
      const byDate = new Map();
      tasks.filter(task => task.due).forEach(task => {
        if (!byDate.has(task.due)) byDate.set(task.due, []);
        byDate.get(task.due).push(task);
      });
      const cells = [];
      for (let i = 0; i < startOffset; i += 1) cells.push('<div class="calendar-day outside"></div>');
      for (let day = 1; day <= daysInMonth; day += 1) {
        const key = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        const dueTasks = byDate.get(key) || [];
        const isToday = key === new Date().toLocaleDateString('en-CA');
        cells.push(`<div class="calendar-day ${isToday ? 'today' : ''}"><span>${day}</span><div>${dueTasks.map(task => `<a href="${escapeHtml(task.url)}" title="${escapeHtml(task.title)}"><i class="priority-dot ${slug(task.priority)}"></i><span>${escapeHtml(task.title)}</span><small>${escapeHtml(task.owner)}</small></a>`).join('')}</div></div>`);
      }
      const monthName = firstDay.toLocaleDateString(undefined, {month: 'long', year: 'numeric'});
      calendar.innerHTML = `<div class="calendar-toolbar"><button type="button" data-task-calendar-prev aria-label="Previous month"><i data-lucide="chevron-left"></i></button><strong>${escapeHtml(monthName)}</strong><button type="button" data-task-calendar-today>Today</button><button type="button" data-task-calendar-next aria-label="Next month"><i data-lucide="chevron-right"></i></button></div><div class="calendar-weekdays">${['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].map(day => `<span>${day}</span>`).join('')}</div><div class="calendar-grid">${cells.join('')}</div>`;
      calendar.querySelector('[data-task-calendar-prev]').addEventListener('click', () => { calendarDate = new Date(year, month - 1, 1); renderTaskCalendar(); });
      calendar.querySelector('[data-task-calendar-next]').addEventListener('click', () => { calendarDate = new Date(year, month + 1, 1); renderTaskCalendar(); });
      calendar.querySelector('[data-task-calendar-today]').addEventListener('click', () => { calendarDate = new Date(); renderTaskCalendar(); });
      if (window.lucide) lucide.createIcons();
    };

    const activateTaskView = mode => {
      buttons.forEach(button => {
        const selected = button.dataset.taskViewMode === mode;
        button.classList.toggle('active', selected);
        button.setAttribute('aria-selected', selected ? 'true' : 'false');
      });
      views.forEach(view => view.hidden = view.dataset.taskView !== mode);
      if (mode === 'board') renderTaskBoard();
      if (mode === 'calendar') renderTaskCalendar();
      localStorage.setItem('arcturide-task-view', mode);
    };
    taskRows.forEach(row => {
      row.addEventListener('click', event => {
        if (event.target.closest('a,button,input,select,textarea,label,form')) return;
        if (row.dataset.url) window.location.href = row.dataset.url;
      });
    });
    buttons.forEach(button => button.addEventListener('click', () => activateTaskView(button.dataset.taskViewMode)));
    const requestedView = taskWorkspace.dataset.initialTaskView;
    const savedView = localStorage.getItem('arcturide-task-view');
    activateTaskView(['list', 'board', 'calendar'].includes(requestedView) ? requestedView : ['list', 'board', 'calendar'].includes(savedView) ? savedView : 'list');
  }

  document.querySelectorAll('.prompt-chips button').forEach(button => button.addEventListener('click', () => {
    const form = document.querySelector('.ai-form');
    form.querySelector('textarea').value = button.textContent;
    form.requestSubmit();
  }));
  document.querySelector('.ai-form')?.addEventListener('submit', async event => {
    event.preventDefault();
    const input = event.currentTarget.querySelector('textarea');
    const box = document.querySelector('.ai-conversation');
    const question = input.value.trim();
    if (!question) return;
    box.insertAdjacentHTML('beforeend', `<div class="user-message"><p>${escapeHtml(question)}</p></div><div class="ai-message loading"><p>Reading the workspace…</p></div>`);
    input.value = '';
    box.scrollTop = box.scrollHeight;
    try {
      const response = await fetch('/api/ai', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({question})});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Workspace request failed');
      const source = data.provider === 'gemini' ? `Gemini · ${data.model}` : 'Local workspace fallback';
      box.querySelector('.loading').innerHTML = `<strong>Workspace answer</strong><span class="ai-source ${data.provider}">${escapeHtml(source)}</span><p>${escapeHtml(data.answer).replace(/\n/g, '<br>')}</p><small>${(data.references || []).map(escapeHtml).join(' · ')}</small>`;
    } catch {
      box.querySelector('.loading').innerHTML = '<p>I could not read the workspace just now.</p>';
    }
    box.querySelector('.loading')?.classList.remove('loading');
    box.scrollTop = box.scrollHeight;
  });

  document.addEventListener('keydown', event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      document.querySelector('.global-search input')?.focus();
    }
    if (event.key === 'Escape') {
      document.querySelectorAll('.open').forEach(element => element.classList.remove('open'));
      body.classList.remove('nav-open');
    }
  });
});
