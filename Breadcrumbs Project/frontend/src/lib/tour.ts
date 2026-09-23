import { useSyncExternalStore } from 'react';

import type { RoleId } from './api';

/**
 * The guided run-through.
 *
 * The product is five workspaces that can be entered in any order, and that is
 * correct for someone who works in one of them — but it left a first-time
 * visitor with no path at all. There was no answer to "show me what this does",
 * which is the only question a judge, a buyer or a new operator actually
 * arrives with.
 *
 * So there is now one ordered path through the whole system. It signs itself in
 * as whichever of the five people the next step belongs to, so the visitor
 * never has to know that the story changes hands four times. Every step lands
 * on a real screen doing real work — the tour narrates the product, it does not
 * replace it with slides.
 */

export interface TourStep {
  /** Who this step happens to. Null where no account is needed. */
  role: RoleId | null;
  to: string;
  /** The person's name, for the "now you are…" line. Filled from the API. */
  who: string;
  title: string;
  body: string;
  /** The one thing to do here, if anything. Absent for read-only stops. */
  todo?: string;
}

/**
 * Part one: how one figure gets proved.
 *
 * This is the whole product in ten steps, and it is the one a first-time
 * visitor needs. It ends on the model refusal, which is the part worth staying
 * for.
 *
 * The wording tracks the screens. Every label a step tells somebody to press
 * has to be the label they will actually see, which is why this file changes
 * whenever the navigation does — a walkthrough naming a button that was renamed
 * last week is worse than no walkthrough, because it teaches the reader that
 * the instructions are not to be trusted.
 */
export const TOUR: TourStep[] = [
  {
    role: 'factory',
    to: '/factory/dashboard',
    who: 'the factory',
    title: 'A factory files its documents',
    body:
      'Each line is a real document, like a wage sheet or a safety check. '
      + 'The files stay in the factory. Only a fingerprint of each one goes on the ledger.',
  },
  {
    role: 'factory',
    to: '/factory/upload',
    who: 'the factory',
    title: 'Upload a document',
    body:
      'Your browser makes the fingerprint. Only the fingerprint is sent. '
      + 'The rows stay with the factory.',
    todo: 'Upload a document, or just carry on.',
  },
  {
    role: 'buyer',
    to: '/buyer/portal',
    who: 'a buyer',
    title: 'A buyer asks for a figure',
    body:
      'A buyer cannot browse the factory. It asks for one figure, from one document type '
      + 'and one month, and says why. The factory can say no.',
    todo: 'Send a request.',
  },
  {
    role: 'factory',
    to: '/factory/access',
    who: 'the factory',
    title: 'The factory decides',
    body:
      'The request waits here. Approving shares one column of one document, until a date. '
      + 'Nothing else is shared.',
    todo: 'Approve the request.',
  },
  {
    role: 'buyer',
    to: '/buyer/portal',
    who: 'a buyer',
    title: 'The buyer opens what it was given',
    body:
      'The new permission is in the list. Open it to see the shared column. '
      + 'Everything else in the file stays locked.',
    todo: 'Open the newest permission.',
  },
  {
    role: 'buyer',
    to: '/verify',
    who: 'a buyer',
    title: 'The buyer checks the figure',
    body:
      'This is the point of the system. A check rebuilds the fingerprint and compares it '
      + 'with the one on the ledger. If they match, the figure is real. Each check leaves a receipt.',
    todo: 'Check every row and watch each one turn green.',
  },
  {
    role: 'auditor',
    to: '/auditor/workspace',
    who: 'an auditor',
    title: 'An auditor checks a whole batch',
    body:
      'The same check, run on many documents at once. Each pass leaves a receipt the '
      + 'factory can see.',
    todo: 'Run the batch.',
  },
  {
    role: 'auditor',
    to: '/periods',
    who: 'an auditor',
    title: 'Is the month complete?',
    body:
      'A closed month has a fixed count of documents. If you were shown fewer, the count '
      + 'does not add up. Nobody has to be trusted to notice.',
  },
  {
    role: 'consortium',
    to: '/model/gate',
    who: 'the consortium',
    title: 'The AI model is checked too',
    body:
      'The members share one AI model. An update that gets worse at an old task is refused, '
      + 'with the reason on the ledger.',
  },
  {
    role: 'consortium',
    to: '/ledger',
    who: 'the consortium',
    title: 'All of it is on here',
    body:
      'The upload, the request, the approval, the checks and the refusal. Five organisations '
      + 'hold a copy. None of them can change it later.',
  },
];

/**
 * Part two: the rest of the system.
 *
 * Offered at the end of part one and easy to skip. These are the screens that
 * matter to somebody who has decided the idea works and now wants to know what
 * else is in the box.
 */
