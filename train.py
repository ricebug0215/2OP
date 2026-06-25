"""
Train a MaskablePPO agent on the PTCG T1/T2 setup environment.

Usage:
    python train.py                  # train 200k steps
    python train.py --steps 500000   # train 500k steps
    python train.py --eval           # evaluate saved model vs playbook
"""

import argparse
import os
import numpy as np
from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker
from stable_baselines3.common.callbacks import BaseCallback

from rl_env import PTCGSetupEnv
from playbook import SimulationRunner


DECK = [
    {'name': '多龍巴魯托ex', 'count': 3}, {'name': '多龍奇', 'count': 4},
    {'name': '多龍梅西亞', 'count': 4}, {'name': '土龍弟弟', 'count': 2},
    {'name': '土龍節節', 'count': 2}, {'name': '土龍節節ex', 'count': 1},
    {'name': '願增猿', 'count': 2}, {'name': '含羞苞', 'count': 1},
    {'name': '可達鴨', 'count': 1}, {'name': '寶可平板', 'count': 4},
    {'name': '好友寶芬', 'count': 4}, {'name': '高級球', 'count': 3},
    {'name': '夜間擔架', 'count': 2}, {'name': '寶可裝置3.0', 'count': 2},
    {'name': '特殊紅牌', 'count': 2}, {'name': '英雄斗篷', 'count': 1},
    {'name': '莉莉艾的決意', 'count': 4}, {'name': '赤松', 'count': 2},
    {'name': '小剛的發掘', 'count': 2}, {'name': '阿塞蘿拉的惡作劇', 'count': 1},
    {'name': '老大的指令', 'count': 3}, {'name': '險惡廢墟', 'count': 2},
    {'name': '基本【超】能量', 'count': 3}, {'name': '基本【火】能量', 'count': 3},
    {'name': '基本【惡】能量', 'count': 2},
]

RL_PB = {
    'active_priority': ['含羞苞', '可達鴨', '願增猿', '土龍弟弟', '多龍梅西亞'],
    'setup_bench_priority': ['多龍梅西亞', '土龍弟弟', '願增猿'],
    'no_bench': ['可達鴨'],
    'play_priority': [],
    'search_priority': ['多龍梅西亞', '土龍弟弟', '多龍奇', '多龍巴魯托ex', '願增猿', '含羞苞', '土龍節節ex'],
    'supporter_priority': ['莉莉艾的決意', '小剛的發掘', '赤松', '阿塞蘿拉的惡作劇', '老大的指令'],
    'main_attacker': ['多龍梅西亞'],
    'discard_priority': ['Energy', '特殊紅牌', '老大的指令', '險惡廢墟'],
    'bench_priority': ['多龍梅西亞', '土龍弟弟', '願增猿'],
    'energy_target': ['多龍梅西亞', '多龍奇', '土龍弟弟'],
    'evolution_lines': {
        '多龍梅西亞': ['多龍奇', '多龍巴魯托ex'],
        '土龍弟弟': ['土龍節節ex', '土龍節節'],
    },
}

FULL_PB = dict(RL_PB, play_priority=[
    {'card': 'bench_basics'},
    {'card': '好友寶芬', 'conditions': {'bench_open_gte': 2}},
    {'card': '寶可平板'}, {'card': '高級球'}, {'card': '寶可裝置3.0'},
    {'card': '夜間擔架'},
    {'card': 'evolve'}, {'card': 'use_ability'},
    {'card': 'attach_energy'},
    {'card': '莉莉艾的決意'}, {'card': '赤松'},
    {'card': '小剛的發掘', 'conditions': {'hand_size_lte': 3}},
])

MODEL_PATH = 'models/ptcg_setup_ppo'


def mask_fn(env):
    return env.action_masks()


class LogCallback(BaseCallback):
    def __init__(self, eval_freq=10000, n_eval=50):
        super().__init__()
        self.eval_freq = eval_freq
        self.n_eval = n_eval
        self.best_mean = -float('inf')

    def _on_step(self):
        if self.num_timesteps % self.eval_freq == 0:
            scores = evaluate_model(self.model, n=self.n_eval)
            mean = np.mean(scores)
            print(f'  [{self.num_timesteps:>7d} steps]  '
                  f'avg={mean:.1f}  median={np.median(scores):.1f}  '
                  f'min={np.min(scores):.0f}  max={np.max(scores):.0f}')
            if mean > self.best_mean:
                self.best_mean = mean
                self.model.save(MODEL_PATH + '_best')
        return True


def make_env():
    env = PTCGSetupEnv(DECK, RL_PB)
    return ActionMasker(env, mask_fn)


def evaluate_model(model, n=100):
    env = PTCGSetupEnv(DECK, RL_PB)
    scores = []
    for _ in range(n):
        obs, info = env.reset()
        while True:
            mask = env.action_masks()
            action, _ = model.predict(obs, action_masks=mask, deterministic=True)
            obs, reward, done, trunc, info = env.step(int(action))
            if done:
                scores.append(reward)
                break
    return scores


def train(total_steps=200_000):
    os.makedirs('models', exist_ok=True)

    env = make_env()
    model = MaskablePPO(
        'MlpPolicy', env,
        learning_rate=3e-4,
        n_steps=1024,
        batch_size=256,
        n_epochs=10,
        gamma=1.0,
        ent_coef=0.05,
        verbose=0,
    )

    print(f'Training MaskablePPO for {total_steps} steps...')
    print(f'Action space: {env.action_space}')
    print(f'Observation space: {env.observation_space.shape}')
    print()

    callback = LogCallback(eval_freq=10000, n_eval=50)
    model.learn(total_timesteps=total_steps, callback=callback)
    model.save(MODEL_PATH)
    print(f'\nModel saved to {MODEL_PATH}')
    return model


def evaluate():
    print('Loading model...')
    model = MaskablePPO.load(MODEL_PATH + '_best')

    print('\n--- RL Agent (100 episodes) ---')
    rl_scores = evaluate_model(model, n=100)
    print(f'avg={np.mean(rl_scores):.1f}  median={np.median(rl_scores):.1f}  '
          f'min={np.min(rl_scores):.0f}  max={np.max(rl_scores):.0f}')

    print('\n--- Playbook Agent (100 episodes) ---')
    runner = SimulationRunner(DECK, FULL_PB)
    pb_scores = [runner.run_once(turns=2, going_first=True)['score'] for _ in range(100)]
    print(f'avg={np.mean(pb_scores):.1f}  median={np.median(pb_scores):.1f}  '
          f'min={np.min(pb_scores):.0f}  max={np.max(pb_scores):.0f}')

    print('\n--- Random Agent (100 episodes) ---')
    env = PTCGSetupEnv(DECK, RL_PB)
    rand_scores = []
    for _ in range(100):
        obs, info = env.reset()
        while True:
            mask = info['action_mask']
            valid = np.where(mask)[0]
            action = env.np_random.choice(valid)
            obs, reward, done, trunc, info = env.step(action)
            if done:
                rand_scores.append(reward)
                break
    print(f'avg={np.mean(rand_scores):.1f}  median={np.median(rand_scores):.1f}  '
          f'min={np.min(rand_scores):.0f}  max={np.max(rand_scores):.0f}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--steps', type=int, default=200_000)
    parser.add_argument('--eval', action='store_true')
    args = parser.parse_args()

    if args.eval:
        evaluate()
    else:
        train(args.steps)
