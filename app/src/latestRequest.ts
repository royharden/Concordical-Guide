/** Accept only the last initiated request, including empty or failed searches. */
export function latestRequest() {
  let generation = 0;
  return {
    begin() { const current = ++generation; return () => current === generation; },
  };
}
