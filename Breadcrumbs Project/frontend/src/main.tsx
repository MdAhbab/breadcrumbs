import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';

// Global layers first. Importing App above these would pull every component
// stylesheet in ahead of the base layer, and equal-specificity rules like
// `.grain { position: relative }` would then win over the component rules they
// are meant to sit beneath.
import './styles/tokens.css';
import './styles/base.css';

import App from './App';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);

// Retire the boot screen once there is something behind it. Two frames, not
// one: the first schedules React's commit, the second happens after it paints.
requestAnimationFrame(() => {
  requestAnimationFrame(() => {
    const boot = document.getElementById('boot');
    if (!boot) return;
    boot.classList.add('is-done');
    window.setTimeout(() => boot.remove(), 280);
  });
});
