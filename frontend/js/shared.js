// shared.js — Nav, mobile drawer, scroll reveal, footer year
(function () {
  // Apply page slide-in transition on load as early as possible
  document.documentElement.style.scrollBehavior = 'auto'; // Prevent scroll jump on load transition
  document.body.classList.add('page-transition-active');
  document.body.classList.add('page-animating');
  
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      document.body.classList.add('page-transition-enter');
      setTimeout(() => {
        document.body.classList.remove('page-animating');
        document.documentElement.style.scrollBehavior = ''; // restore smooth scroll
      }, 350);
    });
  });

  // Intercept clicks on internal links to trigger exit transition
  document.addEventListener('click', event => {
    const anchor = event.target.closest('a');
    if (!anchor) return;

    const href = anchor.getAttribute('href');
    if (!href) return;

    // Check if it is an internal page link and not an anchor / external URL / API / target blank
    const isInternal = href && 
                       !href.startsWith('http') && 
                       !href.startsWith('//') && 
                       !href.startsWith('#') && 
                       !href.startsWith('mailto:') && 
                       !href.startsWith('tel:') && 
                       !href.startsWith('javascript:') &&
                       !href.startsWith('/api/') && 
                       !anchor.getAttribute('target') &&
                       !event.defaultPrevented &&
                       event.button === 0 && 
                       !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey;

    if (isInternal) {
      event.preventDefault();
      document.body.classList.add('page-animating');
      document.body.classList.remove('page-transition-enter');
      document.body.classList.add('page-transition-exit');
      
      setTimeout(() => {
        window.location.href = href;
      }, 320); // Sync with CSS transition duration
    }
  });

  // Disable right-click globally
  document.addEventListener('contextmenu', event => event.preventDefault());


  // Disable selecting and copying text globally (except in inputs & textareas)
  const isInputControl = target => target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA');
  document.addEventListener('selectstart', event => {
    if (!isInputControl(event.target)) event.preventDefault();
  });
  document.addEventListener('copy', event => {
    if (!isInputControl(event.target)) event.preventDefault();
  });

  const currentPage = location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.nav-links a, .mobile-drawer a').forEach(a => {
    const href = a.getAttribute('href');
    if (href === currentPage || (currentPage === '' && href === 'index.html')) {
      a.classList.add('active');
    }
  });

  // ── Nav scroll effect ──
  const nav = document.getElementById('main-nav');
  if (nav) {
    window.addEventListener('scroll', () => {
      nav.classList.toggle('scrolled', window.scrollY > 40);
    }, { passive: true });
  }

  // ── Hamburger / Mobile Drawer ──
  const ham = document.getElementById('hamburger');
  const drawer = document.getElementById('mobile-drawer');
  if (ham && drawer) {
    ham.addEventListener('click', () => {
      const open = ham.classList.toggle('open');
      drawer.classList.toggle('open', open);
      document.body.style.overflow = open ? 'hidden' : '';
    });
    drawer.querySelectorAll('a').forEach(a => {
      a.addEventListener('click', () => {
        ham.classList.remove('open');
        drawer.classList.remove('open');
        document.body.style.overflow = '';
      });
    });
  }

  // ── Scroll Reveal ──
  const ro = new IntersectionObserver((entries) => {
    entries.forEach((e, i) => {
      if (e.isIntersecting) {
        const delay = e.target.dataset.delay || 0;
        setTimeout(() => e.target.classList.add('visible'), delay);
        ro.unobserve(e.target);
      }
    });
  }, { threshold: 0.08, rootMargin: '0px 0px -40px 0px' });

  document.querySelectorAll('.reveal').forEach((el, i) => {
    // Stagger siblings in same parent
    const siblings = el.parentElement.querySelectorAll('.reveal');
    siblings.forEach((s, si) => { if (!s.dataset.delay) s.dataset.delay = si * 80; });
    ro.observe(el);
  });

  // ── Stats counting ──
  const animateStats = async () => {
    try {
      const resp = await fetch('/api/stats/overall?_t=' + Date.now(), { cache: 'no-store' });
      const data = await resp.json();
      
      const map = {
        'stat-projects': data.projects,
        'stat-clients': data.clients,
        'stat-rating': data.rating,
        'stat-years': data.years
      };

      for (const [id, val] of Object.entries(map)) {
        const el = document.getElementById(id);
        if (el) {
          el.dataset.target = val;
          // Apply tabular-nums to prevent character width shaking while counting
          el.style.fontVariantNumeric = 'tabular-nums';
          
          const target = parseFloat(val);
          const isFloat = id === 'stat-rating';
          const duration = 2500; // 2.5s for smooth premium deceleration
          const startTime = performance.now();
          
          let suffix = '+';
          if (id === 'stat-rating') suffix = '★';
          else if (id === 'stat-years') suffix = 'yr';

          // Exponential easing out for a very smooth slow-down effect
          const easeOutExpo = t => t === 1 ? 1 : 1 - Math.pow(2, -10 * t);

          const updateCounter = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const current = target * easeOutExpo(progress);
            
            // Always append the suffix so the width doesn't jump at the end
            el.textContent = (progress === 1 ? target : current).toFixed(isFloat ? 1 : 0) + suffix;
            
            if (progress < 1) {
              requestAnimationFrame(updateCounter);
            }
          };
          
          requestAnimationFrame(updateCounter);
        }
      }
    } catch (e) { console.warn("Stats animation failed:", e); }
  };

  const statsSection = document.querySelector('.hero-stats');
  if (statsSection) {
    const statsObserver = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting) {
        animateStats();
        statsObserver.unobserve(entries[0].target);
      }
    }, { threshold: 0.05 }); // More sensitive
    statsObserver.observe(statsSection);
    
    // Fallback: If already in view on load
    if (statsSection.getBoundingClientRect().top < window.innerHeight) {
      animateStats();
    }
  }

  // ── Dynamic YouTube Stats ──
  const fetchYouTubeStats = async () => {
    try {
      const resp = await fetch('/api/stats/youtube');
      const data = await resp.json();
      if (!data.error) {
        const subsEl = document.getElementById('yt-subs');
        const viewsEl = document.getElementById('yt-views');
        
        // Show full digits with commas for clarity
        const formatter = new Intl.NumberFormat();
        
        if (subsEl) subsEl.textContent = formatter.format(data.full_subs);
        if (viewsEl) viewsEl.textContent = formatter.format(data.full_views);
        
        // Also update dedicated youtube.html page IDs if they exist
        const subsPageEl = document.getElementById('yt-subs-page');
        const viewsPageEl = document.getElementById('yt-views-page');
        if (subsPageEl) subsPageEl.textContent = formatter.format(data.full_subs);
        if (viewsPageEl) viewsPageEl.textContent = formatter.format(data.full_views);

        // Add 'updated' pulses or indicators if needed
        document.querySelectorAll('.live-indicator').forEach(el => {
          el.style.opacity = '1';
          setTimeout(() => el.style.opacity = '0.5', 2000);
        });
      }
    } catch (e) {
      console.warn("YouTube API fetch failed:", e);
    }
  };
  
  // Start Real-Time Polling (every 60 seconds)
  if (document.getElementById('yt-subs') || document.getElementById('yt-subs-page')) {
    fetchYouTubeStats();
    setInterval(fetchYouTubeStats, 60000); 
  }

  // ── Dynamic Recent Videos ──
  let nextPageToken = null;
  let isSearching = false;

  const renderVideos = (videos, clear = false) => {
    const grid = document.getElementById('yt-grid');
    if (!grid) return;
    if (clear) grid.innerHTML = '';
    
    videos.forEach(v => {
      const card = document.createElement('div');
      card.className = 'vid-card reveal';
      card.innerHTML = `
        <a href="https://www.youtube.com/watch?v=${v.id}" target="_blank" class="vid-thumb-link">
          <div class="vid-thumb">
            <img src="${v.thumbnail}" alt="${v.title}" loading="lazy" />
            <div class="play-overlay">
              <span class="play-icon">▶</span>
            </div>
          </div>
        </a>
        <div class="vid-info">
          <div class="vid-title">${v.title}</div>
          <div class="vid-meta">${new Date(v.published).toLocaleDateString()}</div>
        </div>
      `;
      grid.appendChild(card);
    });
    
    // Trigger reveal for new items
    if (typeof ro !== 'undefined') {
      grid.querySelectorAll('.reveal').forEach(el => ro.observe(el));
    }
  };

  const fetchRecentVideos = async (token = null) => {
    try {
      const url = token ? `/api/youtube/videos?pageToken=${token}` : '/api/youtube/videos';
      const resp = await fetch(url);
      const data = await resp.json();
      
      if (data.videos) {
        renderVideos(data.videos, !token);
        nextPageToken = data.nextPageToken;
        const btnWrap = document.getElementById('load-more-wrap');
        if (btnWrap) btnWrap.style.display = nextPageToken ? 'flex' : 'none';
      }
    } catch (e) {
      console.warn("YouTube Videos fetch failed:", e);
    }
  };

  const searchVideos = async (query) => {
    if (!query) {
      isSearching = false;
      fetchRecentVideos();
      return;
    }
    isSearching = true;
    try {
      const resp = await fetch(`/api/youtube/search?q=${encodeURIComponent(query)}`);
      const videos = await resp.json();
      if (Array.isArray(videos)) {
        renderVideos(videos, true);
        const btnWrap = document.getElementById('load-more-wrap');
        if (btnWrap) btnWrap.style.display = 'none'; // Search doesn't paginate in this demo
      }
    } catch (e) {
      console.warn("YouTube Search failed:", e);
    }
  };

  // Event Listeners
  const loadMoreBtn = document.getElementById('load-more-btn');
  if (loadMoreBtn) {
    loadMoreBtn.addEventListener('click', () => {
      if (nextPageToken) fetchRecentVideos(nextPageToken);
    });
  }

  const searchInput = document.getElementById('yt-search');
  if (searchInput) {
    let debounce;
    searchInput.addEventListener('input', (e) => {
      clearTimeout(debounce);
      debounce = setTimeout(() => searchVideos(e.target.value), 400);
    });
  }

  // Initial Call
  if (document.getElementById('yt-grid')) {
    fetchYouTubeStats();
    fetchRecentVideos();
  }

  // ── Footer year ──
  const yr = document.getElementById('footer-year');
  if (yr) yr.textContent = new Date().getFullYear();

  // ── DYNAMIC NAVIGATION (AUTH STATUS) ──
  async function updateNavAuth() {
    const navLinks = document.querySelector('.nav-links');
    if (!navLinks) return;

    // Check if we have cached auth data for this session
    const cachedUser = sessionStorage.getItem('vroyals_user');
    if (cachedUser) {
      applyNavAuth(JSON.parse(cachedUser));
    }

    try {
      const resp = await fetch('/api/user/status');
      const user = await resp.json();
      
      if (user.logged_in) {
        sessionStorage.setItem('vroyals_user', JSON.stringify(user));
        applyNavAuth(user);
      } else {
        sessionStorage.removeItem('vroyals_user');
        applyNavAuth({ logged_in: false });
      }
    } catch (e) {
      console.warn("Auth check failed:", e);
    }
  }

  function applyNavAuth(user) {
    if (user.logged_in) {
      document.documentElement.classList.add('user-logged-in');

      // Personalize Profile fields
      const firstName = (user.full_name || 'User').split(' ')[0];
      
      // Update desktop/mobile nav placeholders
      document.querySelectorAll('.user-name-placeholder').forEach(el => {
        el.textContent = firstName;
      });
      
      document.querySelectorAll('.user-avatar-placeholder').forEach(el => {
        if (user.avatar) {
          el.innerHTML = `<img src="${user.avatar}" style="width:20px; height:20px; border-radius:50%; display:block">`;
        } else {
          el.innerHTML = '👤';
        }
      });

      // Dynamic Admin Link insertion
      if (user.is_admin) {
        document.querySelectorAll('.nav-links').forEach(navLinks => {
          if (!navLinks.querySelector('.nav-admin-link')) {
            const adminLi = document.createElement('li');
            adminLi.className = 'nav-admin-link';
            adminLi.innerHTML = `<a href="/admin" style="color:var(--accent2); font-weight:600">Admin</a>`;
            const yourItems = navLinks.querySelector('li.nav-logged-in');
            if (yourItems) {
              navLinks.insertBefore(adminLi, yourItems);
            } else {
              navLinks.appendChild(adminLi);
            }
          }
        });
        document.querySelectorAll('.mobile-drawer').forEach(drawer => {
          if (!drawer.querySelector('.nav-admin-link-mobile')) {
            const adminA = document.createElement('a');
            adminA.className = 'nav-admin-link-mobile';
            adminA.href = '/admin';
            adminA.style.color = 'var(--accent2)';
            adminA.style.fontWeight = '600';
            adminA.textContent = 'Admin';
            const yourItemsMobile = drawer.querySelector('a.nav-logged-in');
            if (yourItemsMobile) {
              drawer.insertBefore(adminA, yourItemsMobile);
            } else {
              drawer.appendChild(adminA);
            }
          }
        });
      } else {
        document.querySelectorAll('.nav-admin-link, .nav-admin-link-mobile').forEach(el => el.remove());
      }

      // Personalize Homepage Hero (if on index)
      const heroTitle = document.querySelector('.hero-content h1');
      const heroDesc = document.querySelector('.hero-content .section-desc');
      const heroBtn = document.querySelector('.hero-btns .btn-primary');

      if (heroTitle && (location.pathname.includes('index') || location.pathname === '/' || location.pathname.endsWith('/'))) {
        heroTitle.innerHTML = `Welcome Back,<br><em style="font-style:normal;color:var(--accent)">${firstName}.</em>`;
        if (heroDesc) heroDesc.textContent = "Your creative assets and private projects are ready. Access your studio-grade vault below.";
        if (heroBtn) {
          heroBtn.textContent = "Open My Vault →";
          heroBtn.href = "my-reels.html";
        }
      }
    } else {
      document.documentElement.classList.remove('user-logged-in');
      document.querySelectorAll('.nav-admin-link, .nav-admin-link-mobile').forEach(el => el.remove());
    }
  }

  // ── USER REVIEWS (DYNAMIC BEFORE FOOTER) ──
  async function initReviews() {
    const footer = document.querySelector('.site-footer');
    if (!footer) return;

    try {
      const resp = await fetch('/api/reviews');
      const reviews = await resp.json();
      if (!reviews || !reviews.length) return;

      // Create container
      const reviewSection = document.createElement('section');
      reviewSection.className = 'reviews-section reveal';
      reviewSection.id = 'dynamic-reviews-section';
      reviewSection.innerHTML = `
        <div class="container">
          <div class="section-label">Testimonials</div>
          <h2 style="margin-bottom:3rem; text-align:center">Client <em style="color:var(--accent); font-style:normal">Success.</em></h2>
          <div class="reviews-viewport">
            <div class="reviews-track" id="reviews-track"></div>
          </div>
        </div>
      `;
      footer.parentNode.insertBefore(reviewSection, footer);
      const track = document.getElementById('reviews-track');

      reviews.forEach(r => {
        const rating = r.rating || 5;
        const stars = '★'.repeat(rating) + '☆'.repeat(5 - rating);
        const card = document.createElement('div');
        card.className = 'review-card';
        card.innerHTML = `
          <div class="review-stars">${stars}</div>
          <p class="review-text">"${r.comment}"</p>
          <div class="review-user">
            ${r.avatar_url ? `<img src="${r.avatar_url}" alt="${r.user_name}">` : '<div style="width:50px; height:50px; border-radius:50%; background:var(--surface2); display:flex; align-items:center; justify-content:center; border:2px solid var(--accent)">👤</div>'}
            <div>
              <div class="rev-name">${r.user_name}</div>
              <div class="rev-role">${r.user_role || 'Verified Client'}</div>
              ${r.item_name ? `<div style="font-size:0.65rem; color:var(--accent); margin-top:0.2rem">Project: ${r.item_name}</div>` : ''}
            </div>
          </div>
        `;
        track.appendChild(card);
      });

      // Clone the first item and append to end for infinite loop
      if (reviews.length > 1) {
        const firstClone = track.firstElementChild.cloneNode(true);
        track.appendChild(firstClone);
      }

      // Show section immediately
      setTimeout(() => {
        reviewSection.classList.add('visible');
      }, 500);

      // Infinite Slider Logic
      if (reviews.length > 1) {
        let index = 0;
        const totalSlides = reviews.length;
        
        setInterval(() => {
          index++;
          track.style.transition = 'transform 0.8s cubic-bezier(0.65, 0, 0.35, 1)';
          track.style.transform = `translateX(${index * -100}%)`;

          // If we reached the clone
          if (index === totalSlides) {
            setTimeout(() => {
              track.style.transition = 'none';
              index = 0;
              track.style.transform = `translateX(0%)`;
            }, 800); // Match transition duration
          }
        }, 2000); 
      }

    } catch (e) {
      console.error("Reviews fetch failed:", e);
    }
  }

  // ── STORE PREVIEW (HOMEPAGE) ──
  async function initStorePreview() {
    const grid = document.getElementById('index-store-grid');
    if (!grid) return;

    try {
      const resp = await fetch('/api/store');
      const products = await resp.json();
      if (!products || products.length === 0) return;

      grid.innerHTML = '';
      // Show only top 3
      products.slice(0, 3).forEach((p, idx) => {
        const card = document.createElement('div');
        card.className = 'v-card reveal';
        card.style.display = 'flex';
        card.style.flexDirection = 'column';
        if (idx === 1) card.style.borderColor = 'rgba(245,197,24,0.25)';

        card.innerHTML = `
          ${idx === 1 ? '<span class="badge badge-gold" style="margin-bottom: 1rem;">Popular</span>' : ''}
          <h4>${p.title}</h4>
          <p style="font-size: 0.875rem; margin-top: 0.5rem; flex: 1;">${p.description}</p>
          <div class="store-card-footer" style="display:flex; justify-content:space-between; align-items:center; margin-top:1.5rem">
            <span class="price-tag" style="font-weight:700; color:var(--accent); font-size:1.1rem">₹${p.sale_price}</span>
            <a href="projects.html" class="btn ${idx === 1 ? 'btn-primary' : 'btn-ghost'} btn-sm">Buy Now</a>
          </div>
        `;
        grid.appendChild(card);
      });

      // Trigger reveal
      setTimeout(() => {
        grid.querySelectorAll('.reveal').forEach(el => el.classList.add('visible'));
      }, 100);
    } catch (e) {
      console.warn("Store preview failed:", e);
    }
  }

  initStorePreview();
  initReviews();
  updateNavAuth();
})();
