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
        top: calc(100% + 10px);
        left: 50%;
        transform: translateX(-50%);
        display: flex;
        gap: 4px;
        padding: 6px;
        min-width: 230px;
        background: rgba(15, 23, 42, .94);
        border: 1px solid rgba(255,255,255,.12);
        border-radius: 10px;
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
      @media (max-width: 760px) {
        .research-subnav { position: static; transform: none; opacity: 1; visibility: visible; pointer-events: auto; min-width: 0; background: transparent; border: 0; box-shadow: none; padding: 4px 0 0 14px; }
        .research-subnav a { padding: 5px 8px; }
      }
    `;
    document.head.appendChild(style);
  }
});