export const TOUR_MORE: TourStep[] = [
  {
    role: 'factory',
    to: '/factory/records',
    who: 'the factory',
    title: 'Look inside a document',
    body:
      'Open any document to see its rows. The factory sees everything. A buyer sees only '
      + 'the columns it was given. Nobody outside the factory sees a worker\u2019s name.',
    todo: 'Open a document.',
  },
  {
    role: 'buyer',
    to: '/buyer/portal',
    who: 'a buyer',
    title: 'Ask for several figures at once',
    body:
      'Tick several figures and send them together. Each one is still its own permission. '
      + 'The factory can refuse any of them.',
    todo: 'Tick two or three figures and send them.',
  },
  {
    role: 'factory',
    to: '/factory/access',
    who: 'the factory',
    title: 'Answer them together, or one by one',
    body:
      'Approve the whole set with one press, or refuse one figure with a reason. '
      + 'If one fails, the rest still go through.',
    todo: 'Approve a set, or refuse one figure.',
  },
  {
    role: 'buyer',
    to: '/buyer/portal',
    who: 'a buyer',
    title: 'Come back for more',
    body:
      'Any permission can start a new request for the same factory, document type and month. '
      + 'Nothing has to be typed twice.',
  },
  {
    role: 'auditor',
    to: '/factory/records',
    who: 'an auditor',
    title: 'An auditor does not have to ask',
    body:
      'An auditor can open any document without asking. Columns that name a person stay closed.',
    todo: 'Open any document.',
  },
  {
    role: 'auditor',
    to: '/factory/records',
    who: 'an auditor',
    title: 'Reading is not checking',
    body:
      'Reading writes nothing. A check writes a receipt on the ledger. So a check still needs '
      + 'a permission from the factory.',
    todo: 'Open a document and check every row.',
  },
  {
    role: 'auditor',
    to: '/factory/records',
    who: 'an auditor',
    title: 'Sign off on what you read',
    body:
      'At the foot of any document you can confirm your review. It becomes its own document, '
      + 'with your name on it.',
    todo: 'Open a document, scroll down, and sign.',
  },
  {
    role: 'factory',
    to: '/periods',
    who: 'the factory',
    title: 'Close a month',
    body:
      'Closing fixes how many documents a month holds. A late document shows as a correction. '
      + 'You can also share documents from here.',
    todo: 'Press "Close this month" and read the panel first.',
  },
  {
    role: 'consortium',
    to: '/governance',
    who: 'the consortium',
    title: 'Members vote',
    body:
      'A new member needs the others to agree. When the vote passes, the member is added '
      + 'to the ledger straight away.',
    todo: 'Agree to the membership proposal.',
  },
  {
    role: 'consortium',
    to: '/anchor',
    who: 'the consortium',
    title: 'Prove something is not there',
    body:
      'You can prove a certificate was never issued. The other side can check it for itself.',
    todo: 'Try a certificate that was never filed.',
  },
  {
    role: 'consortium',
    to: '/model/registry',
    who: 'the consortium',
    title: 'Every version of the AI model',
    body:
      'Approved and refused, in order. Each was tested on problems fixed before the round began.',
  },
  {
    role: 'regulator',
    to: '/regulator',
    who: 'a regulator',
    title: 'What a regulator sees',
    body:
      'Counts and votes, and no factory document. The closed parts are still shown, with the reason.',
  },
  {
    role: 'regulator',
    to: '/anchor',
    who: 'a regulator',
    title: 'What a regulator can check',
    body:
      'A regulator can check that nothing was altered. It can do this without reading any document.',
  },
];

/* ------------------------------------------------------------------ store -- */

const KEY = 'breadcrumbs.tour';

export type TourPart = 'main' | 'more';

interface TourState {
  active: boolean;
  step: number;
  /** Which script is running. Part two is opt-in at the end of part one. */
  part: TourPart;
}

const SCRIPTS: Record<TourPart, TourStep[]> = { main: TOUR, more: TOUR_MORE };

function read(): TourState {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return { active: false, step: 0, part: 'main' };
    const parsed = JSON.parse(raw) as TourState;
    const part: TourPart = parsed.part === 'more' ? 'more' : 'main';
    // A script edit must never strand a returning visitor past the last step.
    const step = Math.min(Math.max(parsed.step | 0, 0), SCRIPTS[part].length - 1);
    return { active: Boolean(parsed.active), step, part };
  } catch {
    return { active: false, step: 0, part: 'main' };
  }
}

let state: TourState = read();
const listeners = new Set<() => void>();

function set(next: TourState) {
  state = next;
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    /* the tour lives for this page only */
  }
  listeners.forEach((l) => l());
}

export const startTour = (part: TourPart = 'main') => set({ active: true, step: 0, part });
export const endTour = () => set({ active: false, step: 0, part: 'main' });
export const goToStep = (i: number) =>
  set({
    ...state,
    active: true,
    step: Math.min(Math.max(i, 0), SCRIPTS[state.part].length - 1),
  });

/** The steps of whichever part is running. */
export const stepsOf = (part: TourPart): TourStep[] => SCRIPTS[part];

function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

export function useTour(): TourState & { current: TourStep; total: number; steps: TourStep[] } {
  const s = useSyncExternalStore(
    subscribe,
    () => state,
    () => ({ active: false, step: 0, part: 'main' as TourPart }),
  );
  const steps = SCRIPTS[s.part];
  return { ...s, steps, current: steps[s.step], total: steps.length };
}
