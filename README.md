# Bot Ping Pong TT-Series

Script Python che monitora i tornei TT-Series dal sito ufficiale e stampa un alert quando un giocatore **demotivato** incontra un giocatore **motivato**.

## Logica implementata

- Scansione periodica della homepage (o di un seed URL) per trovare pagine torneo (`-result-`).
- Parsing delle partite concluse/in corso.
- Calcolo stato giocatori:
  - **demotivato**: anche vincendo tutte le partite rimanenti non può più arrivare nelle prime 2 posizioni.
  - **motivato**: ha ancora possibilità matematica di top-2.
- Stampa alert solo per partite pending `motivato vs demotivato`.
- Quando un torneo è concluso (nessuna partita pending), viene escluso dalle scansioni successive.

## Avvio

```bash
pip install -r requirements.txt
python bot_pingpong.py --seed-url https://www.tt-series.com/ --interval 60
```

Per monitorare direttamente una pagina specifica:

```bash
python bot_pingpong.py --seed-url "https://www.tt-series.com/917-result-13-02-2026-afternoon-tournament-hsc/" --interval 60
```
