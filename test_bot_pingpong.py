from bot_pingpong import Match, TournamentState, PlayerStats, motivation_buckets, generate_alerts


def test_motivation_buckets_impossible_top2():
    state = TournamentState(url='u', title='t')
    state.players = {
        'A': PlayerStats('A', wins=5, losses=0),
        'B': PlayerStats('B', wins=4, losses=1),
        'C': PlayerStats('C', wins=0, losses=5),
        'D': PlayerStats('D', wins=1, losses=4),
    }

    motivated, demotivated = motivation_buckets(state)

    assert 'C' in demotivated
    assert 'A' in motivated
    assert 'B' in motivated


def test_generate_alerts_demotivated_vs_motivated():
    state = TournamentState(url='u', title='My Tournament')
    state.players = {
        'Mario': PlayerStats('Mario', wins=4, losses=0),
        'Luca': PlayerStats('Luca', wins=3, losses=1),
        'Piero': PlayerStats('Piero', wins=0, losses=4),
    }
    state.pending_matches = [
        Match('Mario', 'Piero', None, None),
    ]

    alerts = list(generate_alerts(state))

    assert len(alerts) == 1
    assert 'Mario (motivato) vs Piero (demotivato)' in alerts[0]
