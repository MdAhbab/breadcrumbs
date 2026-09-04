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
      'Every line here is a real document, like a wage sheet or a safety check, '
      + 'and none of them left the factory. What went onto the shared record is only a '
      + 'fingerprint of each file. That is enough to prove the file later, and not '
      + 'enough to read it.',
  },
  {
    role: 'factory',
    to: '/factory/upload',
    who: 'the factory',
    title: 'Watch one being filed',
    body:
      'The file is fingerprinted here in the browser, and only the fingerprint is sent. '
      + 'You can see how much stays behind: thousands of rows, none of which the shared '
      + 'record ever sees.',
    todo: 'Upload a document, or just carry on.',
  },
  {
    role: 'buyer',
    to: '/buyer/portal',
    who: 'a buyer',
    title: 'A buyer asks for one figure',
    body:
      'The buyer cannot browse the factory. It can only ask a narrow question: one '
      + 'column, one kind of document, one month, and a reason. That question goes to '
      + 'the factory, which is free to say no.',
    todo: 'Send a request.',
  },
  {
    role: 'factory',
    to: '/factory/access',
    who: 'the factory',
    title: 'The factory decides',
    body:
      'The request is waiting here, under "Sharing & permissions". Saying yes releases '
      + 'one column of one document. Not the document, not the other rows, and not '
      + 'forever. The tiles at the top of the page are the other half of the same '
      + 'question: what each buyer can see in total, right now.',
    todo: 'Approve the request.',
  },
  {
    role: 'buyer',
    to: '/buyer/portal',
    who: 'a buyer',
    title: 'The buyer opens what it was given',
    body:
      'The permission is in the list now. "Open the file" goes straight into that '
      + 'document — the columns released to you, padlocks over everything else. '
      + 'Opening it is a read: nothing is written to the shared record, and nobody is '
      + 'told you looked.',
    todo: 'Press "Open the file" on the newest permission.',
  },
  {
    role: 'buyer',
    to: '/verify',
    who: 'a buyer',
    title: 'The buyer checks the answer',
    body:
      'This is the point of the whole system. Checking a row rebuilds the fingerprint '
      + 'from what was sent. If it matches the one the factory published months ago, '
      + 'those figures are real, and the buyer did not have to trust anyone to know it, '
      + 'not the factory and not whoever runs the servers. Each check leaves a receipt '
      + 'on the record, which is the difference between reading a figure and proving one.',
    todo: 'Press "Check every row against the ledger" and watch each row turn green.',
  },
  {
    role: 'auditor',
    to: '/auditor/workspace',
    who: 'an auditor',
    title: 'An auditor checks a whole batch',
    body:
      'The same check, run over everything an auditor holds. Each one is real, and each '
      + 'pass leaves a receipt the factory can see. So the audit is itself evidence, not '
      + 'a document that anybody could have typed.',
    todo: 'Run the batch.',
  },
  {
    role: 'auditor',
    to: '/periods',
    who: 'an auditor',
    title: 'Is the month complete?',
    body:
      'Checking what you were shown is the easy half. This screen answers the hard one. '
      + 'Did the factory file everything for the month, or quietly leave out the bad '
      + 'week? Once a month is closed, nothing can be added to it without the correction '
      + 'being visible to everyone.',
  },
  {
    role: 'consortium',
    to: '/model/gate',
    who: 'the consortium',
    title: 'The part worth staying for',
    body:
      'The members share one fraud detector that learns from all of them. A new version '
      + 'is better at this month\u2019s problem and quietly worse at one it had already '
      + 'solved. On the numbers a review committee looks at, it looks like an '
      + 'improvement. The contract checks the old problems too, finds the damage, and '
      + 'refuses it, with the reason attached.',
  },
  {
    role: 'consortium',
    to: '/ledger',
    who: 'the consortium',
    title: 'All of it is on here',
    body:
      'The document, the request, the approval, the checks and the refusal. Written by '
      + 'five different organisations, held by all of them, and editable by none of them '
      + 'afterwards. That includes the refusal that made somebody look bad.',
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
      'Open any document and you can see what is actually in the file, with anything you '
      + 'are not allowed to read blacked out and the reason next to it. The factory sees '
      + 'all of it. A buyer sees only the columns it was given. Nobody outside the '
      + 'factory ever sees a worker\u2019s name, and no permission opens that.',
    todo: 'Open a document and look at the table near the top.',
  },
  {
    role: 'buyer',
    to: '/buyer/portal',
    who: 'a buyer',
    title: 'Asking for several figures at once',
    body:
      'A net wage on its own tells you very little. To check one you need the basic pay, '
      + 'the overtime and the deductions too. So a buyer can tick several figures and '
      + 'send them as one request. Each one still becomes its own separate permission, '
      + 'which the factory can refuse or withdraw one at a time.',
    todo: 'Tick two or three figures and send them.',
  },
  {
    role: 'factory',
    to: '/factory/access',
    who: 'the factory',
    title: 'Answering several at once, or one at a time',
    body:
      'The factory sees them grouped the way they were asked for, and can release the '
      + 'whole set in one press or refuse any single one of them with a reason. If the '
      + 'contract refuses one, the rest still go through: what was released stays '
      + 'released rather than being undone.',
    todo: 'Release a set, or refuse one figure out of it.',
  },
  {
    role: 'buyer',
    to: '/buyer/portal',
    who: 'a buyer',
    title: 'Coming back for more later',
    body:
      'Holding one figure is usually when you find out you need the next one. Any item '
      + 'in the list has "ask for more from this", which points the form back at the '
      + 'same factory, the same kind of document and the same month, so nothing has to '
      + 'be filled in twice.',
  },
  {
    role: 'auditor',
    to: '/factory/records',
    who: 'an auditor',
    title: 'An auditor does not have to ask',
    body:
      'An auditor can open any document on the network without asking permission. An '
      + 'audit where the audited party chooses what the auditor may look at is not an '
      + 'audit. What stays closed is anything naming a person, because checking whether '
      + 'wages are right never requires knowing whose wages they are.',
    todo: 'Open any document and look at how much of it you can read.',
  },
  {
    role: 'auditor',
    to: '/factory/records',
    who: 'an auditor',
    title: 'Reading is not the same as proving',
    body:
      'Reading a figure is open to an auditor and writes nothing anywhere. Proving one '
      + 'writes a receipt onto the shared record, and a receipt names the exact figure '
      + 'it covers, so that still needs a permission from the factory. Open any document '
      + 'and you can check every row in one press; the panel above the table says what '
      + 'each of the two buttons does before you press either.',
    todo: 'Open a document and press "Check every row against the ledger".',
  },
  {
    role: 'auditor',
    to: '/factory/records',
    who: 'an auditor',
    title: 'Putting your name to what you read',
    body:
      'At the foot of any document is a confirmation of review: you say what you '
      + 'concluded, and it is generated as a document of its own, with its own '
      + 'reference, your name on it, and the receipts on the record that it rests on. '
      + 'It can be handed to somebody who cannot open the register itself. One is '
      + 'generated per reviewer per document — signing the same one twice would be the '
      + 'same claim with a later date on it, and the API refuses it.',
    todo: 'Open a document, scroll to the foot, and sign one.',
  },
  {
    role: 'factory',
    to: '/periods',
    who: 'the factory',
    title: 'Closing a month, and sharing out of it',
    body:
      'Closing a month fixes exactly which documents it contains. Nothing can be '
      + 'slipped in afterwards, and a late document has to be added as an open '
      + 'correction with a reason. Each of these opens a panel at the right that says '
      + 'what it is about to do first — closing a month lists every document it is about '
      + 'to seal in. Below that is the other half: who holds a copy of each document, '
      + 'and sharing any of them with several organisations at once.',
    todo: 'Press "Close this period" and read the panel before confirming.',
  },
  {
    role: 'consortium',
    to: '/governance',
    who: 'the consortium',
    title: 'Admitting a member actually admits them',
    body:
      'Adding a member takes a vote by the others, and when the vote carries the member '
      + 'is written onto the shared record there and then. They appear in the register, '
      + 'in the network map and in the regulator\u2019s totals, with the motion that '
      + 'admitted them attached. Whoever runs the servers cannot do any of it alone.',
    todo: 'Agree to the membership proposal and watch the register change.',
  },
  {
    role: 'consortium',
    to: '/anchor',
    who: 'the consortium',
    title: 'Proving something is not there',
    body:
      'Showing that a document is on the record is easy. Showing that one is not there '
      + 'at all is the hard direction, and this does it. It is the difference between '
      + '"we have no record of that certificate" and something the other side can check '
      + 'for itself.',
    todo: 'Try a certificate reference that was never filed.',
  },
  {
    role: 'consortium',
    to: '/model/registry',
    who: 'the consortium',
    title: 'Every version of the shared model',
    body:
      'Approved and refused, in order, each one tested against problems that were fixed '
      + 'and published before that round opened. Nobody could pick the tests after '
      + 'seeing the result.',
  },
  {
    role: 'regulator',
    to: '/regulator',
    who: 'a regulator',
    title: 'What an observer can see',
    body:
      'The regulator gets counts and governance events, and no factory document at all. '
      + 'Notice that the blocked parts are still drawn, with the reason written on them. '
      + 'Hiding them entirely would teach you nothing about where the line sits.',
  },
  {
    role: 'regulator',
    to: '/anchor',
    who: 'a regulator',
    title: 'What an observer can still check',
    body:
      'An observer that has to take the network\u2019s word for things is not much of '
      + 'an observer. So the regulator can still check that nothing on the shared record '
      + 'has been altered, and can still prove that a document was never filed, without '
      + 'ever being able to read one.',
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
