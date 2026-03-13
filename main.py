"""
Block Blast Human-Playable UI (pygame)
"""
import pygame
import sys
from game import Game

CELL_SIZE = 72
GRID_SIZE = 8
MARGIN = 36
# Ensure enough width for 3 large pieces in the panel
PIECE_PANEL_HEIGHT = 180
SCREEN_WIDTH = max(GRID_SIZE * CELL_SIZE + 2 * MARGIN, 3 * CELL_SIZE * 5 + 2 * MARGIN)
SCREEN_HEIGHT = GRID_SIZE * CELL_SIZE + PIECE_PANEL_HEIGHT + 3 * MARGIN

COLORS = {
    'bg': (30, 30, 40),
    'grid': (60, 60, 80),
    'block': (120, 180, 240),
    'piece': (200, 120, 120),
    'preview': (200, 200, 200, 120),
    'invalid': (220, 60, 60, 120),
    'score': (255, 255, 255),
    'streak': (255, 220, 120),
}

pygame.init()
# Set fixed window size and disable resizing
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.NOFRAME)
pygame.display.set_caption("Block Blast")
font = pygame.font.SysFont(None, 32)
clock = pygame.time.Clock()

game = Game(seed=42)
game.reset(seed=42)

def draw_grid(board):
    for y in range(GRID_SIZE):
        for x in range(GRID_SIZE):
            rect = pygame.Rect(MARGIN + x * CELL_SIZE, MARGIN + y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            pygame.draw.rect(screen, COLORS['grid'], rect, 1)
            if board[y][x]:
                pygame.draw.rect(screen, COLORS['block'], rect.inflate(-6, -6))

def draw_piece(piece, x, y, alpha=255, invalid=False):
    for dy, row in enumerate(piece.shape):
        for dx, cell in enumerate(row):
            if cell:
                px = x + dx * CELL_SIZE
                py = y + dy * CELL_SIZE
                rect = pygame.Rect(px, py, CELL_SIZE, CELL_SIZE)
                color = COLORS['invalid'] if invalid else COLORS['piece']
                surf = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
                surf.fill((*color[:3], alpha))
                screen.blit(surf, rect)

def draw_panel(pieces, dragging_idx, drag_offset):
    for idx, piece in enumerate(pieces):
        if piece is None or idx == dragging_idx:
            continue
        px = MARGIN + idx * (CELL_SIZE * 5)
        py = SCREEN_HEIGHT - PIECE_PANEL_HEIGHT + MARGIN
        draw_piece(piece, px, py)
    if dragging_idx is not None and pieces[dragging_idx]:
        mx, my = drag_offset
        draw_piece(pieces[dragging_idx], mx, my, alpha=180)

def draw_info(score, streak, round_num):
    score_text = font.render(f"Score: {score}", True, COLORS['score'])
    streak_text = font.render(f"Streak: {streak}", True, COLORS['streak'])
    round_text = font.render(f"Round: {round_num}/3", True, COLORS['score'])
    screen.blit(score_text, (MARGIN, SCREEN_HEIGHT - PIECE_PANEL_HEIGHT - 2 * MARGIN))
    screen.blit(streak_text, (MARGIN + 180, SCREEN_HEIGHT - PIECE_PANEL_HEIGHT - 2 * MARGIN))
    screen.blit(round_text, (MARGIN + 360, SCREEN_HEIGHT - PIECE_PANEL_HEIGHT - 2 * MARGIN))

def main():
    dragging = False
    dragging_idx = None
    drag_offset = (0, 0)
    game_over = False
    while True:
        screen.fill(COLORS['bg'])
        state = game.get_state()
        draw_grid(state['board'])
        draw_panel(state['pieces'], dragging_idx, drag_offset)
        draw_info(state['score'], state['streak'], state['placement_in_round'])
        if game_over:
            over_text = font.render("Game Over!", True, COLORS['invalid'][:3])
            screen.blit(over_text, (SCREEN_WIDTH // 2 - 80, SCREEN_HEIGHT // 2 - 40))
            new_game_btn = pygame.Rect(SCREEN_WIDTH // 2 - 60, SCREEN_HEIGHT // 2, 120, 40)
            pygame.draw.rect(screen, COLORS['piece'], new_game_btn)
            btn_text = font.render("New Game", True, COLORS['score'])
            screen.blit(btn_text, (SCREEN_WIDTH // 2 - 50, SCREEN_HEIGHT // 2 + 8))
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if game_over:
                if event.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = event.pos
                    if SCREEN_WIDTH // 2 - 60 <= mx <= SCREEN_WIDTH // 2 + 60 and SCREEN_HEIGHT // 2 <= my <= SCREEN_HEIGHT // 2 + 40:
                        game.reset(seed=42)
                        game_over = False
                        dragging = False
                        dragging_idx = None
                continue
            if event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                for idx, piece in enumerate(state['pieces']):
                    if piece is None:
                        continue
                    px = MARGIN + idx * (CELL_SIZE * 5)
                    py = SCREEN_HEIGHT - PIECE_PANEL_HEIGHT + MARGIN
                    piece_rect = pygame.Rect(px, py, CELL_SIZE * len(piece.shape[0]), CELL_SIZE * len(piece.shape))
                    if piece_rect.collidepoint(mx, my):
                        dragging = True
                        dragging_idx = idx
                        drag_offset = (mx - CELL_SIZE // 2, my - CELL_SIZE // 2)
            if event.type == pygame.MOUSEBUTTONUP and dragging:
                mx, my = event.pos
                grid_x = (mx - MARGIN) // CELL_SIZE
                grid_y = (my - MARGIN) // CELL_SIZE
                if dragging_idx is not None:
                    piece = state['pieces'][dragging_idx]
                    valid = False
                    for action in game.available_actions():
                        idx, x, y = action
                        if idx == dragging_idx and x == grid_x and y == grid_y:
                            valid = True
                            break
                    if valid:
                        _, _, done, _ = game.step((dragging_idx, grid_x, grid_y))
                        if done:
                            game_over = True
                    dragging = False
                    dragging_idx = None
                else:
                    dragging = False
                    dragging_idx = None
            if event.type == pygame.MOUSEMOTION and dragging:
                mx, my = event.pos
                drag_offset = (mx - CELL_SIZE // 2, my - CELL_SIZE // 2)
        clock.tick(60)

if __name__ == '__main__':
    main()
