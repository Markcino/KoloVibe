# FL-B discovery/playback gaps before implementation

Inspected source tree f2b6e51dd62737db6a4addf3f88c9f021f825dac, identical to main a2e7303d9f914fa3b671d76781e33904d7156a9c. Recipes are grouped in discovery.json. No implementation edits precede this record.

| Screen | Gap |
|---|---|
| M-017 | Single list; no real following/trending/latest sections. |
| M-018 | Paging exists; signed-out handling needs explicit prompt. |
| M-019 | No category chips or category query. |
| M-020 | Recipe-only trending route. |
| M-021 | Recipe-only search route; explore has video search only. |
| M-022 | Missing combined video/creator results routing and count/poster fields. |
| M-023 | No applied category filter flow. |
| M-024 | List instead of vertical feed; signed-out playback blocked. |
| M-025 | Player exists; poster/count/share and typed playback states missing; public creator pushes 38. |
| M-026 | Public creator incorrectly routed as 38; missing display_name/location/counts. |
| M-027 | Creator-filter repository exists; route/list missing. |
| M-028 | Follow mutation lacks strict response validation and optimistic rollback. |
| M-029 | Like state exists; like_count ignored. |
| M-030 | No share recording/native sheet binding. |
| M-031 | 404 text exists; dedicated unavailable state/navigation missing. |
| M-032 | No buffering state. |
| M-033 | Basic player error exists; needs retry and typed state. |
| M-034 | No threshold-based slow buffering state; no real quality control available. |
| M-035 | Playback errors flattened to strings; dedicated 403 restriction state missing. |
