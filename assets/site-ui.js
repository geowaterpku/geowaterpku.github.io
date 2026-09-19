/* Local, progressive navigation and bibliography controls. No content is sent
   to a third party by this module. Scientific records are never rewritten. */
document.addEventListener('DOMContentLoaded', () => {
  const header = document.querySelector('.gw-header');
  const menu = header?.querySelector('.gw-menu');
  const closeMenu = () => {
    header?.classList.remove('is-open');
    menu?.setAttribute('aria-expanded', 'false');
  };
  menu?.addEventListener('click', () => {
    const open = header.classList.toggle('is-open');
    menu.setAttribute('aria-expanded', String(open));
  });
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    if (header?.classList.contains('is-open')) { closeMenu(); menu.focus(); }
    header?.querySelectorAll('details[open]').forEach(details => {
      details.open = false;
      if (!window.matchMedia('(max-width:1180px)').matches) details.querySelector('summary')?.focus();
    });
  });
  document.addEventListener('click', event => {
    if (header && !header.contains(event.target)) closeMenu();
    if (event.target.closest('.gw-nav a')) closeMenu();
  });
  window.matchMedia('(max-width:1180px)').addEventListener('change', closeMenu);

  // Promote the existing enquiry section before secondary location media.
  const contactDetails = document.querySelector('.contact-dual-column-layout');
  const enquiry = document.querySelector('.gw-contact-paths');
  if (contactDetails && enquiry) contactDetails.before(enquiry);
  const campusVideo = document.querySelector('.contact-page video');
  if (campusVideo && !campusVideo.getAttribute('poster')) campusVideo.setAttribute('poster', 'assets/contact/building.webp');
  document.querySelector('.contact-page iframe')?.setAttribute('title', 'Remote Sensing Building location at Peking University');

  const input = document.getElementById('publication-search');
  const topic = document.getElementById('publication-topic');
  const year = document.getElementById('publication-year');
  const status = document.getElementById('publication-results');
  const papers = [...document.querySelectorAll('.publications-content .pub-item')];
  const groups = [...document.querySelectorAll('.publications-content .year-block')];
  function filter() {
    if (!input) return;
    const words = input.value.toLowerCase().trim().split(/\s+/).filter(Boolean);
    const active = words.length || topic.value || year.value;
    let count = 0;
    for (const paper of papers) {
      const match = words.every(word => paper.dataset.search.includes(word)) &&
        (!topic.value || paper.dataset.topics.split('|').includes(topic.value)) &&
        (!year.value || paper.dataset.group === year.value);
      paper.hidden = !match;
      if (match) count++;
    }
    for (const group of groups) {
      group.hidden = ![...group.querySelectorAll('.pub-item')].some(paper => !paper.hidden);
      if (active && !group.hidden) group.open = true;
    }
    const selected = document.querySelector('.gw-selected-publications');
    if (selected) selected.hidden = Boolean(active);
    status.textContent = count ? `${count} of ${papers.length} entries match. Topic filters use title keywords.` : 'No matches. Reset the filters or try another term.';
  }
  function reset() {
    if (!input) return;
    input.value = ''; topic.value = ''; year.value = '';
    groups.forEach(group => { group.open = true; });
    filter();
  }
  if (input && topic && year && status) {
    input.value = new URLSearchParams(window.location.search).get('q') || '';
    input.addEventListener('input', filter);
    topic.addEventListener('change', filter);
    year.addEventListener('change', filter);
    const resetButton = document.getElementById('publication-reset');
    const expandButton = document.getElementById('publication-expand');
    const collapseButton = document.getElementById('publication-collapse');
    resetButton.textContent = 'Reset'; resetButton.setAttribute('aria-label', 'Reset publication filters');
    expandButton.textContent = 'Expand all'; expandButton.setAttribute('aria-label', 'Expand all publication years');
    collapseButton.textContent = 'Collapse all'; collapseButton.setAttribute('aria-label', 'Collapse all publication years');
    resetButton.addEventListener('click', reset);
    expandButton.addEventListener('click', () => groups.forEach(group => { group.open = true; }));
    collapseButton.addEventListener('click', () => groups.forEach(group => { group.open = false; }));
    filter();
  }
  function revealTarget() {
    const target = document.getElementById(window.location.hash.slice(1));
    if (!target) return;
    if (target.closest('.publications-content') && target.closest('[hidden]')) reset();
    for (let node = target; node && node !== document.body; node = node.parentElement) {
      if (node.tagName === 'DETAILS') node.open = true;
    }
    target.scrollIntoView({block:'start', behavior:'auto'});
  }
  window.addEventListener('hashchange', revealTarget);
  if (window.location.hash) revealTarget();
  document.querySelectorAll('.publications-sidebar a').forEach(link => {
    link.addEventListener('click', () => {
      const target = document.getElementById(link.hash.slice(1));
      if (target?.hidden) reset();
      if (target?.tagName === 'DETAILS') target.open = true;
    });
  });
  // A visible, selectable field keeps citation export usable without requiring
  // access to the system clipboard.
  document.querySelectorAll('[data-copy]').forEach(button => {
    button.textContent = 'Select citation';
    button.addEventListener('click', () => {
      let field = button.nextElementSibling;
      if (!field?.classList.contains('gw-citation-text')) {
        field = document.createElement('textarea');
        field.className = 'gw-citation-text';
        field.readOnly = true;
        field.setAttribute('aria-label', 'Citation text');
        field.rows = 5;
        field.value = button.dataset.copy;
        button.after(field);
      }
      field.focus(); field.select();
    });
  });
  let printState = [];
  window.addEventListener('beforeprint', () => {
    printState = [...document.querySelectorAll('main details')].map(node => [node, node.open]);
    printState.forEach(([node]) => { node.open = true; });
  });
  window.addEventListener('afterprint', () => printState.forEach(([node, open]) => { node.open = open; }));
});
