import glob
import os
import random
import pickle

from app.bpmn_parser import parse_bpmn
from app.synthetic_metrics import enrich_process
from app.environment import ProcessRedesignEnv
from app.q_learning_agent import QLearningAgent
from app.state_builder import HEURISTIC_ORDER

DATASET_DIR = "data/training_processes_en"
NUM_EPISODES = 5000
MODEL_OUTPUT_PATH = "data/trained_q_table.pkl"


def load_process_files():
    return sorted(glob.glob(os.path.join(DATASET_DIR, "*.bpmn")))


def run_training():
    files = load_process_files()
    agent = QLearningAgent(actions=HEURISTIC_ORDER, epsilon_decay_episodes=int(NUM_EPISODES * 0.8))

    episode_rewards = []

    for episode_num in range(NUM_EPISODES):
        filepath = random.choice(files)

        env = ProcessRedesignEnv(filepath, time_low=5, time_high=20, cost_low=50, cost_high=200)

        base_parsed = parse_bpmn(filepath)
        enriched = enrich_process(base_parsed, seed=episode_num)
        env.parsed = enriched
        env.step_count = 0
        env.baseline_metrics = None
        state = env._get_state()

        total_reward = 0.0
        done = False

        while not done:
            eligible_actions = [name for name in HEURISTIC_ORDER if env.current_details[name]]

            if not eligible_actions:
                break

            action = agent.choose_action(state, eligible_actions, episode_num)
            next_state, reward, done, info = env.step(action)

            next_eligible_actions = [name for name in HEURISTIC_ORDER if env.current_details[name]]

            agent.update(state, action, reward, next_state, next_eligible_actions)

            state = next_state
            total_reward += reward

        episode_rewards.append(total_reward)

        if (episode_num + 1) % 500 == 0:
            avg_recent = sum(episode_rewards[-500:]) / len(episode_rewards[-500:])
            print(f"Episode {episode_num + 1}/{NUM_EPISODES} - Avg reward (last 500): {avg_recent:.4f} - Q-table size: {len(agent.q_table)}")

    return agent, episode_rewards


def save_agent(agent, path):
    with open(path, "wb") as f:
        pickle.dump(agent.q_table, f)
    print(f"\nQ-table saved to {path}")


if __name__ == "__main__":
    agent, rewards = run_training()
    print("\nTraining complete.")
    print(f"Final Q-table size: {len(agent.q_table)} state-action pairs")

    save_agent(agent, MODEL_OUTPUT_PATH)