# CRED-1 dataset attribution

This project uses the compact domain list from **CRED-1: An Open
Multi-Signal Domain Credibility Dataset for Automated Pre-Bunking of Online
Misinformation**, by Alexander Loth, Martin Kappes, and Marc-Oliver Pahl.

- Upstream repository: https://github.com/aloth/cred-1
- Archived dataset DOI: https://doi.org/10.5281/zenodo.18769460
- Pinned release: `v2026-07-28` (2,674 upstream entries)
- Local normalized artifact: `data/cred1_compact.json` (2,635 unique hostnames
  after URL/path aliases are normalized)
- Dataset license: CC BY 4.0
- Updater: `python scripts/update_cred1.py`

CRED-1 combines open source labels with domain age, Tranco popularity,
fact-check frequency, and Safe Browsing signals. It is a negative-signal
dataset: a missing domain is **unknown**, not trustworthy. The application
uses it as one source-level prior and does not treat it as an article-level
fact verdict.

## Dataset schema

### Compact format (`cred1_compact.json`)

Each top-level key is a normalized domain. Its value uses abbreviated field
names to keep the dataset compact. For example:

```json
{
  "infowars.com": {
    "c": "c",
    "s": 0.073,
    "n": 2,
    "d": "1999-10-04",
    "r": 15889
  }
}
```

| Field | Description |
|---|---|
| `c` | Category code: `f` = fake, `u` = unreliable, `m` = mixed, `c` = conspiracy, `s` = satire, `r` = reliable |
| `s` | Credibility score from 0.0 to 1.0; lower values mean less credible |
| `n` | Number of independent source lists flagging the domain |
| `d` | Domain registration date; optional |
| `r` | Tranco Top-1M rank; optional, and a lower rank means the domain is more popular |

The `r` category value under field `c` means **reliable**. The separate
top-level field named `r` contains the optional **Tranco rank**.
