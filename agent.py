import numpy as np
import random
from collections import deque

import torch
from game import Game
from model import Linear_Q, QTrainer
from helper import plot
from pieces import PIECE_POOL, PIECE_SHAPES_4X4
from board import Board


MAX_MEMORY = 100_000
BATCH_SIZE = 1000
GRID_SIZE = 8*8


class Agent:
    def __init__(self):
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.n_games = 0
        self.epsilon = 0 # randomness
        self.gamma = 0.9 # discount rate
        self.memory = deque(maxlen=MAX_MEMORY)
        self.model = Linear_Q(GRID_SIZE + 3 + 3, 512, 3*8*8).to(device) # Placeholder for the neural network model
        self.trainer = QTrainer(self.model, lr=0.001, gamma=0.9) # Placeholder for the trainer (e.g., optimizer, loss function)
        pass

    def get_state(self, game):
        flatten_grid = np.array(game.board.grid).flatten()
        
        pieces_indices = np.array([piece.index if piece else -1 for piece in game.pieces])
        rest_values = np.array([game.score, game.streak, game.round_placement])
        state = np.concatenate([flatten_grid, pieces_indices, rest_values])



        return state
    
    def remember(self, state, action, reward, next_state, done):
        self.memory.append((state, action, reward, next_state, done))
        pass

    def train_long_term(self):
        if len(self.memory) > BATCH_SIZE:
            # Implementation for long-term training
            mini_sample = random.sample(self.memory, BATCH_SIZE) # list of tuples
        else:
            mini_sample = self.memory

        states, actions, rewards, next_states, dones = zip(*mini_sample)
        self.trainer.train_step(states, actions, rewards, next_states, dones)
        pass

    def train_short_term(self, state, action, reward, next_state, done):
        self.trainer.train_step(state, action, reward, next_state, done)
        pass

    def create_mask(self, state):
        grid = state[:GRID_SIZE].reshape(8, 8)
        pieces_indices = state[GRID_SIZE:GRID_SIZE+3]

        mask = np.zeros(3*8*8, dtype=int)

        i = 0
        for idx in pieces_indices:
            if idx >= 0:
                piece = PIECE_POOL[idx]
                for y in range(8 - len(piece.shape) + 1):
                    for x in range(8 - len(piece.shape[0]) + 1):
                        temp_board = Board()
                        temp_board.grid = grid.copy()
                        if temp_board.place_piece(piece, x, y):
                            mask_idx = i * 64 + y * 8 + x
                            mask[mask_idx] = 1

        
            i += 1
        return mask

    def get_action(self, state):
        # random moves: tradeoff exploration / exploitation
        self.epsilon = 160 - self.n_games
        final_move = [0,0,0] # Placeholder for the action (e.g., piece index, x, y)

        mask = self.create_mask(state)

        if random.randint(0, 200) < self.epsilon:

            random_prediction = []
            for i in range(3*8*8):
                random_prediction.append(random.random())
            
            masked_prediction = np.where(mask, random_prediction, -np.inf) # Apply mask to filter out invalid moves
        else:
            state0 = torch.tensor(state, dtype=torch.float32)
            predition = self.model(state0) # Placeholder for model prediction
            predition = predition.detach().numpy() # Apply mask to filter out invalid moves

            masked_prediction = np.where(mask, predition, -np.inf)

            # Take the index of the max value in each part
        idx = torch.argmax(torch.tensor(masked_prediction)).item()

        if idx < 64:
            piece_index = 0
            x = idx % 8
            y = idx // 8
        elif idx < 128:
            piece_index = 1
            x = (idx - 64) % 8
            y = (idx - 64) // 8
        else:
            piece_index = 2
            x = (idx - 128) % 8
            y = (idx - 128) // 8

        final_move = [piece_index, x, y]

        return final_move

def train():
    plot_scores = []
    plot_mean_scores = []
    total_score = 0
    recod = 0
    rounds = 0
    agent = Agent()
    game = Game(seed=42)
    while True:
        
        #get old state
        state_old = agent.get_state(game)
        #get move
        final_move = agent.get_action(state_old)
        #perform move and get new state
        reward, score, done, message = game.step(final_move)

        state_new = agent.get_state(game)
        rounds += 1
        if reward >= 0: reward = rounds

        #train short memory
        agent.train_short_term(state_old, final_move, reward, state_new, done)

        #remember
        agent.remember(state_old, final_move, reward, state_new, done)
        print('Message:', message)
        if done:
            rounds = 0
            #train long memory, plot result
            game.reset(seed=42)

            agent.n_games += 1

            agent.train_long_term()

            if score > recod:
                recod = score

            
            print('Game', agent.n_games, 'Score', score, 'Record:', recod)
            plot_scores.append(score)
            total_score += score
            mean_score = total_score / agent.n_games
            plot_mean_scores.append(mean_score)
            plot(plot_scores, plot_mean_scores)
        
    pass

if __name__ == "__main__":
    train()