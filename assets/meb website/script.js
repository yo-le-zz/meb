/* ==========================================================================
   MEB (Make Easy Deb) — script.js
   Repo   : https://github.com/yo-le-zz/meb
   Auteur : yolezz
   Ce fichier gère :
     1. Le fond animé (points lumineux en WebGL)
     2. Le copier-coller des commandes
     3. Le scroll fluide de la nav
     4. La récupération dynamique de la dernière release GitHub
        (version, lien de téléchargement .deb, nombre de stars)
   ========================================================================== */

const GITHUB_REPO = 'yo-le-zz/meb';
const GITHUB_API_BASE = `https://api.github.com/repos/${GITHUB_REPO}`;

/* --------------------------------------------------------------------------
   1. Fond animé — points lumineux (WebGL shader)
   -------------------------------------------------------------------------- */
function initShaderBackground() {
  const canvas = document.getElementById('shader-canvas-ANIMATION_2');
  if (!canvas) return;

  function syncSize() {
    const w = canvas.clientWidth || 1280;
    const h = canvas.clientHeight || 720;
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
    }
  }
  if (typeof ResizeObserver !== 'undefined') {
    new ResizeObserver(syncSize).observe(canvas);
  }
  syncSize();

  const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
  // Pas de WebGL dispo (vieux navigateur / contexte perdu) : on abandonne
  // proprement, le fond reste simplement uni. C'était ce "return" hors
  // fonction qui cassait tout le script précédemment.
  if (!gl) return;

  const vs = `attribute vec2 a_position;
varying vec2 v_texCoord;
void main() {
  v_texCoord = a_position * 0.5 + 0.5;
  gl_Position = vec4(a_position, 0.0, 1.0);
}`;

  const fs = `precision highp float;
uniform float u_time;
uniform vec2 u_resolution;
uniform vec2 u_mouse;

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

void main() {
    vec2 p = (gl_FragCoord.xy - 0.5 * u_resolution.xy) / min(u_resolution.y, u_resolution.x);

    vec3 color = vec3(0.03, 0.08, 0.15); // Fond bleu nuit

    float m = 0.0;
    float t = u_time * 0.2;

    for (float i = 0.0; i < 40.0; i++) {
        vec2 pos = vec2(hash(vec2(i, 1.0)) - 0.5, hash(vec2(i, 2.0)) - 0.5);
        pos *= 2.0;

        // Mouvement circulaire des points
        pos.x += sin(t + i) * 0.5;
        pos.y += cos(t + i * 0.5) * 0.5;

        float dist = length(p - pos);
        float sparkle = 0.002 / dist;
        sparkle *= smoothstep(1.0, 0.2, dist);

        // Interaction avec la souris
        vec2 mPos = (u_mouse - 0.5 * u_resolution.xy) / min(u_resolution.y, u_resolution.x);
        float mDist = length(p - mPos);
        sparkle += (0.001 / dist) * (1.0 - smoothstep(0.0, 0.3, mDist));

        m += sparkle;
    }

    color += vec3(0.1, 0.4, 0.9) * m; // Points lumineux bleus

    gl_FragColor = vec4(color, 1.0);
}`;

  function compileShader(type, src) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, src);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      console.error('MEB: erreur de compilation shader', gl.getShaderInfoLog(shader));
    }
    return shader;
  }

  const program = gl.createProgram();
  gl.attachShader(program, compileShader(gl.VERTEX_SHADER, vs));
  gl.attachShader(program, compileShader(gl.FRAGMENT_SHADER, fs));
  gl.linkProgram(program);
  gl.useProgram(program);

  const buffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);

  const positionLoc = gl.getAttribLocation(program, 'a_position');
  gl.enableVertexAttribArray(positionLoc);
  gl.vertexAttribPointer(positionLoc, 2, gl.FLOAT, false, 0, 0);

  const uTime = gl.getUniformLocation(program, 'u_time');
  const uRes = gl.getUniformLocation(program, 'u_resolution');
  const uMouse = gl.getUniformLocation(program, 'u_mouse');

  // u_mouse est en coordonnées pixels, alignées sur u_resolution.
  let mouse = { x: canvas.width / 2, y: canvas.height / 2 };
  window.addEventListener('mousemove', (event) => {
    const rect = canvas.getBoundingClientRect();
    if (rect.width && rect.height) {
      const nx = (event.clientX - rect.left) / rect.width;
      const ny = 1.0 - (event.clientY - rect.top) / rect.height;
      mouse.x = nx * canvas.width;
      mouse.y = ny * canvas.height;
    }
  });

  function render(t) {
    if (typeof ResizeObserver === 'undefined') syncSize();
    gl.viewport(0, 0, canvas.width, canvas.height);
    if (uTime) gl.uniform1f(uTime, t * 0.001);
    if (uRes) gl.uniform2f(uRes, canvas.width, canvas.height);
    if (uMouse) gl.uniform2f(uMouse, mouse.x, mouse.y);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    requestAnimationFrame(render);
  }
  requestAnimationFrame(render);
}

/* --------------------------------------------------------------------------
   2. Copier-coller des commandes
   -------------------------------------------------------------------------- */
function copyToClipboard(elementId) {
  const el = document.getElementById(elementId);
  if (!el) return;
  const text = el.innerText.trim();

  navigator.clipboard.writeText(text).then(() => {
    showToast('Copié dans le presse-papiers !');
  }).catch(() => {
    showToast("Impossible de copier — copiez manuellement.");
  });
}
// Exposé globalement car appelé depuis un attribut onclick="" dans le HTML
window.copyToClipboard = copyToClipboard;

