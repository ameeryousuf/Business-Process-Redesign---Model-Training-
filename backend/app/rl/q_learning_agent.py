import random


class QLearningAgent:
    def __init__(self, actions, learning_rate=0.1, discount_factor=0.9,
                 epsilon_start=1.0, epsilon_end=0.05, epsilon_decay_episodes=1000):
        self.actions = actions
        self.q_table = {}
        self.lr = learning_rate
        self.gamma = discount_factor
        self.epsilon_start = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay_episodes = epsilon_decay_episodes

    def get_epsilon(self, episode_num):
        if episode_num >= self.epsilon_decay_episodes:
            return self.epsilon_end
        ratio = episode_num / self.epsilon_decay_episodes
        return self.epsilon_start + ratio * (self.epsilon_end - self.epsilon_start)

    def get_q_value(self, state, action):
        return self.q_table.get((state, action), 0.0)

    def choose_action(self, state, eligible_actions, episode_num):
        if not eligible_actions:
            return None

        epsilon = self.get_epsilon(episode_num)

        if random.random() < epsilon:
            return random.choice(eligible_actions)

        q_values = [(a, self.get_q_value(state, a)) for a in eligible_actions]
        max_q = max(q for _, q in q_values)
        best_actions = [a for a, q in q_values if q == max_q]
        return random.choice(best_actions)

    def update(self, state, action, reward, next_state, next_eligible_actions):
        current_q = self.get_q_value(state, action)

        if next_eligible_actions:
            max_next_q = max(self.get_q_value(next_state, a) for a in next_eligible_actions)
        else:
            max_next_q = 0.0

        new_q = current_q + self.lr * (reward + self.gamma * max_next_q - current_q)
        self.q_table[(state, action)] = new_q