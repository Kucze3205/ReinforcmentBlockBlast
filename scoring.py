"""
Block Blast Scoring System
"""

def placement_points(piece):
    return sum(cell for row in piece.shape for cell in row)

def simultaneous_clear_points(k):
    return (10 * k) * k if k > 0 else 0

def streak_bonus(streak):
    return 10 * max(0, streak - 1)
