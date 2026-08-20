(() => {
  'use strict';

  const WIDTH = 1000;
  const HEIGHT = 500;
  const LAT_MAX = 85;
  const LAT_MIN = -60;
  const SVG_NS = 'http://www.w3.org/2000/svg';

  const countryCentroids = {"Afghanistan":[33,65],"Albania":[41,20],"Algeria":[28,3],"American Samoa":[-14.33333333,-170],"Angola":[-12.5,18.5],"Anguilla":[18.25,-63.16666666],"Antigua and Barbuda":[17.05,-61.8],"Argentina":[-34,-64],"Armenia":[40,45],"Aruba":[12.5,-69.96666666],"Australia":[-27,133],"Austria":[47.33333333,13.33333333],"Azerbaijan":[40.5,47.5],"Bahrain":[26,50.55],"Bangladesh":[24,90],"Barbados":[13.16666666,-59.53333333],"Belarus":[53,28],"Belgium":[50.83333333,4],"Belize":[17.25,-88.75],"Benin":[9.5,2.25],"Bermuda":[32.33333333,-64.75],"Bhutan":[27.5,90.5],"Bolivia":[-17,-65],"Bosnia and Herzegovina":[44,18],"Botswana":[-22,24],"Brazil":[-10,-55],"British Indian Ocean Territory":[-6,71.5],"Brunei":[4.5,114.66666666],"Bulgaria":[43,25],"Burkina Faso":[13,-2],"Burundi":[-3.5,30],"Cambodia":[13,105],"Cameroon":[6,12],"Canada":[60,-95],"Cape Verde":[16,-24],"Cayman Islands":[19.5,-80.5],"Central African Republic":[7,21],"Chad":[15,19],"Chile":[-30,-71],"China":[35,105],"Christmas Island":[-10.5,105.66666666],"Cocos (Keeling) Islands":[-12.5,96.83333333],"Colombia":[4,-72],"Comoros":[-12.16666666,44.25],"Cook Islands":[-21.23333333,-159.76666666],"Costa Rica":[10,-84],"Croatia":[45.16666666,15.5],"Cuba":[21.5,-80],"Cyprus":[35,33],"Czech Republic":[49.75,15.5],"Czechia":[49.75,15.5],"Democratic Republic of the Congo":[0,25],"Denmark":[56,10],"Djibouti":[11.5,43],"Dominica":[15.41666666,-61.33333333],"Dominican Republic":[19,-70.66666666],"East Timor":[-8.83333333,125.91666666],"Ecuador":[-2,-77.5],"Egypt":[27,30],"El Salvador":[13.83333333,-88.91666666],"Equatorial Guinea":[2,10],"Eritrea":[15,39],"Estonia":[59,26],"Eswatini":[-26.5,31.5],"Ethiopia":[8,38],"Falkland Islands":[-51.75,-59],"Faroe Islands":[62,-7],"Federated States of Micronesia":[6.91666666,158.25],"Fiji":[-18,175],"Finland":[64,26],"France":[46,2],"French Guiana":[4,-53],"French Polynesia":[-15,-140],"French Southern and Antarctic Lands":[-49.25,69.167],"Gabon":[-1,11.75],"Georgia":[42,43.5],"Germany":[51,9],"Ghana":[8,-2],"Gibraltar":[36.13333333,-5.35],"Greece":[39,22],"Greenland":[72,-40],"Grenada":[12.11666666,-61.66666666],"Guadeloupe":[16.25,-61.583333],"Guam":[13.46666666,144.78333333],"Guatemala":[15.5,-90.25],"Guernsey":[49.46666666,-2.58333333],"Guinea":[11,-10],"Guinea-Bissau":[12,-15],"Guyana":[5,-59],"Haiti":[19,-72.41666666],"Heard Island and McDonald Islands":[-53.1,72.51666666],"Honduras":[15,-86.5],"Hong Kong":[22.25,114.16666666],"Hungary":[47,20],"Iceland":[65,-18],"India":[20,77],"Indonesia":[-5,120],"Iran":[32,53],"Iraq":[33,44],"Ireland":[53,-8],"Isle of Man":[54.25,-4.5],"Israel":[31.5,34.75],"Italy":[42.83333333,12.83333333],"Ivory Coast":[8,-5],"Jamaica":[18.25,-77.5],"Japan":[36,138],"Jersey":[49.25,-2.16666666],"Jordan":[31,36],"Kazakhstan":[48,68],"Kenya":[1,38],"Kiribati":[1.41666666,173],"Kuwait":[29.5,45.75],"Kyrgyzstan":[41,75],"Laos":[18,105],"Latvia":[57,25],"Lebanon":[33.83333333,35.83333333],"Lesotho":[-29.5,28.5],"Liberia":[6.5,-9.5],"Libya":[25,17],"Liechtenstein":[47.26666666,9.53333333],"Lithuania":[56,24],"Luxembourg":[49.75,6.16666666],"Macao":[22.16666666,113.55],"Macau":[22.16666666,113.55],"Madagascar":[-20,47],"Malawi":[-13.5,34],"Malaysia":[2.5,112.5],"Maldives":[3.25,73],"Mali":[17,-4],"Malta":[35.83333333,14.58333333],"Marshall Islands":[9,168],"Martinique":[14.666667,-61],"Mauritania":[20,-12],"Mauritius":[-20.28333333,57.55],"Mayotte":[-12.83333333,45.16666666],"Mexico":[23,-102],"Moldova":[47,29],"Monaco":[43.73333333,7.4],"Mongolia":[46,105],"Montserrat":[16.75,-62.2],"Morocco":[32,-5],"Mozambique":[-18.25,35],"Namibia":[-22,17],"Nauru":[-0.53333333,166.91666666],"Nepal":[28,84],"Netherlands":[52.5,5.75],"New Caledonia":[-21.5,165.5],"New Zealand":[-41,174],"Nicaragua":[13,-85],"Niger":[16,8],"Nigeria":[10,8],"Niue":[-19.03333333,-169.86666666],"Norfolk Island":[-29.03333333,167.95],"North Korea":[40,127],"Northern Mariana Islands":[15.2,145.75],"Norway":[62,10],"Oman":[21,57],"Pakistan":[30,70],"Palau":[7.5,134.5],"Panama":[9,-80],"Papua New Guinea":[-6,147],"Paraguay":[-23,-58],"Peru":[-10,-76],"Philippines":[13,122],"Pitcairn Islands":[-25.06666666,-130.1],"Poland":[52,20],"Portugal":[39.5,-8],"Puerto Rico":[18.25,-66.5],"Qatar":[25.5,51.25],"Republic of Macedonia":[41.83333333,22],"Republic of the Congo":[-1,15],"Romania":[46,25],"Russia":[60,100],"Rwanda":[-2,30],"Réunion":[-21.15,55.5],"Saint Helena":[-15.95,-5.7],"Saint Kitts and Nevis":[17.33333333,-62.75],"Saint Lucia":[13.88333333,-60.96666666],"Saint Pierre and Miquelon":[46.83333333,-56.33333333],"Saint Vincent and the Grenadines":[13.25,-61.2],"Samoa":[-13.58333333,-172.33333333],"San Marino":[43.76666666,12.41666666],"Saudi Arabia":[25,45],"Senegal":[14,-14],"Serbia":[44.1305021,16.4284181],"Seychelles":[-4.58333333,55.66666666],"Sierra Leone":[8.5,-11.5],"Singapore":[1.36666666,103.8],"Slovakia":[48.66666666,19.5],"Slovenia":[46.11666666,14.81666666],"Solomon Islands":[-8,159],"Somalia":[10,49],"South Africa":[-29,24],"South Georgia":[-54.5,-37],"South Korea":[37,127.5],"South Sudan":[7,30],"Spain":[40,-4],"Sri Lanka":[7,81],"Sudan":[15,30],"Suriname":[4,-56],"Svalbard and Jan Mayen":[78,20],"Swaziland":[-26.5,31.5],"Sweden":[62,15],"Switzerland":[47,8],"Syria":[35,38],"São Tomé and Príncipe":[1,7],"Taiwan":[23.5,121],"Tajikistan":[39,71],"Tanzania":[-6,35],"Thailand":[15,100],"The Bahamas":[24.25,-76],"The Gambia":[13.46666666,-16.56666666],"Togo":[8,1.16666666],"Tokelau":[-9,-172],"Tonga":[-20,-175],"Trinidad and Tobago":[11,-61],"Tunisia":[34,9],"Turkey":[39,35],"Turkmenistan":[40,60],"Tuvalu":[-8,178],"Türkiye":[39,35],"Uganda":[1,32],"Ukraine":[49,32],"United Arab Emirates":[24,54],"United Kingdom":[54,-2],"United States":[38,-97],"Uruguay":[-33,-56],"Uzbekistan":[41,64],"Vanuatu":[-16,167],"Venezuela":[8,-66],"Viet Nam":[16.16666666,107.83333333],"Vietnam":[16.16666666,107.83333333],"Wallis and Futuna":[-13.3,-176.2],"Western Sahara":[24.5,-13],"Yemen":[15,48],"Zambia":[-15,30],"Zimbabwe":[-20,30]};

  // Deliberately simple, local continent outlines. The visitor bubbles use
  // country centroids, so no runtime mapping/CDN dependency is required.
  const land = [
    [[-168,72],[-150,70],[-140,60],[-132,55],[-125,50],[-124,42],[-117,32],[-106,25],[-97,19],[-88,18],[-82,25],[-80,31],[-75,40],[-66,45],[-60,52],[-65,58],[-80,62],[-100,70],[-125,72],[-145,75],[-168,72]],
    [[-82,12],[-75,7],[-70,2],[-66,-10],[-62,-20],[-58,-30],[-63,-42],[-70,-55],[-75,-45],[-78,-30],[-81,-12],[-82,12]],
    [[-54,83],[-20,80],[-18,70],[-28,60],[-42,58],[-52,65],[-60,75],[-54,83]],
    [[-10,36],[-5,44],[8,51],[20,55],[35,58],[50,55],[65,60],[85,58],[100,62],[120,58],[135,50],[150,48],[165,55],[178,52],[170,42],[155,36],[145,28],[135,20],[125,16],[115,8],[105,5],[98,14],[90,22],[80,26],[70,24],[60,30],[50,30],[42,35],[34,42],[25,40],[18,36],[10,38],[2,36],[-10,36]],
    [[-17,36],[-5,36],[10,32],[22,30],[32,23],[40,12],[45,2],[42,-12],[35,-25],[28,-35],[18,-35],[10,-30],[2,-22],[-5,-5],[-10,10],[-17,20],[-17,36]],
    [[112,-10],[125,-12],[138,-16],[153,-26],[151,-38],[140,-44],[128,-39],[118,-32],[112,-20],[112,-10]],
    [[166,-34],[178,-37],[176,-46],[168,-47],[166,-34]],
    [[130,34],[142,44],[145,38],[140,32],[130,34]],
    [[47,-13],[51,-16],[50,-25],[45,-26],[43,-20],[47,-13]]
  ];

  function project(lon, lat) {
    const x = ((lon + 180) / 360) * WIDTH;
    const y = ((LAT_MAX - lat) / (LAT_MAX - LAT_MIN)) * HEIGHT;
    return [x, y];
  }

  function svgEl(name, attrs = {}) {
    const el = document.createElementNS(SVG_NS, name);
    Object.entries(attrs).forEach(([key, value]) => el.setAttribute(key, String(value)));
    return el;
  }

  function drawBaseMap(svg) {
    svg.replaceChildren();
    svg.setAttribute('viewBox', `0 0 ${WIDTH} ${HEIGHT}`);

    svg.appendChild(svgEl('rect', { x: 0, y: 0, width: WIDTH, height: HEIGHT, fill: '#f7faf9' }));

    const grid = svgEl('g', { stroke: '#e4ece9', 'stroke-width': 0.8, fill: 'none' });
    [-120, -60, 0, 60, 120].forEach(lon => {
      const [x] = project(lon, 0);
      grid.appendChild(svgEl('line', { x1: x, y1: 18, x2: x, y2: HEIGHT - 18 }));
    });
    [-30, 0, 30, 60].forEach(lat => {
      const [, y] = project(0, lat);
      grid.appendChild(svgEl('line', { x1: 18, y1: y, x2: WIDTH - 18, y2: y }));
    });
    svg.appendChild(grid);

    const landGroup = svgEl('g', { fill: '#edf3f1', stroke: '#cbd8d4', 'stroke-width': 1.2, 'stroke-linejoin': 'round' });
    land.forEach(points => {
      const d = points.map(([lon, lat], index) => {
        const [x, y] = project(lon, lat);
        return `${index ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`;
      }).join(' ') + ' Z';
      landGroup.appendChild(svgEl('path', { d }));
    });
    svg.appendChild(landGroup);
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
    tooltip.style.left = `${event.clientX - rect.left + 12}px`;
    tooltip.style.top = `${event.clientY - rect.top + 12}px`;
  }

  async function initVisitorMap() {
    const svg = document.getElementById('visitor-map');
    const status = document.getElementById('visitor-map-status');
    const totalEl = document.getElementById('visitor-total-count');
    const tooltip = document.getElementById('visitor-map-tooltip');
    const shell = document.querySelector('.visitor-map-shell');
    if (!svg || !status || !totalEl || !tooltip || !shell) return;

    drawBaseMap(svg);

    let response;
    try {
      response = await fetch(`assets/contact/visitor-stats.json?ts=${Date.now()}`, { cache: 'no-store' });
    } catch (error) {
      console.error('Visitor statistics request failed:', error);
      status.textContent = 'Visitor statistics could not be loaded. Please refresh the page later.';
      totalEl.textContent = '—';
      return;
    }

    if (!response.ok) {
      console.error('Visitor statistics HTTP error:', response.status);
      status.textContent = 'Visitor statistics are temporarily unavailable.';
      totalEl.textContent = '—';
      return;
    }

    let stats;
    try {
      stats = await response.json();
    } catch (error) {
      console.error('Visitor statistics JSON is invalid:', error);
      status.textContent = 'Visitor statistics are temporarily unavailable.';
      totalEl.textContent = '—';
      return;
    }

    totalEl.textContent = Number(stats.total || 0).toLocaleString();
    const rows = Array.isArray(stats.countries) ? stats.countries.filter(row => Number(row.visits || 0) > 0) : [];
    if (!rows.length) {
      status.textContent = 'No Contact page geography data is available for the last 90 days yet.';
      return;
    }

    const maxVisits = Math.max(...rows.map(row => Number(row.visits || 0)), 1);
    const bubbleGroup = svgEl('g', { 'aria-label': 'Visitor locations' });
    let mapped = 0;

    rows.forEach(row => {
      const coords = countryCentroids[row.country];
      if (!coords) {
        console.warn('No visitor-map centroid for country:', row.country);
        return;
      }
      const [lat, lon] = coords;
      const [x, y] = project(lon, lat);
      const visits = Number(row.visits || 0);
      const radius = 5 + 25 * Math.sqrt(visits / maxVisits);
      const circle = svgEl('circle', {
        class: 'visitor-bubble', cx: x, cy: y, r: radius,
        fill: '#147d78', 'fill-opacity': 0.58,
        stroke: '#0e6662', 'stroke-width': 1.2,
        tabindex: 0, role: 'img',
        'aria-label': `${row.country}: ${visits.toLocaleString()} page views`
      });
      circle.appendChild(svgEl('title'));
      circle.querySelector('title').textContent = `${row.country}: ${visits.toLocaleString()} page views`;
      circle.addEventListener('mouseenter', event => {
        circle.setAttribute('fill-opacity', '0.82');
        showTooltip(tooltip, shell, event, row);
      });
      circle.addEventListener('mousemove', event => moveTooltip(tooltip, shell, event));
      circle.addEventListener('mouseleave', () => {
        circle.setAttribute('fill-opacity', '0.58');
        tooltip.style.display = 'none';
      });
      circle.addEventListener('focus', () => circle.setAttribute('fill-opacity', '0.82'));
      circle.addEventListener('blur', () => circle.setAttribute('fill-opacity', '0.58'));
      bubbleGroup.appendChild(circle);
      mapped += 1;
    });

    svg.appendChild(bubbleGroup);
    if (mapped > 0) {
      status.style.display = 'none';
    } else {
      status.textContent = 'Visitor totals are available, but country locations could not be mapped.';
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initVisitorMap, { once: true });
  } else {
    initVisitorMap();
  }
})();
