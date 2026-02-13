 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/bot_pingpong.py b/bot_pingpong.py
new file mode 100644
index 0000000000000000000000000000000000000000..bd9c7013faac84090a587333e4b7d9c927c7ea1e
--- /dev/null
+++ b/bot_pingpong.py
@@ -0,0 +1,256 @@
+#!/usr/bin/env python3
+"""Bot di monitoraggio tornei TT-Series.
+
+Scansiona periodicamente i tornei in corso dal sito ufficiale, calcola quali
+player sono ancora in corsa per le prime 2 posizioni (a premio) e stampa un
+messaggio quando un player demotivato incontra un player motivato.
+"""
+
+from __future__ import annotations
+
+import argparse
+import re
+import time
+from dataclasses import dataclass, field
+from typing import Iterable
+from urllib.parse import urljoin
+
+try:
+    import requests
+except ModuleNotFoundError:  # pragma: no cover - dipendenza opzionale in test offline
+    requests = None
+
+try:
+    from bs4 import BeautifulSoup
+except ModuleNotFoundError:  # pragma: no cover - dipendenza opzionale in test offline
+    BeautifulSoup = None
+
+SCORE_RE = re.compile(r"^(\d+)\s*[-:]\s*(\d+)$")
+TOURNAMENT_LINK_RE = re.compile(r"-result-", re.IGNORECASE)
+
+
+@dataclass
+class Match:
+    player_a: str
+    player_b: str
+    score_a: int | None = None
+    score_b: int | None = None
+
+    @property
+    def completed(self) -> bool:
+        return self.score_a is not None and self.score_b is not None
+
+
+@dataclass
+class PlayerStats:
+    name: str
+    wins: int = 0
+    losses: int = 0
+
+    @property
+    def played(self) -> int:
+        return self.wins + self.losses
+
+
+@dataclass
+class TournamentState:
+    url: str
+    title: str
+    players: dict[str, PlayerStats] = field(default_factory=dict)
+    pending_matches: list[Match] = field(default_factory=list)
+
+    @property
+    def finished(self) -> bool:
+        return len(self.pending_matches) == 0
+
+
+def fetch_html(url: str, timeout: float = 15.0) -> str:
+    if requests is None:
+        raise RuntimeError("Dipendenza mancante: installa 'requests' per usare il monitor live")
+    response = requests.get(url, timeout=timeout)
+    response.raise_for_status()
+    return response.text
+
+
+def discover_tournament_links(seed_url: str) -> list[str]:
+    if BeautifulSoup is None:
+        raise RuntimeError("Dipendenza mancante: installa 'beautifulsoup4' per il parsing HTML")
+    html = fetch_html(seed_url)
+    soup = BeautifulSoup(html, "html.parser")
+    links: set[str] = set()
+
+    for anchor in soup.select("a[href]"):
+        href = anchor.get("href", "").strip()
+        if not href:
+            continue
+        full_url = urljoin(seed_url, href)
+        if TOURNAMENT_LINK_RE.search(full_url):
+            links.add(full_url)
+
+    # fallback: se il seed stesso è una pagina torneo
+    if TOURNAMENT_LINK_RE.search(seed_url):
+        links.add(seed_url)
+
+    return sorted(links)
+
+
+def _clean_name(value: str) -> str:
+    return re.sub(r"\s+", " ", value).strip()
+
+
+def parse_matches(html: str) -> list[Match]:
+    if BeautifulSoup is None:
+        raise RuntimeError("Dipendenza mancante: installa 'beautifulsoup4' per il parsing HTML")
+    soup = BeautifulSoup(html, "html.parser")
+    parsed: list[Match] = []
+
+    # Strategia robusta: cerca righe tabellari con almeno 3 celle.
+    for row in soup.select("tr"):
+        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
+        if len(cells) < 3:
+            continue
+
+        score_idx = -1
+        score_a = score_b = None
+        for i, cell in enumerate(cells):
+            m = SCORE_RE.match(cell)
+            if m:
+                score_idx = i
+                score_a, score_b = int(m.group(1)), int(m.group(2))
+                break
+
+        if score_idx >= 2:
+            player_a = _clean_name(cells[score_idx - 2])
+            player_b = _clean_name(cells[score_idx - 1])
+            if player_a and player_b and player_a != player_b:
+                parsed.append(Match(player_a, player_b, score_a, score_b))
+                continue
+
+        # Match non conclusi: score assente ma riga con 2 nomi plausibili.
+        # Heuristica: prime 2 celle con solo testo alfabetico lungo > 2.
+        names = [c for c in cells if re.search(r"[A-Za-zÀ-ÿ]", c) and len(c) > 2]
+        if len(names) >= 2:
+            pa, pb = _clean_name(names[0]), _clean_name(names[1])
+            if pa and pb and pa != pb:
+                parsed.append(Match(pa, pb, None, None))
+
+    # dedup semplice
+    unique: dict[tuple[str, str, int | None, int | None], Match] = {}
+    for match in parsed:
+        key = (match.player_a, match.player_b, match.score_a, match.score_b)
+        unique[key] = match
+    return list(unique.values())
+
+
+def build_state(url: str) -> TournamentState:
+    if BeautifulSoup is None:
+        raise RuntimeError("Dipendenza mancante: installa 'beautifulsoup4' per il parsing HTML")
+    html = fetch_html(url)
+    soup = BeautifulSoup(html, "html.parser")
+    title = _clean_name(soup.title.get_text()) if soup.title else url
+
+    matches = parse_matches(html)
+    state = TournamentState(url=url, title=title)
+
+    def ensure_player(name: str) -> PlayerStats:
+        if name not in state.players:
+            state.players[name] = PlayerStats(name=name)
+        return state.players[name]
+
+    for match in matches:
+        a = ensure_player(match.player_a)
+        b = ensure_player(match.player_b)
+        if match.completed:
+            if match.score_a > match.score_b:
+                a.wins += 1
+                b.losses += 1
+            elif match.score_b > match.score_a:
+                b.wins += 1
+                a.losses += 1
+        else:
+            state.pending_matches.append(match)
+
+    return state
+
+
+def motivation_buckets(state: TournamentState) -> tuple[set[str], set[str]]:
+    """Restituisce (motivati, demotivati).
+
+    Regola: un giocatore è "demotivato" se, anche vincendo tutte le partite
+    rimanenti, non può più chiudere in top-2 per numero di vittorie.
+    """
+    players = list(state.players.values())
+    n = len(players)
+    if n < 3:
+        return ({p.name for p in players}, set())
+
+    motivated: set[str] = set()
+    demotivated: set[str] = set()
+
+    for p in players:
+        remaining = max(0, (n - 1) - p.played)
+        max_wins = p.wins + remaining
+
+        strictly_ahead = sum(1 for other in players if other.name != p.name and other.wins > max_wins)
+        if strictly_ahead >= 2:
+            demotivated.add(p.name)
+        else:
+            motivated.add(p.name)
+
+    return motivated, demotivated
+
+
+def generate_alerts(state: TournamentState) -> Iterable[str]:
+    motivated, demotivated = motivation_buckets(state)
+    for m in state.pending_matches:
+        if m.player_a in motivated and m.player_b in demotivated:
+            yield f"[{state.title}] Match da monitorare: {m.player_a} (motivato) vs {m.player_b} (demotivato)"
+        elif m.player_b in motivated and m.player_a in demotivated:
+            yield f"[{state.title}] Match da monitorare: {m.player_b} (motivato) vs {m.player_a} (demotivato)"
+
+
+def run_monitor(seed_url: str, interval_s: int) -> None:
+    archived_finished: set[str] = set()
+
+    while True:
+        try:
+            tournament_urls = [u for u in discover_tournament_links(seed_url) if u not in archived_finished]
+
+            if not tournament_urls:
+                print("Nessun torneo in corso trovato.")
+            for url in tournament_urls:
+                try:
+                    state = build_state(url)
+                except Exception as exc:  # noqa: BLE001
+                    print(f"Errore parsing torneo {url}: {exc}")
+                    continue
+
+                if state.finished:
+                    archived_finished.add(url)
+                    print(f"Torneo concluso, lo rimuovo dalla scansione: {state.title}")
+                    continue
+
+                for alert in generate_alerts(state):
+                    print(alert)
+
+        except Exception as exc:  # noqa: BLE001
+            print(f"Errore scansione globale: {exc}")
+
+        time.sleep(interval_s)
+
+
+def main() -> None:
+    parser = argparse.ArgumentParser(description="Monitor tornei TT-Series")
+    parser.add_argument(
+        "--seed-url",
+        default="https://www.tt-series.com/",
+        help="Pagina da cui scoprire tornei in corso (default: homepage TT-Series)",
+    )
+    parser.add_argument("--interval", type=int, default=60, help="Intervallo scansione in secondi")
+
+    args = parser.parse_args()
+    run_monitor(args.seed_url, args.interval)
+
+
+if __name__ == "__main__":
+    main()
 
EOF
)
