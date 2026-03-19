import time

import matplotlib.pyplot as plt
from IPython import display

plt.ion()


def plot(scores, mean_scores):
    
    plt.clf()
    plt.title('Training...')
    plt.xlabel('Number of Games')
    plt.ylabel('Score')
    plt.plot(scores, label='Score')
    plt.plot(mean_scores, label='Mean Score')
    plt.legend()
    plt.ylim(ymin=0)
    plt.show(block=False)