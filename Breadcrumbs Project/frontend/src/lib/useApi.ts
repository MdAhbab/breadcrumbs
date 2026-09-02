import { useCallback, useEffect, useRef, useState } from 'react';

import { ApiError } from './api';

export interface Query<T> {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
  reload: () => void;
}

/**
 * One fetch, with the three states a screen actually has to render.
 *
 * Loading, failed and empty are not edge cases here — a refusal is a *result*
 * in this product. When the regulator opens a page it may not read, the 403 and
 * the contract's sentence explaining it are the content of that screen, so the
 * error is returned rather than thrown, and pages are expected to show it.
 *
 * `deps` is the dependency list for the fetcher, the same contract as
 * `useEffect`. The fetcher itself is held in a ref so a caller does not have to
 * memoise an inline arrow function.
 */
export function useApi<T>(fetcher: () => Promise<T>, deps: unknown[] = []): Query<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [nonce, setNonce] = useState(0);

  const run = useRef(fetcher);
  run.current = fetcher;

  useEffect(() => {
    let live = true;
    setLoading(true);
    setError(null);
    run.current()
      .then((value) => {
        if (live) setData(value);
      })
      .catch((err: unknown) => {
        if (!live) return;
        const failure = err instanceof ApiError
          ? err
          : new ApiError(0, err instanceof Error ? err.message : 'something went wrong');

        // A cold start builds the world on a background thread and refuses data
        // requests until it is done. That is a wait, not a failure, so retry it
        // rather than making the reader press a button every five seconds.
        if (failure.code === 'WORLD_BUILDING') {
          setError(failure);
          window.setTimeout(() => live && setNonce((n) => n + 1), 4000);
          return;
        }
        setData(null);
        setError(failure);
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { data, error, loading, reload };
}

/** Two queries that a screen needs together, resolved into one state. */
export function useApi2<A, B>(
  a: () => Promise<A>,
  b: () => Promise<B>,
  deps: unknown[] = [],
): Query<[A, B]> {
  return useApi(() => Promise.all([a(), b()]) as Promise<[A, B]>, deps);
}

export function useApi3<A, B, C>(
  a: () => Promise<A>,
  b: () => Promise<B>,
  c: () => Promise<C>,
  deps: unknown[] = [],
): Query<[A, B, C]> {
  return useApi(() => Promise.all([a(), b(), c()]) as Promise<[A, B, C]>, deps);
}
