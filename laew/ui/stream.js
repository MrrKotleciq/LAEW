/* Small NDJSON reader shared by the browser client and Node regression tests. */
(() => {
  async function readEventStream(response, onEvent, signal) {
    if (!response.ok) {
      const body = await response.text();
      throw new Error(body || `Request failed (${response.status}).`);
    }
    if (!response.body?.getReader) throw new Error('Streaming is unavailable in this browser.');
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let pending = '';
    let terminal = false;
    const dispatch = (line) => {
      if (!line.trim()) return;
      let event;
      try { event = JSON.parse(line); }
      catch { throw new Error('The local API returned an invalid stream event.'); }
      onEvent(event);
      if (event.type === 'done' || event.type === 'error') terminal = true;
    };
    try {
      while (true) {
        if (signal?.aborted) throw new DOMException('The request was cancelled.', 'AbortError');
        const { value, done } = await reader.read();
        pending += decoder.decode(value || new Uint8Array(), { stream: !done });
        let newline;
        while ((newline = pending.indexOf('\n')) >= 0) {
          dispatch(pending.slice(0, newline));
          pending = pending.slice(newline + 1);
        }
        if (done) break;
      }
      if (pending.trim()) dispatch(pending);
      if (!terminal) throw new Error('The response stream ended before LAEW reported completion. Retry the request.');
    } finally {
      if (signal?.aborted) await reader.cancel().catch(() => {});
      reader.releaseLock();
    }
  }

  const api = { readEventStream };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof window !== 'undefined') window.LAEWStream = api;
})();
