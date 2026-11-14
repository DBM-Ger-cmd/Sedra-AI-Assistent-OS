// Dialog/Modal System – Token-only, Dark/Light ready
// Einbindung: nach tokens.css, ui/dialogs.css

(function() {
  const root = typeof window !== 'undefined' ? window : globalThis;
  
  let activeDialog = null;
  let focusHistory = [];
  
  // Focus Trap
  function trapFocus(element) {
    const focusable = element.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    
    function handleTab(e) {
      if (e.key !== 'Tab') return;
      
      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }
    
    element.addEventListener('keydown', handleTab);
    first?.focus();
    
    return () => element.removeEventListener('keydown', handleTab);
  }
  
  // Escape Handler
  function onEscape(e) {
    if (e.key === 'Escape' && activeDialog) {
      closeDialog(activeDialog);
    }
  }
  
  // Overlay Click
  function onOverlayClick(e) {
    if (e.target === e.currentTarget && activeDialog) {
      closeDialog(activeDialog);
    }
  }
  
  function openDialog(element, options = {}) {
    if (!element) return;
    
    // Close existing dialog
    if (activeDialog) closeDialog(activeDialog);
    
    activeDialog = element;
    element.classList.add('open');
    element.setAttribute('aria-modal', 'true');
    element.setAttribute('role', 'dialog');
    
    // Focus management
    const previouslyFocused = document.activeElement;
    focusHistory.push(previouslyFocused);
    
    const cleanupFocus = trapFocus(element);
    
    // Event listeners
    document.addEventListener('keydown', onEscape);
    const overlay = element.closest('.dialog-overlay');
    if (overlay) overlay.addEventListener('click', onOverlayClick);
    
    // Store cleanup
    element._dialogCleanup = () => {
      cleanupFocus();
      document.removeEventListener('keydown', onEscape);
      if (overlay) overlay.removeEventListener('click', onOverlayClick);
      
      // Restore focus
      const restore = focusHistory.pop();
      if (restore && typeof restore.focus === 'function') {
        restore.focus();
      }
    };
    
    if (options.onOpen) options.onOpen(element);
  }
  
  function closeDialog(element) {
    if (!element || element !== activeDialog) return;
    
    element.classList.remove('open');
    
    if (element._dialogCleanup) {
      element._dialogCleanup();
      element._dialogCleanup = null;
    }
    
    activeDialog = null;
    
    // Remove from DOM after animation if needed
    if (element.hasAttribute('data-auto-remove')) {
      setTimeout(() => {
        if (element.parentNode) element.parentNode.removeChild(element);
      }, 200);
    }
  }
  
  // Create dialog from template
  function createDialog(options = {}) {
    const {
      title = '',
      subtitle = '',
      content = '',
      footer = '',
      size = 'md', // sm, md, lg, xl, full
      closable = true,
      className = '',
      onOpen,
      onClose
    } = options;
    
    const overlay = document.createElement('div');
    overlay.className = 'dialog-overlay';
    overlay.setAttribute('data-auto-remove', 'true');
    
    const dialog = document.createElement('div');
    dialog.className = `dialog dialog-${size} ${className}`;
    dialog.setAttribute('role', 'dialog');
    dialog.setAttribute('aria-modal', 'true');
    if (title) dialog.setAttribute('aria-labelledby', 'dialog-title-' + Date.now());
    
    let html = '';
    
    if (title || closable) {
      html += '<div class="dialog-header">';
      if (title) {
        html += `<h2 id="dialog-title-${Date.now()}" class="dialog-title">${title}</h2>`;
        if (subtitle) html += `<p class="dialog-subtitle">${subtitle}</p>`;
      }
      if (closable) {
        html += '<button type="button" class="dialog-close" aria-label="Schließen"><svg class="icon" aria-hidden="true"><use href="#icon-x-circle"/></svg></button>';
      }
      html += '</div>';
    }
    
    html += `<div class="dialog-body">${content}</div>`;
    
    if (footer) {
      html += `<div class="dialog-footer">${footer}</div>`;
    }
    
    dialog.innerHTML = html;
    overlay.appendChild(dialog);
    
    // Close button handler
    const closeBtn = dialog.querySelector('.dialog-close');
    if (closeBtn) {
      closeBtn.onclick = () => closeDialog(dialog);
    }
    
    // Append to body
    document.body.appendChild(overlay);
    
    // Force reflow then open
    requestAnimationFrame(() => {
      overlay.classList.add('open');
      openDialog(dialog, { onOpen });
    });
    
    return {
      element: dialog,
      overlay,
      close: () => closeDialog(dialog),
      setContent: (newContent) => {
        const body = dialog.querySelector('.dialog-body');
        if (body) body.innerHTML = newContent;
      },
      setFooter: (newFooter) => {
        const footerEl = dialog.querySelector('.dialog-footer');
        if (footerEl) footerEl.innerHTML = newFooter;
      }
    };
  }
  
  // Alert Dialog
  function alert(options) {
    const { title = 'Hinweis', message, variant = 'info', okText = 'OK', onOk } = options;
    
    const icons = {
      info: '<svg class="icon icon-lg" aria-hidden="true"><use href="#icon-info"/></svg>',
      warn: '<svg class="icon icon-lg" aria-hidden="true"><use href="#icon-alert-triangle"/></svg>',
      bad: '<svg class="icon icon-lg" aria-hidden="true"><use href="#icon-alert-circle"/></svg>',
      ok: '<svg class="icon icon-lg" aria-hidden="true"><use href="#icon-check-circle"/></svg>',
      confirm: '<svg class="icon icon-lg" aria-hidden="true"><use href="#icon-help-circle"/></svg>'
    };
    
    const content = `
      <div class="alert-dialog-icon ${variant}" aria-hidden="true">${icons[variant] || icons.info}</div>
      <p class="alert-dialog-message">${message}</p>
    `;
    
    const footer = `<button type="button" class="btn btn-primary" data-dialog-ok>${okText}</button>`;
    
    return new Promise(resolve => {
      const dialog = createDialog({
        title,
        content,
        footer,
        size: 'sm',
        onOpen: (el) => {
          const btn = el.querySelector('[data-dialog-ok]');
          btn.focus();
          btn.onclick = () => {
            dialog.close();
            resolve(true);
            if (onOk) onOk();
          };
        }
      });
    });
  }
  
  // Confirm Dialog
  function confirm(options) {
    const { title = 'Bestätigen', message, variant = 'confirm', confirmText = 'Bestätigen', cancelText = 'Abbrechen', confirmVariant = 'primary', onConfirm, onCancel } = options;
    
    const icons = {
      info: '<svg class="icon icon-lg" aria-hidden="true"><use href="#icon-info"/></svg>',
      warn: '<svg class="icon icon-lg" aria-hidden="true"><use href="#icon-alert-triangle"/></svg>',
      bad: '<svg class="icon icon-lg" aria-hidden="true"><use href="#icon-alert-circle"/></svg>',
      confirm: '<svg class="icon icon-lg" aria-hidden="true"><use href="#icon-help-circle"/></svg>'
    };
    
    const content = `
      <div class="alert-dialog-icon ${variant}" aria-hidden="true">${icons[variant] || icons.confirm}</div>
      <p class="alert-dialog-message">${message}</p>
    `;
    
    const footer = `
      <button type="button" class="btn btn-ghost" data-dialog-cancel>${cancelText}</button>
      <button type="button" class="btn btn-${confirmVariant}" data-dialog-confirm>${confirmText}</button>
    `;
    
    return new Promise(resolve => {
      const dialog = createDialog({
        title,
        content,
        footer,
        size: 'sm',
        onOpen: (el) => {
          const confirmBtn = el.querySelector('[data-dialog-confirm]');
          const cancelBtn = el.querySelector('[data-dialog-cancel]');
          confirmBtn.focus();
          
          confirmBtn.onclick = () => {
            dialog.close();
            resolve(true);
            if (onConfirm) onConfirm();
          };
          
          cancelBtn.onclick = () => {
            dialog.close();
            resolve(false);
            if (onCancel) onCancel();
          };
        }
      });
    });
  }
  
  // Prompt Dialog
  function prompt(options) {
    const { title = 'Eingabe', message, placeholder = '', value = '', okText = 'OK', cancelText = 'Abbrechen', onOk } = options;
    
    const content = `
      <p class="alert-dialog-message" style="text-align:left;margin:0 0 16px">${message}</p>
      <label class="prompt-dialog-label" for="prompt-input">${title}</label>
      <input type="text" id="prompt-input" class="prompt-dialog-input input" placeholder="${placeholder}" value="${value}" autocomplete="off">
    `;
    
    const footer = `
      <button type="button" class="btn btn-ghost" data-dialog-cancel>${cancelText}</button>
      <button type="button" class="btn btn-primary" data-dialog-ok>${okText}</button>
    `;
    
    return new Promise(resolve => {
      const dialog = createDialog({
        title,
        content,
        footer,
        size: 'sm',
        onOpen: (el) => {
          const input = el.querySelector('#prompt-input');
          const okBtn = el.querySelector('[data-dialog-ok]');
          const cancelBtn = el.querySelector('[data-dialog-cancel]');
          input.focus();
          input.select();
          
          const submit = () => {
            dialog.close();
            resolve(input.value);
            if (onOk) onOk(input.value);
          };
          
          okBtn.onclick = submit;
          cancelBtn.onclick = () => {
            dialog.close();
            resolve(null);
          };
          
          input.addEventListener('keydown', e => {
            if (e.key === 'Enter') submit();
            if (e.key === 'Escape') cancelBtn.click();
          });
        }
      });
    });
  }
  
  // Export
  root.sedraDialog = {
    open: openDialog,
    close: closeDialog,
    create: createDialog,
    alert,
    confirm,
    prompt
  };
  
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { openDialog, closeDialog, createDialog, alert, confirm, prompt };
  }
})();