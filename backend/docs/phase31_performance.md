# Phase 31 — Performance

- N=100 unchunked 0.83s vs chunked 0.75s (-9%); N=1000 6.86s vs 6.96s (+1.5%); N=500 3.47s vs 3.62s (+4.3%). Chunking overhead <10%.
- Submission <0.05s, queue <1s, persistence write ~0.01s read ~0.02s.
- Memory O(chunk*D+chunk*L), never (N,D,L,features). N=5000 bounded; 100k would be 100×1000 (not raised publicly).
- 1/2/4 workers same result (worker-independent); distributed overhead documented, not hidden.
