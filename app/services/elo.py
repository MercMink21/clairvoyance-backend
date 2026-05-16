from __future__ import annotations

DEFAULT_RATING = 1500.0
K_FACTOR = 32.0


def expected_score(rating_a: float, rating_b: float) -> float:
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))


def update_ratings(winner_rating: float, loser_rating: float) -> tuple[float, float]:
    exp_w = expected_score(winner_rating, loser_rating)
    exp_l = expected_score(loser_rating, winner_rating)
    new_winner = round(winner_rating + K_FACTOR * (1.0 - exp_w), 2)
    new_loser = round(loser_rating + K_FACTOR * (0.0 - exp_l), 2)
    return new_winner, new_loser