// Petit toast non bloquant à la place de alert() (qui casse la démo/le clic)
function showToast(message) {
  let toast = document.getElementById('meb-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'meb-toast';
    toast.className = 'meb-toast';
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.classList.add('meb-toast-visible');
  clearTimeout(toast._hideTimeout);
  toast._hideTimeout = setTimeout(() => {
    toast.classList.remove('meb-toast-visible');
  }, 1800);
}

/* --------------------------------------------------------------------------
   3. Scroll fluide pour les ancres de nav
   -------------------------------------------------------------------------- */
function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener('click', function (e) {
      const targetId = this.getAttribute('href');
      if (!targetId || targetId.length <= 1) return; // ignore href="#"
      const target = document.querySelector(targetId);
      if (!target) return;
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth' });
    });
  });
}

/* --------------------------------------------------------------------------
   3bis. Scrollspy — souligne le lien de la section actuellement visible
   -------------------------------------------------------------------------- */
function initScrollSpy() {
  const navLinks = Array.from(document.querySelectorAll('#site-nav .nav-link'));
  if (!navLinks.length) return;

  const sections = navLinks
    .map((link) => document.getElementById(link.dataset.section))
    .filter(Boolean);
  if (!sections.length) return;

  function setActive(sectionId) {
    navLinks.forEach((link) => {
      const isActive = link.dataset.section === sectionId;
      link.classList.toggle('text-primary', isActive);
      link.classList.toggle('font-bold', isActive);
      link.classList.toggle('border-primary', isActive);
      link.classList.toggle('text-on-surface-variant', !isActive);
      link.classList.toggle('border-transparent', !isActive);
    });
  }

  // -96px en haut : compense le header fixe. -60% en bas : la section doit
  // occuper le haut du viewport pour être considérée "active".
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) setActive(entry.target.id);
      });
    },
    { rootMargin: '-96px 0px -60% 0px', threshold: 0 }
  );

  sections.forEach((section) => observer.observe(section));
}

/* --------------------------------------------------------------------------
   4. Contenu dynamique depuis l'API GitHub (repo yo-le-zz/meb)
   -------------------------------------------------------------------------- */
async function loadLatestRelease() {
  try {
    const res = await fetch(`${GITHUB_API_BASE}/releases/latest`, {
      headers: { Accept: 'application/vnd.github+json' },
    });
    if (!res.ok) throw new Error(`GitHub API: ${res.status}`);
    const release = await res.json();

    const tag = release.tag_name || 'v1.0.0';
    const versionNumber = tag.replace(/^v/, '');
    const debAsset = (release.assets || []).find((a) => a.name.endsWith('.deb'));

    document.querySelectorAll('[data-meb-version]').forEach((el) => {
      el.textContent = tag;
    });
    document.querySelectorAll('[data-meb-version-number]').forEach((el) => {
      el.textContent = versionNumber;
    });
    document.querySelectorAll('[data-meb-release-link]').forEach((a) => {
      a.href = release.html_url || `https://github.com/${GITHUB_REPO}/releases/latest`;
    });

    if (debAsset) {
      document.querySelectorAll('[data-meb-deb-link]').forEach((a) => {
        a.href = debAsset.browser_download_url;
      });
      document.querySelectorAll('[data-meb-deb-name]').forEach((el) => {
        el.textContent = debAsset.name;
      });
      document.querySelectorAll('[data-meb-deb-cmd]').forEach((el) => {
        el.textContent = `wget ${debAsset.browser_download_url}`;
      });
    }
  } catch (err) {
    // En cas d'échec (repo sans release, rate-limit GitHub, hors-ligne...),
    // on garde silencieusement les valeurs statiques déjà présentes dans le HTML.
    console.warn('MEB: impossible de récupérer la dernière release GitHub.', err);
  }
}

async function loadRepoStats() {
  try {
    // cache: 'no-store' pour toujours afficher le compte réel du moment,
    // y compris quand il baisse (pas de valeur figée par le cache navigateur).
    const res = await fetch(GITHUB_API_BASE, {
      headers: { Accept: 'application/vnd.github+json' },
      cache: 'no-store',
    });
    if (!res.ok) throw new Error(`GitHub API: ${res.status}`);
    const repo = await res.json();

    document.querySelectorAll('[data-meb-stars]').forEach((el) => {
      el.textContent = repo.stargazers_count ?? '0';
    });
    document.querySelectorAll('[data-meb-repo-link]').forEach((a) => {
      a.href = repo.html_url || `https://github.com/${GITHUB_REPO}`;
    });
  } catch (err) {
    console.warn('MEB: impossible de récupérer les statistiques du repo.', err);
  }
}

/* --------------------------------------------------------------------------
   5. Compteur de vues du site (service public counterapi.dev, sans backend)
   -------------------------------------------------------------------------- */
const VIEWS_NAMESPACE = 'yolezz-meb';
const VIEWS_COUNTER = 'site-views';

async function loadSiteViews() {
  try {
    const res = await fetch(
      `https://api.counterapi.dev/v1/${VIEWS_NAMESPACE}/${VIEWS_COUNTER}/up`,
      { cache: 'no-store' }
    );
    if (!res.ok) throw new Error(`CounterAPI: ${res.status}`);
    const data = await res.json();
    const count = data.count ?? data.value;
    if (count !== undefined) {
      document.querySelectorAll('[data-meb-views]').forEach((el) => {
        el.textContent = count.toLocaleString('fr-FR');
      });
    }
  } catch (err) {
    // Le compteur reste sur "--" si le service tiers est indisponible.
    console.warn('MEB: impossible de récupérer le compteur de vues.', err);
  }
}

/* --------------------------------------------------------------------------
   Point d'entrée
   -------------------------------------------------------------------------- */
document.addEventListener('DOMContentLoaded', () => {
  initShaderBackground();
  initSmoothScroll();
  initScrollSpy();
  loadLatestRelease();
  loadRepoStats();
  loadSiteViews();
});