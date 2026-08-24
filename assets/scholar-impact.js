(() => {
  const card = document.querySelector('[data-scholar-impact]');
  if (!card) return;

  if (document.body.classList.contains('cv-page') && !document.getElementById('cv-scholar-impact-grid-fix')) {
    const layoutStyle = document.createElement('style');
    layoutStyle.id = 'cv-scholar-impact-grid-fix';
    layoutStyle.textContent = `
      .cv-page .cv-pi-impact-row.cv-pi-impact-row{
        row-gap:0!important;
        column-gap:clamp(24px,3vw,40px)!important;
      }
      .cv-page .cv-pi-impact-row .scholar-impact-card{
        display:contents!important;
      }
      .cv-page .cv-pi-impact-row .headshot{
        grid-column:1!important;
        grid-row:1 / span 3!important;
        align-self:stretch!important;
        width:100%!important;
        height:100%!important;
        max-height:none!important;
        object-fit:cover!important;
        object-position:center top!important;
      }
      .cv-page .cv-pi-impact-row .scholar-impact-card__header{
        grid-column:2!important;
        grid-row:1!important;
        margin:0!important;
        padding:22px 22px 20px!important;
        border:1px solid #d6e6ee!important;
        border-bottom:0!important;
        border-radius:16px 16px 0 0!important;
        background:linear-gradient(145deg,#fff 0%,#f4f9fc 100%)!important;
      }
      .cv-page .cv-pi-impact-row .scholar-impact-card__primary{
        grid-column:2!important;
        grid-row:2!important;
        padding:0 22px 18px!important;
        border-right:1px solid #d6e6ee!important;
        border-bottom:1px solid #dbe8ee!important;
        border-left:1px solid #d6e6ee!important;
        background:linear-gradient(145deg,#fff 0%,#f4f9fc 100%)!important;
      }
      .cv-page .cv-pi-impact-row .scholar-impact-card__metrics{
        grid-column:2!important;
        grid-row:3!important;
        padding:17px 22px 18px!important;
        border-right:1px solid #d6e6ee!important;
        border-bottom:1px solid #dbe8ee!important;
        border-left:1px solid #d6e6ee!important;
        border-radius:0 0 16px 16px!important;
        background:linear-gradient(145deg,#fff 0%,#f4f9fc 100%)!important;
        box-shadow:0 14px 36px rgba(8,56,82,.08)!important;
      }
      .cv-page .cv-pi-impact-row .scholar-impact-card__trend{
        grid-column:1 / -1!important;
        grid-row:4!important;
        margin-top:22px!important;
        padding:20px 22px 10px!important;
        border:1px solid #d6e6ee!important;
        border-bottom:0!important;
        border-radius:16px 16px 0 0!important;
        background:linear-gradient(145deg,#fff 0%,#f4f9fc 100%)!important;
        box-shadow:0 14px 36px rgba(8,56,82,.08)!important;
      }
      .cv-page .cv-pi-impact-row .scholar-impact-chart{
        height:88px!important;
      }
      .cv-page .cv-pi-impact-row .scholar-impact-card__footer{
        grid-column:1 / -1!important;
        grid-row:5!important;
        margin:0!important;
        padding:4px 22px 18px!important;
        border-right:1px solid #d6e6ee!important;
        border-bottom:1px solid #d6e6ee!important;
        border-left:1px solid #d6e6ee!important;
        border-radius:0 0 16px 16px!important;
        background:linear-gradient(145deg,#fff 0%,#f4f9fc 100%)!important;
      }
      @media(max-width:760px){
        .cv-page .cv-pi-impact-row.cv-pi-impact-row{
          grid-template-columns:1fr!important;
          row-gap:0!important;
        }
        .cv-page .cv-pi-impact-row .headshot{
          grid-column:1!important;
          grid-row:auto!important;
          align-self:start!important;
          width:100%!important;
          height:auto!important;
          max-height:none!important;
          object-fit:initial!important;
          margin-bottom:22px!important;
        }
        .cv-page .cv-pi-impact-row .scholar-impact-card__header,
        .cv-page .cv-pi-impact-row .scholar-impact-card__primary,
        .cv-page .cv-pi-impact-row .scholar-impact-card__metrics,
        .cv-page .cv-pi-impact-row .scholar-impact-card__trend,
        .cv-page .cv-pi-impact-row .scholar-impact-card__footer{
          grid-column:1!important;
          grid-row:auto!important;
        }
      }
    `;
    document.head.appendChild(layoutStyle);
  }

  const citationsEl = card.querySelector('[data-scholar-citations]');
  const hIndexEl = card.querySelector('[data-scholar-h-index]');
  const i10IndexEl = card.querySelector('[data-scholar-i10-index]');
  const chartEl = card.querySelector('[data-scholar-chart]');
  const rangeEl = card.querySelector('[data-scholar-range]');
  const updatedEl = card.querySelector('[data-scholar-updated]');
  const statusEl = card.querySelector('[data-scholar-status]');
  const profileLink = card.querySelector('[data-scholar-profile]');
  const formatter = new Intl.NumberFormat('en-US');

  const setPending = (message) => {
    card.classList.add('is-pending');
    if (statusEl) statusEl.textContent = message;
  };

  const renderChart = (history) => {
    if (!chartEl) return;
    chartEl.replaceChildren();

    const points = Array.isArray(history)
      ? history.filter(point => Number.isFinite(Number(point?.year)) && Number.isFinite(Number(point?.citations))).slice(-8)
      : [];

    if (!points.length) {
      chartEl.setAttribute('aria-label', 'Citation history is not available yet.');
      if (rangeEl) rangeEl.textContent = 'Syncing';
      return;
    }

    const maxValue = Math.max(...points.map(point => Number(point.citations)), 1);
    points.forEach((point, index) => {
      const value = Number(point.citations);
      const year = Number(point.year);
      const formattedValue = formatter.format(value);
      const bar = document.createElement('span');
      const height = Math.max(8, Math.round((value / maxValue) * 100));

      bar.className = 'scholar-impact-chart__bar';
      if (index === 0) bar.classList.add('is-first');
      if (index === points.length - 1) bar.classList.add('is-last');
      bar.style.setProperty('--bar-height', `${height}%`);
      bar.tabIndex = 0;
      bar.setAttribute('role', 'img');
      bar.setAttribute('aria-label', `${year}: ${formattedValue} citations`);

      const tooltip = document.createElement('span');
      tooltip.className = 'scholar-impact-chart__tooltip';
      tooltip.setAttribute('aria-hidden', 'true');

      const tooltipYear = document.createElement('span');
      tooltipYear.className = 'scholar-impact-chart__tooltip-year';
      tooltipYear.textContent = String(year);

      const tooltipValue = document.createElement('strong');
      tooltipValue.className = 'scholar-impact-chart__tooltip-value';
      tooltipValue.textContent = `${formattedValue} citations`;

      tooltip.append(tooltipYear, tooltipValue);
      bar.appendChild(tooltip);
      chartEl.appendChild(bar);
    });

    chartEl.setAttribute('aria-label', 'Google Scholar citations by year. Hover or focus a bar to see its value.');
    if (rangeEl) rangeEl.textContent = `${points[0].year}–${points[points.length - 1].year}`;
  };

  const formatUpdated = (value) => {
    if (!value) return 'Awaiting first sync';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return 'Recently updated';
    return `Updated ${new Intl.DateTimeFormat('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hourCycle: 'h23',
      timeZone: 'Asia/Shanghai'
    }).format(date)} Beijing Time (UTC+8)`;
  };

  fetch(`assets/data/scholar.json?v=${Date.now()}`, { cache: 'no-store' })
    .then(response => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .then(data => {
      if (profileLink && data.profileUrl) profileLink.href = data.profileUrl;

      const citations = Number(data.citations);
      const hIndex = Number(data.hIndex);
      const i10Index = Number(data.i10Index);
      const hasMetrics = Number.isFinite(citations) && Number.isFinite(hIndex) && Number.isFinite(i10Index)
        && data.citations !== null && data.hIndex !== null && data.i10Index !== null;

      if (!hasMetrics) {
        setPending('Sync pending');
        if (updatedEl) updatedEl.textContent = 'Awaiting first sync';
        renderChart([]);
        return;
      }

      card.classList.remove('is-pending');
      if (citationsEl) citationsEl.textContent = formatter.format(citations);
      if (hIndexEl) hIndexEl.textContent = formatter.format(hIndex);
      if (i10IndexEl) i10IndexEl.textContent = formatter.format(i10Index);
      if (statusEl) statusEl.textContent = 'Live snapshot';
      if (updatedEl) updatedEl.textContent = formatUpdated(data.updatedAt);
      renderChart(data.history);
    })
    .catch(() => {
      setPending('Snapshot unavailable');
      if (updatedEl) updatedEl.textContent = 'Google Scholar link remains available';
      renderChart([]);
    });
})();
