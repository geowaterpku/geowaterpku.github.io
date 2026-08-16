document.addEventListener('DOMContentLoaded', () => {
  const currentPage = document.body.dataset.page;
  if (!currentPage) return;

  document.querySelectorAll('.nav-links a[data-page]').forEach(link => {
    const isResearchLink = link.dataset.page === 'research';
    const isCurrentResearch = currentPage === 'current-research';
    const isPastResearch = currentPage === 'research';
    const isActive = isResearchLink
      ? (isCurrentResearch || isPastResearch)
      : link.dataset.page === currentPage;

    link.classList.toggle('active', isActive);
    if (isActive) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');

    if (isResearchLink) {
      const parent = link.closest('li');
      if (!parent) return;
      parent.classList.add('nav-research');

      let subnav = parent.querySelector('.research-subnav');
      if (!subnav) {
        subnav = document.createElement('div');
        subnav.className = 'research-subnav';
        subnav.setAttribute('aria-label', 'Research sections');
        subnav.innerHTML = '<a href="current-research.html">Current Research</a><a href="research.html">Past Research</a>';
        parent.appendChild(subnav);
      }

      subnav.querySelectorAll('a').forEach(sub => {
        const isCurrent = (isCurrentResearch && sub.getAttribute('href') === 'current-research.html') ||
                          (isPastResearch && sub.getAttribute('href') === 'research.html');
        sub.classList.toggle('active', isCurrent);
        if (isCurrent) sub.setAttribute('aria-current', 'page');
        else sub.removeAttribute('aria-current');
      });
    }
  });

  if (!document.getElementById('research-subnav-style')) {
    const style = document.createElement('style');
    style.id = 'research-subnav-style';
    style.textContent = `
      .nav-research { position: relative; }
      .research-subnav {
        position: absolute;
        top: 100%;
        left: 50%;
        transform: translateX(-50%);
        display: flex;
        gap: 4px;
        padding: 6px;
        min-width: 230px;
        background: rgba(15, 23, 42, .94);
        border: 1px solid rgba(255,255,255,.12);
        border-radius: 0 0 8px 8px;
        box-shadow: 0 12px 30px rgba(0,0,0,.18);
        opacity: 0;
        visibility: hidden;
        pointer-events: none;
        transition: opacity .2s ease, transform .2s ease;
        z-index: 1000;
      }
      .nav-research:hover .research-subnav,
      .nav-research:focus-within .research-subnav { opacity: 1; visibility: visible; pointer-events: auto; transform: translate(-50%, 0); }
      .research-subnav a {
        display: block;
        padding: 8px 12px;
        border-radius: 7px;
        color: rgba(255,255,255,.78);
        text-decoration: none;
        white-space: nowrap;
        font-size: .82rem;
      }
      .research-subnav a:hover,
      .research-subnav a.active { color: #fff; background: rgba(255,255,255,.12); }
      /* On the two Research pages, keep both choices permanently accessible. */
      body.research-editorial .research-subnav {
        position: fixed;
        top: 76px;
        left: 0;
        right: 0;
        width: 100%;
        min-width: 0;
        transform: none;
        justify-content: center;
        gap: 0;
        padding: 0;
        border: 0;
        border-bottom: 1px solid #d8e7ef;
        border-radius: 0;
        background: rgba(255,255,255,.97);
        box-shadow: 0 5px 16px rgba(6,42,71,.06);
        opacity: 1;
        visibility: visible;
        pointer-events: auto;
      }
      body.research-editorial .research-subnav a {
        min-width: 160px;
        padding: 12px 22px 10px;
        border-bottom: 3px solid transparent;
        border-radius: 0;
        color: #526978;
        text-align: center;
        font-size: .86rem;
      }
      body.research-editorial .research-subnav a:hover {
        color: #086ca8;
        background: #f2f9fd;
      }
      body.research-editorial .research-subnav a.active {
        color: #083b66;
        border-bottom-color: #1389c9;
        background: #f2f9fd;
        font-weight: 600;
      }
      @media (max-width: 760px) {
        .research-subnav { position: static; transform: none; opacity: 1; visibility: visible; pointer-events: auto; min-width: 0; background: transparent; border: 0; box-shadow: none; padding: 4px 0 0 14px; }
        .research-subnav a { padding: 5px 8px; }
        body.research-editorial .research-subnav {
          position: fixed;
          top: 76px;
          display: grid;
          grid-template-columns: 1fr 1fr;
          padding: 0;
          background: rgba(255,255,255,.98);
          border-bottom: 1px solid #d8e7ef;
        }
        body.research-editorial .research-subnav a {
          min-width: 0;
          padding: 11px 8px 9px;
        }
      }
    `;
    document.head.appendChild(style);
  }
});
