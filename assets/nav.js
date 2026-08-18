document.addEventListener('DOMContentLoaded', () => {
  const currentPage = document.body.dataset.page || '';
  const nav = document.querySelector('.nav-links');
  if (!nav) return;

  nav.innerHTML = `
    <li><a href="home.html" data-page="home">Home</a></li>
    <li><a href="people.html" data-page="people">People</a></li>
    <li class="nav-research">
      <a href="current-research.html" data-page="research">Research</a>
      <div class="research-subnav" aria-label="Research sections">
        <a href="current-research.html" data-subpage="current-research">Current Research</a>
        <a href="research.html" data-subpage="previous-research">Previous Research</a>
      </div>
    </li>
    <li><a href="publications.html" data-page="publications">Publications</a></li>
    <li><a href="teaching.html" data-page="teaching">Teaching</a></li>
    <li><a href="contact.html" data-page="contact">Contact</a></li>`;

  const normalizedPage = currentPage === 'team' ? 'people' : currentPage;
  const isResearchPage = ['research', 'current-research', 'previous-research'].includes(normalizedPage);

  nav.querySelectorAll('a[data-page]').forEach(link => {
    const active = link.dataset.page === 'research'
      ? isResearchPage
      : link.dataset.page === normalizedPage;
    link.classList.toggle('active', active);
    if (active) link.setAttribute('aria-current', 'page');
  });

  nav.querySelectorAll('[data-subpage]').forEach(link => {
    const active = link.dataset.subpage === normalizedPage ||
      (link.dataset.subpage === 'previous-research' && normalizedPage === 'research');
    link.classList.toggle('active', active);
    if (active) link.setAttribute('aria-current', 'page');
  });

  if (!document.getElementById('research-subnav-style')) {
    const style = document.createElement('style');
    style.id = 'research-subnav-style';
    style.textContent = `
      .primary-nav .nav-inner{display:flex!important;align-items:center!important;justify-content:space-between!important;min-height:76px!important}
      .primary-nav .nav-links{display:flex!important;align-items:center!important;gap:clamp(16px,2vw,30px)!important;height:auto!important;margin:0!important;padding:0!important;list-style:none!important;background:transparent!important;border:0!important;border-radius:0!important;box-shadow:none!important}
      .primary-nav .nav-links>li{height:auto!important;margin:0!important;padding:0!important}
      .primary-nav .nav-links>li>a{display:block!important;height:auto!important;padding:9px 0!important;color:#385263!important;line-height:1.2!important;background:transparent!important;border:0!important;border-radius:0!important;box-shadow:none!important;transform:none!important}
      .primary-nav .nav-links>li>a:hover{color:#086ca8!important;background:transparent!important;transform:none!important}
      .primary-nav .nav-links>li>a.active{color:#086ca8!important;background:transparent!important;box-shadow:inset 0 -2px #168bc4!important;transform:none!important}
      .nav-research{position:relative}
      .research-subnav{position:absolute;top:100%;left:50%;transform:translate(-50%,-4px);display:flex;gap:4px;padding:6px;min-width:250px;background:rgba(15,23,42,.96);border:1px solid rgba(255,255,255,.12);border-radius:0 0 8px 8px;box-shadow:0 12px 30px rgba(0,0,0,.18);opacity:0;visibility:hidden;pointer-events:none;transition:opacity .2s ease,transform .2s ease;z-index:1000}
      .nav-research:hover .research-subnav,.nav-research:focus-within .research-subnav{opacity:1;visibility:visible;pointer-events:auto;transform:translate(-50%,0)}
      .research-subnav a{display:block;padding:8px 12px;border-radius:7px;color:rgba(255,255,255,.78);text-decoration:none;white-space:nowrap;font-size:.82rem}
      .research-subnav a:hover,.research-subnav a.active{color:#fff;background:rgba(255,255,255,.12)}
      body.research-editorial .research-subnav{position:fixed;top:76px;left:0;right:0;width:100%;min-width:0;transform:none;justify-content:center;gap:0;padding:0;border:0;border-bottom:1px solid #d8e7ef;border-radius:0;background:rgba(255,255,255,.97);box-shadow:0 5px 16px rgba(6,42,71,.06);opacity:1;visibility:visible;pointer-events:auto}
      body.research-editorial .research-subnav a{min-width:170px;padding:12px 22px 10px;border-bottom:3px solid transparent;border-radius:0;color:#526978;text-align:center;font-size:.86rem}
      body.research-editorial .research-subnav a:hover{color:#086ca8;background:#f2f9fd}
      body.research-editorial .research-subnav a.active{color:#083b66;border-bottom-color:#1389c9;background:#f2f9fd;font-weight:600}
      @media(max-width:900px){.primary-nav .nav-inner{padding-inline:16px!important}.primary-nav .nav-links{gap:18px!important;max-width:calc(100vw - 230px);overflow-x:auto!important;scrollbar-width:none}.primary-nav .nav-links::-webkit-scrollbar{display:none}}
      @media(max-width:760px){.primary-nav .brand-subtitle{display:none}.primary-nav .nav-links{max-width:calc(100vw - 145px);gap:15px!important}.primary-nav .nav-links>li>a{font-size:.82rem!important}.research-subnav{position:absolute;transform:translate(-50%,-4px);opacity:0;visibility:hidden;pointer-events:none;min-width:250px;background:rgba(15,23,42,.96);border:1px solid rgba(255,255,255,.12);box-shadow:0 12px 30px rgba(0,0,0,.18);padding:6px}.nav-research:hover .research-subnav,.nav-research:focus-within .research-subnav{opacity:1;visibility:visible;pointer-events:auto;transform:translate(-50%,0)}.research-subnav a{padding:8px 12px}body.research-editorial .research-subnav{position:fixed;top:76px;display:grid;grid-template-columns:1fr 1fr;padding:0;background:rgba(255,255,255,.98);border-bottom:1px solid #d8e7ef}body.research-editorial .research-subnav a{min-width:0;padding:11px 8px 9px}}
      /* GeoWater deep navy navigation */
      .primary-nav{background:rgba(3,24,42,.97)!important;border-bottom:1px solid rgba(181,215,231,.2)!important;box-shadow:0 8px 28px rgba(0,0,0,.14)!important;backdrop-filter:blur(16px)}
      .primary-nav .brand-label{color:#f3f8fb!important}
      .primary-nav .brand-subtitle{color:#a9c4d4!important}
      .primary-nav .nav-links>li>a{color:#d7e7ef!important}
      .primary-nav .nav-links>li>a:hover{color:#fff!important}
      .primary-nav .nav-links>li>a.active{color:#8fd5f3!important;box-shadow:inset 0 -2px #8fd5f3!important}
      .primary-nav .research-subnav{background:rgba(3,24,42,.98)!important;border-color:rgba(181,215,231,.18)!important}
      .primary-nav .research-subnav a{color:#c8dae4!important}
      .primary-nav .research-subnav a:hover,.primary-nav .research-subnav a.active{color:#fff!important;background:rgba(143,213,243,.13)!important}
      body.research-editorial .research-subnav{background:rgba(3,24,42,.98)!important;border-bottom-color:rgba(181,215,231,.2)!important;box-shadow:0 7px 22px rgba(0,0,0,.16)!important}
      body.research-editorial .research-subnav a{color:#c8dae4!important}
      body.research-editorial .research-subnav a:hover,body.research-editorial .research-subnav a.active{color:#fff!important;background:rgba(143,213,243,.12)!important;border-bottom-color:#8fd5f3!important}

    `;
    document.head.appendChild(style);
  }
});
