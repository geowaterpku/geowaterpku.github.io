(() => {
  'use strict';

  const D3_URL = 'https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js';
  const TOPOJSON_URL = 'https://cdn.jsdelivr.net/npm/topojson-client@3/dist/topojson-client.min.js';
  const WORLD_URL = 'https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json';
  const SVG_NS = 'http://www.w3.org/2000/svg';

  const COUNTRY_ALIASES = new Map([
    ['united states of america', 'united states'],
    ['dem rep congo', 'democratic republic of the congo'],
    ['congo', 'republic of the congo'],
    ['dominican rep', 'dominican republic'],
    ['central african rep', 'central african republic'],
    ['eq guinea', 'equatorial guinea'],
    ['w sahara', 'western sahara'],
    ['falkland is', 'falkland islands'],
    ['fr s antarctic lands', 'french southern and antarctic lands'],
    ['bosnia and herz', 'bosnia and herzegovina'],
    ['s sudan', 'south sudan'],
    ['cote d ivoire', 'ivory coast'],
    ['czech republic', 'czechia'],
    ['viet nam', 'vietnam'],
    ['the bahamas', 'bahamas'],
    ['the gambia', 'gambia'],
    ['republic of macedonia', 'north macedonia'],
    ['macedonia', 'north macedonia'],
    ['swaziland', 'eswatini'],
    ['turkiye', 'turkey']
  ]);

  function normalizeCountryName(name) {
    const normalized = String(name || '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .replace(/&/g, ' and ')
      .replace(/[^a-z0-9]+/g, ' ')
      .trim()
      .replace(/\s+/g, ' ');
    return COUNTRY_ALIASES.get(normalized) || normalized;
  }

  function combineChinaTaiwanRows(rows) {
    const chinaKey = normalizeCountryName('China');
    const taiwanKey = normalizeCountryName('Taiwan');
    const chinaVisits = rows
      .filter(row => normalizeCountryName(row.country) === chinaKey)
      .reduce((sum, row) => sum + Number(row.visits || 0), 0);
    const taiwanVisits = rows
      .filter(row => normalizeCountryName(row.country) === taiwanKey)
      .reduce((sum, row) => sum + Number(row.visits || 0), 0);
    const combinedVisits = chinaVisits + taiwanVisits;

    if (combinedVisits <= 0) return rows;

    const mergedRows = rows.filter(row => {
      const key = normalizeCountryName(row.country);
      return key !== chinaKey && key !== taiwanKey;
    });

    mergedRows.push(
      { country: 'China', visits: combinedVisits },
      { country: 'Taiwan', visits: combinedVisits }
    );
    return mergedRows;
  }

  function svgEl(name, attrs = {}) {
    const el = document.createElementNS(SVG_NS, name);
    Object.entries(attrs).forEach(([key, value]) => el.setAttribute(key, String(value)));
    return el;
  }

  function loadScript(src, globalName) {
    if (window[globalName]) return Promise.resolve(window[globalName]);
    return new Promise((resolve, reject) => {
      const existing = document.querySelector(`script[data-visitor-map-lib="${globalName}"]`);
      if (existing) {
        existing.addEventListener('load', () => resolve(window[globalName]), { once: true });
        existing.addEventListener('error', reject, { once: true });
        return;
      }
      const script = document.createElement('script');
      script.src = src;
      script.async = true;
      script.dataset.visitorMapLib = globalName;
      script.onload = () => resolve(window[globalName]);
      script.onerror = () => reject(new Error(`Failed to load ${src}`));
      document.head.appendChild(script);
    });
  }

  function createLegend(shell, maxVisits) {
    let legend = shell.querySelector('.visitor-map-legend');
    if (!legend) {
      legend = document.createElement('div');
      legend.className = 'visitor-map-legend';
      shell.appendChild(legend);
    }
    legend.replaceChildren();

    const label = document.createElement('span');
    label.className = 'visitor-map-legend-label';
    label.textContent = 'Page views';

    const scale = document.createElement('div');
    scale.className = 'visitor-map-legend-scale';

    const low = document.createElement('span');
    low.textContent = '1';
    const bar = document.createElement('span');
    bar.className = 'visitor-map-legend-bar';
    const high = document.createElement('span');
    high.textContent = Number(maxVisits || 1).toLocaleString();

    scale.append(low, bar, high);
    legend.append(label, scale);
  }

  function showTooltip(tooltip, shell, event, row) {
    tooltip.replaceChildren();
    const strong = document.createElement('strong');
    strong.textContent = row.country;
    tooltip.appendChild(strong);
    tooltip.appendChild(document.createElement('br'));
    tooltip.appendChild(document.createTextNode(`${Number(row.visits || 0).toLocaleString()} page views`));
    tooltip.style.display = 'block';
    moveTooltip(tooltip, shell, event);
  }

  function moveTooltip(tooltip, shell, event) {
    const rect = shell.getBoundingClientRect();
    const padding = 12;
    const tooltipRect = tooltip.getBoundingClientRect();
    let left = event.clientX - rect.left + 14;
    let top = event.clientY - rect.top + 14;

    if (left + tooltipRect.width + padding > rect.width) {
      left = event.clientX - rect.left - tooltipRect.width - 14;
    }
    if (top + tooltipRect.height + padding > rect.height) {
      top = event.clientY - rect.top - tooltipRect.height - 14;
    }

    tooltip.style.left = `${Math.max(padding, left)}px`;
    tooltip.style.top = `${Math.max(padding, top)}px`;
  }

  async function initVisitorMap() {
    const svg = document.getElementById('visitor-map');
    const status = document.getElementById('visitor-map-status');
    const totalEl = document.getElementById('visitor-total-count');
    const tooltip = document.getElementById('visitor-map-tooltip');
    const shell = document.querySelector('.visitor-map-shell');
    if (!svg || !status || !totalEl || !tooltip || !shell) return;

    status.textContent = 'Loading visitor geography…';

    try {
      await Promise.all([
        loadScript(D3_URL, 'd3'),
        loadScript(TOPOJSON_URL, 'topojson')
      ]);
    } catch (error) {
      console.error('Visitor map libraries could not be loaded:', error);
      status.textContent = 'The visitor map could not be loaded. Please refresh the page later.';
      return;
    }

    let statsResponse;
    let worldResponse;
    try {
      [statsResponse, worldResponse] = await Promise.all([
        fetch(`assets/contact/visitor-stats.json?ts=${Date.now()}`, { cache: 'no-store' }),
        fetch(WORLD_URL, { cache: 'force-cache' })
      ]);
    } catch (error) {
      console.error('Visitor map request failed:', error);
      status.textContent = 'Visitor statistics could not be loaded. Please refresh the page later.';
      totalEl.textContent = '—';
      return;
    }

    if (!statsResponse.ok || !worldResponse.ok) {
      console.error('Visitor map HTTP error:', statsResponse.status, worldResponse.status);
      status.textContent = 'Visitor statistics are temporarily unavailable.';
      totalEl.textContent = '—';
      return;
    }

    let stats;
    let topology;
    try {
      [stats, topology] = await Promise.all([statsResponse.json(), worldResponse.json()]);
    } catch (error) {
      console.error('Visitor map JSON is invalid:', error);
      status.textContent = 'Visitor statistics are temporarily unavailable.';
      totalEl.textContent = '—';
      return;
    }

    totalEl.textContent = Number(stats.total || 0).toLocaleString();
    const rawRows = Array.isArray(stats.countries)
      ? stats.countries.filter(row => Number(row.visits || 0) > 0)
      : [];
    const rows = combineChinaTaiwanRows(rawRows);

    const statsByCountry = new Map();
    rows.forEach(row => statsByCountry.set(normalizeCountryName(row.country), row));

    const countries = window.topojson.feature(topology, topology.objects.countries);
    const d3 = window.d3;
    const projection = d3.geoNaturalEarth1().fitExtent([[24, 24], [976, 472]], countries);
    const path = d3.geoPath(projection);

    svg.replaceChildren();
    svg.setAttribute('viewBox', '0 0 1000 500');
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');

    const defs = svgEl('defs');
    const oceanGradient = svgEl('linearGradient', { id: 'visitor-ocean-gradient', x1: '0%', y1: '0%', x2: '100%', y2: '100%' });
    oceanGradient.appendChild(svgEl('stop', { offset: '0%', 'stop-color': '#f7fbfc' }));
    oceanGradient.appendChild(svgEl('stop', { offset: '100%', 'stop-color': '#eef6f7' }));
    defs.appendChild(oceanGradient);
    svg.appendChild(defs);

    svg.appendChild(svgEl('rect', {
      x: 0, y: 0, width: 1000, height: 500,
      rx: 18, fill: 'url(#visitor-ocean-gradient)'
    }));

    const graticule = d3.geoGraticule10();
    d3.select(svg)
      .append('path')
      .datum(graticule)
      .attr('class', 'visitor-graticule')
      .attr('d', path);

    const maxVisits = Math.max(...rows.map(row => Number(row.visits || 0)), 1);
    const colorScale = d3.scaleSequentialSqrt()
      .domain([0, maxVisits])
      .interpolator(t => d3.interpolateRgb('#bfe3df', '#0b6f6a')(0.18 + t * 0.82));

    const countryGroup = d3.select(svg)
      .append('g')
      .attr('class', 'visitor-country-layer');

    const countryPaths = countryGroup
      .selectAll('path')
      .data(countries.features)
      .join('path')
      .attr('class', feature => {
        const row = statsByCountry.get(normalizeCountryName(feature.properties && feature.properties.name));
        return row ? 'visitor-country has-data' : 'visitor-country';
      })
      .attr('d', path)
      .attr('fill', feature => {
        const row = statsByCountry.get(normalizeCountryName(feature.properties && feature.properties.name));
        return row ? colorScale(Number(row.visits || 0)) : '#e5edef';
      })
      .attr('stroke', '#ffffff')
      .attr('stroke-width', 0.75)
      .attr('vector-effect', 'non-scaling-stroke')
      .attr('tabindex', feature => statsByCountry.has(normalizeCountryName(feature.properties && feature.properties.name)) ? 0 : null)
      .attr('role', feature => statsByCountry.has(normalizeCountryName(feature.properties && feature.properties.name)) ? 'img' : null)
      .attr('aria-label', feature => {
        const row = statsByCountry.get(normalizeCountryName(feature.properties && feature.properties.name));
        return row ? `${row.country}: ${Number(row.visits || 0).toLocaleString()} page views` : null;
      });

    countryPaths.each(function(feature) {
      const row = statsByCountry.get(normalizeCountryName(feature.properties && feature.properties.name));
      if (!row) return;
      const title = document.createElementNS(SVG_NS, 'title');
      title.textContent = `${row.country}: ${Number(row.visits || 0).toLocaleString()} page views`;
      this.appendChild(title);
    });

    countryPaths
      .on('mouseenter', function(event, feature) {
        const row = statsByCountry.get(normalizeCountryName(feature.properties && feature.properties.name));
        if (!row) return;
        d3.select(this).classed('is-hovered', true).raise();
        showTooltip(tooltip, shell, event, row);
      })
      .on('mousemove', function(event, feature) {
        const row = statsByCountry.get(normalizeCountryName(feature.properties && feature.properties.name));
        if (!row) return;
        moveTooltip(tooltip, shell, event);
      })
      .on('mouseleave', function() {
        d3.select(this).classed('is-hovered', false);
        tooltip.style.display = 'none';
      })
      .on('focus', function() {
        d3.select(this).classed('is-hovered', true).raise();
      })
      .on('blur', function() {
        d3.select(this).classed('is-hovered', false);
        tooltip.style.display = 'none';
      });

    createLegend(shell, maxVisits);

    if (rows.length) {
      status.style.display = 'none';
    } else {
      status.style.display = 'grid';
      status.textContent = 'No Contact page geography data is available for the last 90 days yet.';
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initVisitorMap, { once: true });
  } else {
    initVisitorMap();
  }
})();
