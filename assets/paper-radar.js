/* Paper Radar: compact, accessible reading with source metadata preserved. */
document.addEventListener('DOMContentLoaded', () => {
  'use strict';
  const list = document.getElementById('radar-list');
  const status = document.getElementById('radar-status');
  const filters = document.getElementById('radar-filters');
  const search = document.getElementById('radar-search');
  const windowSelect = document.getElementById('radar-window');
  const dateInput = document.getElementById('radar-date');
  if (!list || !status || !filters) return;
  let payload = null;
  let keyword = 'All';
  const clean = value => {
    let result = Array.isArray(value) ? value.join(', ') : String(value || '');
    for (let i = 0; i < 2; i++) {
      const parsed = new DOMParser().parseFromString(result, 'text/html');
      const next = parsed.body.textContent || '';
      if (next === result) break;
      result = next;
    }
    return result.replace(/\s+/g, ' ').trim();
  };
  const el = (name, className, value) => {
    const node = document.createElement(name);
    if (className) node.className = className;
    if (value !== undefined) node.textContent = value;
    return node;
  };
  const validLink = value => {
    try {
      const url = new URL(value);
      return ['https:', 'http:'].includes(url.protocol) ? url.href : null;
    } catch { return null; }
  };
  const formatDate = value => {
    const date = new Date(`${value}T12:00:00Z`);
    return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('en', {
      timeZone:'UTC', month:'short', day:'numeric', year:'numeric'
    }).format(date);
  };
  const allDates = () => {
    const end = new Date(`${payload?.targetDate}T12:00:00Z`);
    if (Number.isNaN(end.getTime())) return [];
    const count = Math.min(90, Math.max(1, Number(payload.windowDays) || 30));
    return Array.from({length:count}, (_, index) => {
      const day = new Date(end);
      day.setUTCDate(day.getUTCDate() - index);
      return day.toISOString().slice(0,10);
    });
  };
  function renderFilters() {
    filters.replaceChildren();
    const words = ['All', ...new Set((payload?.keywords || []).filter(value => typeof value === 'string'))];
    words.forEach(word => {
      const button = el('button', `radar-filter${word === keyword ? ' is-active' : ''}`, word);
      button.type = 'button';
      button.setAttribute('aria-pressed', String(word === keyword));
      button.addEventListener('click', () => { keyword = word; renderFilters(); render(); });
      filters.appendChild(button);
    });
  }
  function paperCard(paper) {
    const card = el('article', 'radar-item');
    const row = el('div', 'radar-title-row');
    const title = el('h3', 'radar-title');
    const link = validLink(paper.link);
    if (link) {
      const anchor = el('a', '', clean(paper.title) || 'Untitled paper');
      anchor.href = link; anchor.target = '_blank'; anchor.rel = 'noopener noreferrer';
      title.appendChild(anchor);
    } else title.textContent = clean(paper.title) || 'Untitled paper';
    const tags = el('div', 'radar-tags');
    (paper.matchedKeywords || []).forEach(word => tags.appendChild(el('span', 'radar-tag', clean(word))));
    row.append(title, tags);
    card.append(row, el('p', 'radar-authors', clean(paper.authors) || 'Authors not listed'),
      el('p', 'radar-journal', clean(paper.journal) || 'Publication venue not listed'));
    const summary = String(paper.summaryZh || '').trim();
    if (summary) {
      const lines = summary.split(/\r?\n+/).map(clean).filter(Boolean);
      const preview = el('p', 'radar-preview', (lines[0] || '').slice(0, 180) + ((lines[0] || '').length > 180 ? '…' : ''));
      preview.lang = 'zh-CN';
      card.appendChild(preview);
      const details = el('details', 'radar-summary');
      const caption = el('summary', '', paper.summarySource === 'title-only' ? '展开 AI 中文导读 · 仅基于标题' : '展开 AI 中文导读');
      caption.lang = 'zh-CN'; details.appendChild(caption);
      if (paper.summarySource === 'title-only') {
        const note = el('p', 'radar-summary__caveat', '未获取到可靠英文摘要；该导读仅根据标题概括研究主题，不应视为论文结论。');
        note.lang = 'zh-CN'; details.appendChild(note);
      }
      lines.forEach(line => {
        const p = el('p', 'radar-summary__text', line);
        p.lang = 'zh-CN'; details.appendChild(p);
      });
      card.appendChild(details);
    }
    const sources = el('div', 'gw-radar-source');
    sources.appendChild(el('span', '', `Published ${formatDate(paper.publicationDate)}`));
    if (link) {
      const source = el('a', '', 'Read original paper ↗');
      source.href = link; source.target = '_blank'; source.rel = 'noopener noreferrer';
      sources.appendChild(source);
    }
    card.appendChild(sources);
    return card;
  }
  function render() {
    if (!payload) return;
    list.replaceChildren();
    const archiveDates = allDates();
    let dates = archiveDates.slice(0, windowSelect?.value === '30' ? archiveDates.length : 7);
    if (dateInput?.value) dates = archiveDates.includes(dateInput.value) ? [dateInput.value] : [];
    const terms = clean(search?.value).toLocaleLowerCase().split(' ').filter(Boolean);
    const activeFilter = keyword !== 'All' || terms.length > 0;
    const allPapers = Array.isArray(payload.papers) ? payload.papers : [];
    const filtered = allPapers.filter(paper =>
      dates.includes(paper.publicationDate) &&
      (keyword === 'All' || (paper.matchedKeywords || []).includes(keyword)) &&
      terms.every(term => clean(`${paper.title} ${clean(paper.authors)} ${paper.journal}`).toLocaleLowerCase().includes(term))
    );
    const updated = payload.generatedAt ? new Date(payload.generatedAt) : null;
    const stamp = updated && !Number.isNaN(updated.getTime()) ? ` · Updated ${updated.toLocaleString('en', {dateStyle:'medium', timeStyle:'short'})}` : '';
    status.textContent = `${filtered.length} matching papers across ${dates.length} publication days${stamp}`;
    if (!dates.length) {
      list.appendChild(el('p', 'radar-empty', archiveDates.length ? 'This date is outside the retained archive. Choose another date or reset filters.' : 'The archive is awaiting its first dated crawl.'));
      return;
    }
    if (activeFilter && !filtered.length) list.appendChild(el('p', 'radar-empty', 'No matching papers in this window. Try the full archive or reset the filters.'));
    dates.forEach(date => {
      const papers = filtered.filter(paper => paper.publicationDate === date).sort((a,b) => clean(a.title).localeCompare(clean(b.title)));
      const day = el('details', 'radar-day');
      day.id = `radar-day-${date}`;
      day.open = papers.length > 0 || dates.length === 1;
      const heading = el('summary', 'radar-day__header');
      const dateTitle = el('span', 'radar-day__date', formatDate(date));
      const count = el('span', 'radar-day__count', `${papers.length} paper${papers.length === 1 ? '' : 's'}`);
      heading.append(dateTitle, count); day.appendChild(heading);
      papers.forEach(paper => day.appendChild(paperCard(paper)));
      if (!papers.length) {
        const crawl = payload.crawlHistory?.[date];
        const originalCount = allPapers.filter(paper => paper.publicationDate === date).length;
        const message = activeFilter && originalCount ? 'No papers match these filters on this date.' :
          crawl?.status === 'success' ? 'Checked: no matching papers were returned for this date.' :
          crawl?.status === 'failed' || crawl?.status === 'error' ? 'The crawl did not complete successfully for this date.' : 'This date has not yet been checked successfully.';
        day.appendChild(el('p', 'radar-day__empty', message));
      }
      list.appendChild(day);
    });
  }
  search?.addEventListener('input', render);
  windowSelect?.addEventListener('change', () => { if (dateInput) dateInput.value = ''; render(); });
  dateInput?.addEventListener('change', render);
  document.getElementById('radar-reset')?.addEventListener('click', () => {
    if (search) search.value = '';
    if (windowSelect) windowSelect.value = '7';
    if (dateInput) dateInput.value = '';
    keyword = 'All'; renderFilters(); render();
  });
  document.getElementById('radar-expand')?.addEventListener('click', () => list.querySelectorAll('.radar-day').forEach(day => { day.open = true; }));
  document.getElementById('radar-collapse')?.addEventListener('click', () => list.querySelectorAll('.radar-day').forEach(day => { day.open = false; }));
  async function load() {
    status.textContent = 'Loading paper archive…';
    try {
      const response = await fetch('assets/data/paper-radar.json', {cache:'no-cache'});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (!data || !Array.isArray(data.papers)) throw new Error('Invalid paper archive');
      payload = data;
      const dates = allDates();
      if (dateInput && dates.length) { dateInput.min = dates[dates.length - 1]; dateInput.max = dates[0]; }
      renderFilters(); render();
    } catch (error) {
      status.textContent = 'Paper archive temporarily unavailable';
      list.replaceChildren(el('p', 'radar-empty', 'The paper data could not be loaded. You can retry without leaving this page.'));
      const retry = el('button', 'gw-button', 'Retry loading');
      retry.type = 'button'; retry.addEventListener('click', load);
      list.appendChild(retry);
      console.warn('Paper Radar:', error.message);
    }
  }
  load();
});
