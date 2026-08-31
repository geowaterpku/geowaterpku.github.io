from pathlib import Path


def replace_once(path, old, new):
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Expected text not found in {path}: {old[:120]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# Global navigation
replace_once(
    "assets/nav.js",
    '<li><a href="Resources.html" data-page="resources">Resources</a></li>',
    '<li><a href="Resources.html" data-page="resources">Open Data</a></li>',
)

# Homepage framing
replace_once(
    "index.html",
    "Official website of Dr. Peirong Lin and the GeoWater Research Lab at Peking University. Research in global hydrology, river modeling, remote sensing, GIS, and flood–human interactions.",
    "Official website of Dr. Peirong Lin and the GeoWater Research Lab at Peking University. Research in global hydrology, river modeling, remote sensing, GIS, flood risk, and human–river interactions.",
)
replace_once(
    "index.html",
    "We study the world’s rivers, their pulses, and human–flood interactions.",
    "We study the world’s rivers, hydrological pulses, evolving flood-risk patterns, and their interactions with society.",
)
replace_once(
    "index.html",
    "Rivers · Hydrological pulses · Flood–human interactions",
    "Rivers · Hydrological pulses · Flood-risk patterns · Society",
)
replace_once(
    "index.html",
    '<h2 id="questions-title">Three spatial questions guide our science.</h2>',
    '<h2 id="questions-title">Three overarching questions</h2>',
)
replace_once(
    "index.html",
    "<p>We investigate how a changing water cycle, river-channel form, and human development come together to shape floods.</p>",
    "<p>We investigate how climate change, intensifying human activities, and river-system structure reshape the terrestrial water cycle and flood risk—and how this knowledge can support more resilient decisions.</p>",
)
replace_once(
    "index.html",
    "How does the terrestrial water cycle change under the dual pressures of climate and human activities?",
    "How is the terrestrial water cycle changing under the dual pressures of climate change and intensifying human activities?",
)
replace_once(
    "index.html",
    '<p class="home-v2-eyebrow">Channel form × hydrological pulses</p>',
    '<p class="home-v2-eyebrow">River structure × flood risk</p>',
)
replace_once(
    "index.html",
    "How does the spatial configuration of channel shapes contribute to unexpected floods?",
    "How do river-channel and floodplain patterns impact flood risks and intensities across space and time?",
)
replace_once(
    "index.html",
    "We investigate how channel geometry, flow pathways, and floodplain structure regulate the propagation, attenuation, storage, and spatial expression of hydrological pulses.",
    "We investigate how channel geometry, flow pathways, and floodplain structure shape where floods intensify, persist, or attenuate across river networks and floodplains.",
)
replace_once(
    "index.html",
    "River networks and human development across a global landscape",
    "River networks and human activities across a global landscape",
)
replace_once(
    "index.html",
    '<p class="home-v2-eyebrow">Development × flood exposure</p>',
    '<p class="home-v2-eyebrow">Human activities × flood impacts</p>',
)
replace_once(
    "index.html",
    "How does the spatial distribution of human development interact with floods?",
    "How do human activities alter floods’ severity, frequency, distribution, and duration—and how can this knowledge support more resilient development and flood-risk management?",
)
replace_once(
    "index.html",
    "We examine how urbanization, levees, reservoirs, and settlement patterns interact with river-system organization to reshape flow dynamics and flood hazards.",
    "We examine how urbanization, levees, reservoirs, and settlement patterns reshape flood hazards and exposure, with the goal of informing adaptation, risk reduction, and sustainable development.",
)

# Current Research framing
replace_once(
    "current-research.html",
    "GeoWater Research Lab studies how the spatial organization of river systems shapes terrestrial hydrological dynamics and flood–human interactions.",
    "GeoWater Research Lab studies how climate change, river-system structure, and human activities reshape terrestrial hydrological dynamics, flood risk, and societal impacts.",
)
replace_once(
    "current-research.html",
    "How does the spatial organization of river systems shape terrestrial hydrological dynamics and flood–human interactions?",
    "How do climate change, river-system structure, and human activities reshape hydrological dynamics and flood risk—and what do those changes mean for society?",
)
replace_once(
    "current-research.html",
    "GeoWater Lab combines Earth observations, geospatial information, and process-based and data-driven modeling to understand how this organization shapes terrestrial hydrological dynamics and flood–human interactions, moving toward spatially explicit descriptions and predictions of river networks, hydrological pulses, and their changing capacity to convey and accommodate water.",
    "GeoWater Lab combines Earth observations, geospatial information, and process-based and data-driven modeling to understand how river-system organization shapes terrestrial hydrological dynamics, flood-risk patterns, and societal impacts, moving toward spatially explicit descriptions and predictions that can better support adaptation and decision-making.",
)
replace_once(
    "current-research.html",
    "We seek to better understand how the configuration of human development interacts with the spatial organization of rivers to alter flow dynamics through data-driven approaches.",
    "We seek to better understand how the configuration of human activities interacts with the spatial organization of rivers to alter flow dynamics through data-driven approaches.",
)

style_anchor = """    .research-project__publications .research-publication-link:focus-visible {
      outline: 2px solid rgba(8,119,168,.28);
      outline-offset: 2px;
      border-radius: 2px;
    }
  </style>"""
style_replacement = """    .research-project__publications .research-publication-link:focus-visible {
      outline: 2px solid rgba(8,119,168,.28);
      outline-offset: 2px;
      border-radius: 2px;
    }
    .research-overarching {
      padding: clamp(64px,8vw,112px) 0;
      background: #f4f8fa;
      border-top: 1px solid rgba(22,70,95,.08);
      border-bottom: 1px solid rgba(22,70,95,.08);
    }
    .research-overarching__heading {
      max-width: 820px;
      margin-bottom: clamp(30px,4vw,52px);
    }
    .research-overarching__heading h2 {
      margin: 8px 0 14px;
      font-size: clamp(2rem,4vw,3.5rem);
      line-height: 1.04;
      letter-spacing: -.035em;
      color: #123f55;
    }
    .research-overarching__heading > p:last-child {
      max-width: 760px;
      margin: 0;
      color: #4c6775;
      font-size: 1.04rem;
      line-height: 1.7;
    }
    .research-overarching__grid {
      display: grid;
      grid-template-columns: repeat(3,minmax(0,1fr));
      gap: 18px;
    }
    .research-overarching__card {
      min-height: 270px;
      padding: clamp(24px,3vw,34px);
      background: #fff;
      border: 1px solid rgba(22,70,95,.11);
      border-radius: 18px;
      box-shadow: 0 16px 42px rgba(18,63,85,.06);
    }
    .research-overarching__number {
      display: block;
      margin-bottom: 34px;
      color: #0877a8;
      font-size: .78rem;
      font-weight: 700;
      letter-spacing: .14em;
    }
    .research-overarching__card h3 {
      margin: 0;
      color: #173f53;
      font-size: clamp(1.16rem,1.55vw,1.38rem);
      line-height: 1.48;
      font-weight: 600;
    }
    .research-overarching__card--impact {
      border-color: rgba(8,119,168,.24);
      background: linear-gradient(180deg,#ffffff 0%,#f7fbfd 100%);
    }
    @media (max-width: 900px) {
      .research-overarching__grid { grid-template-columns: 1fr; }
      .research-overarching__card { min-height: 0; }
      .research-overarching__number { margin-bottom: 18px; }
    }
  </style>"""
replace_once("current-research.html", style_anchor, style_replacement)

projects_anchor = '    <section class="research-questions research-projects" id="scientific-questions" aria-labelledby="research-projects-title">'
overarching_block = """    <section class="research-overarching" id="scientific-questions" aria-labelledby="overarching-questions-title">
      <div class="research-shell">
        <div class="research-overarching__heading">
          <p class="research-kicker">Overarching questions</p>
          <h2 id="overarching-questions-title">Three overarching questions</h2>
          <p>Our research connects process understanding with flood risk, societal impacts, and decisions for a changing world.</p>
        </div>
        <div class="research-overarching__grid">
          <article class="research-overarching__card">
            <span class="research-overarching__number">01 · WATER CYCLE</span>
            <h3>How is the terrestrial water cycle changing under the dual pressures of climate change and intensifying human activities?</h3>
          </article>
          <article class="research-overarching__card">
            <span class="research-overarching__number">02 · FLOOD RISK</span>
            <h3>How do river-channel and floodplain patterns impact flood risks and intensities across space and time?</h3>
          </article>
          <article class="research-overarching__card research-overarching__card--impact">
            <span class="research-overarching__number">03 · SOCIETAL IMPACT</span>
            <h3>How do human activities alter floods’ severity, frequency, distribution, and duration—and how can this knowledge support adaptation, planning, and flood-risk management?</h3>
          </article>
        </div>
      </div>
    </section>

    <section class="research-questions research-projects" id="research-projects" aria-labelledby="research-projects-title">"""
replace_once("current-research.html", projects_anchor, overarching_block)
