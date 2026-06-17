import re

with open('index.html', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Update Navigation
nav_regex = re.compile(r'<ul>(.*?)</ul>', re.DOTALL)
new_nav = """<ul>
    <li><a href="#home">Home</a></li>
    <li><a href="#portfolio">Portfolio</a></li>
    <li><a href="#services">Services</a></li>
    <li><a href="#about">About</a></li>
    <li><a href="#contact" class="btn btn-primary" style="padding:.55rem 1.2rem">Hire Me</a></li>
  </ul>"""
text = nav_regex.sub(new_nav, text, count=1)

# Mobile Menu
mobile_menu_regex = re.compile(r'<div class="mobile-menu" id="mobileMenu">(.*?)</div>', re.DOTALL)
new_mobile = """<div class="mobile-menu" id="mobileMenu">
  <a href="#home" onclick="closeMobile()">Home</a>
  <a href="#portfolio" onclick="closeMobile()">Portfolio</a>
  <a href="#services" onclick="closeMobile()">Services</a>
  <a href="#about" onclick="closeMobile()">About</a>
  <a href="#contact" onclick="closeMobile()">Contact</a>
</div>"""
text = mobile_menu_regex.sub(new_mobile, text, count=1)

# 2. Extract and reorder sections
sections = {}
patterns = {
    'head_to_hero': r'(.*?)<!-- SERVICES -->',
    'services': r'<!-- SERVICES -->(.*?)<!-- PROJECTS -->',
    'projects': r'<!-- PROJECTS -->(.*?)<!-- PROCESS -->',
    'contact': r'<!-- CONTACT -->(.*?)<!-- CTA SECTION -->',
    'footer': r'<!-- FOOTER -->(.*?)<script>',
    'script': r'<script>(.*?)</script>',
    'end': r'</script>(.*)'
}

head_to_hero = re.search(r'(?s)(.*?)<!-- SERVICES -->', text).group(1)
services = re.search(r'(?s)<!-- SERVICES -->(.*?)<!-- PROJECTS -->', text).group(0)
projects = re.search(r'(?s)<!-- PROJECTS -->(.*?)<!-- PROCESS -->', text).group(0)
contact = re.search(r'(?s)<!-- CONTACT -->(.*?)<!-- CTA SECTION -->', text).group(0)
footer = re.search(r'(?s)<!-- FOOTER -->(.*?)<script>', text).group(0)
script = re.search(r'(?s)<script>(.*?)</script>', text).group(1)
end = re.search(r'(?s)</script>[\s\n]*</body>[\s\n]*</html>', text).group(0)

# Modify Projects to Portfolio (video only)
portfolio_html = """<!-- PORTFOLIO -->
<section id="portfolio">
  <div class="projects-header">
    <div>
      <div class="section-label">Portfolio</div>
      <h2>Featured Works</h2>
      <p class="section-sub">A selection of my best video production and editing projects.</p>
    </div>
  </div>
  <div class="projects-grid" id="projectsGrid">
    <div class="project-card" data-cat="video">
      <div class="project-thumb">
        <div class="thumb-bg" style="background:linear-gradient(135deg,#2d1200,#8b3a00)"></div>
        <span style="position:relative;z-index:1">🎥</span>
        <span class="thumb-label">Video</span>
      </div>
      <div class="project-body">
        <h3>YouTube Channel Edit Pack</h3>
        <p>Full editing of 4 videos — intros, B-roll, captions, thumbnail design. 48hr delivery.</p>
        <div class="project-footer">
          <button class="arrow-btn" onclick="openContact('YouTube Edit Pack')">→</button>
        </div>
      </div>
    </div>
    <div class="project-card" data-cat="video">
      <div class="project-thumb">
        <div class="thumb-bg" style="background:linear-gradient(135deg,#001a10,#004d30)"></div>
        <span style="position:relative;z-index:1">✂️</span>
        <span class="thumb-label">Video</span>
      </div>
      <div class="project-body">
        <h3>Short-Form Reels Package</h3>
        <p>10 Instagram/TikTok reels edited with captions, music, and trending effects. 5-day delivery.</p>
        <div class="project-footer">
          <button class="arrow-btn" onclick="openContact('Reels Package')">→</button>
        </div>
      </div>
    </div>
    <div class="project-card" data-cat="video">
      <div class="project-thumb">
        <div class="thumb-bg" style="background:linear-gradient(135deg,#1a1a3e,#2d1b69)"></div>
        <span style="position:relative;z-index:1">🎬</span>
        <span class="thumb-label">Video</span>
      </div>
      <div class="project-body">
        <h3>Commercial Brand Ad</h3>
        <p>A dynamic, high-retention 60-second advertisement shot and edited for a tech product launch.</p>
        <div class="project-footer">
          <button class="arrow-btn" onclick="openContact('Commercial Brand Ad')">→</button>
        </div>
      </div>
    </div>
  </div>
</section>
"""

# Modify Services logic
# Let's keep the design of services from original. It doesn't need to change, just move it.

# Create About section
about_html = """<!-- ABOUT -->
<section id="about" style="background: var(--surface);">
  <div class="contact-wrap" style="align-items: center;">
    <div class="contact-info">
      <div class="section-label">About Me</div>
      <h2>Creative. Reliable. Fast.</h2>
      <p style="color: var(--muted); margin-bottom: 1.5rem; font-size: 1.05rem;">
        Hi, I'm Veerapandi. I am a multi-disciplinary creator with a passion for building high-quality digital experiences. By bridging the gap between creative vision and technical execution, I help brands and creators tell their stories effectively.
      </p>
      <p style="color: var(--muted); font-size: 0.95rem;">
        Whether it's an incredibly polished YouTube video, an engaging Short-form reel, or a robust custom website, I treat every project as an opportunity to deliver excellence. Let's work together to make your next idea an outstanding reality.
      </p>
    </div>
    <div style="display: flex; gap: 1rem; flex-wrap: wrap;">
       <div style="flex: 1; min-width: 150px; background: rgba(255,255,255,0.03); border: 1px solid var(--border); padding: 2rem; border-radius: 16px; text-align: center;">
         <div style="font-size: 2rem; color: var(--accent); font-weight: 700; margin-bottom: 0.5rem;">5+</div>
         <div style="font-size: 0.8rem; color: var(--muted);">Years Experience</div>
       </div>
       <div style="flex: 1; min-width: 150px; background: rgba(255,255,255,0.03); border: 1px solid var(--border); padding: 2rem; border-radius: 16px; text-align: center;">
         <div style="font-size: 2rem; color: var(--accent2); font-weight: 700; margin-bottom: 0.5rem;">100%</div>
         <div style="font-size: 0.8rem; color: var(--muted);">Client Satisfaction</div>
       </div>
    </div>
  </div>
</section>
"""

# Update Footer Links
new_footer_links = """<div class="footer-links">
      <a href="#home">Home</a>
      <a href="#portfolio">Portfolio</a>
      <a href="#services">Services</a>
      <a href="#about">About</a>
      <a href="#contact">Contact</a>
    </div>"""
footer = re.sub(r'<div class="footer-links">.*?</div>', new_footer_links, footer, flags=re.DOTALL)

# Clean Script
script = re.sub(r'// ── PROJECT FILTER ──.*?// ── OPEN CONTACT WITH PRE-FILL ──', '// ── OPEN CONTACT WITH PRE-FILL ──', script, flags=re.DOTALL)
script = re.sub(r'// ── PRICING TABS ──.*?// ── OPEN CONTACT WITH PRE-FILL ──', '// ── OPEN CONTACT WITH PRE-FILL ──', script, flags=re.DOTALL)
# Also remove occurrences of test-card, process-step, pricing-card from the observer querySelector
script = script.replace(', .process-step, .pricing-card, .testi-card', '')

# Assemble final HTML
final_html = head_to_hero + portfolio_html + services + about_html + contact + footer + "<script>\n" + script + "\n</script>\n</body>\n</html>"

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(final_html)

print("Rewrote index.html structure fully.")
