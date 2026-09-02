import { Bell } from 'lucide-react';
import { useState } from 'react';

import { api, type Notification } from '../lib/api';
import { dateTime } from '../lib/format';
import { useApi } from '../lib/useApi';
import { Modal, ModalHead } from './ui';
import './chainstatus.css';

/**
 * What is waiting for this organisation.
 *
 * Addressed by MSP, so a factory sees what was sent to the factory. The list is
 * short by design: a notification here is a pointer to somewhere else in the
 * product, not a place to do work.
 */
export function Notices() {
  const [open, setOpen] = useState(false);
  const notices = useApi(() => api.notifications(), []);
  const items: Notification[] = notices.data ?? [];
  const unread = items.filter((n) => !n.read).length;

  // Nothing addressed to this organisation, or the role cannot read them: no
  // control at all rather than a bell that opens on an empty box.
  if (notices.error || items.length === 0) return null;

  return (
    <>
      <button
        type="button"
        className="notices"
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
        aria-label={`${unread} notices for your organisation`}
      >
        <Bell size={14} strokeWidth={1.75} />
        <span className="stamp-type notices__label">Notices</span>
        {unread > 0 && <span className="notices__count mono">{unread}</span>}
      </button>

      {open && (
        <Modal label="Notices" onClose={() => setOpen(false)}>
          <ModalHead
            eyebrow={`${items.length} addressed to your organisation`}
            title="Notices"
            onClose={() => setOpen(false)}
          />
          <div className="modal__body">
            <ul className="notices__list">
              {items.map((n) => (
                <li key={n.id} className="notices__row">
                  <span className="stamp-type notices__kind">
                    {n.kind.replace(/_/g, ' ')}
                  </span>
                  <span className="notices__body">{n.body}</span>
                  <span className="small dim">{dateTime(n.created_at)}</span>
                </li>
              ))}
            </ul>
          </div>
        </Modal>
      )}
    </>
  );
}
