document.addEventListener('DOMContentLoaded', () => {
  const list = document.getElementById('radar-list');
  const status = document.getElementById('radar-status');
  const filters = document.getElementById('radar-filters');
  if (!list || !status || !filters) return;

  let payload = null;
  let activeKeyword = 'All';

  const formatUpdatedAt = (value) => {
    if (!value) return 'Awaiting first sync';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return 'Updated daily';
    return `Updated ${new Intl.DateTimeFormat('en', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    }).format(date)}`;
  };

  const renderFilters = () => {
    filters.replaceChildren();
    const keywords = ['All', ...(payload?.keywords || [])];
    keywords.forEach(keyword => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = `radar-filter${keyword === activeKeyword ? ' is-active' : ''}`;
      button.textContent = keyword;
      button.setAttribute('aria-pressed', keyword === activeKeyword ? 'true' : 'false');
      button.addEventListener('click', () => {
        activeKeyword = keyword;
        renderFilters();
        renderPapers();
      });
      filters.appendChild(button);
    });
  };

  const renderPapers = () => {
    list.replaceChildren();
    const allPapers = Array.isArray(payload?.papers) ? payload.papers : [];
    const papers = activeKeyword === 'All'
      ? allPapers
      : allPapers.filter(paper => (paper.matchedKeywords || []).includes(activeKeyword));

    status.textContent = `${papers.length} paper${papers.length === 1 ? '' : 's'} · ${formatUpdatedAt(payload?.generatedAt)}`;

    if (!papers.length) {
      const empty = document.createElement('div');
      empty.className = 'radar-empty';
      empty.textContent = allPapers.length
        ? 'No papers in this keyword filter yet.'
        : 'Paper Radar is ready. The first daily Google Scholar sync will populate this page.';
      list.appendChild(empty);
      return;
    }

    papers.forEach(paper => {
      const item = document.createElement('a');
      item.className = 'radar-item';
      item.href = paper.link;
      item.target = '_blank';
      item.rel = 'noopener noreferrer';

      const title = document.createElement('h3');
      title.className = 'radar-title';
      title.textContent = paper.title || 'Untitled paper';

      const authors = document.createElement('p');
      authors.className = 'radar-authors';
      authors.textContent = paper.authors || 'Authors not listed';

      const journal = document.createElement('p');
      journal.className = 'radar-journal';
      journal.textContent = paper.journal || 'Publication venue not listed';

      item.append(title, authors, journal);
      list.appendChild(item);
    });
  };

  fetch(`assets/data/paper-radar.json?v=${Date.now()}`, { cache: 'no-store' })
    .then(response => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .then(data => {
      payload = data;
      renderFilters();
      renderPapers();
    })
    .catch(error => {
      console.error('Paper Radar data load failed:', error);
      status.textContent = 'Data temporarily unavailable';
      const empty = document.createElement('div');
      empty.className = 'radar-empty';
      empty.textContent = 'Paper Radar data could not be loaded. Please try again later.';
      list.replaceChildren(empty);
    });
});
