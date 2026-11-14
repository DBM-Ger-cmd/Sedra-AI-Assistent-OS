// Toast/Notification System – Token-only, Dark/Light ready
// Einbindung: nach tokens.css, ui/toasts.css

(function() {
  const root = typeof window !== 'undefined' ? window : globalThis;
  
  const DEFAULT_DURATION = 6000;
  const MAX_TOASTS = 3;
  
  let container = null;
  let toasts = [];
  
  function getContainer() {
    if (!container && typeof document !== 'undefined') {
      container = document.querySelector('.toast-container');
      if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        container.setAttribute('role', 'region');
        container.setAttribute('aria-label', 'Benachrichtigungen');
        container.setAttribute('aria-live', 'polite');
        document.body.appendChild(container);
      }
    }
    return container;
  }
  
  function createToastElement(options) {
    const { type = 'note', title, message, actions, duration = DEFAULT_DURATION, onClose } = options;
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.setAttribute('role', 'status');
    toast.setAttribute('aria-live', 'polite');
    toast.setAttribute('aria-atomic', 'true');
    
    // Icon
    const icon = document.createElement('div');
    icon.className = 'toast-icon';
    icon.setAttribute('aria-hidden', 'true');
    toast.appendChild(icon);
    
    // Content
    const content = document.createElement('div');
    content.className = 'toast-content';
    
    if (title) {
      const titleEl = document.createElement('div');
      titleEl.className = 'toast-title';
      titleEl.textContent = title;
      content.appendChild(titleEl);
    }
    
    if (message) {
      const msgEl = document.createElement('div');
      msgEl.className = 'toast-message';
      msgEl.textContent = message;
      content.appendChild(msgEl);
    }
    
    toast.appendChild(content);
    
    // Actions
    if (actions && actions.length) {
      const actionsEl = document.createElement('div');
      actionsEl.className = 'toast-actions';
      actions.forEach(action => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = `btn btn-${action.variant || 'ghost'} btn-sm`;
        btn.textContent = action.label;
        btn.onclick = () => {
          if (action.onClick) action.onClick();
          if (!action.keepOpen) removeToast(toast);
        };
        actionsEl.appendChild(btn);
      });
      toast.appendChild(actionsEl);
    }
    
    // Close button
    const closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'toast-close';
    closeBtn.setAttribute('aria-label', 'Schließen');
    closeBtn.innerHTML = '<svg class="icon" aria-hidden="true"><use href="#icon-x-circle"/></svg>';
    closeBtn.onclick = () => removeToast(toast);
    toast.appendChild(closeBtn);
    
    // Progress bar for auto-dismiss
    if (duration > 0) {
      const progress = document.createElement('div');
      progress.className = 'toast-progress';
      progress.style.animationDuration = duration + 'ms';
      toast.appendChild(progress);
    }
    
    // Pause on hover
    toast.addEventListener('mouseenter', () => {
      toast.style.animationPlayState = 'paused';
      if (progress) progress.style.animationPlayState = 'paused';
    });
    
    toast.addEventListener('mouseleave', () => {
      toast.style.animationPlayState = 'running';
      if (progress) progress.style.animationPlayState = 'running';
    });
    
    return toast;
  }
  
  function show(options) {
    const container = getContainer();
    if (!container) return null;
    
    // Limit toasts
    while (toasts.length >= MAX_TOASTS) {
      removeToast(toasts[0]);
    }
    
    const toast = createToastElement(options);
    container.appendChild(toast);
    toasts.push(toast);
    
    // Auto remove
    if (options.duration && options.duration > 0) {
      setTimeout(() => removeToast(toast), options.duration);
    }
    
    return {
      element: toast,
      close: () => removeToast(toast),
      update: (newOptions) => updateToast(toast, newOptions)
    };
  }
  
  function removeToast(toast) {
    if (!toast || !toast.parentNode) return;
    
    toast.style.animation = 'hs-fade-out var(--transition-fast) forwards, hs-slide-out-right var(--transition-fast) forwards';
    
    setTimeout(() => {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
      const idx = toasts.indexOf(toast);
      if (idx >= 0) toasts.splice(idx, 1);
    }, 200);
  }
  
  function updateToast(toast, options) {
    if (!toast) return;
    
    if (options.message) {
      const msgEl = toast.querySelector('.toast-message');
      if (msgEl) msgEl.textContent = options.message;
    }
    
    if (options.title) {
      const titleEl = toast.querySelector('.toast-title');
      if (titleEl) titleEl.textContent = options.title;
    }
  }
  
  // Convenience methods
  function note(message, title, options = {}) {
    return show({ type: 'note', title, message, ...options });
  }
  
  function ok(message, title, options = {}) {
    return show({ type: 'ok', title, message, ...options });
  }
  
  function warn(message, title, options = {}) {
    return show({ type: 'warn', title, message, ...options });
  }
  
  function bad(message, title, options = {}) {
    return show({ type: 'bad', title, message, duration: 10000, ...options });
  }
  
  function clearAll() {
    [...toasts].forEach(removeToast);
  }
  
  // Export
  root.sedraToast = {
    show,
    note,
    ok,
    warn,
    bad,
    clearAll
  };
  
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { show, note, ok, warn, bad, clearAll };
  }
})();

// Keyframes für Toast Exit (in tokens.css oder hier via JS)
if (typeof document !== 'undefined' && !document.getElementById('toast-exit-keyframes')) {
  const style = document.createElement('style');
  style.id = 'toast-exit-keyframes';
  style.textContent = `
    @keyframes hs-fade-out {
      from { opacity: 1; }
      to { opacity: 0; }
    }
    @keyframes hs-slide-out-right {
      from { transform: translateX(0); }
      to { transform: translateX(100%); }
    }
  `;
  document.head.appendChild(style);
}