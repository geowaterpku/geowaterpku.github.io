(() => {
  const siteUrl = 'https://geowaterpku.github.io';
  const siteName = 'GeoWater Research Lab';
  const defaultImage = `${siteUrl}/assets/home/geowater-river-city-v1.webp`;
  const page = document.body?.dataset?.page || '';

  const pages = {
    home: {
      path: '/',
      title: 'GeoWater Research Lab | Peking University',
      description: 'GeoWater Research Lab at Peking University studies global rivers, hydrological pulses, river networks, flood–human interactions, Earth observations, geospatial information, and hydrological modeling.'
    },
    people: {
      path: '/people.html',
      title: 'People | GeoWater Research Lab at Peking University',
      description: 'Meet the faculty, students, postdoctoral researchers, visitors, and alumni of the GeoWater Research Lab at Peking University.'
    },
    'current-research': {
      path: '/current-research.html',
      title: 'Current Research | GeoWater Research Lab at Peking University',
      description: 'GeoWater Research Lab studies how the spatial organization of river systems shapes terrestrial hydrological dynamics and flood–human interactions.'
    },
    research: {
      path: '/research.html',
      title: 'Past Research | GeoWater Research Lab at Peking University',
      description: 'Past research from GeoWater Research Lab on global hydrology, river networks, remote sensing, hydrological modeling, and floodplain processes.'
    },
    publications: {
      path: '/publications.html',
      title: 'Publications | GeoWater Research Lab at Peking University',
      description: 'Peer-reviewed publications and datasets from GeoWater Research Lab on global river discharge, river networks, flood modeling, Earth observations, and hydrological processes.'
    },
    teaching: {
      path: '/teaching.html',
      title: 'Teaching | GeoWater Research Lab at Peking University',
      description: 'Teaching and student training activities of GeoWater Research Lab at Peking University in hydrology, remote sensing, GIS, and geospatial data science.'
    },
    contact: {
      path: '/contact.html',
      title: 'Contact | GeoWater Research Lab at Peking University',
      description: 'Contact GeoWater Research Lab at Peking University for research collaboration, student opportunities, and academic visits.'
    },
    resources: {
      path: '/Resources.html',
      title: 'Data & Resources | GeoWater Research Lab at Peking University',
      description: 'Datasets and community modeling resources from GeoWater Research Lab, including global river discharge, river networks, large-sample hydrology, and floodplain data.'
    },
    cv: {
      path: '/cv.html',
      title: 'Peirong Lin | GeoWater Research Lab at Peking University',
      description: 'Academic profile, research, publications, teaching, and service of Peirong Lin at Peking University and the GeoWater Research Lab.'
    }
  };

  const fallbackPath = window.location.pathname === '/home.html' || window.location.pathname === '/index.html'
    ? '/'
    : window.location.pathname;
  const meta = pages[page] || {
    path: fallbackPath,
    title: document.title,
    description: document.querySelector('meta[name="description"]')?.content || ''
  };

  const canonicalUrl = `${siteUrl}${meta.path}`;

  const ensureLink = (rel, href) => {
    let link = document.head.querySelector(`link[rel="${rel}"]`);
    if (!link) {
      link = document.createElement('link');
      link.rel = rel;
      document.head.appendChild(link);
    }
    link.href = href;
  };

  const ensureMeta = (selector, attr, key, content) => {
    let tag = document.head.querySelector(selector);
    if (!tag) {
      tag = document.createElement('meta');
      tag.setAttribute(attr, key);
      document.head.appendChild(tag);
    }
    tag.content = content;
  };

  document.title = meta.title;
  let description = document.head.querySelector('meta[name="description"]');
  if (!description) {
    description = document.createElement('meta');
    description.name = 'description';
    document.head.appendChild(description);
  }
  description.content = meta.description;

  ensureLink('canonical', canonicalUrl);
  ensureMeta('meta[property="og:type"]', 'property', 'og:type', 'website');
  ensureMeta('meta[property="og:site_name"]', 'property', 'og:site_name', siteName);
  ensureMeta('meta[property="og:title"]', 'property', 'og:title', meta.title);
  ensureMeta('meta[property="og:description"]', 'property', 'og:description', meta.description);
  ensureMeta('meta[property="og:url"]', 'property', 'og:url', canonicalUrl);
  ensureMeta('meta[property="og:image"]', 'property', 'og:image', defaultImage);
  ensureMeta('meta[name="twitter:card"]', 'name', 'twitter:card', 'summary_large_image');
  ensureMeta('meta[name="twitter:title"]', 'name', 'twitter:title', meta.title);
  ensureMeta('meta[name="twitter:description"]', 'name', 'twitter:description', meta.description);
  ensureMeta('meta[name="twitter:image"]', 'name', 'twitter:image', defaultImage);

  document.querySelectorAll('a[href="home.html"]').forEach(link => link.setAttribute('href', '/'));

  const graph = [
    {
      '@context': 'https://schema.org',
      '@type': 'WebPage',
      '@id': `${canonicalUrl}#webpage`,
      url: canonicalUrl,
      name: meta.title,
      description: meta.description,
      isPartOf: { '@id': `${siteUrl}/#website` },
      about: { '@id': `${siteUrl}/#organization` }
    }
  ];

  if (meta.path === '/') {
    graph.unshift(
      {
        '@context': 'https://schema.org',
        '@type': 'WebSite',
        '@id': `${siteUrl}/#website`,
        url: `${siteUrl}/`,
        name: 'GeoWater Research Lab',
        alternateName: 'GeoWater Lab',
        description: meta.description,
        publisher: { '@id': `${siteUrl}/#organization` }
      },
      {
        '@context': 'https://schema.org',
        '@type': 'Organization',
        '@id': `${siteUrl}/#organization`,
        name: 'GeoWater Research Lab',
        alternateName: 'GeoWater Lab',
        url: `${siteUrl}/`,
        description: 'A research lab at Peking University studying global rivers, terrestrial hydrology, Earth observations, geospatial information, and flood–human interactions.',
        image: defaultImage,
        parentOrganization: {
          '@type': 'CollegeOrUniversity',
          name: 'Peking University',
          url: 'https://english.pku.edu.cn/'
        },
        sameAs: ['https://github.com/geowaterpku']
      }
    );
  }

  let structured = document.head.querySelector('script[data-geowater-seo="jsonld"]');
  if (!structured) {
    structured = document.createElement('script');
    structured.type = 'application/ld+json';
    structured.dataset.geowaterSeo = 'jsonld';
    document.head.appendChild(structured);
  }
  structured.textContent = JSON.stringify(graph);
})();
