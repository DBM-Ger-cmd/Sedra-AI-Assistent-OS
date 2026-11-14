// Icon Helper – SVG-Sprite Injection & Icon Rendering
// Einbindung: nach tokens.css, vor Shell-spezifischem JS
// Nutzt ui/icons.css (SVG-Sprite) – muss einmalig im DOM sein

(function() {
  const root = typeof window !== 'undefined' ? window : globalThis;
  
  // Icon-Namen Mapping (aus icons.css)
  const ICONS = {
    // Navigation
    'home': 'home',
    'folder': 'folder',
    'folder-open': 'folder-open',
    'message-square': 'message-square',
    'chat': 'chat',
    'search': 'search',
    'menu': 'menu',
    'chevron-left': 'chevron-left',
    'chevron-right': 'chevron-right',
    'chevron-down': 'chevron-down',
    'chevron-up': 'chevron-up',
    'arrow-left': 'arrow-left',
    'arrow-right': 'arrow-right',
    
    // Aktionen
    'plus': 'plus',
    'plus-circle': 'plus-circle',
    'edit': 'edit',
    'trash': 'trash',
    'copy': 'copy',
    'download': 'download',
    'upload': 'upload',
    'save': 'save',
    'refresh': 'refresh',
    'settings': 'settings',
    'cog': 'cog',
    'play': 'play',
    'pause': 'pause',
    'stop': 'stop',
    'record': 'record',
    'mic': 'mic',
    'mic-off': 'mic-off',
    
    // Zustände
    'check-circle': 'check-circle',
    'alert-circle': 'alert-circle',
    'alert-triangle': 'alert-triangle',
    'info': 'info',
    'help-circle': 'help-circle',
    'x-circle': 'x-circle',
    'loader': 'loader',
    'flag': 'flag',
    'shield': 'shield',
    'bell': 'bell',
    'bell-off': 'bell-off',
    
    // Objekte
    'file': 'file',
    'file-text': 'file-text',
    'code': 'code',
    'image': 'image',
    'database': 'database',
    'server': 'server',
    'cpu': 'cpu',
    'memory': 'memory',
    'globe': 'globe',
    'link': 'link',
    'unlink': 'unlink',
    'git-branch': 'git-branch',
    'git-commit': 'git-commit',
    'git-merge': 'git-merge',
    
    // Spezial
    'dragon': 'dragon',
    'dragon-3d': 'dragon-3d',
    'layers': 'layers',
    'layout': 'layout',
    'zap': 'zap',
    'coin': 'coin',
    'flask': 'flask',
    'pyramid': 'pyramid',
    'pyramid-3d': 'pyramid-3d'
  };
  
  let spriteInjected = false;
  
  // SVG-Sprite einmalig injizieren
  function injectSprite() {
    if (spriteInjected || typeof document === 'undefined') return;
    
    // Prüfen ob Sprite schon da ist
    if (document.getElementById('sedra-icon-sprite')) {
      spriteInjected = true;
      return;
    }
    
    // Sprite aus icons.css extrahieren (oder direkt hier definieren)
    // Für Performance: Sprite als separates File laden oder inline
    const spriteUrl = '/uix/ui/icons.css';
    
    fetch(spriteUrl)
      .then(r => r.text())
      .then(css => {
        // SVG aus CSS extrahieren (zwischen <svg> und </svg>)
        const match = css.match(/<svg[^>]*>[\s\S]*<\/svg>/);
        if (match) {
          const div = document.createElement('div');
          div.innerHTML = match[0];
          const svg = div.querySelector('svg');
          if (svg) {
            svg.id = 'sedra-icon-sprite';
            svg.setAttribute('aria-hidden', 'true');
            svg.style.display = 'none';
            document.body.insertBefore(svg, document.body.firstChild);
            spriteInjected = true;
          }
        }
      })
      .catch(() => {
        // Fallback: Sprite direkt hier definieren (minimal)
        console.warn('Icon sprite could not be loaded from CSS, using fallback');
      });
  }
  
  // Icon erstellen
  function createIcon(name, options = {}) {
    const iconName = ICONS[name] || name;
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
    
    svg.setAttribute('class', 'icon' + (options.size ? ' icon-' + options.size : ''));
    svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('role', 'img');
    
    if (options.title) {
      const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
      title.textContent = options.title;
      svg.appendChild(title);
    }
    
    use.setAttribute('href', '#icon-' + iconName);
    use.setAttribute('xlink:href', '#icon-' + iconName); // IE11 fallback
    svg.appendChild(use);
    
    if (options.class) {
      svg.classList.add(...options.class.split(' '));
    }
    
    if (options.style) {
      Object.assign(svg.style, options.style);
    }
    
    return svg;
  }
  
  // Icon als HTML String (für Templates)
  function iconHtml(name, options = {}) {
    const iconName = ICONS[name] || name;
    const sizeClass = options.size ? ' icon-' + options.size : '';
    const title = options.title ? `<title>${escapeHtml(options.title)}</title>` : '';
    const extraClass = options.class ? ' ' + options.class : '';
    return `<svg class="icon${sizeClass}${extraClass}" aria-hidden="true" role="img">${title}<use href="#icon-${iconName}"/></svg>`;
  }
  
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
  
  // Icon in Element rendern (ersetzen)
  function renderIcon(element, name, options = {}) {
    if (!element) return;
    const icon = createIcon(name, options);
    element.innerHTML = '';
    element.appendChild(icon);
    return icon;
  }
  
  // Auto-Inject beim Laden
  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', injectSprite);
    } else {
      injectSprite();
    }
  }
  
  // Export
  root.sedraIcons = {
    create: createIcon,
    html: iconHtml,
    render: renderIcon,
    inject: injectSprite,
    list: ICONS
  };
  
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { createIcon, iconHtml, renderIcon, injectSprite, ICONS };
  }
})();