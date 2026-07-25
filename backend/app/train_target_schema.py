import functools

from app.train import run_training, save_agent
from app.target_schema_parser import parse_target_process_file

DATASET_DIR = "data/target_training"
MODEL_OUTPUT_PATH = "data/trained_q_table_target_schema.pkl"
NUM_EPISODES = 5000


def _parser_fn(filepath):
    return parse_target_process_file(filepath, processes_dir=DATASET_DIR)


if __name__ == "__main__":
    agent, rewards = run_training(
        dataset_dir=DATASET_DIR,
        file_pattern="*.json",
        parser_fn=_parser_fn,
        num_episodes=NUM_EPISODES,
    )
    print("\nTraining complete.")
    print(f"Final Q-table size: {len(agent.q_table)} state-action pairs")

    save_agent(agent, MODEL_OUTPUT_PATH)
